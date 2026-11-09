#!/usr/bin/env python3
"""RIFTWILD stays on the overworld and is not erased by a dungeon timer."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SCREEN_ROOM = 5
BGT_DOOR = 3
RIFTWILD = (76, 77, 78, 79, 80, 77, 81, 82)


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


(RS, PL, EN, TM, SCREEN, TICKS, SEALED, LARGE, WORLD_W, WORLD_H,
 ORIGIN_X, ORIGIN_Y) = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_loop_current_screen", "_room_district_label_ticks",
    "_room_combat_sealed", "_procgen_current_room_is_large",
    "_room_world_width", "_room_world_height",
    "_room_bg_origin_x", "_room_bg_origin_y",
))


def tick(pb, count):
    for _ in range(count):
        pb.tick()


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    tick(pb, 240)
    pb.button("start")
    tick(pb, 30)
    pb.button("a")
    for _ in range(240):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            for slot in range(32):
                entity = EN + slot * 28
                if pb.memory[entity] == 2:
                    pb.memory[entity] = pb.memory[entity + 1] = 0
            pb.memory[PL + 2] = 12
            pb.memory[PL + 15] = 200
    assert pb.memory[SCREEN] == SCREEN_ROOM
    return pb


def row_at(pb, x, y, width):
    ox, oy = pb.memory[ORIGIN_X], pb.memory[ORIGIN_Y]
    return tuple(
        pb.memory[0, 0x9800 + ((oy + y) & 31) * 32 + ((ox + x + i) & 31)]
        for i in range(width))


def main():
    pb = boot()
    try:
        # A live dungeon countdown must not survive the step into Rift Wild.
        pb.memory[TICKS] = 100
        pb.memory[RS + 17] = 1          # world_mode
        pb.memory[RS + 18] = 0          # world_screen
        pb.memory[SEALED] = 0
        pb.memory[LARGE] = 0
        pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
        for tx, ty in ((19, 8), (19, 9)):
            pb.memory[TM + ty * 20 + tx] = BGT_DOOR
        put16(pb, PL + 9, 144)
        put16(pb, PL + 11, 60)
        for _ in range(180):
            pb.memory[PL + 15] = 200
            pb.tick()
            if row_at(pb, 6, 1, 8) == RIFTWILD and pb.memory[TICKS] == 0:
                break
        assert pb.memory[RS + 17] == 1
        assert pb.memory[TICKS] == 0, (
            f"dungeon timer leaked onto the overworld: {pb.memory[TICKS]}")
        assert row_at(pb, 6, 1, 8) == RIFTWILD, row_at(pb, 6, 1, 8)
        for _ in range(130):
            pb.memory[PL + 15] = 200
            pb.tick()
        assert row_at(pb, 6, 1, 8) == RIFTWILD, "RIFTWILD faded after entry"
        assert pb.memory[TICKS] == 0
    finally:
        pb.stop(save=False)
    print("[riftwild-label] PASS RIFTWILD stays and drops the dungeon timer")


if __name__ == "__main__":
    main()
