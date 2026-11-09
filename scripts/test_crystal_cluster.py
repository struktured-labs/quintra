#!/usr/bin/env python3
"""The crystal tile is a rooted cluster and still shatters when shot."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SOURCE = (ROOT / "src/render/sprites_gen.c").read_text()
PENDANT = (
    "0x18, 0x18, 0x24, 0x3C, 0x42, 0x7E, 0x81, 0xFF, "
    "0x42, 0x7E, 0x24, 0x3C, 0x3C, 0x7E, 0x00, 0xFF"
)
BGT_CRYSTAL = 22
BGT_FLOOR = 1
ENT_PROJECTILE = 1
SCREEN_ROOM = 5


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


PL, EN, TM, SCREEN = map(addr, (
    "_player", "_entities", "_room_tilemap", "_loop_current_screen",
))


def tick(pb, count):
    for _ in range(count):
        pb.tick()


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def main():
    match = re.search(r"bgt_crystal\[16\] = \{([^}]+)\}", SOURCE)
    assert match, "crystal tile bytes disappeared"
    body = " ".join(match.group(1).split())
    assert body != PENDANT, "crystal art is still the pendant silhouette"
    assert "0xFF, 0xFF" in body, "crystal cluster lost its wide base"

    pb = PyBoy(str(ROM), window="null", cgb=True)
    try:
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
        cell = TM + 8 * 20 + 8
        pb.memory[cell] = BGT_CRYSTAL
        shot = EN
        pb.memory[shot] = ENT_PROJECTILE
        pb.memory[shot + 1] = 0x11
        put16(pb, shot + 3, 64)
        put16(pb, shot + 7, 64)
        pb.memory[shot + 16] = 8
        for offset in range(17, 25):
            pb.memory[shot + offset] = 0
        tick(pb, 6)
        assert pb.memory[cell] == BGT_FLOOR, (
            f"shot did not shatter the crystal, tile={pb.memory[cell]}")
    finally:
        pb.stop(save=False)
    print("[crystal-cluster] PASS rooted crystal art still shatters")


if __name__ == "__main__":
    main()
