#!/usr/bin/env python3
"""Per-room status-effect scenarios for the human-skill balance bots.

Each scenario is a real generated combat room: the cartridge boots a stage
with its progression-matched loadout (``boot_to_stage`` /
``apply_prior_progression``), the fixture crosses one maze edge into an
ordinary court (``test_stage_archetypes`` helpers), and the room's own enemy
set spawns. The same pilot and human filter as ``balance_arena.py`` then
fight it to a clear or a death.

The earlier first-room slices mostly timed out because the pilot chased the
nearest hostile by straight-line distance, which in 248 px districts is often
behind a wall. Here the pilot only sees hostiles it can walk to (a flood fill
over the same collision field it routes on), and a short wiggle breaks a
pose stuck for 1.5 s. Hostiles no path reaches are logged, not chased.

    # 1) fixtures: one boot per (stage, hero, difficulty), N rooms each
    python3 scripts/balance_rooms.py fixtures --stages 1-9 --rooms 4 --out tmp/balance/rooms
    # 2) fights: every tier x seed on every fixture
    python3 scripts/balance_rooms.py fight --fixtures tmp/balance/rooms --seeds 2 \\
        --skills bot skilled average nonexpert --out tmp/balance/rooms-normal.csv

Writes the fight CSV plus ``<out>.events.csv`` (every status landing, hit and
death with HP, attacker, crowd and chain context) for
``scripts/balance_rooms_report.py``. Fixture writes (seed, run roles) happen
before the room exists, exactly as the ROM fixture tests do; the fight itself
is input-only.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from balance_arena import (CHAMPIONS, HARMFUL, STATUS_NAMES, HumanFilter,  # noqa: E402
                           noi_symbols, parse_stages)

FPS = 59.7275
WINDOWS = (300, 600)          # 5 s and 10 s after a landing
HAZARD_TILES = {31}           # BGT_SPIKES; rooms carry no pits
DOT = {1, 2, 9}               # poison, burn, bleed tick for 1 and floor at 1 HP

FIGHT_FIELDS = ("skill,seed,hero,class,stage,difficulty,room_id,fixture,enemy_kinds,cinder,"
                "outcome,frames,hits,dmg_taken,dot_dmg,hp_start,hp_end,hp_min,hp_max,"
                "lands,harmful,unreachable,exposed5,exposed10,death_kind,death_age,"
                "death_chain").split(",")
EVENT_FIELDS = ("skill,seed,hero,stage,difficulty,room_id,fixture,frame,event,kind,hp,hp_max,"
                "attacker,carrier,procced,replaced,crowd,hazard_near,status_active,"
                "status_age").split(",")


def status_carriers() -> dict[int, int]:
    """enemy id -> status it inflicts on hit, parsed from the cartridge."""
    enemies = {m.group(1): int(m.group(2)) for m in re.finditer(
        r"#define ENEMY_(\w+)\s+(\d+)", (ROOT / "src/generated/enemies.h").read_text())}
    names = {n.upper(): i for i, n in enumerate(STATUS_NAMES) if n}
    src = (ROOT / "src/game/status.c").read_text()
    body = src[src.index("status_hostile_kind_for_enemy(u8 eid)"):]
    body = body[:body.index("\n}\n")]
    out: dict[int, int] = {}
    pending: list[str] = []
    for line in body.splitlines():
        pending += re.findall(r"case ENEMY_(\w+):", line)
        m = re.search(r"return QSTATUS_(\w+);", line)
        if m:
            for name in pending:
                if name in enemies and m.group(1) in names:
                    out[enemies[name]] = names[m.group(1)]
            pending = []
    return out


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------
def make_fixtures(task: dict) -> list[dict]:
    os.environ["QUINTRA_TEST_ROM"] = task["rom"]
    import test_stage_archetypes as ta
    from make_stage_states import (boot_to_stage, cross_graph_edge,
                                   normalize_compact_source, select_rom_topology)
    from quintra_topology import STAGE_START, dungeon_predecessor, dungeon_size

    rom = Path(task["rom"])
    select_rom_topology(rom)
    addrs = ta.symbol_addresses(rom)
    st0 = task["stage"] - 1
    hero = task["hero"]
    pb, _ram, _entry = boot_to_stage(rom, addrs, st0, task["difficulty"], CHAMPIONS.index(hero))
    base = io.BytesIO()
    pb.save_state(base)
    out_dir = Path(task["out"])
    out_dir.mkdir(parents=True, exist_ok=True)
    made, seed = [], (0x5EED0000 + task["stage"] * 0x1111 + CHAMPIONS.index(hero) * 0x77) & 0xFFFFFFFF
    tries = 0
    prefs = (4, 6, 10, 12, 13, 14, 16, 18, 20, 22)
    want = set(task.get("want_kinds", ()))
    want_n = task.get("want_rooms", 0)
    n_gen = n_want = 0
    while (n_gen < task["rooms"] or n_want < want_n) and tries < (task["rooms"] + want_n) * 12:
        tries += 1
        seed = (seed * 1103515245 + 12345) & 0xFFFFFFFF
        try:
            local = ta.archetype_sample_cell(st0, seed, prefs[tries % len(prefs)])
        except AssertionError:
            continue
        base.seek(0)
        pb.load_state(base)
        rs = ta.RS
        for i, byte in enumerate(seed.to_bytes(4, "little")):
            pb.memory[rs + 2 + i] = byte
        for off in (36, 37, 12, 13, 28):
            pb.memory[rs + off] = 0
        pb.memory[addrs["_room_puzzle_locked"]] = 0
        pb.memory[ta.addr("_room_combat_sealed")] = 0
        src, direction_id = dungeon_predecessor(local, dungeon_size(st0), seed, st0)
        pb.memory[rs + 1] = STAGE_START[st0] + src
        pb.memory[rs + 6] = 0xFF
        normalize_compact_source(pb, addrs)
        for i in range(32):
            ep = ta.EN + i * 28
            if pb.memory[ep] == 2:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        direction = ("up", "right", "down", "left")[direction_id]
        cross_graph_edge(pb, ta.PL, ta.TM, direction)
        target = STAGE_START[st0] + local
        for _ in range(120):
            pb.tick()
            if pb.memory[rs + 1] == target:
                break
        pb.button_release(direction)
        if pb.memory[rs + 1] != target:
            continue
        pb.memory[rs + 28] = 0
        try:
            ta.wait_for_generated_room(pb)
        except AssertionError:
            continue
        # Step off the threshold so the fight starts inside the room.
        pb.button_press(direction)
        pb.tick(16)
        pb.button_release(direction)
        pb.tick(20)
        if pb.memory[rs + 1] != target:
            continue
        kinds = sorted({pb.memory[ta.EN + i * 28 + 17] for i in range(32)
                        if pb.memory[ta.EN + i * 28] == 2 and pb.memory[ta.EN + i * 28 + 1] & 1})
        if not kinds:
            continue
        hit = bool(want & set(kinds))
        if hit and n_want < want_n:
            n_want += 1
        elif n_gen < task["rooms"]:
            n_gen += 1
        else:
            continue
        name = f"room-s{task['stage']:02d}-{hero}-{task['difficulty']}-{len(made):02d}.pyboy"
        with (out_dir / name).open("wb") as f:
            pb.save_state(f)
        made.append({"file": name, "stage": task["stage"], "hero": hero,
                     "difficulty": task["difficulty"], "seed": seed, "cell": local,
                     "room_id": target, "enemy_kinds": kinds,
                     "focus": "cinder" if hit and want else ""})
    pb.stop(save=False)
    return made


# --------------------------------------------------------------------------
# Navigation: only hostiles the champion can walk to
# --------------------------------------------------------------------------
def reach_map(obs: dict, blocked: frozenset | set = frozenset()) -> dict[tuple[int, int], tuple[int, int] | None]:
    """Flood fill of champion poses; maps each reachable cell to its parent."""
    from run_pyboy_checkpoints import FULL_BODY_BLOCKERS, WALKABLE, observation_grid
    tiles, w, h = observation_grid(obs)

    def body_open(x, y):
        return (0 <= x < w - 1 and 0 <= y < h - 1
                and all(tiles[yy * w + xx] in WALKABLE
                        for xx, yy in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1))))
    start = (max(0, min(w - 2, (obs["x"] + 2) // 8)), max(0, min(h - 2, (obs["y"] + 8) // 8)))
    seen = {start: None}
    queue = [start]
    for x, y in queue:
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            # Stay off the outer door ring so walking never leaves the room.
            if ((nx, ny) in seen or (nx, ny) in blocked or not body_open(nx, ny)
                    or nx < 1 or ny < 1 or nx > w - 3 or ny > h - 3):
                continue
            if ny != y and ny > 0 and 0 <= nx < w - 1 and any(
                    tiles[(ny - 1) * w + xx] in FULL_BODY_BLOCKERS for xx in (nx, nx + 1)):
                continue
            seen[(nx, ny)] = (x, y)
            queue.append((nx, ny))
    return seen


_GOAL_CACHE: dict = {}


def nav_action(obs: dict, cells: dict, enemy: dict, lane: int = 48) -> int:
    """Walk the flood fill to the nearest pose with a firing lane on ``enemy``.

    Quintra attacks are four-way, so the goal is a cell whose cardinal ray
    reaches the target (else the cell nearest it). ``cells`` is in BFS order,
    so the first lane cell is the closest by walking distance.
    """
    from run_pyboy_checkpoints import grid_step_action, hostile_firing_action
    fire = hostile_firing_action(obs, enemy, lane)
    if fire:
        return fire | 0x10
    # Lane goals depend only on the map, the fill and the target's pose:
    # cache them so a long walk does not re-scan every cell each frame.
    ck = (id(cells), len(cells), next(iter(cells)), enemy["x"], enemy["y"])
    if ck not in _GOAL_CACHE:
        if len(_GOAL_CACHE) > 256:
            _GOAL_CACHE.clear()
        _GOAL_CACHE[ck] = next((c for c in cells if hostile_firing_action(
            obs, enemy, lane, player_x=c[0] * 8 - 2, player_y=c[1] * 8 - 8)), None)
    goal = _GOAL_CACHE[ck]
    if goal is None:
        ex, ey = (enemy["x"] + 4) // 8, (enemy["y"] + 4) // 8
        goal = min(cells, key=lambda c: abs(c[0] - ex) + abs(c[1] - ey))
    path = [goal]
    while cells[path[-1]] is not None:
        path.append(cells[path[-1]])
    start = path[-1]
    if len(path) < 2:
        # Already on the goal cell: square up to the pose grid.
        tx, ty = start[0] * 8 - 2, start[1] * 8 - 8
        return ((0x02 if tx > obs["x"] else 0x08 if tx < obs["x"] else 0)
                | (0x04 if ty > obs["y"] else 0x01 if ty < obs["y"] else 0))
    nxt = path[-2]
    return grid_step_action(obs, start, nxt[0] - start[0], nxt[1] - start[1])


def keep_inside(obs: dict, action: int, margin: int = 8) -> int:
    """Drop d-pad bits that would walk the champion out through a door.

    The scenario measures one fight; leaving the room would end it with
    no result, so the edge band acts like a sealed combat room.
    """
    w = obs.get("world_width", 160)
    h = obs.get("world_height", 144)
    if obs["x"] < margin:
        action &= ~0x08
    if obs["x"] > w - margin - 16:
        action &= ~0x02
    if obs["y"] < margin:
        action &= ~0x01
    if obs["y"] > h - margin - 16:
        action &= ~0x04
    return action


def reachable(enemy: dict, cells: set[tuple[int, int]]) -> bool:
    ex, ey = (enemy["x"] + 4) // 8, (enemy["y"] + 4) // 8
    return any((ex + dx, ey + dy) in cells for dx in range(-3, 4) for dy in range(-3, 4))


def tile_near(obs: dict, kinds: set[int], radius: int = 1) -> bool:
    from run_pyboy_checkpoints import observation_grid
    tiles, w, h = observation_grid(obs)
    cx, cy = (obs["x"] + 8) // 8, (obs["y"] + 12) // 8
    return any(0 <= cx + dx < w and 0 <= cy + dy < h and tiles[(cy + dy) * w + cx + dx] in kinds
               for dx in range(-radius - 1, radius + 2) for dy in range(-radius - 1, radius + 2))


# --------------------------------------------------------------------------
# Fight
# --------------------------------------------------------------------------
def fight(task: dict) -> tuple[dict, list[dict]]:
    from quintra_pyboy_env import QuintraPyBoyEnv
    from run_pyboy_checkpoints import ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_UP, controller_action

    rom = Path(task["rom"])
    syms = noi_symbols(rom)
    s_kind, s_ticks = syms["_player_status_kind"], syms["_player_status_ticks"]
    carriers = task["carriers"]
    fx = task["fixture"]
    env = QuintraPyBoyEnv(rom)
    events: list[dict] = []
    try:
        obs = env.load_state(Path(task["dir"]) / fx["file"], require_manifest=False)
        mem = env.pb.memory
        ent = env.addrs["_entities"]
        cls = CHAMPIONS.index(fx["hero"])
        human = HumanFilter(task["skill"], task["seed"], cls)
        for _ in range(task["seed"] % 7):
            obs, _, _, _ = env.step(0, 1)
        base = dict(skill=task["skill"], seed=task["seed"], hero=fx["hero"], stage=fx["stage"],
                    difficulty=fx["difficulty"], room_id=fx["room_id"], fixture=fx["file"])

        def ev(frame, event, **kw):
            row = dict(base, frame=frame, event=event, kind="", hp=obs["hp"],
                       hp_max=obs["hp_max"], attacker="", carrier="", procced="", replaced="",
                       crowd="", hazard_near="", status_active="", status_age="")
            row.update(kw)
            events.append(row)

        # Cells the map calls open but the champion cannot enter (props,
        # dynamic blockers): learned when a walk makes no progress.
        blocked: set[tuple[int, int]] = set()
        cells = reach_map(obs, blocked)
        room0 = obs["room"]
        hist = []
        last_hp = hp_start = hp_min = obs["hp"]
        hits = dmg = dot = lands = harmful = 0
        last_st, last_tk = mem[s_kind], mem[s_ticks]
        last_land = None           # (frame, kind)
        land_frames: list[int] = []
        dot_pinned = False
        pending_hits: list[dict] = []
        seen_live = cleared_for = 0
        still, last_pos, wiggle = 0, None, 0
        stall, last_pool, stalls, last_action = 0, None, 0, 0
        outcome, frame, cap = "timeout", 0, task["frames"]
        unreach = 0
        death_chain = ""
        while frame < cap:
            if frame % 10 == 0:
                cells = reach_map(obs, blocked)
            live = [e for e in obs["hostiles"] if not e["giant"]]
            reach = [e for e in live if reachable(e, cells)]
            unreach = len(live) - len(reach)
            view = dict(obs)
            view["hostiles"] = reach
            hidden = human.scan(mem, ent, frame)
            blind = human.p and mem[s_kind] == 5
            if hidden or blind:
                view["projectiles"] = [s for s in obs["projectiles"]
                                       if (s["x"], s["y"]) not in hidden and not (
                                           blind and max(abs(s["x"] - obs["x"]),
                                                         abs(s["y"] - obs["y"])) > 32)]
            threatened = bool(view["projectiles"]) or any(
                max(abs(e["x"] - obs["x"]), abs(e["y"] - obs["y"])) <= 40 for e in reach)
            pos = (obs["x"], obs["y"])
            still = still + 1 if pos == last_pos else 0
            last_pos = pos
            # Engage with the pilot near a target; walk the flood fill to
            # reach one; a pose stuck for 0.5 s walks the fill instead.
            near = min(reach, key=lambda e: max(abs(e["x"] - obs["x"]), abs(e["y"] - obs["y"])),
                       default=None)
            dist = max(abs(near["x"] - obs["x"]), abs(near["y"] - obs["y"])) if near else 999
            # No damage dealt for 3 s (dodging forever, or pinned on a
            # wall): commit to walking up to the target for 1.5 s.
            pool = (len(live), sum(e.get("hp", 0) for e in live))
            stall = 0 if pool != last_pool else stall + 1
            last_pool = pool
            if wiggle and still > 20 and cells:
                # The walk is pinned: mark the cell it was walking into.
                sx, sy = max(0, (obs["x"] + 2) // 8), max(0, (obs["y"] + 8) // 8)
                step = {0x02: (1, 0), 0x08: (-1, 0), 0x04: (0, 1), 0x01: (0, -1)}
                for bit, (ddx, ddy) in step.items():
                    if last_action & bit:
                        blocked.add((sx + ddx, sy + ddy))
                cells = reach_map(obs, blocked)
                still = 0
            if near is not None and (still > 30 or stall > 180):
                wiggle, still, stall = 90, 0, 0
                stalls += 1
            if near is not None and (wiggle or (dist > 72 and not view["projectiles"])):
                wiggle = max(0, wiggle - 1)
                if frame % 10 == 0 or frame < 2:
                    cells = reach_map(obs, blocked)
                # Rotate targets on repeated stalls so one unreachable
                # angle cannot pin the pilot for the whole fight.
                order = sorted(reach, key=lambda e: max(abs(e["x"] - obs["x"]), abs(e["y"] - obs["y"])))
                target = order[stalls % len(order)]
                action = nav_action(obs, cells, target)
                if os.environ.get("QBAL_DEBUG") == "3" and frame % 60 == 0:
                    print("nav", frame, (obs["x"], obs["y"]), (target["x"], target["y"]), len(cells),
                          next(iter(cells)), action, file=sys.stderr)
            else:
                action = controller_action(view, frame)
            action = human.apply(action, threatened)
            action = keep_inside(obs, action)
            last_action = action
            if os.environ.get("QBAL_DEBUG") == "2" and frame % 240 == 0:
                print("dbg", frame, (obs["x"], obs["y"]), len(live), len(reach),
                      near and (near["x"], near["y"], near["hp"] if "hp" in near else ""), dist,
                      wiggle, action, len(view["projectiles"]), file=sys.stderr)
            hist.append((obs["x"], obs["y"], action))
            obs, _, terminal, _ = env.step(action, 1)
            frame += 1
            hp, st, tk = obs["hp"], mem[s_kind], mem[s_ticks]
            # ---- status landings
            landed = 0 < st < len(STATUS_NAMES) and (st != last_st or tk > last_tk)
            if landed:
                lands += 1
                replaced = STATUS_NAMES[last_st] if (last_st and last_tk and last_st != st) else ""
                crowd = sum(1 for e in live if max(abs(e["x"] - obs["x"]), abs(e["y"] - obs["y"])) <= 48)
                if st in HARMFUL:
                    harmful += 1
                    last_land = (frame, st)
                    land_frames.append(frame)
                ev(frame, "status", kind=STATUS_NAMES[st], replaced=replaced, crowd=crowd,
                   hazard_near=int(tile_near(obs, HAZARD_TILES)))
                for h in pending_hits:
                    if frame - h["frame"] <= 3 and h["carrier"] == STATUS_NAMES[st]:
                        h["procced"] = 1
            last_st, last_tk = st, tk
            # ---- damage
            if hp < last_hp:
                taken = last_hp - hp
                is_dot = (taken == 1 and last_st in DOT and obs["iframes"] <= 8)
                if is_dot:
                    dot += taken
                    if hp == 1:
                        dot_pinned = True
                else:
                    hits += 1
                    dmg += taken
                    # Attacker: nearest hostile body or hostile shot.
                    best, att, carrier = 99, "", ""
                    for slot in range(32):
                        b = ent + slot * 28
                        fl = mem[b + 1]
                        if not fl & 1 or mem[b] not in (1, 2) or (mem[b] == 1 and fl & 0x10):
                            continue
                        x = mem[b + 3] | (mem[b + 4] << 8)
                        y = mem[b + 7] | (mem[b + 8] << 8)
                        x -= 0x10000 if x & 0x8000 else 0
                        y -= 0x10000 if y & 0x8000 else 0
                        d = max(abs(x - obs["x"]), abs(y - obs["y"]))
                        if d < best:
                            if mem[b] == 2:
                                eid, kind = mem[b + 17], carriers.get(mem[b + 17], 0)
                                if fl & 0x80:          # EF_RARE: slow/poison at 100%
                                    kind = 3 if mem[b + 17] & 1 else 1
                            else:
                                tag = mem[b + 22]
                                eid = (tag - 1) if tag and not tag & 0x80 else -1
                                kind = (tag & 0x7F) if tag & 0x80 else carriers.get(eid, 0)
                            best, att = d, ("shot:" if mem[b] == 1 else "") + str(eid)
                            carrier = STATUS_NAMES[kind] if 0 < kind < len(STATUS_NAMES) else ""
                    h = dict(base, frame=frame, event="hit", kind="", hp=hp, hp_max=obs["hp_max"],
                             attacker=att, carrier=carrier, procced=0, replaced="",
                             crowd=sum(1 for e in live if max(abs(e["x"] - obs["x"]),
                                                              abs(e["y"] - obs["y"])) <= 48),
                             hazard_near=int(tile_near(obs, HAZARD_TILES)),
                             status_active=STATUS_NAMES[last_st] if last_st in HARMFUL else "",
                             status_age=(frame - last_land[0]) if last_land else -1)
                    if landed and carrier == STATUS_NAMES[st]:
                        h["procced"] = 1
                    events.append(h)
                    pending_hits.append(h)
            elif hp > last_hp:
                dot_pinned = False
            pending_hits = [h for h in pending_hits if frame - h["frame"] <= 3]
            last_hp = hp
            hp_min = min(hp_min, hp)
            if hp == 0 or terminal:
                outcome = "died"
                age = frame - last_land[0] if last_land else -1
                recent = [e for e in events if e["event"] == "status" and frame - e["frame"] <= 600]
                chain = []
                if last_st == 4 or any(e["kind"] == "stop" and frame - e["frame"] <= 150 for e in recent):
                    chain.append("stop_then_hit")
                if any(e["kind"] == "confusion" and frame - e["frame"] <= 300 for e in recent) and (
                        tile_near(obs, HAZARD_TILES) or any(e["kind"] == "confusion" and e["hazard_near"] for e in recent)):
                    chain.append("confusion_near_hazard")
                crowd = sum(1 for e in live if max(abs(e["x"] - obs["x"]), abs(e["y"] - obs["y"])) <= 48)
                if (last_st == 5 or any(e["kind"] == "blind" and frame - e["frame"] <= 600 for e in recent)) and crowd >= 3:
                    chain.append("blind_in_crowd")
                if dot_pinned:
                    chain.append("dot_pinned_then_hit")
                if any(e["replaced"] for e in recent if e["kind"] in [STATUS_NAMES[k] for k in HARMFUL]):
                    chain.append("status_replaced")
                death_chain = "+".join(chain)
                ev(frame, "death", kind=STATUS_NAMES[last_land[1]] if last_land else "",
                   status_active=STATUS_NAMES[last_st] if last_st in HARMFUL else "",
                   status_age=age, crowd=crowd, replaced=death_chain,
                   hazard_near=int(tile_near(obs, HAZARD_TILES)))
                break
            if obs["room"] != room0 or obs["screen"] != 5:
                outcome = "left_room"
                if os.environ.get("QBAL_DEBUG"):
                    print("left", task["fixture"], frame, obs["room"], room0, obs["screen"], hist[-12:], file=sys.stderr)
                break
            seen_live |= bool(live)
            cleared_for = cleared_for + 1 if seen_live and not reach else 0
            if cleared_for >= 30:
                outcome = "cleared"
                frame -= 30
                break
        exposed = [0, 0]
        for i, w in enumerate(WINDOWS):
            cover = set()
            for f0 in land_frames:
                cover.update(range(f0, min(frame, f0 + w)))
            exposed[i] = len(cover)
        died = outcome == "died"
        row = dict(base, **{"class": cls}, fixture=fx["file"],
                   enemy_kinds=" ".join(map(str, fx["enemy_kinds"])),
                   cinder=int(bool({14, 25} & set(fx["enemy_kinds"]))),
                   outcome=outcome, frames=frame, hits=hits, dmg_taken=dmg, dot_dmg=dot,
                   hp_start=hp_start, hp_end=obs["hp"], hp_min=hp_min, hp_max=obs["hp_max"],
                   lands=lands, harmful=harmful, unreachable=unreach,
                   exposed5=exposed[0], exposed10=exposed[1],
                   death_kind=STATUS_NAMES[last_land[1]] if died and last_land else "",
                   death_age=(frame - last_land[0]) if died and last_land else -1,
                   death_chain=death_chain)
        return row, events
    finally:
        env.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fixtures")
    f.add_argument("--rom", type=Path, default=ROOT / "rom/working/quintra.gbc")
    f.add_argument("--stages", default="1-9")
    f.add_argument("--heroes", nargs="+", default=list(CHAMPIONS), choices=CHAMPIONS)
    f.add_argument("--difficulties", nargs="+", default=["normal", "easy"], choices=("normal", "easy"))
    f.add_argument("--rooms", type=int, default=4)
    f.add_argument("--extra", default="1-3:8", help="stages:rooms override, e.g. 1-3:8")
    f.add_argument("--cinder", type=int, default=8,
                   help="extra Ember (stage 3) rooms per hero that contain Cinder Maw/Kite")
    f.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    f.add_argument("--out", type=Path, default=ROOT / "tmp/balance/rooms")
    g = sub.add_parser("fight")
    g.add_argument("--rom", type=Path, default=ROOT / "rom/working/quintra.gbc")
    g.add_argument("--fixtures", type=Path, default=ROOT / "tmp/balance/rooms")
    g.add_argument("--skills", nargs="+", default=["bot", "skilled", "average", "nonexpert"])
    g.add_argument("--stages", default="1-9")
    g.add_argument("--heroes", nargs="+", default=list(CHAMPIONS), choices=CHAMPIONS)
    g.add_argument("--difficulty", choices=("normal", "easy"), default="normal")
    g.add_argument("--rooms", type=int, default=99, help="max fixtures per (stage, hero)")
    g.add_argument("--seeds", type=int, default=2)
    g.add_argument("--seed-base", type=int, default=1)
    g.add_argument("--frames", type=int, default=7200)
    g.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    g.add_argument("--out", type=Path, default=ROOT / "tmp/balance/rooms.csv")
    args = ap.parse_args()
    started = time.time()

    if args.cmd == "fixtures":
        extra = {}
        if args.extra:
            span, n = args.extra.split(":")
            extra = {s: int(n) for s in parse_stages(span)}
        tasks = [dict(rom=str(args.rom.resolve()), stage=s, hero=h, difficulty=d,
                      rooms=extra.get(s, args.rooms), out=str(args.out),
                      want_kinds=(14, 25) if s == 3 else (), want_rooms=args.cinder if s == 3 else 0)
                 for s in parse_stages(args.stages) for h in args.heroes for d in args.difficulties]
        man_path = args.out / "fixtures.json"
        made = json.loads(man_path.read_text()) if man_path.exists() else []
        done = {(m["stage"], m["hero"], m["difficulty"]) for m in made}
        tasks = [t for t in tasks if (t["stage"], t["hero"], t["difficulty"]) not in done]
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            futs = {pool.submit(make_fixtures, t): t for t in tasks}
            for n, fut in enumerate(as_completed(futs), 1):
                t = futs[fut]
                try:
                    rows = fut.result()
                except Exception as exc:  # report, keep the rest
                    print(f"[rooms] fixture failed s{t['stage']} {t['hero']} {t['difficulty']}: {exc}",
                          flush=True)
                    continue
                made.extend(rows)
                args.out.mkdir(parents=True, exist_ok=True)
                man_path.write_text(json.dumps(made, indent=1))
                if len(rows) < t["rooms"] + t["want_rooms"]:
                    print(f"[rooms] s{t['stage']} {t['hero']} {t['difficulty']}: "
                          f"{len(rows)}/{t['rooms'] + t['want_rooms']}",
                          flush=True)
        print(f"[rooms] {len(made)} fixtures in {round(time.time() - started)}s -> {args.out}")
        return 0

    fixtures = json.loads((args.fixtures / "fixtures.json").read_text())
    stages = set(parse_stages(args.stages))
    per: dict = {}
    chosen = []
    for fx in sorted(fixtures, key=lambda m: m["file"]):
        key = (fx["stage"], fx["hero"])
        if fx["difficulty"] != args.difficulty or fx["stage"] not in stages or fx["hero"] not in args.heroes:
            continue
        if per.get(key, 0) >= args.rooms:
            continue
        per[key] = per.get(key, 0) + 1
        chosen.append(fx)
    carriers = status_carriers()
    tasks = [dict(rom=str(args.rom), dir=str(args.fixtures), fixture=fx, skill=sk,
                  seed=args.seed_base + i, frames=args.frames, carriers=carriers)
             for fx in chosen for sk in args.skills for i in range(args.seeds)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ev_path = args.out.with_suffix(".events.csv")
    with args.out.open("w", newline="") as fo, ev_path.open("w", newline="") as fe, \
            ProcessPoolExecutor(max_workers=args.jobs) as pool:
        wo = csv.DictWriter(fo, fieldnames=FIGHT_FIELDS)
        we = csv.DictWriter(fe, fieldnames=EVENT_FIELDS)
        wo.writeheader()
        we.writeheader()
        futs = [pool.submit(fight, t) for t in tasks]
        for n, fut in enumerate(as_completed(futs), 1):
            try:
                row, events = fut.result()
            except Exception as exc:  # one broken fight must not sink the sweep
                print(f"[rooms] fight failed: {exc}", flush=True)
                continue
            wo.writerow({k: row[k] for k in FIGHT_FIELDS})
            we.writerows({k: e[k] for k in EVENT_FIELDS} for e in events)
            fo.flush()
            fe.flush()
            if n % 100 == 0 or n == len(tasks):
                print(f"[rooms] {n}/{len(tasks)} fights, {round(time.time() - started)}s", flush=True)
    (args.out.with_suffix(".json")).write_text(json.dumps(
        {"fights": len(tasks), "difficulty": args.difficulty, "skills": args.skills,
         "seeds": args.seeds, "seconds": round(time.time() - started)}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
