#!/usr/bin/env python3
"""Live-ROM contract: Corvin's target-mark B refuses an empty room."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


def main():
    player, entities = map(addr, ("_player", "_entities"))
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    for _ in range(2):
        pb.button("down")
        pb.tick(8)
    pb.button("a")
    pb.tick(100)
    assert pb.memory[player] == 2, "did not enter as Corvin"

    # Fill the fixed entity table with inert resident pickups. Raven Mark has
    # no shield or activation ward, so no valid enemy means no resource spend.
    for slot in range(32):
        entity = entities + slot * 28
        for i in range(28):
            pb.memory[entity + i] = 0
        pb.memory[entity] = 3
        pb.memory[entity + 1] = 3
        pb.memory[entity + 14] = 1
        pb.memory[entity + 17] = 8  # PICKUP_MERCHANT: inert visual resident
        pb.memory[entity + 25] = 0x66
    pb.memory[player + 4] = pb.memory[player + 3]
    mp_before = pb.memory[player + 4]
    pb.memory[player + 19] = 0
    pb.button_press("b")
    pb.tick(4)
    pb.button_release("b")
    pb.tick(2)
    remaining = sum(
        1 for slot in range(32)
        if pb.memory[entities + slot * 28 + 1] & 1
    )
    projectiles = sum(
        1 for slot in range(32)
        if pb.memory[entities + slot * 28] == 1
    )
    assert pb.memory[player + 4] == mp_before, (
        "enemy-free table charged Corvin MP without marking a foe "
        f"(mp={pb.memory[player + 4]} active={remaining} "
        f"projectiles={projectiles} cooldown={pb.memory[player + 19]})"
    )
    assert pb.memory[player + 19] == 0, \
        "full entity table started Corvin's cooldown without an ability"
    pb.stop(save=False)
    print("[corvin-capacity] PASS enemy-free table refuses empty Raven Mark")


if __name__ == "__main__":
    main()
