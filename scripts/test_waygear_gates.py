#!/usr/bin/env python3
"""Live-ROM contract for hero nature and one equipped traversal implement."""

from test_overworld import EN, PL, RS, SCREEN, TM, exit_at, put16
from test_riftwild_landmarks import boot_world


ENTITY_SIZE = 28
PICKUP_WAYGEAR = 22
BGT_GATE_BOULDER = 100
SCREEN_INVENTORY = 9
WAYGEAR_OWNED = 44
WAYGEAR_EQUIPPED = 45


def pickup_slots(pb, kind, gear=None):
    slots = []
    for slot in range(32):
        base = EN + slot * ENTITY_SIZE
        if (pb.memory[base] == 3 and pb.memory[base + 1] & 1
                and pb.memory[base + 17] == kind
                and (gear is None or pb.memory[base + 18] == gear)):
            slots.append(slot)
    return slots


def move_up(pb, frames=40):
    pb.button_press("up")
    try:
        for _ in range(frames):
            pb.memory[PL + 15] = 120
            pb.tick()
    finally:
        pb.button_release("up")
    return pb.memory[PL + 11] | pb.memory[PL + 12] << 8


def main():
    pb = boot_world()
    try:
        # Reach field three through real reciprocal seams. Its first implement
        # is freely discoverable rather than hidden behind its own gate.
        exit_at(pb, 232, 60)
        exit_at(pb, 232, 60)
        exit_at(pb, 232, 60)
        assert pb.memory[RS + 18] == 3
        assert pickup_slots(pb, PICKUP_WAYGEAR, 0), \
            "field 3 did not spawn the Titan Glove"

        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 32)
        for _ in range(30):
            pb.tick()
        assert pb.memory[PL + WAYGEAR_OWNED] & 1
        assert pb.memory[PL + WAYGEAR_EQUIPPED] == 0

        # Enter field 17 from its real northern neighbour. The Tide Raft is
        # visible inside a boulder-gated optional grove.
        pb.memory[RS + 18] = 11
        exit_at(pb, 72, 232)
        assert pb.memory[RS + 18] == 17
        assert (pb.memory[TM + 7 * 20 + 14],
                pb.memory[TM + 7 * 20 + 15]) == (
                    BGT_GATE_BOULDER, BGT_GATE_BOULDER)
        assert pickup_slots(pb, PICKUP_WAYGEAR, 1), \
            "field 17 gated grove lost the Tide Raft"

        # Wolfkin cannot cross boulders by nature alone.
        pb.memory[PL] = 0
        pb.memory[PL + WAYGEAR_EQUIPPED] = 0xFF
        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 72)
        assert move_up(pb) >= 56, "Wolfkin crossed a boulder without Waygear"

        # The equipped Glove substitutes for Sauran's innate stone lift.
        pb.memory[PL + WAYGEAR_EQUIPPED] = 0
        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 72)
        assert move_up(pb) < 56, "equipped Titan Glove did not open boulders"

        # Sauran gets the same route for free, leaving the gear slot available.
        pb.memory[PL] = 1
        pb.memory[PL + WAYGEAR_EQUIPPED] = 0xFF
        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 72)
        assert move_up(pb) < 56, "Sauran nature did not lift boulders"

        # START -> SELECT is a graphical loadout, not another prose dump.
        pb.button("start")
        for _ in range(24):
            pb.tick()
        assert pb.memory[SCREEN] == SCREEN_INVENTORY
        pb.button("select")
        for _ in range(24):
            pb.tick()
        assert pb.memory[0xFE12] == 204, \
            "Waygear page did not render the Titan Glove icon"
    finally:
        pb.stop(save=False)

    print("[waygear] PASS permanent pickup + gated grove + hero/tool access + Pack UI")


if __name__ == "__main__":
    main()
