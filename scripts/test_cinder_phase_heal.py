#!/usr/bin/env python3
"""ROM contract: Cinder Rex drops two reachable half-hearts at the transform.

Phase 1 can chip the champion down, and the 64-tick metamorphosis used to
heal nothing. This locks the mid-transform pair: both hearts spawn, sit on
reachable floor, and stay clear of live fire pools. Easy mode is the same
code path (no difficulty branch).
"""
from pathlib import Path
import os

from test_boss_identity import EN, PL, TM, addr, enter_boss, put16
from test_colossal_cinder import (
    CINDER_PHASE, CINDER_ALIVE, keep_alive, clear_hostiles,
)

ROOT = Path(__file__).resolve().parent.parent
ENTITY_SIZE = 28
ENT_PICKUP = 3
EF_ACTIVE = 0x01
PICKUP_HEART_HALF = 0
HP = 14
ROOM_W, ROOM_H = 20, 17
BGT_WALL, BGT_WALL_CRACK = 2, 24

F_TX = addr("_cinder_fire_tx")
F_TY = addr("_cinder_fire_ty")
F_SZ = addr("_cinder_fire_size")
F_TTL = addr("_cinder_fire_ttl")
WORLD_W = addr("_room_world_width")
WORLD_H = addr("_room_world_height")
PREVIEW = Path(os.environ.get(
    "CINDER_HEAL_PREVIEW",
    ROOT / "tmp" / "cinder-rex-phase-heal.png",
))


def entity_xy(pb, ep):
    return pb.memory[ep + 3], pb.memory[ep + 7]


def heart_pickups(pb):
    found = []
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if (pb.memory[ep] == ENT_PICKUP
                and pb.memory[ep + 1] & EF_ACTIVE
                and pb.memory[ep + 17] == PICKUP_HEART_HALF):
            found.append(ep)
    return found


def tile_at(pb, tx, ty):
    if tx < 0 or ty < 0 or ty >= ROOM_H:
        return BGT_WALL
    if tx < ROOM_W:
        return pb.memory[TM + ty * ROOM_W + tx]
    return 1  # streamed wide-arena extension is walkable floor


def tile_walkable(tile):
    return tile not in (0, BGT_WALL, BGT_WALL_CRACK)


def footprint_walkable(pb, x, y):
    for dx, dy in ((1, 1), (14, 1), (1, 14), (14, 14)):
        if not tile_walkable(tile_at(pb, (x + dx) >> 3, (y + dy) >> 3)):
            return False
    return True


def overlaps_fire(pb, x, y):
    tx0, ty0 = x >> 3, y >> 3
    tx1, ty1 = (x + 15) >> 3, (y + 15) >> 3
    for i in range(8):
        if not pb.memory[F_TTL + i]:
            continue
        fx, fy, s = pb.memory[F_TX + i], pb.memory[F_TY + i], pb.memory[F_SZ + i]
        if tx1 >= fx and tx0 < fx + s and ty1 >= fy and ty0 < fy + s:
            return True
    return False


def reachable_from_player(pb, x, y):
    px = pb.memory[PL + 9] + 8
    py = pb.memory[PL + 11] + 12
    world_w = pb.memory[WORLD_W] or 160
    world_h = pb.memory[WORLD_H] or 136
    max_tx, max_ty = world_w >> 3, world_h >> 3
    start = (px >> 3, py >> 3)
    goals = {
        ((x + 1) >> 3, (y + 1) >> 3),
        ((x + 14) >> 3, (y + 1) >> 3),
        ((x + 1) >> 3, (y + 14) >> 3),
        ((x + 14) >> 3, (y + 14) >> 3),
    }
    stack = [start]
    seen = {start}
    while stack:
        tx, ty = stack.pop()
        if (tx, ty) in goals:
            goals.remove((tx, ty))
            if not goals:
                return True
        for nx, ny in ((tx - 1, ty), (tx + 1, ty), (tx, ty - 1), (tx, ty + 1)):
            if (nx, ny) in seen:
                continue
            if nx < 0 or ny < 0 or nx >= max_tx or ny >= max_ty:
                continue
            if not tile_walkable(tile_at(pb, nx, ny)):
                continue
            seen.add((nx, ny))
            stack.append((nx, ny))
    return False


def assert_hearts_ok(pb, when):
    hearts = heart_pickups(pb)
    assert len(hearts) == 2, (
        f"{when}: expected 2 half-hearts, found {len(hearts)} at "
        f"{[entity_xy(pb, ep) for ep in hearts]}"
    )
    positions = [entity_xy(pb, ep) for ep in hearts]
    for x, y in positions:
        assert footprint_walkable(pb, x, y), (
            f"{when}: heart at {(x, y)} is not on walkable floor"
        )
        assert not overlaps_fire(pb, x, y), (
            f"{when}: heart at {(x, y)} overlaps a live fire pool; "
            f"pools={[(pb.memory[F_TX+i], pb.memory[F_TY+i], pb.memory[F_SZ+i], pb.memory[F_TTL+i]) for i in range(8) if pb.memory[F_TTL+i]]}"
        )
        assert reachable_from_player(pb, x, y), (
            f"{when}: heart at {(x, y)} is not reachable from the champion "
            f"at {(pb.memory[PL+9], pb.memory[PL+11])}"
        )
    # The pair should be distinct seats, not two stacked drops.
    assert positions[0] != positions[1], f"{when}: both hearts stacked at {positions[0]}"
    return positions


def drive_to_transform(pb, boss):
    pb.memory[PL + 1] = pb.memory[PL + 2] = 255
    pb.memory[PL + 15] = 255
    clear_hostiles(pb)
    pb.memory[boss + HP] = 120
    for _ in range(80):
        keep_alive(pb, 1)
        if pb.memory[CINDER_PHASE] == 1:
            return
    raise AssertionError(
        f"pack did not begin metamorphosis "
        f"(phase={pb.memory[CINDER_PHASE]} alive={pb.memory[CINDER_ALIVE]})"
    )


def main():
    pb, boss = enter_boss(2, keep_open=True)
    assert pb.memory[CINDER_PHASE] == 0, "Cinder fight did not start in pack phase"
    drive_to_transform(pb, boss)
    assert pb.memory[CINDER_PHASE] == 1

    # Give the first transform tick a moment to spawn, then park the
    # champion on open floor so the reachability flood-fill is honest
    # and the preview shows both drops.
    keep_alive(pb, 1)
    put16(pb, PL + 9, 80)
    put16(pb, PL + 11, 112)
    pb.memory[PL + 15] = 255
    # The Ember arena is 224px wide. Park the camera on the shared
    # 160px window so both drops are on-screen for the preview.
    cam_x, cam_y = addr("_room_camera_x"), addr("_room_camera_y")
    pb.memory[cam_x] = pb.memory[cam_y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    keep_alive(pb, 2)
    positions = assert_hearts_ok(pb, "during transform")

    PREVIEW.parent.mkdir(parents=True, exist_ok=True)
    pb.screen.image.save(str(PREVIEW))

    for _ in range(120):
        pb.memory[PL + 15] = 255
        if pb.memory[CINDER_PHASE] == 2:
            break
        keep_alive(pb, 1)
    assert pb.memory[CINDER_PHASE] == 2, "Cinder Rex did not unfold"
    assert_hearts_ok(pb, "as phase 2 begins")

    print(
        f"[cinder-phase-heal] PASS two half-hearts at {positions} "
        f"during transform, still present and clear of fire as Rex unfolds; "
        f"preview={PREVIEW}",
        flush=True,
    )
    pb.stop()


if __name__ == "__main__":
    main()
