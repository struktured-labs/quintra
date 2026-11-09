#!/usr/bin/env python3
"""Dungeon merchant shelves stay sold out after leaving the room."""
import re
from pathlib import Path

from quintra_topology import STAGE_BOSS_ROOM, dungeon_direction
from test_shop_surge import (
    CAMERA_X, CAMERA_Y, EN, LARGE, PL, RS, TM, WORLD_H, WORLD_W,
    boot_shop, put16,
)

NOI = Path(__file__).resolve().parent.parent.joinpath("rom/working/quintra.noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


SEALED, PUZZLE = addr("_room_combat_sealed"), addr("_room_puzzle_locked")


PICKUP_SHOP = 4
SHOP_BOUGHT = 58
SHOP_CIVIC = 59


def tick(pb, count):
    for _ in range(count):
        pb.tick()


def clear_hostiles(pb):
    for i in range(32):
        entity = EN + i * 28
        if pb.memory[entity] == 2:
            pb.memory[entity] = pb.memory[entity + 1] = 0


def shelves(pb):
    found = []
    for i in range(32):
        entity = EN + i * 28
        if (pb.memory[entity] == 3
                and pb.memory[entity + 17] == PICKUP_SHOP):
            found.append((
                pb.memory[entity + 3],
                pb.memory[entity + 18],
                pb.memory[entity + 19],
            ))
    return sorted(found)


def cross(pb, source, target):
    direction = dungeon_direction(source, target)
    clear_hostiles(pb)
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[SEALED] = pb.memory[PUZZLE] = 0
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    pb.memory[RS + 1] = source
    for tx, ty in {
        0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
        2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
    }[direction]:
        pb.memory[TM + ty * 20 + tx] = 3
    x, y = {0: (72, 0), 1: (144, 60), 2: (72, 120), 3: (0, 60)}[direction]
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    pb.memory[PL + 15] = 200
    for _ in range(240):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, (
        f"did not reach room {target} from {source}")
    tick(pb, 30)


def buy_at(pb, x):
    ware = next(EN + i * 28 for i in range(32)
                if pb.memory[EN + i * 28] == 3
                and pb.memory[EN + i * 28 + 17] == PICKUP_SHOP
                and abs(pb.memory[EN + i * 28 + 3] - x) < 8)
    pb.memory[PL + 16] = 200
    pb.memory[PL + 17] = 0
    put16(pb, PL + 9, pb.memory[ware + 3])
    put16(pb, PL + 11, max(0, pb.memory[ware + 7] - 8))
    pb.memory[PL + 15] = 120
    for _ in range(24):
        pb.tick()
        if pb.memory[ware] == 0:
            return
    raise AssertionError(f"shelf at x={x} was not bought")


def walk_town(pb, direction, screen):
    clear_hostiles(pb)
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[SEALED] = pb.memory[PUZZLE] = 0
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    pb.memory[RS + 1] = 63
    pb.memory[RS + 17] = 0
    for tx, ty in {
        0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
        2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
    }[direction]:
        pb.memory[TM + ty * 20 + tx] = 3
    x, y = {0: (72, 0), 1: (144, 60), 2: (72, 120), 3: (0, 60)}[direction]
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    pb.memory[PL + 15] = 200
    for _ in range(240):
        pb.tick()
        if pb.memory[RS + 19] == screen and pb.memory[RS + 1] == 63:
            break
    assert pb.memory[RS + 19] == screen and pb.memory[RS + 1] == 63, (
        f"town screen {pb.memory[RS + 19]} room {pb.memory[RS + 1]}")
    tick(pb, 30)


def civic_shelves(pb):
    # Arrival is west of the quarter. Buy the forge and the chart, leave,
    # and come back: those two stay gone.
    pb.memory[RS + 19] = 0
    walk_town(pb, 3, 2)
    quarter = shelves(pb)
    assert len(quarter) == 3, quarter
    forge = next(item for item in quarter if abs(item[0] - 40) < 8)
    buy_at(pb, 40)
    assert pb.memory[RS + SHOP_CIVIC] & 2, pb.memory[RS + SHOP_CIVIC]
    walk_town(pb, 1, 0)
    arrival = shelves(pb)
    chart = next(item for item in arrival if abs(item[0] - 48) < 8)
    buy_at(pb, 48)
    assert pb.memory[RS + SHOP_CIVIC] & 1, pb.memory[RS + SHOP_CIVIC]
    walk_town(pb, 3, 2)
    again = shelves(pb)
    assert forge not in again and len(again) == 2, again
    walk_town(pb, 1, 0)
    back = shelves(pb)
    assert chart not in back, back


def main():
    target = STAGE_BOSS_ROOM[0] - 2
    source = target - 1
    pb = boot_shop(1)
    try:
        before = shelves(pb)
        assert len(before) == 4, before
        heart = next(item for item in before if abs(item[0] - 44) < 8)
        build = next(item for item in before if abs(item[0] - 92) < 8)
        kept = [item for item in before if item not in (heart, build)]
        pb.memory[PL + 2] = max(1, pb.memory[PL + 1] - 2)
        buy_at(pb, 44)
        buy_at(pb, 92)
        assert pb.memory[RS + SHOP_BOUGHT] & 0x05, (
            f"purchase mask {pb.memory[RS + SHOP_BOUGHT]:02x}")
        cross(pb, target, source)
        cross(pb, source, target)
        after = shelves(pb)
        assert len(after) == 2, after
        assert heart not in after and build not in after, after
        assert sorted(after) == sorted(kept), (after, kept)
        civic_shelves(pb)
        # The next dungeon starts with a full counter.
        pb.memory[RS + 1] = 63
        pb.memory[RS + 19] = 0
        pb.memory[TM + 9] = pb.memory[TM + 10] = 3
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 0)
        for _ in range(180):
            pb.tick()
            if pb.memory[RS + SHOP_BOUGHT] == 0:
                break
        assert pb.memory[RS + SHOP_BOUGHT] == 0, (
            f"next dungeon kept sold shelves {pb.memory[RS + SHOP_BOUGHT]:02x}")
        assert pb.memory[RS + SHOP_CIVIC] == 0, (
            f"next dungeon kept civic shelves {pb.memory[RS + SHOP_CIVIC]:02x}")
    finally:
        pb.stop(save=False)
    print("[merchant-stock] PASS sold shelves stay empty until the next dungeon")


if __name__ == "__main__":
    main()
