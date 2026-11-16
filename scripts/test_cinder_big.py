#!/usr/bin/env python3
"""Bigger Ember boss: 16x16 Kilnbacks, a 48x32 Cinder Rex that owns the OAM
tail (16..39), and background fire pools whose drawn square is the hazard.

Covers the body hitboxes (armor and contact), the 16x16 and 24x24 pools
(warning ring, lit flame, damage only inside the square, floor restored
afterwards) and the scanline layout that keeps shots visible over the boss.
"""
from test_boss_identity import EN, PL, addr, enter_boss, put16

WARN_P1, WARN_P2, FLASH = 24, 28, 6   # cinder_big.h pool fairness floors
from test_colossal_cinder import (CINDER_PHASE, CINDER_PATTERN, CINDER_TIMER,
                                  CINDER_X, CINDER_Y, CINDER_ALIVE,
                                  clear_hostiles, keep_alive, place_player_shot)

OAM = 0xFE00
HP, IFRAMES = 2, 15
F_TX, F_TY, F_SZ = addr("_cinder_fire_tx"), addr("_cinder_fire_ty"), addr("_cinder_fire_size")
F_DL, F_TTL = addr("_cinder_fire_delay"), addr("_cinder_fire_ttl")
OAM_END, OAM_LIMIT = addr("_cinder_oam_end"), addr("_cinder_oam_limit")
ORIGIN_X, ORIGIN_Y = addr("_room_bg_origin_x"), addr("_room_bg_origin_y")
CAM_X, CAM_Y = addr("_room_camera_x"), addr("_room_camera_y")


def sprite(pb, i):
    return [pb.memory[OAM + i * 4 + k] for k in range(4)]


def bg(pb, bank, x, y):
    saved = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = bank
    v = pb.memory[0x9800 + ((pb.memory[ORIGIN_Y] + y) & 31) * 32
                  + ((pb.memory[ORIGIN_X] + x) & 31)]
    pb.memory[0xFF4F] = saved
    return v


def hold(pb, boss, frames, pattern, timer, hp=110, clear=True):
    """Advance gameplay with the boss frozen on one beat of one attack."""
    for _ in range(frames):
        pb.memory[CINDER_PATTERN] = pattern
        pb.memory[CINDER_TIMER] = timer
        pb.memory[boss + 14] = hp
        if clear:
            clear_hostiles(pb)
        keep_alive(pb, 1)


def place_player(pb, cx, cy):
    """Put the champion's contact point (x+8, y+12) at a world pixel."""
    put16(pb, PL + 9, cx - 8)
    put16(pb, PL + 11, cy - 12)


def take_hit(pb, boss, cx, cy, pattern, timer, frames=4):
    before = pb.memory[PL + HP]
    for _ in range(frames):
        pb.memory[PL + HP] = before
        place_player(pb, cx, cy)
        pb.memory[CINDER_PATTERN] = pattern
        pb.memory[CINDER_TIMER] = timer
        pb.memory[boss + 14] = 110
        clear_hostiles(pb)
        pb.memory[PL + IFRAMES] = 0
        pb.tick()
        if pb.memory[PL + HP] < before:
            pb.memory[PL + HP] = before
            pb.memory[PL + IFRAMES] = 255
            return True
    pb.memory[PL + IFRAMES] = 255
    return False


def run_past(pb, boss, timer, hp=110):
    """Advance until the boss timer has run beat `timer` (pools appear)."""
    for _ in range(12):
        if pb.memory[CINDER_TIMER] > timer:
            return
        pb.memory[boss + 14] = hp
        keep_alive(pb, 1)
    raise AssertionError(f"boss timer stuck before {timer}")


