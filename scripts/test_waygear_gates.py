#!/usr/bin/env python3
"""Live-ROM contract for Warden-gated permanent Riftwild Waygear."""

from test_overworld import (
    EN, PL, RS, SCREEN, addr, exit_at, put16,
)
from test_riftwild_landmarks import boot_world


ENTITY_SIZE = 28
PICKUP_WAYGEAR = 22
SCREEN_INVENTORY = 9
SCREEN_ROOM = 5
SCREEN_DIALOG = 10
REWARD_TIMER = addr("_room_major_reward_pending")
POSE_LOCKED = addr("_room_player_pose_locked")
OAM_MAJOR_REWARD_ICON = 39
SPR_WAYGEAR_GLOVE = 204
WAYGEAR_OWNED = 44
WAYGEAR_EQUIPPED = 45
RIFT_FLAGS = 47
RIFT_READY = 0x80
GUARD_BITS = (0x04, 0x08, 0x10)


def pickup_slots(pb, kind, gear=None):
    slots = []
    for slot in range(32):
        base = EN + slot * ENTITY_SIZE
        if (pb.memory[base] == 3 and pb.memory[base + 1] & 1
                and pb.memory[base + 17] == kind
                and (gear is None or pb.memory[base + 18] == gear)):
            slots.append(slot)
    return slots


def sentinel_slots(pb):
    return [slot for slot in range(32)
            if pb.memory[EN + slot * ENTITY_SIZE] == 2
            and pb.memory[EN + slot * ENTITY_SIZE + 1] & 1
            and pb.memory[EN + slot * ENTITY_SIZE + 17] == 1]


def main():
    pb = boot_world()
    try:
        # Leg one: the Glove is carried by a live Warden, not sitting beside
        # the shortest path. The gate remains dormant until that fight's bit
        # is persisted.
        exit_at(pb, 232, 60)
        exit_at(pb, 232, 60)
        exit_at(pb, 232, 60)
        assert pb.memory[RS + 18] == 3
        assert sentinel_slots(pb), "field 3 did not spawn its Riftwild Warden"
        assert not pickup_slots(pb, PICKUP_WAYGEAR), \
            "Titan Glove appeared before the Warden fell"

        # Model the persistent result of the combat, leave, and return. The
        # pedestal recovery is essential: an immediate drop left behind can
        # never make the run unwinnable.
        pb.memory[RS + RIFT_FLAGS] |= GUARD_BITS[0]
        exit_at(pb, 0, 60)
        exit_at(pb, 232, 60)
        assert not sentinel_slots(pb), "cleared Warden respawned"
        assert pickup_slots(pb, PICKUP_WAYGEAR, 0), \
            "cleared Warden did not restore its missed Titan Glove"

        put16(pb, PL + 9, 112)
        put16(pb, PL + 11, 32)
        for _ in range(30):
            pb.tick()
            if pb.memory[REWARD_TIMER]:
                break
        assert pb.memory[PL + WAYGEAR_OWNED] & 1
        assert pb.memory[PL + WAYGEAR_EQUIPPED] == 0
        assert pb.memory[SCREEN] == SCREEN_ROOM
        assert 118 <= pb.memory[REWARD_TIMER] <= 120, \
            "Waygear skipped its protected two-second claim ceremony"
        # The collision transaction can publish 120 before the following
        # room-draw edge writes OAM. Observe that first presentation frame.
        if pb.memory[REWARD_TIMER] == 120:
            pb.tick()
        assert pb.memory[POSE_LOCKED] == 1, \
            "Waygear ceremony did not raise the champion's arms"
        icon = 0xFE00 + OAM_MAJOR_REWARD_ICON * 4
        assert pb.memory[icon + 2] == SPR_WAYGEAR_GLOVE \
            and pb.memory[icon] != 0, \
            ("Titan Glove was not held visibly above the champion: "
             f"oam={list(pb.memory[icon:icon + 4])} "
             f"timer={pb.memory[REWARD_TIMER]}")
        frames = 0
        while pb.memory[SCREEN] == SCREEN_ROOM and frames < 130:
            pb.tick()
            frames += 1
        assert pb.memory[SCREEN] == SCREEN_DIALOG and 118 <= frames <= 121
        pb.tick(30)
        pb.button_press("a")
        pb.tick(3)
        pb.button_release("a")
        pb.tick(24)
        assert pb.memory[SCREEN] == SCREEN_ROOM, \
            "Waygear claim page did not resume the Riftwild field"

        # Leg two: preserve the first victory, advance the campaign counter,
        # and enter the second Warden field through a reciprocal world seam.
        pb.memory[RS + 11] = 2
        pb.memory[RS + RIFT_FLAGS] = RIFT_READY | GUARD_BITS[0]
        pb.memory[RS + 18] = 11
        exit_at(pb, 72, 232)
        assert pb.memory[RS + 18] == 17
        assert sentinel_slots(pb), "field 17 did not spawn its Riftwild Warden"
        assert not pickup_slots(pb, PICKUP_WAYGEAR, 1)
        pb.memory[RS + RIFT_FLAGS] |= GUARD_BITS[1]
        exit_at(pb, 72, 0)
        exit_at(pb, 72, 232)
        assert pickup_slots(pb, PICKUP_WAYGEAR, 1), \
            "second Warden did not restore its missed Tide Raft"

        # Leg three repeats the same mandatory cadence for the Rift Hook.
        pb.memory[RS + 11] = 3
        pb.memory[RS + RIFT_FLAGS] = (RIFT_READY | GUARD_BITS[0]
                                      | GUARD_BITS[1])
        pb.memory[RS + 18] = 23
        exit_at(pb, 72, 232)
        assert pb.memory[RS + 18] == 29
        assert sentinel_slots(pb), "field 29 did not spawn its Riftwild Warden"
        assert not pickup_slots(pb, PICKUP_WAYGEAR, 2)
        pb.memory[RS + RIFT_FLAGS] |= GUARD_BITS[2]
        exit_at(pb, 72, 0)
        exit_at(pb, 72, 232)
        assert pickup_slots(pb, PICKUP_WAYGEAR, 2), \
            "third Warden did not restore its missed Rift Hook"

        # START -> SELECT is a graphical loadout, not another prose dump.
        pb.button_press("start")
        for _ in range(60):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_INVENTORY:
                break
        pb.button_release("start")
        assert pb.memory[SCREEN] == SCREEN_INVENTORY, \
            f"START did not open Pack after Warden reward: screen={pb.memory[SCREEN]}"
        pb.button_press("select")
        for _ in range(60):
            pb.tick()
            if pb.memory[0xFE12] == 204:
                break
        pb.button_release("select")
        assert pb.memory[0xFE12] == SPR_WAYGEAR_GLOVE, \
            "Waygear page did not render the Titan Glove icon"
    finally:
        pb.stop(save=False)

    print("[waygear] PASS three Warden gates + raised-arm claim + recovery + Pack UI")


if __name__ == "__main__":
    main()
