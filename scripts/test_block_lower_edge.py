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
BGT_SPIKES = 31
BGT_CRYSTAL, BGT_RUBBLE = 22, 23
BGT_PILLAR = 21
BGT_BLOCK, BGT_BLOCK_TR, BGT_BLOCK_BL, BGT_BLOCK_BR = 25, 28, 29, 30


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PL, EN, TM, EXT, BOTTOM, WORLD_W, WORLD_H, SCREEN = map(addr, (
    "_player", "_entities", "_room_tilemap", "_room_world_extension",
    "_room_world_bottom", "_room_world_width", "_room_world_height",
    "_loop_current_screen",
))


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


def center_obstacle_fixture(pb):
    """A one-tile pillar centred between both corner probes stays solid."""
    fixture(pb)
    tx, ty = 10, 6
    for y in (ty, ty + 1):
        for x in range(tx - 1, tx + 2):
            pb.memory[TM + y * ROOM_W + x] = BGT_FLOOR
    pb.memory[TM + ty * ROOM_W + tx] = BGT_PILLAR
    # Collision edges land in columns 9 and 11; only the new centre sample
    # sees the pillar in column 10.
    put16(pb, PL + 9, 77)
    put16(pb, PL + 11, 64)
    pb.memory[PL + 23] = 0


def center_overlap_fixture(pb):
    """An impossible embedded fixture cannot be used to tunnel either way."""
    fixture(pb)
    tx, ty = 10, 8
    for y in (ty, ty + 1):
        for x in range(tx - 1, tx + 3):
            pb.memory[TM + y * ROOM_W + x] = BGT_FLOOR
    pb.memory[TM + ty * ROOM_W + tx] = BGT_PILLAR
    # Centre sample begins inside the pillar. Real knockback now rejects this
    # position; this synthetic state proves input cannot exploit it.
    put16(pb, PL + 9, 77)
    put16(pb, PL + 11, 56)
    pb.memory[PL + 23] = 0


