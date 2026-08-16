#!/usr/bin/env python3
"""Live-ROM contract for one persistent Riftwild per three-dungeon region."""

from test_overworld import (
    CAMERA_X, CAMERA_Y, EN, LARGE, PL, ROM, RS, SCREEN, TM, WORLD_H,
    WORLD_W, exit_at,
)
from test_riftwild_landmarks import boot_world
from quintra_topology import STAGE_BOSS_ROOM


ROOM_W = 20
SCREEN_ROOM = 5
SCREEN_MAP = 8
BGT_PORTAL = 34
BGT_MAP_ROOM = 49
BGT_DOOR = 3
READY = 0x80
WELL = 0x01
VAULT = 0x02
REGION = 46
FLAGS = 47
WORLD_MODE = 17
WORLD_SCREEN = 18
WORLD_SEEN = 21
GATE_NODES = {6: (7, 7), 11: (10, 10), 12: (1, 13)}


def set16(pb, off, value):
    pb.memory[RS + off] = value & 0xFF
    pb.memory[RS + off + 1] = value >> 8


def get16(pb, off):
    return pb.memory[RS + off] | (pb.memory[RS + off + 1] << 8)


def return_after_boss(pb, number):
    """Turn the live room into a defeated compact arena and take its exit."""
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[number - 1]
    pb.memory[RS + 11] = number
    pb.memory[RS + WORLD_MODE] = 0
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    for slot in range(32):
        base = EN + slot * 28
        pb.memory[base] = pb.memory[base + 1] = 0
    pb.memory[TM + 16 * ROOM_W + 9] = BGT_DOOR
    pb.memory[TM + 16 * ROOM_W + 10] = BGT_DOOR
    exit_at(pb, 72, 120)
    assert pb.memory[RS + WORLD_MODE] == 1


def open_map(pb):
    pb.button_press("select")
    try:
        for _ in range(180):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_MAP:
                for _ in range(90):
                    pb.tick()
                return
    finally:
        pb.button_release("select")
    raise AssertionError("regional Riftwild map did not open")


def close_map(pb):
    pb.button_press("b")
    try:
        for _ in range(180):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_ROOM:
                break
        else:
            raise AssertionError("regional Riftwild map did not close")
    finally:
        pb.button_release("b")
    for _ in range(90):
        pb.memory[PL + 2] = pb.memory[PL + 1]
        pb.memory[PL + 15] = 120
        pb.tick()


def assert_gate_map(pb, active):
    open_map(pb)
    for gate, (x, y) in GATE_NODES.items():
        tile = pb.memory[0x9800 + y * 32 + x]
        expected = BGT_PORTAL if gate == active else BGT_MAP_ROOM
        assert tile == expected, (
            f"region gate {gate} tile={tile}, expected={expected}; active={active}"
        )
    close_map(pb)


def main():
    pb = boot_world()
    try:
        # Boss one creates region zero.  Make its exploration and one-use
        # landmarks unmistakable, then prove the next two returns retain them.
        assert (pb.memory[RS + REGION], pb.memory[RS + WORLD_SCREEN]) == (0, 0)
        assert pb.memory[RS + FLAGS] == READY
        first_region_tiles = bytes(pb.memory[TM:TM + ROOM_W * 17])
        set16(pb, WORLD_SEEN, 0xFFFF)
        pb.memory[RS + FLAGS] = READY | WELL | VAULT

        return_after_boss(pb, 2)
        assert (pb.memory[RS + REGION], pb.memory[RS + WORLD_SCREEN]) == (0, 7)
        assert get16(pb, WORLD_SEEN) == 0xFFFF
        assert pb.memory[RS + FLAGS] == READY | WELL | VAULT
        assert_gate_map(pb, 11)

        # Gate six remains visible geography but is inert; gate eleven is the
        # only live threshold for the second trip through the shared region.
        exit_at(pb, 0, 60)
        assert pb.memory[RS + WORLD_SCREEN] == 6
        assert pb.memory[TM + 8 * ROOM_W + 10] != BGT_PORTAL
        exit_at(pb, 232, 60)
        exit_at(pb, 72, 232)
        assert pb.memory[RS + WORLD_SCREEN] == 11
        assert pb.memory[TM + 8 * ROOM_W + 10] == BGT_PORTAL

        return_after_boss(pb, 3)
        assert (pb.memory[RS + REGION], pb.memory[RS + WORLD_SCREEN]) == (0, 13)
        assert get16(pb, WORLD_SEEN) == 0xFFFF
        assert pb.memory[RS + FLAGS] == READY | WELL | VAULT
        assert_gate_map(pb, 12)
        exit_at(pb, 0, 60)
        assert pb.memory[RS + WORLD_SCREEN] == 12
        assert pb.memory[TM + 8 * ROOM_W + 10] == BGT_PORTAL

        # The fourth defeated Colossus starts region one: fog and claimed
        # landmarks reset, the first arch wakes again, and its seed namespace
        # produces genuinely different geography from region zero.
        return_after_boss(pb, 4)
        assert (pb.memory[RS + REGION], pb.memory[RS + WORLD_SCREEN]) == (1, 0)
        assert get16(pb, WORLD_SEEN) == 0x0001
        assert pb.memory[RS + FLAGS] == READY
        assert bytes(pb.memory[TM:TM + ROOM_W * 17]) != first_region_tiles
    finally:
        pb.stop(save=False)

    print(
        "[regional-riftwild] PASS persistent exploration + one-use landmarks "
        "+ sequential gates 6/11/12 across three returns + fresh next region"
    )


if __name__ == "__main__":
    main()
