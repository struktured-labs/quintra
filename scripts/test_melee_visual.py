#!/usr/bin/env python3
"""ROM contract: every melee starter is visibly an arc, never a bullet."""
import re
from pathlib import Path

from pyboy import PyBoy
from test_will_max import boot as boot_to_room

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    m = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not m:
        raise RuntimeError(name)
    return int(m.group(1), 16)


def first_player_shot(pb, player, entities, tilemap):
    # This is an attack-art contract, not a seed-dependent collision test.
    # Clear the opening room's entities and floor so a nearby body or scenery
    # tile cannot consume a short-lived physical arc on its spawn frame.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1
    pb.memory[player + 22] = 0
    # Stay one half-heart below max so Wolfkin's full-heart beam does not
    # appear beside the melee arc in this art-identity test.
    hp_max = pb.memory[player + 1]
    if pb.memory[player] == 0:
        pb.memory[player + 2] = max(1, hp_max - 1)
    pb.button_press("a")
    for _ in range(5): pb.tick()
    pb.button_release("a")
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] == 1 and (pb.memory[e + 1] & 0x10):
            return e
    raise AssertionError("no player projectile")


def main():
    player = addr("_player")
    entities = addr("_entities")
    tilemap = addr("_room_tilemap")
    for moves, name, max_ttl in (
        (0, "Wolfkin", 21),  # Claw Sword spin: 3f cock-back + 9 x 2f steps
        (1, "Sauran", 12),
        (4, "Vespine", 12),
    ):
        hero = boot_to_room(moves)
        shot = first_player_shot(hero, player, entities, tilemap)
        tile = hero.memory[shot + 12]
        if name == "Wolfkin":
            assert 144 <= tile <= 159, f"{name} melee is not Claw Sword art ({tile})"
        else:
            assert tile == 122, f"{name} melee is not arc art"
        assert hero.memory[shot + 16] <= max_ttl, f"{name} melee is not short lived"
        hero.stop(save=False)

    corvin = boot_to_room(2)
    shot = first_player_shot(corvin, player, entities, tilemap)
    assert corvin.memory[shot + 12] in (28, 29), "ranged champion lost bullet art"
    corvin.stop(save=False)
    print("[melee-visual] PASS melee arcs + ranged bullet identity")


if __name__ == "__main__":
    main()
