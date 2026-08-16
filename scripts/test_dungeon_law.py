#!/usr/bin/env python3
"""Live-ROM contract: one seeded mutable Law reshapes multiple dungeon cells."""

import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import dungeon_maze_neighbor, dungeon_size

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, EN, TM, EXT, SCREEN, WORLD_W, WORLD_H, SEALED, LOCKED = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_world_extension",
    "_loop_current_screen", "_room_world_width", "_room_world_height",
    "_room_combat_sealed", "_room_puzzle_locked"))

RS_ROOM, RS_SEED, RS_STAGE, RS_LAW = 1, 2, 11, 36
PL_X, PL_Y, PL_IFRAMES = 9, 11, 15
BGT_FLOOR2, BGT_PILLAR, BGT_CRYSTAL = 19, 21, 22
BGT_SPIKES, BGT_SWITCH = 31, 33


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def press(pb, button, held=4, released=5):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    press(pb, "start")
    pb.tick(30)
    press(pb, "a")
    pb.tick(90)
    assert pb.memory[SCREEN] == 5
    return pb


def row(pb):
    # The Law owns the far-east apron (x=21..27), safely beyond each stage's
    # western 20x17 identity silhouette. Extension rows are eleven tiles wide.
    return [pb.memory[EXT + 5 * 11 + (x - 20)] & 0x7F
            for x in range(21, 28)]


def expected_band(material, gap):
    return [BGT_FLOOR2 if x in (gap, gap + 1) else material
            for x in range(21, 28)]


def clear_hostiles(pb):
    for i in range(32):
        e = EN + i * 28
        if pb.memory[e] == 2:
            pb.memory[e] = pb.memory[e + 1] = 0


def main():
    pb = boot()
    law = pb.memory[RS + RS_LAW]
    assert law & 0x40, "opening dungeon has no initialized global Law"
    assert not law & 0x80, "new dungeon did not begin in readable WAX state"
    kind = law & 3
    assert kind < 3
    material = (BGT_CRYSTAL, BGT_SPIKES, BGT_PILLAR)[kind]
    assert row(pb) == expected_band(material, 22), "WAX band was not projected"
    assert pb.memory[TM + 8 * 20 + 3] == BGT_SWITCH, "district altar missing"

    # Feet onto the row-opening altar, then use contextual A. The switch
    # rewrites both architecture phrases over successive VBlanks.
    put16(pb, PL + PL_X, 16)
    put16(pb, PL + PL_Y, 52)
    pb.memory[PL + PL_IFRAMES] = 120
    press(pb, "a", held=24, released=30)
    law = pb.memory[RS + RS_LAW]
    assert law & 0x80, "altar did not flip the persistent WANE bit"
    assert row(pb) == expected_band(material, 25), "current room did not reshape"

    # The switch persists immediately, not only at the next doorway.
    pb.memory[0x0000] = 0x0A
    pb.memory[0x4000] = 0
    assert pb.memory[0xA005 + RS_LAW] == law, "Law was not suspend-saved"
    pb.memory[0x0000] = 0

    # Cross a real generated edge. The destination is regenerated from its
    # own room seed but must project the same global WANE opening.
    seed = sum(pb.memory[RS + RS_SEED + i] << (8 * i) for i in range(4))
    stage = pb.memory[RS + RS_STAGE]
    size = dungeon_size(stage)
    target = direction = None
    for d in range(4):
        neighbor = dungeon_maze_neighbor(0, size, d, seed, stage)
        if neighbor is not None:
            direction, target = d, neighbor
            break
    assert target is not None
    # This test owns the ambient Law contract, not mission-role mechanics.
    # If the generated first edge lands on one of the seven objectives,
    # vacate that role in the external fixture so the destination is an
    # ordinary court where the Law is supposed to project.
    for offset in range(39, 46):
        if pb.memory[RS + offset] == target:
            pb.memory[RS + offset] = 0
    clear_hostiles(pb)
    pb.memory[SEALED] = pb.memory[LOCKED] = 0
    edge = {
        0: (72, 0),
        1: (pb.memory[WORLD_W] - 16, 60),
        2: (72, pb.memory[WORLD_H] - 16),
        3: (0, 60),
    }[direction]
    put16(pb, PL + PL_X, edge[0])
    put16(pb, PL + PL_Y, edge[1])
    for _ in range(180):
        pb.memory[PL + PL_IFRAMES] = 120
        pb.tick()
        if pb.memory[RS + RS_ROOM] == target:
            break
    assert pb.memory[RS + RS_ROOM] == target, "could not cross generated edge"
    pb.tick(40)
    assert pb.memory[RS + RS_LAW] == law, "Law reset at a room boundary"
    assert row(pb) == expected_band(material, 25), (
        "destination did not inherit the global WANE architecture")
    pb.stop(save=False)
    print("[dungeon-law] PASS seeded WAX/WANE state reshapes multiple rooms")


if __name__ == "__main__":
    main()
