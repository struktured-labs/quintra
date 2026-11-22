#!/usr/bin/env python3
"""Will-scaled Morningstar radius / obstacles and Boomerang travel."""
import math
import os
from pathlib import Path

from PIL import Image

from test_will_max import (
    ROM, PLAYER as P, ENTITIES as E, TILEMAP as T,
    WILL_OFFSET, LEVEL_OFFSET, WILL_MAX,
    boot, clear_arena, put16, addr,
)

WAYGEAR = 44
ITEM_BOOM = 45
ITEM_STAR = 47
ITEM_HOOK = 46
AUX_BOOM = 0xF4
AUX_HOOK = 0xF5
AUX_STAR = 0xF6
BGT_WALL, BGT_PILLAR, BGT_CRYSTAL, BGT_POT = 2, 21, 22, 32

# Peak orbit = sx * peak / 24, with sx peaking at 24.
PEAK = {0: 24, 1: 29, 2: 34, 3: 39}
# Cardinal outbound at 3 px/tick.
OUT_PX = {0: 84, 1: 108, 2: 132, 3: 168}

GIF_DIR = Path(os.environ.get("MSTAR_GIF_DIR", "builds/will-b-weapons"))
GIF_DIR.mkdir(parents=True, exist_ok=True)


def i16(pb, base, off):
    v = pb.memory[base + off] | (pb.memory[base + off + 1] << 8)
    return v - 65536 if v >= 32768 else v


def shots(pb, marker):
    return [E + i * 28 for i in range(32)
            if pb.memory[E + i * 28] == 1
            and pb.memory[E + i * 28 + 1] & 1
            and pb.memory[E + i * 28 + 23] == marker]


def set_will(pb, level, charge, waygear=0):
    pb.memory[P + LEVEL_OFFSET] = level
    pb.memory[P + WILL_OFFSET] = charge
    pb.memory[P + WAYGEAR] = waygear


def scene(item, x=72, y=64, facing=1):
    pb = boot(0)
    clear_arena(pb)
    pb.memory[addr("_entity_enemy_count")] = 0
    pb.memory[P + 24] = item
    pb.memory[P + 18] = item
    pb.memory[P + 19] = 0
    pb.memory[P + 13] = facing
    put16(pb, P + 9, x)
    put16(pb, P + 11, y)
    pb.tick(2)
    return pb


def fire_b(pb):
    pb.button_press("b")
    pb.tick(2)
    pb.button_release("b")


def fire_right(pb):
    pb.button_press("right")
    pb.button_press("b")
    pb.tick(2)
    pb.button_release("b")
    pb.button_release("right")


def wall_room(pb):
    for x in range(20):
        pb.memory[T + 0 * 20 + x] = BGT_WALL
        pb.memory[T + 16 * 20 + x] = BGT_WALL
    for y in range(17):
        pb.memory[T + y * 20 + 0] = BGT_WALL
        pb.memory[T + y * 20 + 19] = BGT_WALL


def save_gif(frames, path, scale=4):
    if not frames:
        return
    scaled = [f.resize((f.width * scale, f.height * scale), Image.NEAREST)
              for f in frames]
    scaled[0].save(path, save_all=True, append_images=scaled[1:],
                   duration=50, loop=0, optimize=True)
    print(f"  gif {path} ({len(scaled)} frames)")


def grab(pb):
    return pb.screen.image.copy()


# will setups: (level, charge, waygear) -> expected tier
TIER_CASES = (
    (0, 0, 0, 0, "empty"),
    (0, 10, 0, 0, "just-below-third"),
    (0, 30, 0, 1, "one-third"),
    (0, 60, 0, 1, "two-thirds"),
    (1, 0, 7, 2, "banked-cap4"),
    (3, 40, 7, 2, "level3-cap4"),
    (1, 90, 0, 3, "full-cap1"),
    (4, 90, 7, 3, "full-cap4"),
)


