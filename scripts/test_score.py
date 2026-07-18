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
    rs, pl, entities, tilemap, screen, input_keys, input_prev, input_pressed, input_released = map(
        addr, (
            "_run_state", "_player", "_entities", "_room_tilemap", "_loop_current_screen",
            "_input_keys", "_input_prev", "_input_pressed", "_input_released",
        )
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
    # PyBoy can surface the new room one frame before its enter callback has
    # finished publishing the generated entity table. Cross that boundary
    # before installing a synthetic fixture.
    pb.tick()
    assert pb.memory[screen] == 5, "room changed while settling score fixture"

    # Use a real open floor cell. The hero's visual head may overhang a wall
    # while its feet box remains valid, so player.x/y is not necessarily a
    # valid projectile origin for this synthetic collision fixture.
    px = py = None
    for ty in range(2, 15):
        for tx in range(2, 18):
            if all(pb.memory[tilemap + (ty + dy) * 20 + tx + dx] == 1
                   for dy in (0, 1) for dx in (0, 1)):
                px, py = tx * 8 + 1, ty * 8 + 1
                break
        if px is not None:
            break
    assert px is not None, "no clear 2x2 floor cell for score collision fixture"

    for i in range(32 * 28):
        pb.memory[entities + i] = 0

    # Keep the live controller idle while this synthetic collision resolves.
    # The cooldown also prevents a physical input poll from adding a second
    # shot to this two-entity fixture.
    for address in (input_keys, input_prev, input_pressed, input_released):
        pb.memory[address] = 0
    pb.memory[pl + 22] = 60       # player.fire_cooldown

    enemy = entities
    pb.memory[enemy] = 2          # ENT_ENEMY
    pb.memory[enemy + 1] = 3      # EF_ACTIVE | EF_ALIVE
    put16(pb, enemy + 3, px)
    put16(pb, enemy + 7, py)
    pb.memory[enemy + 14] = 1     # one-hit crawler
    pb.memory[enemy + 16] = 0xFF  # keep the synthetic Walker on the shot
    pb.memory[enemy + 17] = 0     # generated enemy id 0, worth 10
    pb.memory[enemy + 25] = 0x88

    shot = entities + 28
    pb.memory[shot] = 1           # ENT_PROJECTILE
    pb.memory[shot + 1] = 0x13    # active, alive, player-owned
    put16(pb, shot + 3, px)
    put16(pb, shot + 7, py)
    pb.memory[shot + 10] = 0    # synthetic collision: no inherited velocity
    pb.memory[shot + 11] = 0
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
    assert score == 0xFFFF, (
        f"high score wrapped instead of saturating: {score}; "
        f"enemy type={pb.memory[enemy]} flags={pb.memory[enemy + 1]} "
        f"hp={pb.memory[enemy + 14]} pos={pb.memory[enemy + 3]},{pb.memory[enemy + 7]} "
        f"box={pb.memory[enemy + 25]:02x} shot type={pb.memory[shot]} "
        f"flags={pb.memory[shot + 1]} pos={pb.memory[shot + 3]},{pb.memory[shot + 7]} "
        f"box={pb.memory[shot + 25]:02x}")
    assert pb.memory[rs + 16] == 1, "injected enemy did not die through combat"
    pb.stop(save=False)
    print("[score] PASS generated enemy award saturates at 65535")


if __name__ == "__main__":
    main()
