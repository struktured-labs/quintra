#!/usr/bin/env python3
"""ROM contract: Wolfkin's melee is visibly an arc, not a bullet."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not m:
        raise RuntimeError(name)
    return int(m.group(1), 16)


def boot(class_moves=0):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    for _ in range(class_moves):
        pb.button("down")
        for _ in range(8): pb.tick()
    pb.button("a")
    for _ in range(60): pb.tick()
    return pb


def first_player_shot(pb, entities):
    pb.button("a")
    for _ in range(3): pb.tick()
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] == 1 and (pb.memory[e + 1] & 0x10):
            return e
    raise AssertionError("no player projectile")


def main():
    entities = addr("_entities")
    wolf = boot()
    shot = first_player_shot(wolf, entities)
    assert wolf.memory[shot + 12] == 122, "Wolfkin shot is not claw-arc art"
    assert wolf.memory[shot + 16] <= 9, "Wolfkin claw is not short lived"
    wolf.stop(save=False)

    corvin = boot(2)
    shot = first_player_shot(corvin, entities)
    assert corvin.memory[shot + 12] in (28, 29), "ranged champion lost bullet art"
    corvin.stop(save=False)
    print("[melee-visual] PASS Wolfkin arc + ranged bullet identity")


if __name__ == "__main__":
    main()
