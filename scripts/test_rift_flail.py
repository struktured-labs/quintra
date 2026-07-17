#!/usr/bin/env python3
"""ROM contract: the Rift Flail is a real, collectable melee weapon swap."""
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
    pb.button("a")  # Wolfkin: proves a non-starter can replace true melee.
    for _ in range(80):
        pb.tick()
    assert pb.memory[screen] == 5, "did not enter a live room"

    # Empty the table on a VBlank boundary, then feed a real PICKUP_WEAPON
    # entity through normal collision/swap code. No player stat or weapon
    # field is written directly by the test.
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
    pb.memory[orb + 12] = 35       # normal weapon-orb art
    pb.memory[orb + 13] = 4
    pb.memory[orb + 17] = 5        # PICKUP_WEAPON
    pb.memory[orb + 18] = 20       # Rift Flail's generated items[] index
    pb.memory[orb + 25] = 0x66     # normal walk-over pickup hitbox
    for _ in range(3):
        pb.tick()
    assert pb.memory[player + 21] == 20, "Rift Flail orb did not swap A weapon"

    # The shared swing art is intentional, but Flail physics must differ from
    # every starter: 17-frame reach and three-target pierce.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    pb.memory[player + 22] = 0      # fire cooldown
    pb.button("a")
    for _ in range(3):
        pb.tick()
    shot = first_player_shot(pb, entities)
    assert pb.memory[shot + 12] == 122, "Rift Flail lost physical arc art"
    assert 14 <= pb.memory[shot + 16] <= 17, "Rift Flail range/cadence geometry drifted"
    assert pb.memory[shot + 14] == 3, "Rift Flail did not pierce three targets"
    assert pb.memory[shot + 26] == pb.memory[player + 5] + 3, "Rift Flail damage drifted"
    assert pb.memory[shot + 19] == 1, "Rift Flail shimmered like a bullet"
    pb.stop(save=False)
    print("[rift-flail] PASS real weapon swap + physical sweep stats")


if __name__ == "__main__":
    main()
