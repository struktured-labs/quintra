#!/usr/bin/env python3
"""ROM contract: the seed-14 final-stage Rift Sigil has a body-valid path."""
from pathlib import Path

from pyboy import PyBoy

from test_boss_identity import EN, PL, RS, TM, put16


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
ENTITY_SIZE = 28
PICKUP_RIFT_SIGIL = 11
ROOM_W, ROOM_H = 20, 17
WALKABLE = {1, 3, 7, *range(9, 19), 19, 20, 23, 31, 33, 34}


def put32(pb, address, value):
    for i in range(4):
        pb.memory[address + i] = (value >> (8 * i)) & 0xFF


def body_open(pb, x, y):
    return (0 <= x < ROOM_W - 1 and 0 <= y < ROOM_H - 1
            and all(pb.memory[TM + yy * ROOM_W + xx] in WALKABLE
                    for xx, yy in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1))))


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()

    # Replay the real room-49 -> room-50 transaction of the seed that found
    # the controller stall. Previous eight Sigils exist; only stage eight's
    # bit is absent, so the room must publish its final mandatory fixture.
    put32(pb, RS + 2, 2064128116)
    pb.memory[RS + 1] = 49
    pb.memory[RS + 11] = 8
    pb.memory[RS + 23] = 0xFF
    pb.memory[RS + 24] = 0x00
    pb.memory[RS + 6] = 0xFF
    for i in range(32):
        entity = EN + i * ENTITY_SIZE
        pb.memory[entity] = pb.memory[entity + 1] = 0
    pb.memory[TM + 16 * ROOM_W + 9] = pb.memory[TM + 16 * ROOM_W + 10] = 3
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 120)
    for _ in range(240):
        pb.tick()
        if pb.memory[RS + 1] == 50:
            break
    assert pb.memory[RS + 1] == 50, "could not enter final-stage Sigil room"
    for _ in range(60):
        pb.tick()

    sigils = [EN + i * ENTITY_SIZE for i in range(32)
              if pb.memory[EN + i * ENTITY_SIZE] == 3
              and pb.memory[EN + i * ENTITY_SIZE + 17] == PICKUP_RIFT_SIGIL]
    assert len(sigils) == 1, f"expected one final Sigil, got {len(sigils)}"
    sigil = sigils[0]
    target_x, target_y = pb.memory[sigil + 3] - 2, pb.memory[sigil + 7] - 9
    start = ((pb.memory[PL + 9] + 2) // 8, (pb.memory[PL + 11] + 8) // 8)
    goal = ((target_x + 2) // 8, (target_y + 8) // 8)
    assert body_open(pb, start[0], start[1]), f"entry footprint blocked at {start}"
    assert body_open(pb, goal[0], goal[1]), f"Sigil footprint blocked at {goal}"

    seen, queue = {start}, [start]
    while queue:
        x, y = queue.pop(0)
        for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if point not in seen and body_open(pb, *point):
                seen.add(point)
                queue.append(point)
    assert goal in seen, (
        f"final Sigil at {(pb.memory[sigil + 3], pb.memory[sigil + 7])} "
        f"has no body-valid path from {start} to {goal}")
    pb.stop(save=False)
    print(f"[stage8-sigil-path] PASS seed14 {start}->{goal} ({len(seen)} body cells)")


if __name__ == "__main__":
    main()