def measure_star(level, charge, waygear, tiles=(), pos=(72, 64), walled=False,
                 record=None):
    pb = scene(ITEM_STAR, x=pos[0], y=pos[1])
    frames = []
    try:
        set_will(pb, level, charge, waygear)
        before = (pb.memory[P + WILL_OFFSET], pb.memory[P + LEVEL_OFFSET])
        if walled:
            wall_room(pb)
        for kind, tx, ty in tiles:
            pb.memory[T + ty * 20 + tx] = kind
        fire_b(pb)
        after = (pb.memory[P + WILL_OFFSET], pb.memory[P + LEVEL_OFFSET])
        cx, cy = pos[0] + 4, pos[1] + 4
        pts = []
        for f in range(90):
            live = shots(pb, AUX_STAR)
            if record is not None and f % 2 == 0:
                frames.append(grab(pb))
            if not live:
                break
            e = live[0]
            x, y = i16(pb, e, 3), i16(pb, e, 7)
            pts.append((f, x, y, math.hypot(x - cx, y - cy)))
            pb.tick()
        peak = max((p[3] for p in pts), default=0)
        life = (pts[-1][0] + 1) if pts else 0
        if record:
            save_gif(frames, GIF_DIR / record)
        # The bar may fill during the swing; a spend would drop charge or level.
        spent = after[1] < before[1] or after[0] < before[0]
        return dict(peak=peak, life=life, spent=spent,
                    before=before, after=after, points=pts)
    finally:
        pb.stop(save=False)


def measure_boom(level, charge, waygear, tiles=(), pos=(24, 64),
                 wide=False, record=None):
    pb = scene(ITEM_BOOM, x=pos[0], y=pos[1])
    frames = []
    try:
        set_will(pb, level, charge, waygear)
        before = (pb.memory[P + WILL_OFFSET], pb.memory[P + LEVEL_OFFSET])
        if wide:
            # 208 px court: floor past the 160 px viewport so tier 3 can
            # show its full 168 px throw without hitting the crystal seam.
            pb.memory[addr("_room_world_width")] = 208
        for kind, tx, ty in tiles:
            pb.memory[T + ty * 20 + tx] = kind
        fire_right(pb)
        after = (pb.memory[P + WILL_OFFSET], pb.memory[P + LEVEL_OFFSET])
        pts = []
        for f in range(220):
            live = shots(pb, AUX_BOOM)
            if record is not None and f % 2 == 0:
                frames.append(grab(pb))
            if not live:
                break
            e = live[0]
            x, y = i16(pb, e, 3), i16(pb, e, 7)
            pts.append((f, x, y, pb.memory[e + 15], pb.memory[e + 17]))
            pb.tick()
        xs = [p[1] for p in pts]
        outbound = [p for p in pts if p[3] == 0]
        travel = (max(xs) - (pos[0] + 4)) if xs else 0
        if record:
            save_gif(frames, GIF_DIR / record)
        return dict(travel=travel, max_x=max(xs) if xs else None,
                    outbound=len(outbound), total=len(pts),
                    returned=not shots(pb, AUX_BOOM) and bool(pts),
                    spent=(after[1] < before[1] or after[0] < before[0]),
                    before=before, after=after, points=pts)
    finally:
        pb.stop(save=False)


def assert_near(label, got, expected, slop):
    if abs(got - expected) > slop:
        raise AssertionError(f"{label}: got {got}, expected {expected} ±{slop}")


def test_star_tiers():
    results = {}
    for level, charge, gear, tier, name in TIER_CASES:
        rec = measure_star(level, charge, gear,
                           record=f"morningstar-tier{tier}-{name}.gif"
                           if name in ("empty", "full-cap1") else None)
        print(f"[star {name} t{tier}] peak={rec['peak']:.1f} life={rec['life']} "
              f"spent={rec['spent']}")
        # Only a max-Will swing spends the gauge; mid tiers stay heat-scaled
        # without emptying the bank.
        if tier >= 3:
            assert rec["spent"], (name, rec["before"], rec["after"])
        else:
            assert not rec["spent"], (name, rec["before"], rec["after"])
        assert rec["life"] >= 30, (name, rec["life"])
        assert_near(f"star {name} peak", rec["peak"], PEAK[tier], 1.5)
        if tier >= 3:
            assert rec["life"] >= 40, rec["life"]
        results[name] = rec
    # Full Will is clearly wider than empty.
    assert results["full-cap1"]["peak"] - results["empty"]["peak"] >= 14
    return results


