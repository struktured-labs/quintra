#!/usr/bin/env python3
"""Stage 2 Farfold Cache: a guarded relic must say why it stays put.

Carmelo (itch v0.20.20-beta38) found a red gem at the side of a Stage 2 map
that ignored him, then later let him take it (turning violet). That is the
Farfold Cache relic: treasure_cache_guarded() refuses it while any enemy in
the large reliquary room lives, and the refusal used to be completely silent.
This walks the real cache room for several Stage 2 seeds and requires:
  * the guarded relic stays (no theft before combat),
  * touching it raises the GUARD notice (and only at the refusal cadence),
  * once the guards are gone the same walk-over claims it.
"""
import os
import re
import sys
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_START, dungeon_cache_cell, dungeon_predecessor, dungeon_size,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ENTITY_SIZE = 28
MAX_ENTITIES = 32
ENT_ENEMY = 2
ENT_PICKUP = 3
PICKUP_FARFOLD_RELIC = 19
RUN_FARFOLD_CACHE_BIT = 0x02
SCREEN_ROOM = 5
STAGE = 1  # bosses_beaten == 1: the second dungeon ("stage 2")
SEEDS = (0x1234ABCD, 0x00C0FFEE, 0x51DE5EED, 0x0BADF00D, 0x7E57AB1E)
# Status-word glyph tiles that spell GUARD (G, U, A, R, D).
BGT_AREA_G, BGT_AREA_A, BGT_AREA_R, BGT_AREA_D = 85, 84, 76, 82
SHOTS = Path(os.environ.get("REDGEM_SHOTS", ROOT / "tmp"))


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


(RS, PL, EN, TM, SEALED, PUZZLE_LOCKED, SCREEN, TICKS, LARGE, WORLD_W,
 WORLD_H, CAMERA_X, CAMERA_Y) = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_combat_sealed", "_room_puzzle_locked", "_loop_current_screen",
    "_hud_notice_ticks", "_procgen_current_room_is_large",
    "_room_world_width", "_room_world_height", "_room_camera_x", "_room_camera_y",
))
ENC_KIND = addr("_room_encounter_kind")


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def get16(pb, address):
    return pb.memory[address] | pb.memory[address + 1] << 8


def settle(pb, frames=90, hold=None):
    for _ in range(frames):
        pb.memory[PL + 2] = pb.memory[PL + 1]   # keep HP topped up
        pb.memory[PL + 15] = 120                # and invulnerable
        if hold:
            put16(pb, PL + 9, hold[0])
            put16(pb, PL + 11, hold[1])
        pb.tick()


def enemies(pb):
    return [EN + s * ENTITY_SIZE for s in range(MAX_ENTITIES)
            if pb.memory[EN + s * ENTITY_SIZE] == ENT_ENEMY
            and pb.memory[EN + s * ENTITY_SIZE + 1] & 1]


def clear_hostiles(pb):
    for slot in range(MAX_ENTITIES):
        base = EN + slot * ENTITY_SIZE
        if pb.memory[base] == ENT_ENEMY:
            pb.memory[base] = pb.memory[base + 1] = 0


def relics(pb):
    return [EN + s * ENTITY_SIZE for s in range(MAX_ENTITIES)
            if pb.memory[EN + s * ENTITY_SIZE] == ENT_PICKUP
            and pb.memory[EN + s * ENTITY_SIZE + 1] & 1
            and pb.memory[EN + s * ENTITY_SIZE + 17] == PICKUP_FARFOLD_RELIC]


def guard_word_visible(pb):
    """True when G?ARD glyphs sit side by side in either tile map."""
    for base in (0x9800, 0x9C00):
        for row in range(32):
            line = [pb.memory[base + row * 32 + c] for c in range(32)]
            for c in range(28):
                if (line[c] == BGT_AREA_G and line[c + 2] == BGT_AREA_A
                        and line[c + 3] == BGT_AREA_R
                        and line[c + 4] == BGT_AREA_D):
                    return True
    return False


