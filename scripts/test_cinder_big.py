#!/usr/bin/env python3
"""Bigger Ember boss: 16x16 Kilnbacks, a 48x32 Cinder Rex that owns the OAM
tail (16..39), and background fire pools whose drawn square is the hazard.

Covers the body hitboxes (armor and contact), the 16x16 and 24x24 pools
(warning ring, lit flame, damage only inside the square, floor restored
afterwards) and the scanline layout that keeps shots visible over the boss.
"""
from test_boss_identity import EN, PL, addr, enter_boss, put16
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
    keep_alive(pb, 2)
    live = [i for i in range(8) if pb.memory[F_TTL + i]]
    assert len(live) >= 5, f"Kiln Stomp marked {len(live)} pools"
    assert all(pb.memory[F_SZ + i] == 3 for i in live), "Rex pools are not 24x24"
    i = live[0]
    tx, ty = pb.memory[F_TX + i], pb.memory[F_TY + i]
    cells = [(tx + cx_, ty + cy_) for cy_ in range(3) for cx_ in range(3)]
    for x, y in cells:
        assert bg(pb, 1, x, y) & 0x08 and 64 <= bg(pb, 0, x, y) <= 67, (
            f"warning ring not painted at {(x, y)}")
    # Keep only one pool, light it, and hold it.
    for j in live[1:]:
        pb.memory[F_TTL + j] = 1
    pb.memory[F_DL + i] = 1
    hold(pb, boss, 2, 1, 100)
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

    # ---- Furnace Breath: the wall parts around the body, and every lane
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
    assert 3 <= len(lanes) <= 7, f"Furnace Breath lanes: {lanes}"
    assert not [x for x in lanes if x + 8 > x0 and x < x1], (
        f"a lane spawned inside the Rex body {x0}..{x1}: {lanes}")
    dropped = 0
    for _ in range(90):
        pb.memory[boss + 14] = 110
        keep_alive(pb, 1)
        for line in range(144):
            on = [i for i in range(40)
                  if pb.memory[OAM + i * 4] and pb.memory[OAM + i * 4] < 160
                  and pb.memory[OAM + i * 4] - 16 <= line < pb.memory[OAM + i * 4] - 8]
            dropped += sum(1 for i in on[10:] if i < 16)
    assert dropped == 0, f"{dropped} shot sprites lost a scanline to the Rex"
    pb.stop(save=False)
    print("[cinder-big] PASS 16x16 Kilnbacks (<=8 pack sprites per line), 48x32 bank-1 Rex at "
          "OAM 16..39, tail armor, body contact box, 24x24 BG pools "
          "(ring, flame, square-only burn, floor restored), wall parts around Rex")


if __name__ == "__main__":
    main()