def test_star_max_resets():
    """A max-Will Morningstar spends the bank; a second B does not re-fire at max."""
    pb = scene(ITEM_STAR, x=72, y=64)
    try:
        set_will(pb, 1, 90, 0)  # cap 1, full -> tier 3
        fire_b(pb)
        assert pb.memory[P + LEVEL_OFFSET] == 0, "max star did not reset will_level"
        # fire_b ticks past the spend; will_charge_tick may add one natural
        # point depending on frame phase, so allow <= 1.
        assert pb.memory[P + WILL_OFFSET] <= 1, "max star did not reset will_charge"
        # Let the orbit and the 56-frame item cooldown finish. Do not press A.
        for _ in range(80):
            pb.tick()
        assert pb.memory[P + LEVEL_OFFSET] == 0, "will_level banked back during cooldown"
        fire_b(pb)
        cx, cy = 76, 68
        peak = 0.0
        for _ in range(90):
            live = shots(pb, AUX_STAR)
            if not live:
                break
            e = live[0]
            x, y = i16(pb, e, 3), i16(pb, e, 7)
            peak = max(peak, math.hypot(x - cx, y - cy))
            pb.tick()
        print(f"[star max-reset] second peak={peak:.1f} (max is {PEAK[3]})")
        # A little natural recharge may promote the empty bar to tier 1,
        # but it must not still be a max-radius swing.
        assert peak <= PEAK[1] + 2, (
            f"second swing still reached {peak}, want well below max {PEAK[3]}")
        assert pb.memory[P + LEVEL_OFFSET] == 0
    finally:
        pb.stop(save=False)


def test_star_obstacles():
    # Tile 13,9 is the east-peak sample with a south starting heading.
    cases = {
        "pillar": [(BGT_PILLAR, 13, 9)],
        "crystal": [(BGT_CRYSTAL, 13, 9)],
        "pot": [(BGT_POT, 13, 9)],
        "wall-tile": [(BGT_WALL, 13, 9)],
        "ring": [(BGT_PILLAR, 13, 9), (BGT_PILLAR, 9, 5),
                 (BGT_PILLAR, 6, 9), (BGT_PILLAR, 9, 13)],
    }
    for name, tiles in cases.items():
        rec = measure_star(0, 0, 0, tiles=tiles,
                           record=f"morningstar-obst-{name}.gif"
                           if name in ("pillar", "ring") else None)
        print(f"[star obst {name}] peak={rec['peak']:.1f} life={rec['life']}")
        assert rec["life"] >= 30, (name, rec["life"])
        assert_near(f"star obst {name} peak", rec["peak"], 24, 1.5)

    corner = measure_star(0, 0, 0, pos=(16, 16), walled=True,
                          record="morningstar-corner-t0.gif")
    print(f"[star corner t0] peak={corner['peak']:.1f} life={corner['life']}")
    assert corner["life"] >= 30, corner
    # Toward the open court the head still reaches full radius.
    assert corner["peak"] >= 22, corner

    corner_full = measure_star(1, 90, 0, pos=(16, 16), walled=True,
                               record="morningstar-corner-full.gif")
    print(f"[star corner full] peak={corner_full['peak']:.1f} "
          f"life={corner_full['life']}")
    assert corner_full["life"] >= 40, corner_full
    # Clamped on two sides, but the interior arc should still out-reach t0.
    assert corner_full["peak"] >= corner["peak"] - 0.5, (corner, corner_full)

    full_pillar = measure_star(1, 90, 0, tiles=[(BGT_PILLAR, 13, 9)],
                               record="morningstar-pillar-full.gif")
    print(f"[star pillar full] peak={full_pillar['peak']:.1f} "
          f"life={full_pillar['life']}")
    assert full_pillar["life"] >= 40
    assert_near("star pillar full peak", full_pillar["peak"], 39, 1.5)


