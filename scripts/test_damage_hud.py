#!/usr/bin/env python3
"""ROM contract: ordinary hostile damage updates the visible heart row now."""
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


PL, EN, SCREEN = map(addr, ("_player", "_entities", "_loop_current_screen"))


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()
    press(pb, "a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[SCREEN] == 5

    # Force a known four-heart state and let the public HUD redraw path settle.
    pb.memory[PL + 1] = 8
    pb.memory[PL + 2] = 8
    pb.memory[PL + 6] = 0
    pb.memory[PL + 15] = 0
    for i in range(32 * 28):
        pb.memory[EN + i] = 0
    for _ in range(2):
        pb.tick()
    pb.memory[0xFF4F] = 0
    before = bytes(pb.memory[0x9C00:0x9C08])

    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    projectile = EN
    for i in range(28):
        pb.memory[projectile + i] = 0
    pb.memory[projectile] = 1
    pb.memory[projectile + 1] = 3
    put_fix8(pb, projectile + 2, px + 5)
    put_fix8(pb, projectile + 6, py + 9)
    pb.memory[projectile + 14] = 1
    pb.memory[projectile + 16] = 20
    pb.memory[projectile + 25] = 0x77
    pb.memory[projectile + 26] = 1

    for _ in range(60):
        pb.tick()
        if pb.memory[PL + 2] == 7:
            break
    assert pb.memory[PL + 2] == 7, (
        f"hostile projectile did not damage player: hp={pb.memory[PL + 2]} "
        f"iframes={pb.memory[PL + 15]} entity="
        f"{pb.memory[projectile]}/{pb.memory[projectile + 1]}"
    )
    pb.memory[0xFF4F] = 0
    after = bytes(pb.memory[0x9C00:0x9C08])
    assert before != after, f"heart row stayed stale after damage: {before.hex()}"
    assert after[3] in (5, 6) and after[:3] == bytes([4, 4, 4]), \
        f"damage did not visibly reduce the fourth heart: {after.hex()}"
    pb.stop(save=False)
    print("[damage-hud] OK: combat HP loss redraws hearts in the same hit")


if __name__ == "__main__":
    main()
