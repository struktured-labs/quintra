#!/usr/bin/env python3
"""The Stage 2 Warden cannot be cheesed by standing behind a block.

Verdant Hollow's required mid-boss is a compact Stone Sentinel (mb_variant 1)
in a sealed Warden court. Its chase used to step only along the pursuit axes,
so a 16x16 crate directly between it and the champion pinned it in place.
This fixture places the player behind that block and requires the Warden to
reach the player's side, or land a shot next to them, within a few seconds.
"""
import os
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi").read_text()

ROOM_W, ROOM_H = 20, 17
BGT_FLOOR, BGT_WALL = 1, 2
BGT_BLOCK, BGT_BLOCK_TR, BGT_BLOCK_BL, BGT_BLOCK_BR = 25, 28, 29, 30
ENT_ENEMY = 2
ENEMY_STONE_SENTINEL = 1
ENTITY_SIZE = 28
# 16x16 crate at tiles (9, 7): pixels 72..87, 56..71.
BLOCK_TX, BLOCK_TY = 9, 7
BLOCK_PX, BLOCK_PY = BLOCK_TX * 8, BLOCK_TY * 8
BOSS_X, BOSS_Y = 72, 42
PLAYER_X, PLAYER_Y = 72, 80
TIME_BOUND = 360
SPR_BOSS = 24


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


(RS, PL, EN, TM, LARGE, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y,
 ENEMY_COUNT) = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_procgen_current_room_is_large", "_room_world_width",
    "_room_world_height", "_room_camera_x", "_room_camera_y",
    "_entity_enemy_count",
))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def read16(pb, address):
    return pb.memory[address] | (pb.memory[address + 1] << 8)


def paint_vram(pb, x, y, tile):
    bank = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 0
    pb.memory[0x9800 + y * 32 + x] = tile
    pb.memory[0xFF4F] = bank


def set_tile(pb, x, y, tile):
    pb.memory[TM + y * ROOM_W + x] = tile
    paint_vram(pb, x, y, tile)


def clear_entities(pb):
    pb.memory[ENEMY_COUNT] = 0
    for i in range(32 * ENTITY_SIZE):
        pb.memory[EN + i] = 0


def install_fixture(pb):
    """Compact court, one crate, Stage 2 Warden north, champion south."""
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0

    for y in range(ROOM_H):
        for x in range(ROOM_W):
            tile = BGT_WALL if (y == 0 or y == ROOM_H - 1
                                or x == 0 or x == ROOM_W - 1) else BGT_FLOOR
            set_tile(pb, x, y, tile)

    set_tile(pb, BLOCK_TX, BLOCK_TY, BGT_BLOCK)
    set_tile(pb, BLOCK_TX + 1, BLOCK_TY, BGT_BLOCK_TR)
    set_tile(pb, BLOCK_TX, BLOCK_TY + 1, BGT_BLOCK_BL)
    set_tile(pb, BLOCK_TX + 1, BLOCK_TY + 1, BGT_BLOCK_BR)

    clear_entities(pb)
    put16(pb, PL + 9, PLAYER_X)
    put16(pb, PL + 11, PLAYER_Y)
    pb.memory[PL + 15] = 255  # iframes: stay put and survive contact

    e = EN
    pb.memory[ENEMY_COUNT] = 1
    pb.memory[e] = ENT_ENEMY
    pb.memory[e + 1] = 7  # active + alive + on-screen
    pb.memory[e + 2] = 0
    put16(pb, e + 3, BOSS_X)
    pb.memory[e + 6] = 0
    put16(pb, e + 7, BOSS_Y)
    pb.memory[e + 12] = SPR_BOSS
    pb.memory[e + 13] = 7
    pb.memory[e + 14] = 80
    pb.memory[e + 15] = 0
    pb.memory[e + 16] = 0
    pb.memory[e + 17] = ENEMY_STONE_SENTINEL
    pb.memory[e + 18] = 46  # authored Stage 2 volley cadence
    pb.memory[e + 19] = 1   # Stage 2 / Verdant mb_variant
    pb.memory[e + 20] = 0   # compact Warden, not a giant Colossus
    for offset in range(21, 25):
        pb.memory[e + offset] = 0
    pb.memory[e + 25] = 0xEE
    pb.memory[e + 26] = 2
    pb.memory[e + 27] = 4
    return e


def boss_pos(pb, e):
    return read16(pb, e + 3), read16(pb, e + 7)


def reached_or_threatened(pb, e):
    bx, by = boss_pos(pb, e)
    # The Warden must physically come around or past the crate. Stray
    # diagonal volleys can clip beside it without the body ever moving,
    # so shots alone do not count as clearing this cheese.
    if by >= BLOCK_PY + 8:
        return True
    if abs(bx - PLAYER_X) > 20 and by >= BLOCK_PY - 8:
        return True
    return abs(bx - PLAYER_X) + abs(by - PLAYER_Y) <= 24


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(120):
        pb.tick()
    return pb


def run_fixture(pb, screenshot_dir=None, label="after"):
    e = install_fixture(pb)
    # Let the forced compact camera and tile writes present once.
    for _ in range(2):
        pb.tick()
    start = boss_pos(pb, e)
    if screenshot_dir is not None:
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        pb.screen.image.save(screenshot_dir / f"{label}-t0.png")

    resolved_at = None
    for frame in range(TIME_BOUND):
        pb.memory[PL + 15] = 255
        put16(pb, PL + 9, PLAYER_X)
        put16(pb, PL + 11, PLAYER_Y)
        pb.tick()
        if resolved_at is None and reached_or_threatened(pb, e):
            resolved_at = frame
            if screenshot_dir is not None:
                pb.screen.image.save(screenshot_dir / f"{label}-resolved.png")
            break

    end = boss_pos(pb, e)
    if screenshot_dir is not None and resolved_at is None:
        pb.screen.image.save(screenshot_dir / f"{label}-t{TIME_BOUND}.png")
    return start, end, resolved_at


def main():
    screenshot_dir = os.environ.get("TRAPBOSS_SHOTS")
    shots = Path(screenshot_dir) if screenshot_dir else None
    expect_fail = os.environ.get("TRAPBOSS_EXPECT_STUCK") == "1"

    pb = boot()
    start, end, resolved_at = run_fixture(
        pb, shots, "before" if expect_fail else "after")
    pb.stop(save=False)

    print(f"[trap-boss-unstick] start={start} end={end} resolved_at={resolved_at}")
    if expect_fail:
        if resolved_at is not None:
            raise SystemExit(
                f"baseline unexpectedly reached/threatened at frame {resolved_at}: "
                f"{start}->{end}")
        print("[trap-boss-unstick] BASELINE STUCK as expected")
        return
    assert resolved_at is not None, (
        f"Stage 2 Warden stayed pinned behind the crate for {TIME_BOUND} frames: "
        f"{start}->{end}")
    print(f"[trap-boss-unstick] PASS Warden reached or threatened at frame {resolved_at} "
          f"{start}->{end}")


if __name__ == "__main__":
    main()