def test_boom_tiers():
    results = {}
    setups = (
        (0, 0, 0, 0, "empty"),
        (0, 30, 0, 1, "one-third"),
        (1, 0, 7, 2, "banked-cap4"),
        (1, 90, 0, 3, "full-cap1"),
    )
    for level, charge, gear, tier, name in setups:
        rec = measure_boom(level, charge, gear, wide=True,
                           record=f"boomerang-tier{tier}-{name}.gif")
        print(f"[boom {name} t{tier}] travel={rec['travel']} max_x={rec['max_x']} "
              f"out={rec['outbound']} total={rec['total']} ret={rec['returned']} "
              f"spent={rec['spent']}")
        if tier >= 3:
            assert rec["spent"], (name, rec["before"], rec["after"])
        else:
            assert not rec["spent"], (name, rec["before"], rec["after"])
        assert rec["returned"], name
        # Allow a few frames of button latency; distance should land close
        # to the authored 3 px/tick table.
        assert_near(f"boom {name} travel", rec["travel"], OUT_PX[tier], 8)
        results[tier] = rec
    assert results[3]["travel"] > results[2]["travel"] + 20
    assert results[2]["travel"] > results[1]["travel"] + 16
    assert results[1]["travel"] > results[0]["travel"] + 16
    return results


def test_boom_obstacles():
    # Sample y is player.y+4+4 = 72, so row 9. Tile 8,9 sits ~36 px out.
    pillar = measure_boom(0, 0, 0, tiles=[(BGT_PILLAR, 8, 9)], wide=True,
                          record="boomerang-pillar-t0.gif")
    print(f"[boom pillar] travel={pillar['travel']} out={pillar['outbound']} "
          f"ret={pillar['returned']}")
    assert pillar["returned"]
    # Must pass the pillar and keep the empty-will throw (~84 px), not the
    # pre-fix 34 px bounce.
    assert pillar["travel"] >= 76, pillar

    wall = measure_boom(0, 0, 0, tiles=[(BGT_WALL, 8, 9)],
                        record="boomerang-wall-t0.gif")
    print(f"[boom wall] travel={wall['travel']} out={wall['outbound']} "
          f"ret={wall['returned']}")
    assert wall["returned"]
    # A true room wall still turns the disk around.
    assert wall["travel"] <= 50, wall

    full_pillar = measure_boom(1, 90, 0, tiles=[(BGT_PILLAR, 8, 9)], wide=True,
                               record="boomerang-pillar-full.gif")
    print(f"[boom pillar full] travel={full_pillar['travel']} "
          f"out={full_pillar['outbound']} ret={full_pillar['returned']}")
    assert full_pillar["returned"]
    assert full_pillar["travel"] >= 150, full_pillar


HOOK_PX = {0: 96, 1: 112, 2: 128, 3: 144}


def measure_hook(level, charge, waygear, pos=(24, 64), wide=False, record=None):
    pb = scene(ITEM_HOOK, x=pos[0], y=pos[1])
    frames = []
    try:
        set_will(pb, level, charge, waygear)
        before = (pb.memory[P + WILL_OFFSET], pb.memory[P + LEVEL_OFFSET])
        if wide:
            pb.memory[addr("_room_world_width")] = 208
        fire_right(pb)
        after = (pb.memory[P + WILL_OFFSET], pb.memory[P + LEVEL_OFFSET])
        pts = []
        for f in range(220):
            live = shots(pb, AUX_HOOK)
            if record is not None and f % 2 == 0:
                frames.append(grab(pb))
            if not live:
                break
            e = live[0]
            x, y = i16(pb, e, 3), i16(pb, e, 7)
            pts.append((f, x, y))
            pb.tick()
        xs = [p[1] for p in pts]
        travel = (max(xs) - (pos[0] + 4)) if xs else 0
        if record:
            save_gif(frames, GIF_DIR / record)
        return dict(travel=travel, max_x=max(xs) if xs else None,
                    total=len(pts),
                    returned=not shots(pb, AUX_HOOK) and bool(pts),
                    spent=(after[1] < before[1] or after[0] < before[0]),
                    before=before, after=after)
    finally:
        pb.stop(save=False)