def enter_cache(pb, seed):
    """Walk through a real door from the cache cell's maze predecessor."""
    cache = dungeon_cache_cell(dungeon_size(STAGE), seed, STAGE)
    source, direction = dungeon_predecessor(
        cache, dungeon_size(STAGE), seed, STAGE)
    target = STAGE_START[STAGE] + cache
    clear_hostiles(pb)
    pb.memory[RS + 1] = STAGE_START[STAGE] + source
    pb.memory[RS + 11] = STAGE
    for i in range(4):
        pb.memory[RS + 2 + i] = (seed >> (8 * i)) & 0xFF
    pb.memory[RS + 37] = 0
    pb.memory[RS + 28] &= ~RUN_FARFOLD_CACHE_BIT & 0xFF
    pb.memory[SEALED] = 0
    pb.memory[PUZZLE_LOCKED] = 0
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    for tx, ty in {
        0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
        2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
    }[direction]:
        pb.memory[TM + ty * 20 + tx] = 3
    x, y = {0: (72, 0), 1: (144, 60), 2: (72, 120), 3: (0, 60)}[direction]
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    for _ in range(240):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    settle(pb, 120)
    assert pb.memory[RS + 1] == target, (
        f"seed {seed:08x}: did not reach cache room {target} "
        f"(at {pb.memory[RS + 1]})")
    return cache


def run_seed(seed, shots):
    pb = PyBoy(str(ROM), window="null", cgb=True, sound_emulated=False)
    try:
        settle(pb, 240)
        pb.button("start")
        settle(pb, 30)
        pb.button("a")
        settle(pb, 90)
        assert pb.memory[SCREEN] == SCREEN_ROOM
        cache = enter_cache(pb, seed)
        found = relics(pb)
        assert len(found) == 1, f"seed {seed:08x}: {len(found)} relics"
        relic = found[0]
        rx, ry = get16(pb, relic + 3), get16(pb, relic + 7)
        guards = enemies(pb)
        assert guards, f"seed {seed:08x}: cache spawned unguarded"
        stand = (rx - 12, ry - 8)
        # Walk in with real input so the camera follows the hero.
        put16(pb, PL + 9, rx - 40)
        put16(pb, PL + 11, ry - 8)
        settle(pb, 60)
        if shots:
            pb.screen.image.save(shots / f"redgem-approach-{seed:08x}.png")
        pb.button_press("right")
        for _ in range(90):
            settle(pb, 1)
            if get16(pb, PL + 9) >= rx - 12:
                break
        pb.button_release("right")
        saw_notice = False
        for _ in range(40):
            settle(pb, 3, hold=stand)
            if pb.memory[TICKS] and guard_word_visible(pb):
                saw_notice = True
                break
        if shots:
            settle(pb, 12 if saw_notice else 1, hold=stand)
        if shots:
            pb.screen.image.save(shots / f"redgem-guarded-{seed:08x}.png")
        assert relics(pb) == [relic], f"seed {seed:08x}: relic taken while guarded"
        assert not (pb.memory[RS + 28] & RUN_FARFOLD_CACHE_BIT)
        assert saw_notice, (
            f"seed {seed:08x}: guarded relic refused the hero silently "
            f"({len(guards)} guards alive, no GUARD notice)")
        # Kill the guards; the very same step now claims it.
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 60)
        # The reliquary's encounter directive may answer a clear with a
        # follow-up wave (WAVE/TRAP) or keep spawning for a timer (HOLD):
        # that is why the orb "eventually" let Carmelo take it. Keep
        # clearing until the room stays quiet, re-checking the notice on
        # the way, then the very same step must claim it.
        kind = pb.memory[ENC_KIND]
        waves = 0
        quiet = 0
        for _ in range(80):
            if enemies(pb):
                waves += 1
                clear_hostiles(pb)
                quiet = 0
            else:
                quiet += 1
                if quiet >= 4:
                    break
            settle(pb, 60)
        assert not enemies(pb), f"seed {seed:08x}: reliquary never quieted"
        settle(pb, 12, hold=stand)
        assert pb.memory[RS + 28] & RUN_FARFOLD_CACHE_BIT, (
            f"seed {seed:08x}: unguarded relic still refused")
        assert not relics(pb)
        if shots:
            settle(pb, 20)
            pb.screen.image.save(shots / f"redgem-claimed-{seed:08x}.png")
        return cache, len(guards), rx, ry, kind, waves
    finally:
        pb.stop(save=False)


def main():
    shots = None
    if "--shots" in sys.argv:
        shots = SHOTS
        shots.mkdir(parents=True, exist_ok=True)
    for seed in SEEDS:
        cache, guards, rx, ry, kind, waves = run_seed(seed, shots)
        print(f"[farfold-guard] seed={seed:08x} cell={cache} guards={guards} "
              f"encounter={kind} refills={waves} relic=({rx},{ry}) "
              f"GUARD notice + claim after clear OK")
    print("[farfold-guard] PASS")


if __name__ == "__main__":
    main()