def side_body_fixture(pb):
    """Horizontal movement must respect a pillar above the feet box."""
    fixture(pb)
    for y in range(ROOM_H):
        for x in range(ROOM_W):
            pb.memory[TM + y * ROOM_W + x] = BGT_FLOOR
    pb.memory[TM + 6 * ROOM_W + 10] = BGT_PILLAR
    # The pillar occupies x=80..87/y=48..55. The champion's feet start below
    # it at y=56, but the visible upper body still shares y=48..55. The old
    # horizontal-only feet check walked straight through its side.
    put16(pb, PL + 9, 64)
    put16(pb, PL + 11, 48)
    pb.memory[PL + 23] = 0


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

    center_obstacle_fixture(pb)
    pb.button_press("up")
    for _ in range(40):
        pb.tick()
    pb.button_release("up")
    for _ in range(4):
        pb.tick()
    center_y = read16(pb, PL + 11)
    assert center_y >= 56, (
        f"walk tunnelled through centre of one-tile pillar: y={center_y}"
    )

    center_overlap_fixture(pb)
    pb.button_press("right")
    for _ in range(60):
        pb.tick()
    pb.button_release("right")
    for _ in range(4):
        pb.tick()
    tunnel_x = read16(pb, PL + 9)
    assert tunnel_x == 77, (
        f"overlap recovery tunnelled deeper through pillar: x={tunnel_x}"
    )

    center_overlap_fixture(pb)
    pb.button_press("left")
    for _ in range(30):
        pb.tick()
    pb.button_release("left")
    for _ in range(4):
        pb.tick()
    escaped_x = read16(pb, PL + 9)
    assert escaped_x == 77, (
        f"embedded fixture escaped through opposite pillar face: x={escaped_x}"
    )

    side_body_fixture(pb)
    pb.button_press("right")
    for _ in range(40):
        pb.tick()
    pb.button_release("right")
    for _ in range(4):
        pb.tick()
    side_x = read16(pb, PL + 9)
    assert side_x <= 66, (
        f"horizontal walk buried upper body in pillar: x={side_x}"
    )

    # The same overlap exception must never turn a real field boundary into
    # an infinite escape lane. Stand exactly on each legal far threshold with
    # a non-door wall under the collision probes, then hold outward.
    assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)
    for ty in (5, 6, 7):
        for tx in (29, 30):
            pb.memory[EXT + ty * 11 + tx - 20] = BGT_WALL
    put16(pb, PL + 9, 232)
    put16(pb, PL + 11, 40)
    pb.button_press("right")
    for _ in range(80):
        pb.tick()
    pb.button_release("right")
    pb.tick(4)
    east_x = read16(pb, PL + 9)
    assert east_x == 232, f"walk escaped east world bound: x={east_x}"

    for tx in (5, 6, 7):
        pb.memory[BOTTOM + 13 * 31 + tx] = BGT_WALL
    put16(pb, PL + 9, 40)
    put16(pb, PL + 11, 232)
    pb.button_press("down")
    for _ in range(80):
        pb.tick()
    pb.button_release("down")
    pb.tick(4)
    south_y = read16(pb, PL + 11)
    assert south_y == 232, f"walk escaped south world bound: y={south_y}"

    # Scrolling courts store their east side outside the legacy 20x17
    # projection. A far-field spike is still a real hazard.
    pb.memory[EXT + 8 * 11 + 2] = BGT_SPIKES  # world tile (22, 8)
    put16(pb, PL + 9, 22 * 8 - 8)
    put16(pb, PL + 11, 8 * 8 - 12)
    pb.memory[PL + 2] = 8
    pb.memory[PL + 15] = 0
    for _ in range(4):
        pb.tick()
    far_spike_hp = pb.memory[PL + 2]
    assert far_spike_hp == 7, \
        f"far-field dungeon spike was harmless: hp={far_spike_hp}"

    # Far-field rubble and crystals share their compact counterparts'
    # interaction contract instead of becoming decorative/invulnerable past
    # column 19.
    pb.memory[EXT + 8 * 11 + 3] = BGT_RUBBLE  # world tile (23, 8)
    put16(pb, PL + 9, 23 * 8 - 8)
    put16(pb, PL + 11, 8 * 8 - 12)
    pb.memory[PL + 15] = 120
    for _ in range(4):
        pb.tick()
    assert pb.memory[EXT + 8 * 11 + 3] == BGT_FLOOR, \
        "far-field rubble did not break under the champion"

    for i in range(32 * 28):
        pb.memory[EN + i] = 0
    pb.memory[EXT + 8 * 11 + 4] = BGT_CRYSTAL  # world tile (24, 8)
    shot = EN
    pb.memory[shot] = 1
    pb.memory[shot + 1] = 0x13
    put16(pb, shot + 3, 24 * 8 - 4)
    put16(pb, shot + 7, 8 * 8 - 4)
    pb.memory[shot + 14] = 1
    pb.memory[shot + 16] = 30
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 26] = 1
    for _ in range(4):
        pb.tick()
    assert pb.memory[EXT + 8 * 11 + 4] == BGT_FLOOR, \
        "far-field crystal ignored player fire"

    # A lethal floor hit uses the same 50-frame fall beat as combat instead
    # of hard-cutting directly to GAME OVER.
    for i in range(32 * 28):
        pb.memory[EN + i] = 0
    pb.memory[EXT + 8 * 11 + 2] = BGT_SPIKES
    put16(pb, PL + 9, 22 * 8 - 8)
    put16(pb, PL + 11, 8 * 8 - 12)
    pb.memory[PL + 2] = 1
    pb.memory[PL + 15] = 0
    for _ in range(4):
        pb.tick()
    assert pb.memory[PL + 2] == 0 and pb.memory[SCREEN] == 5, \
        "lethal hazard skipped its in-room death animation"
    for _ in range(70):
        pb.tick()
        if pb.memory[SCREEN] == 11:
            break
    assert pb.memory[SCREEN] == 11, \
        "lethal hazard death beat never reached GAME OVER"

    pb.stop(save=False)
    print(
        f"[block-lower-edge] PASS crate walk y={walked_y}, dash y={dashed_y}; "
        f"pillar y={pillar_y}, centre pillar y={center_y}, "
        f"overlap hold={tunnel_x}, escape x={escaped_x}, side x={side_x}; "
        f"world bounds east={east_x} south={south_y}; "
        f"far spike hp={far_spike_hp}; rubble/crystal active"
    )


if __name__ == "__main__":
    main()