def test_boom_max_resets():
    """A max-Will boomerang spends the bank; a second throw is not a max toss."""
    pb = scene(ITEM_BOOM, x=24, y=64)
    try:
        pb.memory[addr("_room_world_width")] = 208
        set_will(pb, 1, 90, 0)
        fire_right(pb)
        assert pb.memory[P + LEVEL_OFFSET] == 0, "max boom did not reset will_level"
        # fire_b ticks past the spend; will_charge_tick may add one natural
        # point depending on frame phase, so allow <= 1.
        assert pb.memory[P + WILL_OFFSET] <= 1, "max boom did not reset will_charge"
        for _ in range(240):
            if not shots(pb, AUX_BOOM):
                break
            pb.tick()
        assert pb.memory[P + LEVEL_OFFSET] == 0, "will_level banked back before second toss"
        fire_right(pb)
        xs = []
        for _ in range(220):
            live = shots(pb, AUX_BOOM)
            if not live:
                break
            xs.append(i16(pb, live[0], 3))
            pb.tick()
        travel = (max(xs) - 28) if xs else 0
        print(f"[boom max-reset] second travel={travel} (max is {OUT_PX[3]})")
        assert travel <= OUT_PX[1] + 12, (
            f"second toss still reached {travel}, want well below max {OUT_PX[3]}")
        assert pb.memory[P + LEVEL_OFFSET] == 0
    finally:
        pb.stop(save=False)


def test_hook_tiers():
    results = {}
    setups = (
        (0, 0, 0, 0, "empty"),
        (0, 30, 0, 1, "one-third"),
        (1, 0, 7, 2, "banked-cap4"),
        (1, 90, 0, 3, "full-cap1"),
    )
    for level, charge, gear, tier, name in setups:
        rec = measure_hook(level, charge, gear, wide=True,
                           record=f"hookshot-tier{tier}-{name}.gif")
        print(f"[hook {name} t{tier}] travel={rec['travel']} max_x={rec['max_x']} "
              f"total={rec['total']} ret={rec['returned']} spent={rec['spent']}")
        if tier >= 3:
            assert rec["spent"], (name, rec["before"], rec["after"])
        else:
            assert not rec["spent"], (name, rec["before"], rec["after"])
        assert rec["returned"], name
        assert_near(f"hook {name} travel", rec["travel"], HOOK_PX[tier], 16)
        results[tier] = rec
    assert results[3]["travel"] > results[2]["travel"] + 8
    assert results[2]["travel"] > results[1]["travel"] + 8
    assert results[1]["travel"] > results[0]["travel"] + 8
    return results


def test_hook_max_resets():
    """A max-Will hookshot spends the bank; a second shot is not a max reach."""
    pb = scene(ITEM_HOOK, x=24, y=64)
    try:
        pb.memory[addr("_room_world_width")] = 208
        set_will(pb, 1, 90, 0)
        fire_right(pb)
        assert pb.memory[P + LEVEL_OFFSET] == 0, "max hook did not reset will_level"
        # fire_b ticks past the spend; will_charge_tick may add one natural
        # point depending on frame phase, so allow <= 1.
        assert pb.memory[P + WILL_OFFSET] <= 1, "max hook did not reset will_charge"
        # Wait for the hook to fully retract; a mid-flight B only cancels it.
        for _ in range(240):
            if not shots(pb, AUX_HOOK):
                break
            pb.tick()
        assert not shots(pb, AUX_HOOK), "hookshot never retracted"
        assert pb.memory[P + LEVEL_OFFSET] == 0
        fire_right(pb)
        xs = []
        for _ in range(220):
            live = shots(pb, AUX_HOOK)
            if not live:
                break
            xs.append(i16(pb, live[0], 3))
            pb.tick()
        travel = (max(xs) - 28) if xs else 0
        print(f"[hook max-reset] second travel={travel} (max is {HOOK_PX[3]})")
        assert travel <= HOOK_PX[1] + 16, (
            f"second hook still reached {travel}, want well below max {HOOK_PX[3]}")
        assert pb.memory[P + LEVEL_OFFSET] == 0
    finally:
        pb.stop(save=False)


def main():
    test_star_tiers()
    test_star_max_resets()
    test_star_obstacles()
    test_boom_tiers()
    test_boom_obstacles()
    test_boom_max_resets()
    test_hook_tiers()
    test_hook_max_resets()
    print("[will-b-weapons] PASS morningstar/boomerang/hookshot will tiers and max-reset")


if __name__ == "__main__":
    main()
