#!/usr/bin/env python3
"""Deterministic crowded-screen baseline for unmodified Quintra.

Measures SM83 T-cycles inside a CGB double-speed PyBoy run. One LCD frame in
double speed is 456 cycles/line * 154 lines * 2 = 140448 T-cycles. That
constant was checked on a tiny GBDK ROM (KEY1 bit 7 set, PyBoy 2.7.0
``_cycles()`` advanced by exactly 140448 per ``tick``). Host wall time is not
a result.

The ROM is not modified. Hooks use PyBoy's breakpoint opcode, which the
calibration showed does not add emulated cycles. Sections are exclusive
slices from one hooked entry to the next hooked entry, so a slice includes
the uninstrumented code that runs before the next probe. Major phase brackets
are reported separately and should sum to the work total.

Work is the T-cycle gap from ``input_poll`` to ``wait_vbl_done``. When the
update crosses VBlank, ``loop.c`` skips the wait; that update is an overrun
and its work is the whole gap until the next poll. Lag frames are LCD frames
minus completed ``loop_frame_counter`` steps over the same window (the same
ratio as ``scripts/test_performance.py``).

An exclusive slice runs from one hooked entry until the next hooked entry.
It therefore includes the uninstrumented caller that continues after a short
callee returns. ``aabb_overlap_ee`` slices are pair-loop bodies in
``combat_player_shots``. The ``hud_redraw_boss`` slice is mostly the rest of
``room_tick`` after that call, because the bar function returns immediately
when its segment cache hits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi")

# Hardware double-speed SM83 frame. Confirmed against PyBoy, not assumed from
# host time. NOP is 4 of these T-cycles.
FRAME_T = 140448
# Displayed rate stays the PPU's ~59.7275 Hz in double speed. The CPU gets
# twice as many T-cycles inside that same frame (FRAME_T).
LCD_HZ = 59.72750056960583

ROOM_W = 20
ENT = 28
ENT_PROJECTILE = 1
ENT_ENEMY = 2
EF_ACTIVE = 0x01
EF_ALIVE = 0x02
EF_ON_SCREEN = 0x04
EF_PLAYER_PROJ = 0x10
BGT_FLOOR = 1
SPR_CRAWLER = 20
SPR_ORC = 23
SPR_BULLET = 28
SPR_WISP = 34
ENEMY_CRAWLER = 0
ENEMY_ORC = 4
ENEMY_WISP = 5

# Linear SDCC addresses (bank in the high half) -> (mbc_bank, cpu_addr).
HOOKS = {
    "input_poll": "_input_poll",
    "room_tick": "_room_tick",
    "entity_update_all": "_entity_update_all",
    "entity_update_from": "_entity_update_from",
    "enemy_update": "_enemy_update",
    "enemy_try_step": "_enemy_try_step",
    "projectile_update_one": "_projectile_update_one",
    "room_player_position_clear": "_room_player_position_clear",
    "room_tile_at_px": "_room_tile_at_px",
    "combat_resolve": "_combat_resolve",
    "room_draw": "_room_draw",
    "entity_draw_all": "_entity_draw_all",
    "entity_draw_all_world": "_entity_draw_all_world",
    "audio_tick": "_audio_tick",
    "music_tick": "_music_tick",
    "sfx_tick": "_sfx_tick",
    "pickup_check_player_collision": "_pickup_check_player_collision",
    "dungeon_director_update": "_dungeon_director_update",
    "aabb_overlap_player": "_aabb_overlap_player",
    "aabb_overlap_ee": "_aabb_overlap_ee",
    "hud_redraw_boss": "_hud_redraw_boss",
    "wait_vbl_done": "_wait_vbl_done",
}


def load_noi(path: Path) -> dict[str, int]:
    syms = {}
    for line in path.read_text(errors="replace").splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "DEF":
            syms[parts[1]] = int(parts[2], 16)
    return syms


def cpu_site(linear: int) -> tuple[int, int]:
    """Map an sdld extended address to the PyBoy hook bank and CPU address."""
    if linear < 0x4000:
        return 0, linear
    if linear >= 0x10000:
        bank = linear >> 16
        cpu = linear & 0xFFFF
        if 0x4000 <= cpu < 0x8000 and 0 < bank < 512:
            return bank, cpu
    raise RuntimeError(f"cannot map symbol address {linear:#x} to a ROM bank")


def stats(values: list[int]) -> dict | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)

    def pct(p: float) -> int:
        index = int(round((n - 1) * p))
        return ordered[min(n - 1, max(0, index))]

    return {
        "n": n,
        "min": ordered[0],
        "p10": pct(0.10),
        "median": pct(0.50),
        "p90": pct(0.90),
        "max": ordered[-1],
        "mean": sum(ordered) // n,
        "sum": sum(ordered),
    }


def u16(pb: PyBoy, addr: int) -> int:
    return pb.memory[addr] | (pb.memory[addr + 1] << 8)


def s16(pb: PyBoy, addr: int) -> int:
    value = u16(pb, addr)
    return value - 0x10000 if value & 0x8000 else value


class Probe:
    def __init__(self, pb: PyBoy, epoch_addr: int):
        self.pb = pb
        self.epoch_addr = epoch_addr
        self.events: list[tuple[int, str, int]] = []

    def mark(self, name: str) -> None:
        self.events.append((self.pb._cycles(), name, self.pb.memory[self.epoch_addr]))

    def install(self, sites: dict[str, tuple[int, int]]) -> None:
        for name, (bank, addr) in sites.items():
            self.pb.hook_register(bank, addr, self._callback, name)

    def remove(self, sites: dict[str, tuple[int, int]]) -> None:
        for bank, addr in sites.values():
            self.pb.hook_deregister(bank, addr)

    def _callback(self, name: str) -> None:
        self.mark(name)


def boot_room() -> PyBoy:
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240, render=False, sound=False)
    pb.button("start")
    pb.tick(30, render=False, sound=False)
    pb.button("a")
    pb.tick(90, render=False, sound=False)
    return pb


def clear_entities(pb: PyBoy, sym: dict[str, int]) -> None:
    base = sym["_entities"]
    for offset in range(32 * ENT):
        pb.memory[base + offset] = 0
    pb.memory[sym["_entity_enemy_count"]] = 0
    status = sym["_enemy_status_kind"]
    for slot in range(32):
        pb.memory[status + slot] = 0


def write_entity(pb: PyBoy, base: int, slot: int, kind: int, flags: int,
                 x: int, y: int, sprite: int, hp: int, damage: int,
                 hitbox: int, vx: int = 0, vy: int = 0, state: int = 0,
                 timer: int = 0, ai0: int = 0, ai1: int = 0) -> None:
    ep = base + slot * ENT
    for offset in range(ENT):
        pb.memory[ep + offset] = 0
    pb.memory[ep] = kind
    pb.memory[ep + 1] = flags
    pb.memory[ep + 3] = x & 0xFF
    pb.memory[ep + 4] = (x >> 8) & 0xFF
    pb.memory[ep + 7] = y & 0xFF
    pb.memory[ep + 8] = (y >> 8) & 0xFF
    pb.memory[ep + 10] = vx & 0xFF
    pb.memory[ep + 11] = vy & 0xFF
    pb.memory[ep + 12] = sprite
    pb.memory[ep + 13] = 3
    pb.memory[ep + 14] = hp
    pb.memory[ep + 15] = state
    pb.memory[ep + 16] = timer
    pb.memory[ep + 17] = ai0
    pb.memory[ep + 18] = ai1
    pb.memory[ep + 25] = hitbox
    pb.memory[ep + 26] = damage
    pb.memory[ep + 27] = (4 + slot) & 0xFF


def fill_floor(pb: PyBoy, sym: dict[str, int]) -> None:
    base = sym["_room_tilemap"]
    for y in range(2, 15):
        for x in range(2, 18):
            pb.memory[base + y * ROOM_W + x] = BGT_FLOOR


def grid(n: int, x0: int, y0: int, cols: int, step: int) -> list[tuple[int, int]]:
    return [(x0 + (i % cols) * step, y0 + (i // cols) * step) for i in range(n)]


def spawn_enemies(pb: PyBoy, sym: dict[str, int], kind_id: int, sprite: int,
                  count: int, origin: tuple[int, int], hp: int = 200,
                  timer: int = 12, ai1: int = 0) -> None:
    base = sym["_entities"]
    for slot, (x, y) in enumerate(grid(count, origin[0], origin[1], 4, 20)):
        write_entity(
            pb, base, slot, ENT_ENEMY,
            EF_ACTIVE | EF_ALIVE | EF_ON_SCREEN,
            x, y, sprite, hp, 1, 0x77, state=slot & 7, timer=timer,
            ai0=kind_id, ai1=ai1,
        )
    pb.memory[sym["_entity_enemy_count"]] = count


def spawn_bullets(pb: PyBoy, sym: dict[str, int], start: int, count: int,
                  origin: tuple[int, int], player: bool, vx: int = 0,
                  vy: int = 0) -> None:
    base = sym["_entities"]
    flags = EF_ACTIVE | EF_ALIVE | (EF_PLAYER_PROJ if player else 0)
    for index, (x, y) in enumerate(grid(count, origin[0], origin[1], 4, 16)):
        write_entity(
            pb, base, start + index, ENT_PROJECTILE, flags,
            x, y, SPR_BULLET, 8, 1, 0x66, vx=vx, vy=vy, timer=255,
        )


def pin_coordinates(pb: PyBoy, sym: dict[str, int], saved: list[int]) -> None:
    base = sym["_entities"]
    for slot in range(32):
        ep = base + slot * ENT
        saved_at = slot * ENT
        for offset in (2, 3, 4, 5, 6, 7, 8, 9):
            pb.memory[ep + offset] = saved[saved_at + offset]
        # Keep the crowded set awake. A scrolling district would otherwise
        # sleep bodies that the fixture intentionally placed on screen.
        if pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE:
            pb.memory[ep + 1] |= EF_ON_SCREEN


def snapshot_entities(pb: PyBoy, sym: dict[str, int]) -> list[int]:
    base = sym["_entities"]
    return [pb.memory[base + offset] for offset in range(32 * ENT)]


def sustain_player(pb: PyBoy, sym: dict[str, int]) -> None:
    player = sym["_player"]
    pb.memory[player + 1] = 240
    pb.memory[player + 2] = 240
    pb.memory[player + 15] = 240
    pb.memory[sym["_g_hitstop"]] = 0


def census(pb: PyBoy, sym: dict[str, int]) -> dict:
    base = sym["_entities"]
    rows = []
    counts = {"enemy": 0, "projectile": 0, "player_projectile": 0, "other": 0, "on_screen": 0}
    for slot in range(32):
        ep = base + slot * ENT
        flags = pb.memory[ep + 1]
        if not flags & EF_ACTIVE:
            continue
        kind = pb.memory[ep]
        row = {
            "slot": slot,
            "type": kind,
            "flags": flags,
            "x": s16(pb, ep + 3),
            "y": s16(pb, ep + 7),
            "vx": pb.memory[ep + 10] - 256 if pb.memory[ep + 10] & 128 else pb.memory[ep + 10],
            "vy": pb.memory[ep + 11] - 256 if pb.memory[ep + 11] & 128 else pb.memory[ep + 11],
            "hp": pb.memory[ep + 14],
            "timer": pb.memory[ep + 16],
            "ai0": pb.memory[ep + 17],
        }
        rows.append(row)
        if kind == ENT_ENEMY:
            counts["enemy"] += 1
            if flags & EF_ON_SCREEN:
                counts["on_screen"] += 1
        elif kind == ENT_PROJECTILE:
            counts["projectile"] += 1
            if flags & EF_PLAYER_PROJ:
                counts["player_projectile"] += 1
        else:
            counts["other"] += 1
    return {"counts": counts, "rows": rows}


def oam_summary(pb: PyBoy) -> dict:
    lcdc = pb.memory[0xFF40]
    height = 16 if lcdc & 0x04 else 8
    sprites = []
    lines = [0] * 144
    for index in range(40):
        address = 0xFE00 + index * 4
        y, x, tile, attr = (pb.memory[address + k] for k in range(4))
        if y == 0 or y >= 160:
            continue
        sprites.append({"i": index, "y": y, "x": x, "tile": tile, "attr": attr})
        top = y - 16
        for scan in range(max(0, top), min(144, top + height)):
            lines[scan] += 1
    peak = max(lines) if lines else 0
    return {
        "lcdc": lcdc,
        "obj_height": height,
        "visible": len(sprites),
        "max_sprites_on_a_scanline": peak,
        "scanlines_over_10": sum(1 for value in lines if value > 10),
        "sprites": sprites,
    }


def room_info(pb: PyBoy, sym: dict[str, int]) -> dict:
    return {
        "screen": pb.memory[sym["_loop_current_screen"]],
        "double_speed": bool(pb.memory[0xFF4D] & 0x80),
        "key1": pb.memory[0xFF4D],
        "world_w": pb.memory[sym["_room_world_width"]],
        "world_h": pb.memory[sym["_room_world_height"]],
        "camera_x": pb.memory[sym["_room_camera_x"]],
        "camera_y": pb.memory[sym["_room_camera_y"]],
        "boss": pb.memory[sym["_procgen_current_room_is_boss"]],
        "player_x": s16(pb, sym["_player"] + 9),
        "player_y": s16(pb, sym["_player"] + 11),
        "serpent": pb.memory[sym["_serpent_tail_active"]],
        "cinder": pb.memory[sym["_cinder_pack_active"]],
    }


def make_fixed_crawlers(pb: PyBoy, sym: dict[str, int]) -> None:
    """Same roster normalization as scripts/test_performance.py."""
    base = sym["_entities"]
    kept = 0
    for slot in range(32):
        ep = base + slot * ENT
        if pb.memory[ep] != ENT_ENEMY or not (pb.memory[ep + 1] & EF_ACTIVE):
            continue
        if kept >= 16:
            pb.memory[ep] = pb.memory[ep + 1] = 0
            continue
        kept += 1
        pb.memory[ep + 12] = 20
        pb.memory[ep + 13] = 3
        pb.memory[ep + 14] = 8
        pb.memory[ep + 15] = pb.memory[ep + 16] = 0
        for offset in range(17, 25):
            pb.memory[ep + offset] = 0
        pb.memory[ep + 25] = 0x77
        pb.memory[ep + 26] = 1


def dense_projectiles(pb: PyBoy, sym: dict[str, int]) -> None:
    """Twelve stationary hostile shots, matching scripts/test_performance.py."""
    tilemap = sym["_room_tilemap"]
    for y in range(3, 14):
        for x in range(3, 17):
            pb.memory[tilemap + y * ROOM_W + x] = BGT_FLOOR
    clear_entities(pb, sym)
    base = sym["_entities"]
    for slot in range(12):
        x = 32 + (slot % 7) * 16
        y = 24 + (slot // 7) * 24
        ep = base + slot * ENT
        pb.memory[ep] = ENT_PROJECTILE
        pb.memory[ep + 1] = 0x03
        value_x = x << 8
        value_y = y << 8
        for byte in range(4):
            pb.memory[ep + 2 + byte] = (value_x >> (8 * byte)) & 0xFF
            pb.memory[ep + 6 + byte] = (value_y >> (8 * byte)) & 0xFF
        pb.memory[ep + 10] = pb.memory[ep + 11] = 0
        pb.memory[ep + 12] = 28
        pb.memory[ep + 13] = 2
        pb.memory[ep + 14] = 1
        pb.memory[ep + 16] = 255
        pb.memory[ep + 25] = 0x77
        pb.memory[ep + 26] = 1


def analyze(events: list[tuple[int, str, int]], frame_cycles: int) -> dict:
    polls = [index for index, event in enumerate(events) if event[1] == "input_poll"]
    updates = []
    exclusive: dict[str, list[int]] = {}
    brackets = {
        "input_to_room": [],
        "room_to_entities": [],
        "entities_to_combat": [],
        "combat_to_draw": [],
        "draw_to_oam": [],
        "oam_to_audio": [],
        "audio_to_wait": [],
    }
    works = []
    idles = []
    overruns = 0
    full = 0
    early = 0
    vblanks_during_update = []

    for nth, start in enumerate(polls[:-1]):
        end = polls[nth + 1]
        window = events[start:end]
        names = {event[1]: event[0] for event in window}
        work_end_name = "wait_vbl_done" if "wait_vbl_done" in names else None
        next_cycle = events[end][0]
        start_cycle = window[0][0]
        if work_end_name:
            work = names[work_end_name] - start_cycle
            idle = next_cycle - names[work_end_name]
        else:
            work = next_cycle - start_cycle
            idle = 0
        overrun = work_end_name is None or work > FRAME_T
        if overrun:
            overruns += 1
        works.append(work)
        idles.append(idle)
        epoch_delta = (events[end][2] - window[0][2]) & 0xFF
        vblanks_during_update.append(epoch_delta)
        reached_sim = "entity_update_all" in names
        if reached_sim:
            full += 1
        else:
            early += 1

        def bracket(key: str, left: str, right: str) -> None:
            if left in names and right in names and names[right] >= names[left]:
                brackets[key].append(names[right] - names[left])

        oam_name = "entity_draw_all_world" if "entity_draw_all_world" in names else "entity_draw_all"
        bracket("input_to_room", "input_poll", "room_tick")
        bracket("room_to_entities", "room_tick", "entity_update_all")
        bracket("entities_to_combat", "entity_update_all", "combat_resolve")
        bracket("combat_to_draw", "combat_resolve", "room_draw")
        bracket("draw_to_oam", "room_draw", oam_name)
        bracket("oam_to_audio", oam_name, "audio_tick")
        if work_end_name:
            bracket("audio_to_wait", "audio_tick", "wait_vbl_done")

        # Exclusive slices cover only the work region. On an overrun the
        # uninstrumented tail after the last probe still belongs to work,
        # because loop.c never reached wait_vbl_done.
        end_cycle = names[work_end_name] if work_end_name else next_cycle
        work_events = [event for event in window if event[0] <= end_cycle]
        for event_index, event in enumerate(work_events[:-1]):
            delta = work_events[event_index + 1][0] - event[0]
            if delta >= 0:
                exclusive.setdefault(event[1], []).append(delta)
        if work_events and work_events[-1][0] < end_cycle and work_events[-1][1] != "wait_vbl_done":
            exclusive.setdefault(work_events[-1][1], []).append(end_cycle - work_events[-1][0])
        updates.append({
            "work": work,
            "idle": idle,
            "overrun": overrun,
            "full_sim": reached_sim,
            "vblanks": epoch_delta,
        })

    exclusive_sum = sum(sum(values) for values in exclusive.values())
    work_sum = sum(works)
    return {
        "updates_observed": len(updates),
        "full_sim_updates": full,
        "early_out_updates": early,
        "overrun_updates": overruns,
        "work_cycles": stats(works),
        "idle_cycles": stats(idles),
        "vblanks_per_update": stats(vblanks_during_update),
        "phase_brackets_cycles": {key: stats(values) for key, values in brackets.items()},
        "exclusive_slices_cycles": {
            key: stats(values) for key, values in sorted(exclusive.items())
        },
        "exclusive_sum_cycles": exclusive_sum,
        "work_sum_cycles": work_sum,
        "exclusive_matches_work": abs(exclusive_sum - work_sum) <= max(8, len(works)),
        "frame_budget_t_cycles": FRAME_T,
        "median_work_fraction_of_frame": (
            None if not works else round(sorted(works)[len(works) // 2] / FRAME_T, 4)
        ),
        "pyboy_cycles_per_lcd_frame": frame_cycles,
    }


def measure(pb: PyBoy, sym: dict[str, int], sites: dict[str, tuple[int, int]],
            frames: int, pin: bool, sustain: bool) -> tuple[dict, dict, dict]:
    saved = snapshot_entities(pb, sym) if pin else []
    probe = Probe(pb, sym["_g_vbl_epoch"])
    probe.install(sites)
    start_loops = u16(pb, sym["_loop_frame_counter"])
    start_cycles = pb._cycles()
    start_epoch = pb.memory[sym["_g_vbl_epoch"]]
    mid_oam = None
    try:
        for frame in range(frames):
            if sustain:
                sustain_player(pb, sym)
            if pin:
                pin_coordinates(pb, sym, saved)
            pb.tick(1, render=False, sound=False)
            if frame == frames // 2:
                mid_oam = oam_summary(pb)
    finally:
        probe.remove(sites)
    end_loops = u16(pb, sym["_loop_frame_counter"])
    end_cycles = pb._cycles()
    end_epoch = pb.memory[sym["_g_vbl_epoch"]]
    lcd_cycles = end_cycles - start_cycles
    per_lcd = lcd_cycles / frames if frames else 0
    updates = (end_loops - start_loops) & 0xFFFF
    vblanks = (end_epoch - start_epoch) & 0xFF
    # The epoch byte wraps every 256 VBlanks. The windows used here are shorter.
    if frames > 200:
        raise RuntimeError("vblank epoch delta is only wrap-safe under 256 LCD frames")
    profile = analyze(probe.events, round(per_lcd))
    cadence = {
        "lcd_frames": frames,
        "game_updates": updates,
        "vblank_epochs": vblanks,
        "lag_lcd_frames": frames - updates if frames >= updates else None,
        "updates_per_lcd": round(updates / frames, 4) if frames else None,
        "sim_hz": round(LCD_HZ * updates / frames, 3) if frames else None,
        "pyboy_cycles": lcd_cycles,
        "pyboy_cycles_per_lcd_frame": round(per_lcd, 3),
        "frame_budget_ok": abs(per_lcd - FRAME_T) <= 8,
    }
    picture = {"mid": mid_oam, "end": oam_summary(pb), "entities_end": census(pb, sym)}
    return cadence, profile, picture


def run_one(name: str, setup, sym, sites, frames: int, warmup: int,
            pin: bool, sustain: bool) -> dict:
    pb = boot_room()
    try:
        info = room_info(pb, sym)
        if info["screen"] != 5:
            raise RuntimeError(f"{name}: expected SCREEN_ROOM (5), got {info['screen']}")
        if not info["double_speed"]:
            raise RuntimeError(f"{name}: cartridge is not in CGB double-speed mode")
        setup(pb, sym, info)
        saved = snapshot_entities(pb, sym) if pin else []
        for _ in range(warmup):
            if sustain:
                sustain_player(pb, sym)
            if pin:
                pin_coordinates(pb, sym, saved)
            pb.tick(1, render=False, sound=False)
        before = census(pb, sym)
        before_room = room_info(pb, sym)
        cadence, profile, picture = measure(pb, sym, sites, frames, pin, sustain)
    finally:
        pb.stop(save=False)
    picture["entities_before_window"] = before
    return {
        "scene": name,
        "room_at_boot": info,
        "room_at_window": before_room,
        "cadence": cadence,
        "profile": profile,
        "trace": {
            "entities_before": before,
            "entities_end": picture["entities_end"],
            "oam_mid": picture["mid"],
            "oam_end": picture["end"],
        },
    }


def build_scenes(selected: set[str] | None):
    def view_origin(info: dict, dx: int, dy: int) -> tuple[int, int]:
        return info["camera_x"] + dx, info["camera_y"] + dy

    def scene_empty(pb, sym, info):
        fill_floor(pb, sym)
        clear_entities(pb, sym)

    def scene_walkers(count):
        def setup(pb, sym, info):
            fill_floor(pb, sym)
            clear_entities(pb, sym)
            spawn_enemies(pb, sym, ENEMY_CRAWLER, SPR_CRAWLER, count, view_origin(info, 32, 32))
        return setup

    def scene_orcs(pb, sym, info):
        fill_floor(pb, sym)
        clear_entities(pb, sym)
        spawn_enemies(pb, sym, ENEMY_ORC, SPR_ORC, 8, view_origin(info, 28, 28), hp=200, timer=8)

    def scene_wisps(pb, sym, info):
        fill_floor(pb, sym)
        clear_entities(pb, sym)
        # ai_data[1] is the shooter countdown. 1 makes the first live updates fire.
        spawn_enemies(pb, sym, ENEMY_WISP, SPR_WISP, 6, view_origin(info, 36, 36),
                      hp=200, timer=4, ai1=1)

    def scene_split(overlap: bool):
        def setup(pb, sym, info):
            fill_floor(pb, sym)
            clear_entities(pb, sym)
            enemy_at = view_origin(info, 40, 40)
            spawn_enemies(pb, sym, ENEMY_CRAWLER, SPR_CRAWLER, 8, enemy_at, hp=255)
            bullet_at = enemy_at if overlap else view_origin(info, 104, 96)
            spawn_bullets(pb, sym, 8, 8, bullet_at, player=True)
        return setup

    def scene_hostile_spread(pb, sym, info):
        fill_floor(pb, sym)
        clear_entities(pb, sym)
        spawn_bullets(pb, sym, 0, 16, view_origin(info, 28, 28), player=False, vx=1, vy=0)

    catalog = [
        ("natural_opening", lambda pb, sym, info: None, 0, False, False),
        ("fixed_crawlers", lambda pb, sym, info: make_fixed_crawlers(pb, sym), 0, False, False),
        ("dense12_stationary", lambda pb, sym, info: dense_projectiles(pb, sym), 0, False, False),
        ("empty_room", scene_empty, 0, False, True),
        ("walkers8_pinned", scene_walkers(8), 0, True, True),
        ("walkers16_pinned", scene_walkers(16), 0, True, True),
        ("orcs8_pinned", scene_orcs, 0, True, True),
        ("wisps6_live", scene_wisps, 150, False, True),
        ("player_shots_miss", scene_split(False), 0, True, True),
        ("player_shots_overlap", scene_split(True), 0, True, True),
        ("hostile16_moving", scene_hostile_spread, 0, False, True),
    ]
    if selected is None:
        return catalog
    missing = selected.difference(name for name, *_ in catalog)
    if missing:
        raise SystemExit(f"unknown scene(s): {', '.join(sorted(missing))}")
    return [item for item in catalog if item[0] in selected]


def provenance() -> dict:
    def run(cmd: list[str]) -> str:
        try:
            return subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT).strip()
        except Exception as exc:
            return f"unavailable: {exc}"

    rom_bytes = ROM.read_bytes()
    return {
        "git_head": run(["git", "-C", str(ROOT), "rev-parse", "HEAD"]),
        "git_subject": run(["git", "-C", str(ROOT), "log", "-1", "--format=%s"]),
        "rom_path": str(ROM),
        "rom_bytes": len(rom_bytes),
        "rom_sha256": hashlib.sha256(rom_bytes).hexdigest(),
        "noi_sha256": hashlib.sha256(NOI.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "pyboy": run([sys.executable, "-c", "import pyboy; print(getattr(pyboy, '__version__', '2.7.0'))"]),
        "note": "ROM bytes are identified by hash and are not part of the handoff bundle.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=180)
    parser.add_argument("--scenes", default="all",
                        help="comma list, or all")
    parser.add_argument("--out", type=Path, default=Path("/tmp/quintra-crowded-baseline.json"))
    args = parser.parse_args()
    if not (1 <= args.frames <= 200):
        raise SystemExit("--frames must be 1..200 so the 8-bit vblank epoch cannot wrap")
    sym = load_noi(NOI)
    missing = [name for name in HOOKS.values() if name not in sym]
    if missing:
        raise SystemExit(f"noi missing symbols: {missing}")
    sites = {label: cpu_site(sym[name]) for label, name in HOOKS.items()}
    selected = None if args.scenes == "all" else set(args.scenes.split(","))
    report = {
        "provenance": provenance(),
        "metric": {
            "frame_t_cycles": FRAME_T,
            "lcd_hz": LCD_HZ,
            "work": "T-cycles from input_poll entry to wait_vbl_done entry; the whole poll gap when the wait is skipped",
            "exclusive_slice": "T-cycles from a hooked entry until the next hooked entry in that update",
            "lag_lcd_frames": "LCD frames minus loop_frame_counter steps",
            "position_pin": "Pinned scenes restore entity coordinates and EF_ON_SCREEN between LCD frames so geometry stays put. The restore is a host write and is not emulated work.",
            "sustain": "Sustained scenes refresh player HP, HP max, and iframes, and clear g_hitstop, between LCD frames so the fixture cannot enter the death screen.",
        },
        "hook_sites": {label: {"bank": bank, "cpu": cpu, "linear": sym[HOOKS[label]]}
                       for label, (bank, cpu) in sites.items()},
        "scenes": [],
    }
    for name, setup, warmup, pin, sustain in build_scenes(selected):
        print(f"[bench] {name} warmup={warmup} frames={args.frames} pin={pin}", flush=True)
        result = run_one(name, setup, sym, sites, args.frames, warmup, pin, sustain)
        report["scenes"].append(result)
        cadence = result["cadence"]
        work = result["profile"]["work_cycles"]
        print(
            f"[bench] {name} updates={cadence['game_updates']}/{cadence['lcd_frames']} "
            f"lag_lcd={cadence['lag_lcd_frames']} sim_hz={cadence['sim_hz']} "
            f"work_median={None if not work else work['median']} "
            f"frame_ok={cadence['frame_budget_ok']} "
            f"exclusive_ok={result['profile']['exclusive_matches_work']}",
            flush=True,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(f"[bench] wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
