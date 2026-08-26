#!/usr/bin/env python3
"""Live-ROM contract for hero nature and one equipped traversal implement."""

from test_overworld import (
    EN, ORIGIN_X, ORIGIN_Y, PL, RS, SCREEN, TM, exit_at, put16,
)
from test_riftwild_landmarks import boot_world


ENTITY_SIZE = 28
PICKUP_WAYGEAR = 22
BGT_GATE_BOULDER = 100
BGT_GATE_WATER = 101
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


def move_down(pb, frames=48):
    pb.button_press("down")
    try:
        for _ in range(frames):
            pb.memory[PL + 15] = 120
            pb.tick()
    finally:
        pb.button_release("down")
    return pb.memory[PL + 11] | pb.memory[PL + 12] << 8


def hook_grove_contract():
    pb = boot_world()
    try:
        # Follow the real eastern ridge and southern chain from field zero.
        for _ in range(5):
            exit_at(pb, 232, 60)
        for _ in range(3):
            exit_at(pb, 72, 232)
        assert pb.memory[RS + 18] == 23
        pb.memory[PL] = 0
        pb.memory[PL + WAYGEAR_OWNED] = 0x03
        pb.memory[PL + WAYGEAR_EQUIPPED] = 1
        exit_at(pb, 72, 232)
        assert pb.memory[RS + 18] == 29
        assert (pb.memory[TM + 7 * 20 + 14],
                pb.memory[TM + 7 * 20 + 15]) == (
                    BGT_GATE_WATER, BGT_GATE_WATER)
        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 72)
        assert move_up(pb) < 56, "equipped Tide Raft did not cross deep water"
        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 32)
        for _ in range(40):
            pb.tick()
            if pb.memory[PL + WAYGEAR_EQUIPPED] == 2:
                break
        assert pb.memory[PL + WAYGEAR_EQUIPPED] == 2, \
            "Rift Hook collection did not auto-equip"
        assert (pb.memory[TM + 7 * 20 + 14],
                pb.memory[TM + 7 * 20 + 15]) == (35, 35), \
            "Hook reward left its old paired water gate closed"
        gate_py = (pb.memory[ORIGIN_Y] + 7) & 31
        gate_px = (pb.memory[ORIGIN_X] + 14) & 31
        assert [pb.memory[0x9800 + gate_py * 32 + ((gate_px + i) & 31)]
                for i in range(2)] == [35, 35], \
            "opened Hook grove retained its paired gate in visible BG VRAM"
        assert move_down(pb) > 56, \
            "newly equipped Hook still left the champion trapped in its grove"
    finally:
        pb.stop(save=False)


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

        # Collecting the Raft auto-equips it. The grove mouth must collapse
        # first, or that swap revokes the Glove permission used to enter and
        # strands the champion behind the two boulder-rune tiles.
        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 32)
        for _ in range(40):
            pb.tick()
            if pb.memory[PL + WAYGEAR_EQUIPPED] == 1:
                break
        assert pb.memory[PL + WAYGEAR_EQUIPPED] == 1, \
            "Tide Raft collection did not auto-equip"
        assert (pb.memory[TM + 7 * 20 + 14],
                pb.memory[TM + 7 * 20 + 15]) == (35, 35), \
            "Waygear reward left its old paired gate closed: " \
            f"screen={pb.memory[RS + 18]} tiles=" \
            f"{pb.memory[TM + 7 * 20 + 14]}," \
            f"{pb.memory[TM + 7 * 20 + 15]}"
        gate_py = (pb.memory[ORIGIN_Y] + 7) & 31
        gate_px = (pb.memory[ORIGIN_X] + 14) & 31
        assert [pb.memory[0x9800 + gate_py * 32 + ((gate_px + i) & 31)]
                for i in range(2)] == [35, 35], \
            "opened Raft grove retained its paired gate in visible BG VRAM"
        assert move_down(pb) > 56, \
            "newly equipped Raft still left the champion trapped in its grove"

        # Sauran gets the same route for free, leaving the gear slot available.
        pb.memory[PL] = 1
        pb.memory[PL + WAYGEAR_EQUIPPED] = 0xFF
        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 72)
        assert move_up(pb) < 56, "Sauran nature did not lift boulders"

        # START -> SELECT is a graphical loadout, not another prose dump.
        pb.button_press("start")
        for _ in range(60):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_INVENTORY:
                break
        pb.button_release("start")
        assert pb.memory[SCREEN] == SCREEN_INVENTORY, \
            f"START did not open Pack after grove escape: screen={pb.memory[SCREEN]}"
        pb.button_press("select")
        for _ in range(60):
            pb.tick()
            if pb.memory[0xFE12] == 204:
                break
        pb.button_release("select")
        assert pb.memory[0xFE12] == 204, \
            "Waygear page did not render the Titan Glove icon"
    finally:
        pb.stop(save=False)

    hook_grove_contract()
    print("[waygear] PASS Raft/Hook self-opening groves + hero/tool access + Pack UI")


if __name__ == "__main__":
    main()
