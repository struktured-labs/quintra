#!/usr/bin/env python3
"""ROM contract: Sauran's B shield blocks an overlapping hostile body."""
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


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def main():
    player, entities, screen = map(addr, ("_player", "_entities", "_loop_current_screen"))
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    pb.button("down")
    for _ in range(8): pb.tick()
    pb.button("a")
    for _ in range(80): pb.tick()
    assert pb.memory[screen] == 5 and pb.memory[player] == 1, "did not enter as Sauran"

    # Drain any entity work scheduled across the VBlank boundary, then create
    # a real hostile body on the shield's small combat hurtbox.
    for i in range(32 * 28): pb.memory[entities + i] = 0
    pb.tick()
    for i in range(32 * 28): pb.memory[entities + i] = 0
    pb.memory[player + 2] = pb.memory[player + 1]
    pb.memory[player + 4] = 3
    pb.memory[player + 19] = 0  # B cooldown
    pb.memory[player + 15] = 0  # iframes

    # Use the actual B edge, rather than writing the shield timer.
    pb.button_press("b")
    for _ in range(2): pb.tick()
    pb.button_release("b")
    pb.tick()
    assert pb.memory[player + 20] > 50, "Sauran B did not raise a shield"
    assert any(pb.memory[0x8000 + 127 * 16 + i] for i in range(16)), \
        "Sauran shield aura art was not loaded"
    for _ in range(8): pb.tick()
    assert any(
        pb.memory[entities + i * 28] == 4
        and pb.memory[entities + i * 28 + 12] == 127
        for i in range(32)
    ), "Sauran shield did not emit its ward aura"

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
    hp = pb.memory[player + 2]
    for _ in range(8): pb.tick()
    assert pb.memory[player + 2] == hp, "shielded body contact damaged Sauran"

    # When it expires, the same public body-contact path must hurt normally.
    pb.memory[player + 20] = 0
    pb.memory[player + 15] = 0
    for _ in range(8):
        pb.tick()
        if pb.memory[player + 2] < hp:
            break
    assert pb.memory[player + 2] < hp, "unshielded hostile body did not damage Sauran"
    pb.stop(save=False)
    print("[sauran-shield] PASS B shield blocks bodies and expires cleanly")


if __name__ == "__main__":
    main()
