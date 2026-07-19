#!/usr/bin/env python3
"""ROM contract: melee B bursts grant only their short activation ward."""
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


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def boot(class_moves):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    for _ in range(class_moves):
        pb.button("down")
        for _ in range(8): pb.tick()
    pb.button("a")
    for _ in range(80): pb.tick()
    return pb


def assert_guard(class_moves, class_id, name, minimum, player, entities):
    pb = boot(class_moves)
    assert pb.memory[player] == class_id, f"did not enter as {name}"
    for i in range(32 * 28): pb.memory[entities + i] = 0
    pb.memory[player + 15] = 0  # iframes
    pb.memory[player + 19] = 0  # B cooldown
    pb.memory[player + 4] = 4   # enough MP for the public B input
    hp = pb.memory[player + 2]

    pb.button_press("b")
    for _ in range(2): pb.tick()
    pb.button_release("b")
    assert pb.memory[player + 15] >= minimum, (
        f"{name} B activation ward too short: {pb.memory[player + 15]}")
    assert pb.memory[player + 20] == 0, f"{name} became a projectile shield"

    px = pb.memory[player + 9] | (pb.memory[player + 10] << 8)
    py = pb.memory[player + 11] | (pb.memory[player + 12] << 8)
    enemy = entities
    pb.memory[enemy] = 2
    pb.memory[enemy + 1] = 3
    put_fix8(pb, enemy + 2, px + 5)
    put_fix8(pb, enemy + 6, py + 9)
    pb.memory[enemy + 14] = 9
    pb.memory[enemy + 16] = 120
    pb.memory[enemy + 17] = 0
    pb.memory[enemy + 25] = 0x77
    pb.memory[enemy + 26] = 2
    for _ in range(4): pb.tick()
    assert pb.memory[player + 2] == hp, f"{name} B ward did not cover its activation"
    pb.stop(save=False)


def main():
    player, entities = map(addr, ("_player", "_entities"))
    assert_guard(0, 0, "Wolfkin", 20, player, entities)
    assert_guard(4, 4, "Vespine", 14, player, entities)
    print("[melee-guard] PASS Wolfkin/Vespine B activation wards are short and non-shielding")


if __name__ == "__main__":
    main()
