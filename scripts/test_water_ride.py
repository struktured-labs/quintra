#!/usr/bin/env python3
"""Live-ROM contract: water traversal is drawn, not a hero walking on water.

The Tide Raft waygear and Picsean's innate swim both make Riftwild water
passable (WAYGEAR_TILE_PASSABLE). While the champion's feet are over water a
non-Picsean rides a two-frame bobbing log raft (OAM 36..38, bank-1 OBJ 0..5,
palette 5) and the Picsean swims: the torso sinks and a ripple ring (bank-1
OBJ 6..9) replaces the legs in OAM 2..3. Back on land everything returns.
"""
import os
import sys

from pyboy import PyBoy

from test_overworld import (
    CAMERA_X, CAMERA_Y, EN, LARGE, PL, ROM, RS, TM, WORLD_H, WORLD_W,
    addr, exit_at, put16,
)
from test_riftwild_landmarks import WALKABLE, wide_tiles
from quintra_topology import STAGE_BOSS_ROOM

MODE = addr("_water_ride_mode")
WATER = (97, 101)
RAFT_OAM = 36
RAFT_PAL = 5
BANK1 = 0x08
PICSEAN = 3
WAYGEAR_OWNED = 44
RAFT_BIT = 0x02
SHOTS = os.environ.get("WATER_RIDE_SHOTS")


def boot(cls):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    for _ in range(cls):
        pb.button("down")
        pb.tick(12)
    pb.button("a")
    pb.tick(60)
    assert pb.memory[PL] == cls, f"class select picked {pb.memory[PL]}"
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[0]
    pb.memory[RS + 11] = 1
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    pb.memory[TM + 16 * 20 + 9] = 3
    pb.memory[TM + 16 * 20 + 10] = 3
    exit_at(pb, 72, 120)
    assert pb.memory[RS + 17] == 1 and pb.memory[RS + 18] == 0, \
        "fixture did not reach the opening Riftwild field"
    return pb


def calm(pb, frames):
    for _ in range(frames):
        for i in range(32):
            p = EN + i * 28
            if pb.memory[p] == 2:
                pb.memory[p] = pb.memory[p + 1] = 0
        pb.memory[PL + 2] = pb.memory[PL + 1]
        pb.memory[PL + 15] = 0          # no damage flicker
        pb.tick()


def spots(pb):
    w = wide_tiles(pb)
    water = land = None
    for y in range(1, 28):
        for x in range(1, 28):
            block = [w[y + dy][x + dx] for dy in range(3) for dx in range(3)]
            if water is None and all(t in WATER for t in block):
                water = (x, y)
            if land is None and all(t in WALKABLE for t in block):
                land = (x, y)
    assert water and land, "opening Riftwild field has no 3x3 pond or clearing"
    # Feet probe is (x + 8, y + 12): centre the body on the 3x3 block.
    return ((water[0] * 8 + 4, water[1] * 8), (land[0] * 8 + 4, land[1] * 8))


def oam(pb, i):
    b = 0xFE00 + i * 4
    return tuple(pb.memory[b:b + 4])   # y, x, tile, prop


def teleport(pb, pos):
    put16(pb, PL + 9, pos[0])
    put16(pb, PL + 11, pos[1])
    calm(pb, 70)                        # let the scrolling camera settle


def check_raft():
    pb = boot(0)
    try:
        pb.memory[PL + WAYGEAR_OWNED] |= RAFT_BIT
        water, land = spots(pb)
        teleport(pb, land)
        assert pb.memory[MODE] == 0, "raft shown on dry land"
        teleport(pb, water)
        assert pb.memory[MODE] == 1, \
            f"Tide Raft not shown on water (mode={pb.memory[MODE]})"
        assert any(pb.memory[1, 0x8000 + i] for i in range(16 * 6)), \
            "raft tiles were not uploaded to bank-1 OBJ VRAM"
        tiles, bobs = set(), set()
        for _ in range(48):
            calm(pb, 1)
            hero = oam(pb, 0)
            raft = [oam(pb, RAFT_OAM + k) for k in range(3)]
            assert hero[0] and hero[2] < 20, "hero hidden or not the class pose"
            for k, (y, x, tile, prop) in enumerate(raft):
                assert prop & 0x0F == RAFT_PAL | BANK1, f"raft prop {prop:#x}"
                assert x == (hero[1] - 4 + 8 * k) & 255, "raft not centred"
                assert y - hero[0] in (11, 12), "raft not under the feet"
            assert raft[1][2] == raft[0][2] + 1 and raft[2][2] == raft[0][2] + 2
            tiles.add(raft[0][2])
            bobs.add(raft[0][0] - hero[0])
            assert oam(pb, 2)[2] < 20 and not oam(pb, 2)[3] & BANK1, \
                "non-Picsean legs were replaced"
        assert tiles == {0, 3}, f"raft wake did not animate: {tiles}"
        assert bobs == {11, 12}, f"raft did not bob: {bobs}"
        if SHOTS:
            pb.screen.image.save(f"{SHOTS}/raft-water.png")
        teleport(pb, land)
        assert pb.memory[MODE] == 0, "raft stuck on after landing"
        assert all(oam(pb, RAFT_OAM + k)[0] == 0 for k in range(3)), \
            "raft OAM left visible on land"
    finally:
        pb.stop(save=False)


def check_swim():
    pb = boot(PICSEAN)
    try:
        assert not pb.memory[PL + WAYGEAR_OWNED] & RAFT_BIT
        water, land = spots(pb)
        teleport(pb, land)
        assert pb.memory[MODE] == 0
        teleport(pb, water)
        assert pb.memory[MODE] == 2, \
            f"Picsean swim not shown on water (mode={pb.memory[MODE]})"
        rings, sinks = set(), set()
        for _ in range(48):
            calm(pb, 1)
            top, top_r, low, low_r = (oam(pb, i) for i in range(4))
            assert top[2] < 20, "Picsean upper body replaced"
            assert low[3] & BANK1 and low_r[3] & BANK1
            assert low[2] in (6, 8) and low_r[2] == low[2] + 1, \
                f"swim ring tiles wrong: {low[2]}"
            assert low[1] == top[1] and low_r[1] == top[1] + 8
            sinks.add(low[0] - top[0])
            rings.add(low[2])
            assert not any(oam(pb, RAFT_OAM + k)[3] & 0x0F == RAFT_PAL | BANK1
                           and oam(pb, RAFT_OAM + k)[0] for k in range(3)), \
                "Picsean should swim, not ride the raft"
        assert rings == {6, 8}, f"swim ring did not animate: {rings}"
        assert sinks == {5, 6}, f"torso did not sink and bob: {sinks}"
        if SHOTS:
            pb.screen.image.save(f"{SHOTS}/picsean-swim.png")
        teleport(pb, land)
        assert pb.memory[MODE] == 0
        assert oam(pb, 2)[2] < 20 and not oam(pb, 2)[3] & BANK1, \
            "Picsean legs did not come back on land"
        assert oam(pb, 2)[0] - oam(pb, 0)[0] == 8
    finally:
        pb.stop(save=False)


def main():
    check_raft()
    check_swim()
    print("[water-ride] PASS Tide Raft bobs under the feet; Picsean swims")


if __name__ == "__main__":
    sys.exit(main())