def rex_box(pb):
    """World-space box of the visible Rex sprites (OAM 16..39)."""
    cam_x, cam_y = pb.memory[CAM_X], pb.memory[CAM_Y]
    vis = [sprite(pb, i) for i in range(16, 40)]
    vis = [s for s in vis if s[0] and s[1]]
    xs = [s[1] - 8 + cam_x for s in vis]
    ys = [s[0] - 16 + cam_y for s in vis]
    return vis, min(xs), min(ys), max(xs) + 8, max(ys) + 8


def main():
    pb, boss = enter_boss(2, keep_open=True)

    # ---- Act 1: five 16x16 Kilnbacks, four sprites each, OAM 4..23.
    keep_alive(pb, 4)
    assert pb.memory[CINDER_ALIVE] == 5
    assert pb.memory[OAM_END] == 24 and pb.memory[OAM_LIMIT] == 40
    quads = [sprite(pb, 4 + k) for k in range(4)]
    tiles = sorted(s[2] for s in quads)
    assert tiles in ([40, 41, 44, 45], [42, 43, 46, 47]), f"Kilnback quad: {tiles}"
    ys = sorted({s[0] for s in quads})
    assert len(ys) == 2 and ys[1] - ys[0] == 8, f"Kilnback is not 16px tall: {ys}"
    # The lower half is body armor too, not air under a 16x8 sliver.
    shot = place_player_shot(pb, pb.memory[CINDER_X] + 5, pb.memory[CINDER_Y] + 10)
    keep_alive(pb, 2)
    assert not (pb.memory[shot + 1] & 1), "shot passed the lower half of a Kilnback"
    # Kiln Press staggers the odd crucibles one body height behind the line.
    # While regrouping at most four bodies share a scanline, so the pack
    # plus the champion (2) still fits the GBC's ten (the old 16x8 phalanx
    # put all five, ten sprites, on one line).
    worst = 0
    for f in range(110):
        pb.memory[CINDER_PATTERN] = 1
        if f == 0:
            pb.memory[CINDER_TIMER] = 0
        pb.memory[boss + 14] = 200
        clear_hostiles(pb)
        keep_alive(pb, 1)
        rows = [0] * 160
        for i in range(4, 24):
            y = pb.memory[OAM + i * 4]
            if y and y < 160:
                for line in range(max(0, y - 16), y - 8):
                    rows[line] += 1
        worst = max(worst, max(rows))
    assert worst <= 8, f"Kiln Press stacked {worst} pack sprites on one line"
    # Kiln Press weave: on every row, two neighbouring crucibles (other than
    # the one vaulting across the lane) leave either no gap or a gap the
    # champion's contact point clears with room to spare (>= 12px).
    pinch = 99
    for f in range(110):
        pb.memory[CINDER_PATTERN] = 1
        if f == 0:
            pb.memory[CINDER_TIMER] = 0
        t = pb.memory[CINDER_TIMER]
        pb.memory[boss + 14] = 200
        clear_hostiles(pb)
        keep_alive(pb, 1)
        alive = pb.memory[CINDER_ALIVE]
        vault = alive >> 1 if 52 <= t < 92 else 99
        bodies = [(pb.memory[CINDER_X + i], pb.memory[CINDER_Y + i])
                  for i in range(alive) if i != vault]
        for row in range(8, 128):
            spans = sorted((x + 1, x + 15) for x, y in bodies if y + 4 <= row < y + 18)
            for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
                if b0 > a1:
                    pinch = min(pinch, b0 - a1)
    assert pinch >= 12, f"Kiln Press left a {pinch}px pinch between crucibles"
    # Every pack brand warns for at least WARN_P1 frames.
    seen = set()
    for f in range(200):
        pb.memory[CINDER_PATTERN] = 2
        if f == 0:
            pb.memory[CINDER_TIMER] = 0
            for k in range(8):
                pb.memory[F_TTL + k] = 0
        pb.memory[boss + 14] = 200
        clear_hostiles(pb)
        keep_alive(pb, 1)
        for k in range(8):
            key = (k, pb.memory[F_TX + k], pb.memory[F_TY + k])
            if pb.memory[F_TTL + k] and key not in seen:
                seen.add(key)
                assert pb.memory[F_DL + k] >= WARN_P1 - 2, (
                    f"pack brand warned only {pb.memory[F_DL + k]} frames")
    assert seen, "Brand pattern marked no pools"

    # ---- Act 2: Cinder Rex, 48x32, 24 bank-1 sprites at the OAM tail.
    pb.memory[boss + 14] = 120
    for _ in range(400):
        keep_alive(pb, 1)
        if pb.memory[CINDER_PHASE] == 2:
            break
    assert pb.memory[CINDER_PHASE] == 2, "Rex never unfolded"
    hold(pb, boss, 3, 1, 100)
    assert pb.memory[OAM_END] == 4 and pb.memory[OAM_LIMIT] == 16
    vis, x0, y0, x1, y1 = rex_box(pb)
    assert len(vis) == 24, f"Rex is not a 6x4 body: {len(vis)} sprites"
    assert all(s[3] & 0x08 and 64 <= s[2] < 112 for s in vis), "Rex left VRAM bank 1"
    assert (x1 - x0, y1 - y0) == (48, 32), f"Rex box {(x1 - x0, y1 - y0)}"
    assert len({s[2] for s in vis}) == 24, "Rex repeated a tile"

    # Armor: a shot into the far (tail) end of the body sparks while closed.
    flip = vis[0][3] & 0x20
    tail_x = x0 + 4 if flip else x1 - 8
    shot = place_player_shot(pb, tail_x, y0 + 14)
    hold(pb, boss, 2, 1, 100, clear=False)
    assert not (pb.memory[shot + 1] & 1), "shot passed through Rex's tail armor"

    # Contact: the body centre hurts; 2px past the drawn box never does.
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    assert take_hit(pb, boss, cx, cy, 1, 100), "Rex body centre did not hurt"
    assert not take_hit(pb, boss, x1 + 2, cy, 1, 100), "air beside Rex hurt"
    assert not take_hit(pb, boss, cx, y1 + 6, 1, 100), "air below Rex's feet hurt"
    # 36x24 contact box, biased down: a dropped 8px edge column or the top
    # spikes never hurt; just inside the box does.
    assert not take_hit(pb, boss, x0 + 5, cy, 1, 100), "Rex's left edge column hurt"
    assert not take_hit(pb, boss, x1 - 6, cy, 1, 100), "Rex's right edge column hurt"
    assert not take_hit(pb, boss, cx, y0 - 3, 1, 100), "Rex's top spikes hurt"
    assert take_hit(pb, boss, x0 + 7, cy, 1, 100), "Rex contact box lost its body"
    place_player(pb, 40, 112)

    # ---- Kiln Stomp: five 24x24 pools around the champion, painted in BG.
    for i in range(8):
        pb.memory[F_TTL + i] = 0
    hold(pb, boss, 4, 1, 100)
    place_player(pb, 120, 96)
    snapshot = {(x, y): (bg(pb, 0, x, y), bg(pb, 1, x, y))
                for y in range(1, 16) for x in range(1, 28)}
    pb.memory[CINDER_PATTERN] = 2
    pb.memory[CINDER_TIMER] = 19
    run_past(pb, boss, 20)
    live = [i for i in range(8) if pb.memory[F_TTL + i]]
    assert len(live) >= 5, f"Kiln Stomp marked {len(live)} pools"
    assert all(pb.memory[F_DL + i] >= WARN_P2 - 2 for i in live), (
        f"Rex pools warn < {WARN_P2}: {[pb.memory[F_DL + i] for i in live]}")
    assert all(pb.memory[F_SZ + i] == 3 for i in live), "Rex pools are not 24x24"
    i = live[0]
    tx, ty = pb.memory[F_TX + i], pb.memory[F_TY + i]
    cells = [(tx + cx_, ty + cy_) for cy_ in range(3) for cx_ in range(3)]
    for x, y in cells:
        assert bg(pb, 1, x, y) & 0x08 and 64 <= bg(pb, 0, x, y) <= 67, (
            f"warning ring not painted at {(x, y)}")
    # Keep only one pool. Its ring flashes over the last FLASH frames
    # (flame, ring, flame) and then it burns.
    for j in live[1:]:
        pb.memory[F_TTL + j] = 1
    pb.memory[F_DL + i] = FLASH + 2
    states = []
    for _ in range(FLASH + 2):
        hold(pb, boss, 1, 1, 100)
        t0 = bg(pb, 0, tx + 1, ty + 1)
        states.append((pb.memory[F_DL + i], "lit" if t0 >= 68 else "ring"))
    runs = [st for k, (_, st) in enumerate(states) if k == 0 or st != states[k - 1][1]]
    assert runs == ["ring", "lit", "ring", "lit"], (
        f"warning ring did not flash (flame, ring) before ignition: {states}")
    assert states[-1] == (0, "lit"), states
    assert all(d <= FLASH for d, st in states if st == "lit"), states
    pb.memory[F_TTL + i] = 200
    for x, y in cells:
        assert 68 <= bg(pb, 0, x, y) <= 71, f"lit flame not painted at {(x, y)}"
    left, top = tx * 8, ty * 8
    assert take_hit(pb, boss, left + 12, top + 12, 1, 100), "lit pool centre did not burn"
    assert take_hit(pb, boss, left + 3, top + 21, 1, 100), "lit pool corner did not burn"
    assert not take_hit(pb, boss, left - 1, top + 12, 1, 100), "fire left of the square burned"
    assert not take_hit(pb, boss, left + 12, top + 25, 1, 100), "fire below the square burned"

    # Expiry restores the exact floor (tile and attribute) under every pool.
    pb.memory[F_TTL + i] = 2
    hold(pb, boss, 4, 1, 100)
    assert not any(pb.memory[F_TTL + k] for k in range(8))
    changed = [c for c, v in snapshot.items()
               if (bg(pb, 0, *c), bg(pb, 1, *c)) != v]
    assert not changed, f"floor not restored under pools: {changed[:6]}"

    # ---- Corner seal: with Rex against a wall, Stomp and the slab-tail slam
    # keep their pools 16px off that wall, so a 16x16 escape strip along the
    # wall always stays clear beside the champion.
    W = pb.memory[addr("_room_world_width")] | pb.memory[addr("_room_world_width") + 1] << 8
    home = [pb.memory[boss + k] for k in (3, 4, 7, 8)]
    for side in ("left", "right"):
        # Move the body (anchor offset learned from the drawn box), then
        # stand by that wall so the camera shows both.
        _, bx0, _, _, _ = rex_box(pb) if side == "left" else (0, rex_x0, 0, 0, 0)
        anchor = pb.memory[boss + 3] | pb.memory[boss + 4] << 8
        if side == "left":
            rex_x0, off = bx0, anchor - bx0
        want = 8 if side == "left" else W - 8 - 48
        put16(pb, boss + 3, want + off)
        put16(pb, boss + 7, 52)
        place_player(pb, 30 if side == "left" else W - 30, 116)
        hold(pb, boss, 8, 1, 100)
        bx = (pb.memory[boss + 3] | pb.memory[boss + 4] << 8) - off
        by = (pb.memory[boss + 7] | pb.memory[boss + 8] << 8) - 9
        assert bx == want, f"Rex body not against the {side} wall: x={bx}"
        y1 = by + 32
        for pattern, timer, px, py in ((2, 19, 14 if side == "left" else W - 14, y1 + 14),
                                       (3, 87, 0, 0)):
            for k in range(8):
                pb.memory[F_TTL + k] = 0
            if px:
                place_player(pb, px, py)
            pb.memory[CINDER_PATTERN] = pattern
            pb.memory[CINDER_TIMER] = timer
            pb.memory[boss + 14] = 110
            clear_hostiles(pb)
            run_past(pb, boss, timer + 1)
            live = [k for k in range(8) if pb.memory[F_TTL + k]]
            assert live, f"{side} pattern {pattern} marked no pools"
            for k in live:
                l = pb.memory[F_TX + k] * 8
                r = l + pb.memory[F_SZ + k] * 8
                if side == "left":
                    assert l >= 8 + 16, f"pool at x={l} seals the left wall (pattern {pattern})"
                else:
                    assert r <= W - 8 - 16, f"pool to x={r} seals the right wall (pattern {pattern})"
            assert all(pb.memory[F_DL + k] >= WARN_P2 - 2 for k in live)
            for k in range(8):
                pb.memory[F_TTL + k] = 1
            hold(pb, boss, 2, 1, 100)
    for k, v in zip((3, 4, 7, 8), home):
        pb.memory[boss + k] = v
    place_player(pb, 120, 116)
    hold(pb, boss, 8, 1, 100)

    # ---- Furnace Breath: the wall passes behind the body, and every lane
    # sprite is ahead of the Rex block in OAM, so a crowded scanline drops a
    # boss edge rather than a shot.
    clear_hostiles(pb)
    pb.memory[CINDER_PATTERN] = 0
    pb.memory[CINDER_TIMER] = 35
    keep_alive(pb, 3)
    _, x0, y0, x1, y1 = rex_box(pb)
    lanes = []
    for k in range(32):
        ep = EN + k * 28
        if pb.memory[ep] == 1 and pb.memory[ep + 1] & 1 and not pb.memory[ep + 1] & 0x10:
            lanes.append(pb.memory[ep + 3] | pb.memory[ep + 4] << 8)
    assert 4 <= len(lanes) <= 8, f"Furnace Breath lanes: {lanes}"
    body_lanes = [x for x in lanes if x + 7 > x0 and x < x1]
    assert body_lanes, f"no lane crosses the Rex columns {x0}..{x1}: {lanes}"
    dropped = 0
    behind = 0
    for _ in range(90):
        pb.memory[boss + 14] = 110
        keep_alive(pb, 1)
        _, x0, y0, x1, y1 = rex_box(pb)
        for k in range(32):
            ep = EN + k * 28
            if pb.memory[ep] == 1 and pb.memory[ep + 1] & 1 and not pb.memory[ep + 1] & 0x10:
                lx = pb.memory[ep + 3] | pb.memory[ep + 4] << 8
                ly = pb.memory[ep + 7] | pb.memory[ep + 8] << 8
                if lx + 7 > x0 and lx < x1:
                    assert not (ly + 7 > y0 and ly < y1), (
                        f"a lane sprite sat on the Rex body at {(lx, ly)}")
                    behind += ly >= y1

        for line in range(144):
            on = [i for i in range(40)
                  if pb.memory[OAM + i * 4] and pb.memory[OAM + i * 4] < 160
                  and pb.memory[OAM + i * 4] - 16 <= line < pb.memory[OAM + i * 4] - 8]
            dropped += sum(1 for i in on[10:] if i < 16)
    assert behind, "no Furnace Breath lane continued behind the Rex"
    assert dropped == 0, f"{dropped} shot sprites lost a scanline to the Rex"
    pb.stop(save=False)
    print("[cinder-big] PASS 16x16 Kilnbacks (<=8 pack sprites per line), 48x32 bank-1 Rex at "
          "OAM 16..39, tail armor, body contact box, 24x24 BG pools "
          "(ring, flame, square-only burn, floor restored), 24/28f warnings with a "
          "6f flash, 16px wall strip kept clear, 36x24 contact, lanes pass behind Rex, "
          "no Kiln Press pinch")


if __name__ == "__main__":
    main()
