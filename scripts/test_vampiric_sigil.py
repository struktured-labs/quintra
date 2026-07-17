#!/usr/bin/env python3
"""Live-ROM contract: Vampiric Sigil heals exactly on each fifth real kill."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PL, EN, RS, SCREEN = map(addr, (
    "_player", "_entities", "_run_state", "_loop_current_screen"))
ENTITY_SIZE = 28
ITEM_VAMPIRIC_SIGIL = 29


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def put16(pb, address, pixels):
    pb.memory[address] = pixels & 0xFF
    pb.memory[address + 1] = (pixels >> 8) & 0xFF


def clear_entities(pb):
    for i in range(32 * ENTITY_SIZE):
        pb.memory[EN + i] = 0


def lethal_crawler(pb):
    """Resolve one normal player projectile kill through the cartridge."""
    clear_entities(pb)
    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    enemy, shot = EN, EN + ENTITY_SIZE
    pb.memory[enemy] = 2             # ENT_ENEMY
    pb.memory[enemy + 1] = 3         # active + alive
    put16(pb, enemy + 3, px)
    put16(pb, enemy + 7, py)
    pb.memory[enemy + 14] = 1
    pb.memory[enemy + 17] = 0        # Crawler; ordinary score/drop path
    pb.memory[enemy + 25] = 0x88
    pb.memory[shot] = 1              # ENT_PROJECTILE
    pb.memory[shot + 1] = 0x13       # active, alive, player-owned
    put16(pb, shot + 3, px)
    put16(pb, shot + 7, py)
    pb.memory[shot + 14] = 1
    pb.memory[shot + 16] = 30
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 26] = 20
    for _ in range(8):
        pb.tick()
        if pb.memory[enemy] == 0:
            return
    raise AssertionError("injected player projectile did not kill its crawler")


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()
    press(pb, "a")
    for _ in range(140):
        pb.tick()
    assert pb.memory[SCREEN] == 5, "did not reach a live room"

    # This test isolates the on-kill behavior. The town contract buys the
    # real shelf; here the Sigil is equipped so every kill goes through the
    # ordinary combat path without relying on a particular town arrival.
    pb.memory[PL + 1], pb.memory[PL + 2] = 10, 4
    for i in range(16):
        pb.memory[PL + 24 + i] = 0xFF
    pb.memory[PL + 24] = ITEM_VAMPIRIC_SIGIL
    pb.memory[RS + 16] = 4
    pb.memory[PL + 15] = 60  # no incidental body contact in the fixture
    lethal_crawler(pb)
    assert pb.memory[RS + 16] == 5, "fifth kill did not increment normally"
    assert pb.memory[PL + 2] == 5, "Vampiric Sigil did not heal on fifth kill"

    # A following kill must not heal again. This catches accidental
    # per-kill sustain that would turn the item into an immortal build.
    pb.memory[PL + 2] = 4
    pb.memory[PL + 15] = 60
    lethal_crawler(pb)
    assert pb.memory[RS + 16] == 6, "sixth kill did not increment normally"
    assert pb.memory[PL + 2] == 4, "Vampiric Sigil healed before the next fifth kill"
    pb.stop(save=False)
    print("[vamp-sigil] PASS fifth-kill half-heart sustain, no per-kill healing")


if __name__ == "__main__":
    main()
