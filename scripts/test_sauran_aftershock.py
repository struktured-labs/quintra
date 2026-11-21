#!/usr/bin/env python3
"""Sauran L4 Aftershock: the lateral T-fault hits flanks the slam missed."""

from test_will_max import PLAYER, boot, clear_arena, put16
from test_will_max_v2 import (
    LIVE, TICK, arm, crawler, get16, press_max, put_fix8, run_art,
)

SAURAN = 1
LIFE = 64
SHADOW_OAM = None  # filled in main via the same addr helper as other tests


def _addr(name):
    from test_will_max import addr
    return addr(name)


def oam_y(pb, slot):
    return pb.memory[SHADOW_OAM + slot * 4]


def pin(pb, e, x, y):
    """Keep a fixture still and on-screen until the aftershock resolves."""
    put_fix8(pb, e + 2, x)
    put_fix8(pb, e + 6, y)
    pb.memory[e + 1] = 0x07          # ACTIVE|ALIVE|ON_SCREEN
    pb.memory[e + 10] = pb.memory[e + 11] = 0  # vx, vy
    pb.memory[e + 15] = 0            # state
    pb.memory[e + 16] = 0            # state_timer



def assert_oam_clear(pb, lo, hi, label):
    lit = [s for s in range(lo, hi) if oam_y(pb, s)]
    assert not lit, f"{label}: leftover OAM y in slots {lit}"


def east_cast(pb):
    """Lane dummy slammed and skipped; flanks take aftershock; far is safe."""
    clear_arena(pb)
    px = get16(pb, PLAYER + 9)
    py = get16(pb, PLAYER + 11)
    cx, cy = px + 8, py + 8
    lane = crawler(pb, 10, cx + 32, cy, hp=200)
    north = crawler(pb, 11, cx + 32, cy - 40, hp=200)
    south = crawler(pb, 12, cx + 32, cy + 34, hp=200)
    far = crawler(pb, 13, cx + 32, cy - 70, hp=200)
    pin(pb, lane, cx + 32, cy)
    pin(pb, north, cx + 32, cy - 40)
    pin(pb, south, cx + 32, cy + 34)
    pin(pb, far, cx + 32, cy - 70)
    pre = {}
    oam_mid = {}

    def on_tick():
        t = pb.memory[TICK]
        if t < 48:
            pin(pb, lane, cx + 32, cy)
            pin(pb, north, cx + 32, cy - 40)
            pin(pb, south, cx + 32, cy + 34)
            pin(pb, far, cx + 32, cy - 70)
        if t == 47 and not pre and pb.memory[LIVE]:
            pre["l"] = pb.memory[lane + 14]
            pre["n"] = pb.memory[north + 14]
            pre["s"] = pb.memory[south + 14]
            pre["f"] = pb.memory[far + 14]
        if t == 50 and not oam_mid and pb.memory[LIVE]:
            oam_mid["y"] = [oam_y(pb, s) for s in range(24, 36)]

    arm(pb)
    assert press_max_held(pb, "right"), "Sauran MAX did not fire"
    run_art(pb, SAURAN, limit=160, on_tick=on_tick)
    assert pb.memory[LIVE] == 0, "Aftershock art never ended"
    assert pre, "never saw tick 47 (slam done, aftershock not yet)"
    dmg_l = pre["l"] - pb.memory[lane + 14]
    dmg_n = pre["n"] - pb.memory[north + 14]
    dmg_s = pre["s"] - pb.memory[south + 14]
    dmg_f = pre["f"] - pb.memory[far + 14]
    print(f"    pre HP l/n/s/f={pre['l']}/{pre['n']}/{pre['s']}/{pre['f']} "
          f"aftershock dmg {dmg_l}/{dmg_n}/{dmg_s}/{dmg_f}")
    assert pre["n"] == 200 and pre["s"] == 200, (
        f"flanks were slammed early n={pre['n']} s={pre['s']}")
    assert dmg_l == 0, f"aftershock re-hit the slam victim ({dmg_l})"
    assert 1 <= dmg_n <= 12, f"north flank missed or overhit: {dmg_n}"
    assert 1 <= dmg_s <= 12, f"south flank missed or overhit: {dmg_s}"
    assert dmg_n == dmg_s, f"flank damage split {dmg_n} vs {dmg_s}"
    assert dmg_f == 0, f"far body should be outside +/-40: {dmg_f}"
    # Cosmetic wall uses the legacy 32..35 tail after pylons hide.
    if oam_mid:
        low = [i for i, y in enumerate(oam_mid["y"][:8]) if y]
        tail = [i for i, y in enumerate(oam_mid["y"][8:]) if y]
        assert not low, f"aftershock wall spilled into 24..31: {oam_mid['y']}"
        assert len(tail) >= 4, f"aftershock wall did not light 32..35: {oam_mid['y']}"
    assert_oam_clear(pb, 24, 36, "after east art ended")
    print(f"  ok  Aftershock flanks +{dmg_n} each, lane skipped, far safe")
    return dmg_n


