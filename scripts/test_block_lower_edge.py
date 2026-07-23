#!/usr/bin/env python3
"""Live-ROM regression: crates block a champion approaching from below.

The normal wall box is feet-anchored for Zelda-style overhangs.  A 16x16
pushable crate additionally owns its visible north face, so neither walking
nor a double-tap dodge may let a hero enter it through the lower centre.
"""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

ROOM_W, ROOM_H = 20, 17
BGT_FLOOR, BGT_WALL = 1, 2
BGT_PILLAR = 21
BGT_BLOCK, BGT_BLOCK_TR, BGT_BLOCK_BL, BGT_BLOCK_BR = 25, 28, 29, 30


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PL, EN, TM = map(addr, ("_player", "_entities", "_room_tilemap"))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def read16(pb, address):
    return pb.memory[address] | (pb.memory[address + 1] << 8)


def press(pb, button, held=2, released=2):
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def fixture(pb):
    for i in range(32 * 28):
        pb.memory[EN + i] = 0
    for y in range(ROOM_H):
        for x in range(ROOM_W):
            pb.memory[TM + y * ROOM_W + x] = BGT_FLOOR

    # 16x16 crate at pixels 72..87, 48..63.  Its north side is walled so
    # holding UP cannot legitimately solve this fixture by pushing it.
    tx, ty = 9, 6
    pb.memory[TM + ty * ROOM_W + tx] = BGT_BLOCK
    pb.memory[TM + ty * ROOM_W + tx + 1] = BGT_BLOCK_TR
    pb.memory[TM + (ty + 1) * ROOM_W + tx] = BGT_BLOCK_BL
    pb.memory[TM + (ty + 1) * ROOM_W + tx + 1] = BGT_BLOCK_BR
    pb.memory[TM + (ty - 1) * ROOM_W + tx] = BGT_WALL
    pb.memory[TM + (ty - 1) * ROOM_W + tx + 1] = BGT_WALL

    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 64)  # sprite top touches the crate's lower edge
    pb.memory[PL + 14] = 0  # facing/animation byte is irrelevant here
    pb.memory[PL + 15] = 0
    pb.memory[PL + 23] = 0  # move accumulator


def small_obstacle_fixture(pb):
    """A one-tile pillar must not be enterable from its visible lower edge."""
    fixture(pb)
    tx, ty = 9, 6
    for y in (ty, ty + 1):
        for x in (tx, tx + 1):
            pb.memory[TM + y * ROOM_W + x] = BGT_FLOOR
    pb.memory[TM + ty * ROOM_W + tx] = BGT_PILLAR


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(120):
        pb.tick()

    fixture(pb)
    pb.button_press("up")
    for _ in range(40):
        pb.tick()
    pb.button_release("up")
    for _ in range(4):
        pb.tick()
    walked_y = read16(pb, PL + 11)
    assert walked_y >= 64, f"walk entered crate through lower edge: y={walked_y}"

    fixture(pb)
    # This is the actual dash input available to a player, not an emulator
    # state edit.  It must obey the same full-body crate face as walking.
    press(pb, "up")
    press(pb, "up", held=8, released=4)
    dashed_y = read16(pb, PL + 11)
    assert dashed_y >= 64, f"dash entered crate through lower edge: y={dashed_y}"

    small_obstacle_fixture(pb)
    pb.button_press("up")
    for _ in range(40):
        pb.tick()
    pb.button_release("up")
    for _ in range(4):
        pb.tick()
    pillar_y = read16(pb, PL + 11)
    # The 8px pillar ends at y=55; stopping at y=56 lets the sprite touch
    # its edge but never overlaps it.  Before the full-body probe this ran
    # all the way through to y=48.
    assert pillar_y >= 56, f"walk entered small solid tile through lower edge: y={pillar_y}"

    pb.stop(save=False)
    print(f"[block-lower-edge] PASS crate walk y={walked_y}, dash y={dashed_y}; pillar y={pillar_y}")


if __name__ == "__main__":
    main()
