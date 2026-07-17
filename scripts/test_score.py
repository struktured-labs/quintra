#!/usr/bin/env python3
"""ROM contract: high scores saturate instead of wrapping to zero."""

import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


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


def main():
    rs, pl, entities, screen = map(
        addr, ("_run_state", "_player", "_entities", "_loop_current_screen")
    )
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()
    press(pb, "a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[screen] == 5, "did not reach the live room"
    # Slide/fade room entry can still be publishing its spawn in the first
    # visible frames. Let that finish before replacing the entity table;
    # otherwise this test races a transition instead of exercising combat.
    for _ in range(60):
        pb.tick()

    # Use the settled player location. It is necessarily a collision-valid
    # interior point, so projectile movement cannot eat the injected shot on
    # cover before combat_resolve sees the overlap.
    px = pb.memory[pl + 9] | (pb.memory[pl + 10] << 8)
    py = pb.memory[pl + 11] | (pb.memory[pl + 12] << 8)

    for i in range(32 * 28):
        pb.memory[entities + i] = 0

    enemy = entities
    pb.memory[enemy] = 2          # ENT_ENEMY
    pb.memory[enemy + 1] = 3      # EF_ACTIVE | EF_ALIVE
    put16(pb, enemy + 3, px)
    put16(pb, enemy + 7, py)
    pb.memory[enemy + 14] = 1     # one-hit crawler
    pb.memory[enemy + 17] = 0     # generated enemy id 0, worth 10
    pb.memory[enemy + 25] = 0x88

    shot = entities + 28
    pb.memory[shot] = 1           # ENT_PROJECTILE
    pb.memory[shot + 1] = 0x13    # active, alive, player-owned
    put16(pb, shot + 3, px)
    put16(pb, shot + 7, py)
    pb.memory[shot + 14] = 1      # one pierce
    pb.memory[shot + 16] = 30     # live long enough to resolve
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 26] = 20

    pb.memory[rs + 14] = 0xFA     # score = 65,530
    pb.memory[rs + 15] = 0xFF
    pb.memory[pl + 15] = 60       # avoid unrelated contact damage
    for _ in range(4):
        pb.tick()

    score = pb.memory[rs + 14] | (pb.memory[rs + 15] << 8)
    assert score == 0xFFFF, f"high score wrapped instead of saturating: {score}"
    assert pb.memory[rs + 16] == 1, "injected enemy did not die through combat"
    pb.stop(save=False)
    print("[score] PASS generated enemy award saturates at 65535")


if __name__ == "__main__":
    main()