def press_max_held(pb, *dirs):
    """Tap MAX while holding aim keys, but pin the hero so they don't walk
    off the fixture mid (down+right would otherwise shift a SE mid)."""
    from test_will_max_v2 import LEVEL_OFFSET
    x, y = get16(pb, PLAYER + 9), get16(pb, PLAYER + 11)
    for d in dirs:
        pb.button_press(d)
    pb.button_press("a")
    fired = False
    for _ in range(30):
        put16(pb, PLAYER + 9, x)
        put16(pb, PLAYER + 11, y)
        pb.tick()
        if pb.memory[PLAYER + LEVEL_OFFSET] == 0:
            fired = True
            break
    pb.button_release("a")
    for d in dirs:
        pb.button_release(d)
    put16(pb, PLAYER + 9, x)
    put16(pb, PLAYER + 11, y)
    pb.tick(2)
    return fired


def press_max_diag(pb):
    """Down-right + A so room_input_dir8 returns SE (dir 3)."""
    return press_max_held(pb, "right", "down")


def diag_cast(pb):
    """SE aim: flanks along the perpendicular at ~28 steps (~40 px)."""
    clear_arena(pb)
    # Keep mid and flanks inside the 160x136 court.
    put16(pb, PLAYER + 9, 48)
    put16(pb, PLAYER + 11, 40)
    px, py = 48, 40
    cx, cy = px + 8, py + 8
    mx, my = cx + 32, cy + 34
    # Perp for dx=1, dy=1 is qx=-1, qy=1.
    lane = crawler(pb, 10, mx, my, hp=200)
    a = crawler(pb, 11, mx - 28, my + 28, hp=200)
    b = crawler(pb, 12, mx + 28, my - 28, hp=200)
    far = crawler(pb, 13, mx - 50, my + 50, hp=200)
    pin(pb, lane, mx, my)
    pin(pb, a, mx - 28, my + 28)
    pin(pb, b, mx + 28, my - 28)
    pin(pb, far, mx - 50, my + 50)
    pre = {}

    def on_tick():
        t = pb.memory[TICK]
        if t < 48:
            pin(pb, lane, mx, my)
            pin(pb, a, mx - 28, my + 28)
            pin(pb, b, mx + 28, my - 28)
            pin(pb, far, mx - 50, my + 50)
        if t == 47 and not pre and pb.memory[LIVE]:
            pre["l"] = pb.memory[lane + 14]
            pre["a"] = pb.memory[a + 14]
            pre["b"] = pb.memory[b + 14]
            pre["f"] = pb.memory[far + 14]

    arm(pb)
    assert press_max_diag(pb), "Sauran SE MAX did not fire"
    run_art(pb, SAURAN, limit=160, on_tick=on_tick)
    assert pb.memory[LIVE] == 0, "SE Aftershock art never ended"
    assert pre, "SE cast never saw tick 47"
    dmg_l = pre["l"] - pb.memory[lane + 14]
    dmg_a = pre["a"] - pb.memory[a + 14]
    dmg_b = pre["b"] - pb.memory[b + 14]
    dmg_f = pre["f"] - pb.memory[far + 14]
    assert dmg_l == 0, f"SE aftershock re-hit the slam victim ({dmg_l})"
    assert 1 <= dmg_a <= 12, f"SE flank A missed or overhit: {dmg_a}"
    assert 1 <= dmg_b <= 12, f"SE flank B missed or overhit: {dmg_b}"
    assert dmg_a == dmg_b, f"SE flank damage split {dmg_a} vs {dmg_b}"
    assert dmg_f == 0, f"SE far body should be outside the wall: {dmg_f}"
    assert pre["a"] == 200 and pre["b"] == 200, (
        f"SE flanks were slammed early a={pre['a']} b={pre['b']}")
    assert_oam_clear(pb, 24, 36, "after SE art ended")
    print(f"  ok  SE Aftershock flanks +{dmg_a} each, lane skipped, far safe")


def main():
    global SHADOW_OAM
    SHADOW_OAM = _addr("_shadow_OAM")
    pb = boot(SAURAN)
    try:
        east_cast(pb)
        diag_cast(pb)
        _ = LIFE
    finally:
        pb.stop(save=False)


if __name__ == "__main__":
    main()
