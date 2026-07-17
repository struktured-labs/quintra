#!/usr/bin/env python3
"""ROM contract: every melee starter is visibly an arc, never a bullet."""
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
    for moves, name, max_ttl in (
        (0, "Wolfkin", 9),
        (1, "Sauran", 12),
        (4, "Vespine", 12),
    ):
        hero = boot(moves)
        shot = first_player_shot(hero, entities)
        assert hero.memory[shot + 12] == 122, f"{name} melee is not arc art"
        assert hero.memory[shot + 16] <= max_ttl, f"{name} melee is not short lived"
        hero.stop(save=False)

    corvin = boot(2)
    shot = first_player_shot(corvin, entities)
    assert corvin.memory[shot + 12] in (28, 29), "ranged champion lost bullet art"
    corvin.stop(save=False)
    print("[melee-visual] PASS melee arcs + ranged bullet identity")


if __name__ == "__main__":
    main()
