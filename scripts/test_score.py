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


def put_fix8(pb, address, pixels):
    value = pixels << 8
    for offset in range(4):
        pb.memory[address + offset] = (value >> (offset * 8)) & 0xFF


def main():
    rs, pl, entities, tilemap = map(
        addr, ("_run_state", "_player", "_entities", "_room_tilemap")
    )
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()
    press(pb, "a")
    for _ in range(60):
        pb.tick()

    # Pick an interior walkable tile so projectile_update cannot consume the
    # injected shot against cover before combat resolves it.
    walkable = {1, 3, 7, 19, 20, 23, 31, 33, 34, *range(9, 19)}
    target = next(
        (x, y)
        for y in range(3, 14)
        for x in range(3, 17)
        if pb.memory[tilemap + y * 20 + x] in walkable
    )
    px, py = target[0] * 8, target[1] * 8

    for i in range(32 * 28):
        pb.memory[entities + i] = 0

    enemy = entities
    pb.memory[enemy] = 2          # ENT_ENEMY
    pb.memory[enemy + 1] = 3      # EF_ACTIVE | EF_ALIVE
    put_fix8(pb, enemy + 2, px)
    put_fix8(pb, enemy + 6, py)
    pb.memory[enemy + 14] = 1     # one-hit crawler
    pb.memory[enemy + 17] = 0     # generated enemy id 0, worth 10
    pb.memory[enemy + 25] = 0x88

    shot = entities + 28
    pb.memory[shot] = 1           # ENT_PROJECTILE
    pb.memory[shot + 1] = 0x13    # active, alive, player-owned
    put_fix8(pb, shot + 2, px)
    put_fix8(pb, shot + 6, py)
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
