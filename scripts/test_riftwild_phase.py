#!/usr/bin/env python3
"""Live-ROM contract for the Worldglass Waking/Hollow counterpart system."""

from test_overworld import EN, PL, RS, SCREEN, addr, exit_at, put16
from test_riftwild_landmarks import boot_world, wide_tiles


ENTITY_SIZE = 28
SCREEN_ROOM = 5
PICKUP_HOLLOW_RELIC = 25
PICKUP_WAYGEAR = 22
WAYGEAR_OWNED = 44
INVENTORY = 24
RIFTWILD_SHADOW = 57
HOLLOW_BIT = 0x01
RELIC_ONE_BIT = 0x02
MUSIC = addr("_music_track_id")
ROOM_REWARD = addr("_room_major_reward_pending")


def hostiles(pb):
    return [slot for slot in range(32)
            if pb.memory[EN + slot * ENTITY_SIZE] == 2
            and pb.memory[EN + slot * ENTITY_SIZE + 1] & 1]


def shift(pb):
    """Press the chord together and let the 56-frame shear transaction end."""
    pb.button_press("select")
    pb.button_press("b")
    pb.tick()
    pb.button_release("select")
    pb.button_release("b")
    for _ in range(110):
        pb.memory[PL + 2] = pb.memory[PL + 1]
        pb.memory[PL + 15] = 120
        pb.tick()


def assert_safe_footprint(pb):
    tiles = wide_tiles(pb)
    x = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    y = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    walkable = {1, 3, 8, *range(9, 21), 23, 24, *range(33, 37),
                *range(59, 64), 96, 105, 106, 107}
    assert x <= 232 and y <= 232, f"unsafe shift bounds: {x},{y}"
    for py in (y + 8, y + 15):
        for px in (x + 2, x + 8, x + 13):
            assert tiles[py >> 3][px >> 3] in walkable, \
                f"Worldglass left hero in solid terrain at {px},{py}"


def check_worldglass_recovery():
    pb = boot_world()
    try:
        # The first defeated Warden wakes arch 8. Worldglass is restored beside
        # any active Waking arch until claimed, so walking past it cannot make
        # the counterpart route permanently missable.
        pb.memory[RS + 47] |= 0x04
        pb.memory[RS + 18] = 7
        exit_at(pb, 232, 60)
        assert pb.memory[RS + 18] == 8
        glass = [s for s in range(32)
                 if pb.memory[EN + s * ENTITY_SIZE] == 3
                 and pb.memory[EN + s * ENTITY_SIZE + 1] & 1
                 and pb.memory[EN + s * ENTITY_SIZE + 17] == PICKUP_WAYGEAR
                 and pb.memory[EN + s * ENTITY_SIZE + 18] == 3]
        assert len(glass) == 1, "active arch did not restore Worldglass"
        base = EN + glass[0] * ENTITY_SIZE
        put16(pb, PL + 9, pb.memory[base + 3] | (pb.memory[base + 4] << 8))
        put16(pb, PL + 11, pb.memory[base + 7] | (pb.memory[base + 8] << 8))
        for _ in range(16):
            pb.tick()
            if pb.memory[ROOM_REWARD]:
                break
        assert pb.memory[PL + WAYGEAR_OWNED] & (1 << 3)
        assert pb.memory[ROOM_REWARD], \
            "Worldglass skipped the protected raised-arm ceremony"
    finally:
        pb.stop(save=False)


def main():
    check_worldglass_recovery()
    pb = boot_world()
    try:
        assert pb.memory[SCREEN] == SCREEN_ROOM
        pb.memory[PL + WAYGEAR_OWNED] |= 1 << 3
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 60)
        waking_screen = pb.memory[RS + 18]
        waking_tiles = wide_tiles(pb)
        waking_count = len(hostiles(pb))

        shift(pb)
        assert pb.memory[RS + RIFTWILD_SHADOW] & HOLLOW_BIT, \
            "Worldglass chord did not manifest Hollow Riftwild"
        assert pb.memory[RS + 18] == waking_screen, \
            "counterpart shift moved to a different world cell"
        assert pb.memory[MUSIC] == 23, \
            "Hollow did not start The Road Unremembered"
        assert wide_tiles(pb) != waking_tiles, \
            "Hollow is only a palette swap; terrain did not transform"
        assert len(hostiles(pb)) >= waking_count + 2, \
            "Hollow field did not add meaningful encounter pressure"
        assert all(pb.memory[EN + s * ENTITY_SIZE + 26] >= 2
                   for s in hostiles(pb)), \
            "Hollow enemy contact damage was not hardened"
        assert_safe_footprint(pb)

        shift(pb)
        assert not (pb.memory[RS + RIFTWILD_SHADOW] & HOLLOW_BIT)
        assert pb.memory[RS + 18] == waking_screen
        assert pb.memory[MUSIC] == 22, \
            "return to Waking did not restore the title-linked Riftwild theme"
        assert wide_tiles(pb) == waking_tiles, \
            "returning to Waking did not restore deterministic geography"

        # First regional relic lives far across field five only in Hollow.
        # Setting the logical cell is a debugger shortcut; the shift itself
        # performs the same complete room regeneration used in play.
        pb.memory[RS + 18] = 5
        shift(pb)
        relics = [s for s in range(32)
                  if pb.memory[EN + s * ENTITY_SIZE] == 3
                  and pb.memory[EN + s * ENTITY_SIZE + 1] & 1
                  and pb.memory[EN + s * ENTITY_SIZE + 17]
                  == PICKUP_HOLLOW_RELIC]
        assert len(relics) == 1, "Hollow relic shrine did not spawn uniquely"
        base = EN + relics[0] * ENTITY_SIZE
        assert pb.memory[base + 18] == 43, \
            "first Hollow shrine does not contain Blast Seed"
        # This check is about the transaction, not surviving incidental fire.
        for s in hostiles(pb):
            pb.memory[EN + s * ENTITY_SIZE] = 0
            pb.memory[EN + s * ENTITY_SIZE + 1] = 0
        put16(pb, PL + 9, pb.memory[base + 3] | (pb.memory[base + 4] << 8))
        put16(pb, PL + 11, pb.memory[base + 7] | (pb.memory[base + 8] << 8))
        for _ in range(12):
            pb.tick()
            if pb.memory[ROOM_REWARD]:
                break
        assert pb.memory[RS + RIFTWILD_SHADOW] & RELIC_ONE_BIT
        assert 43 in list(pb.memory[PL + INVENTORY:PL + INVENTORY + 16])
        assert pb.memory[ROOM_REWARD], \
            "Hollow relic skipped the protected raised-arm ceremony"
    finally:
        pb.stop(save=False)

    print("[riftwild-phase] PASS Worldglass chord + terrain + music + pressure + relic")


if __name__ == "__main__":
    main()
