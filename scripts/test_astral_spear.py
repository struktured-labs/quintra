#!/usr/bin/env python3
"""ROM contract: Astral Spear is a collectable, distinct long-reach weapon."""
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


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def first_player_shot(pb, entities):
    for i in range(32):
        entity = entities + i * 28
        if pb.memory[entity] == 1 and (pb.memory[entity + 1] & 0x10):
            return entity
    raise AssertionError("no player projectile")


def main():
    player, entities, screen = map(addr, ("_player", "_entities", "_loop_current_screen"))
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[screen] == 5, "did not enter a live room"

    # Feed the real pickup collision/swap path rather than assigning the
    # weapon field. Generated table index 21 is Astral Spear (after Flail).
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    pb.tick()
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    px = pb.memory[player + 9] | (pb.memory[player + 10] << 8)
    py = pb.memory[player + 11] | (pb.memory[player + 12] << 8)
    orb = entities
    pb.memory[orb] = 3             # ENT_PICKUP
    pb.memory[orb + 1] = 3         # EF_ACTIVE | EF_ALIVE
    put16(pb, orb + 3, px + 4)
    put16(pb, orb + 7, py + 8)
    pb.memory[orb + 12] = 35       # weapon-orb art
    pb.memory[orb + 13] = 4
    pb.memory[orb + 17] = 5        # PICKUP_WEAPON
    pb.memory[orb + 18] = 21       # Astral Spear generated items[] index
    pb.memory[orb + 25] = 0x66
    for _ in range(3):
        pb.tick()
    assert pb.memory[player + 21] == 21, "Astral Spear orb did not swap A weapon"

    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    pb.memory[player + 22] = 0
    pb.button("a")
    for _ in range(3):
        pb.tick()
    shot = first_player_shot(pb, entities)
    # Four pixels/tick for 22 ticks: a deliberate long, single-target lane
    # tool. Its spear tile must not regress to generic bullet or claw art.
    assert pb.memory[shot + 12] == 123, "Astral Spear lost its pointed sprite"
    assert 19 <= pb.memory[shot + 16] <= 22, "Astral Spear reach geometry drifted"
    assert pb.memory[shot + 14] == 1, "Astral Spear unexpectedly cleaves crowds"
    assert pb.memory[shot + 26] == pb.memory[player + 5] + 4, "Astral Spear damage drifted"
    assert pb.memory[shot + 19] == 1, "Astral Spear shimmered like a bullet"
    pb.stop(save=False)
    print("[astral-spear] PASS weapon swap + long precise physical thrust")


if __name__ == "__main__":
    main()
