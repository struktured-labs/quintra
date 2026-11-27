#!/usr/bin/env python3
"""Every first-phase Kilnback kill drops one guaranteed half-heart (#248).

Carmelo's design call: in the pack phase, each of the five Kilnback kills
must always drop a heart. PICKUP_HEART_HALF is the only heart pickup. The
drop sits beside the fallen body, on walkable floor, clear of the fire
pool the body leaves. The two half-hearts at the pack-to-Rex transform
are kept, so a full pack clear leaves 5 + 2.
"""
from test_boss_identity import PL, addr, enter_boss, put16
from test_cinder_phase_heal import (
    HP, entity_xy, footprint_walkable, heart_pickups, overlaps_fire,
)
from test_colossal_cinder import (
    CINDER_ALIVE, CINDER_PHASE, CINDER_X, CINDER_Y, clear_hostiles,
    keep_alive,
)

KILNBACKS = 5
MAX_HP = 23                    # entity.ai_data[6]: remembered max HP
NEAR = 48                      # the helper searches within 32px + a body
CAMERA_X, CAMERA_Y = addr("_room_camera_x"), addr("_room_camera_y")


def park_player(pb):
    # Bottom-left corner, away from every start seat, so no drop is
    # collected (or magnetised) before it is counted.
    put16(pb, PL + 9, 8)
    put16(pb, PL + 11, 112)
    pb.memory[PL + 1] = pb.memory[PL + 2] = 255
    pb.memory[PL + 15] = 255


def main():
    pb, boss = enter_boss(2, keep_open=True)
    assert pb.memory[CINDER_PHASE] == 0, "Cinder fight did not start in pack phase"
    assert pb.memory[CINDER_ALIVE] == KILNBACKS
    park_player(pb)
    clear_hostiles(pb)
    keep_alive(pb, 2)
    assert not heart_pickups(pb), "hearts on the floor before any kill"

    max_hp = pb.memory[boss + MAX_HP]
    assert max_hp == 240, f"boss max HP changed: {max_hp}"
    step = (max_hp - max_hp // 2) // KILNBACKS
    known, drops = set(), []
    for kill in range(1, KILNBACKS + 1):
        fallen = KILNBACKS - kill
        park_player(pb)
        clear_hostiles(pb)
        # One Kilnback's worth of HP: exactly one component dies.
        pb.memory[boss + HP] = max_hp - step * kill
        # The last kill crosses half HP, where the shared boss-phase beat
        # holds the fight for 40 frames before the body falls.
        for _ in range(80):
            park_player(pb)
            body = pb.memory[CINDER_X + fallen], pb.memory[CINDER_Y + fallen]
            keep_alive(pb, 1)
            if pb.memory[CINDER_ALIVE] == fallen or pb.memory[CINDER_PHASE] == 1:
                break
        assert pb.memory[CINDER_ALIVE] == fallen or pb.memory[CINDER_PHASE] == 1, (
            f"kill {kill}: alive={pb.memory[CINDER_ALIVE]}")
        fresh = [ep for ep in heart_pickups(pb) if ep not in known]
        assert len(fresh) == 1, (
            f"kill {kill}: expected exactly one new half-heart, got "
            f"{[entity_xy(pb, ep) for ep in fresh]}")
        x, y = entity_xy(pb, fresh[0])
        assert abs(x - body[0]) <= NEAR and abs(y - body[1]) <= NEAR, (
            f"kill {kill}: heart at {(x, y)} is not near the body at {body}")
        assert footprint_walkable(pb, x, y), (
            f"kill {kill}: heart at {(x, y)} is not on walkable floor")
        assert not overlaps_fire(pb, x, y), (
            f"kill {kill}: heart at {(x, y)} sits in a fire pool")
        known.add(fresh[0])
        drops.append((x, y))
        assert len(heart_pickups(pb)) == kill

    assert len(set(drops)) == KILNBACKS, f"kill hearts stacked: {drops}"
    # The transform pair is still dropped on top of the five kill hearts.
    assert pb.memory[CINDER_PHASE] == 1, "pack did not begin metamorphosis"
    park_player(pb)
    keep_alive(pb, 3)
    assert set(heart_pickups(pb)) >= known, "a kill heart vanished"
    assert len(heart_pickups(pb)) == KILNBACKS + 2, (
        f"expected 5 kill hearts + 2 transform hearts, found "
        f"{len(heart_pickups(pb))}")

    pb.stop(save=False)
    print(f"[cinder-kill-hearts] PASS one half-heart per Kilnback kill at "
          f"{drops}, plus the transform pair (7 total)")


if __name__ == "__main__":
    main()
