#!/usr/bin/env python3
"""Live-ROM: slower starting SPD, the raised SPD cap, and no wall clipping.

SPD is fifths of a pixel per frame. Starters are Wolfkin 6 (5 + its
FAST MOVEMENT perk), Vespine 6, Sauran/Corvin/Picsean 4. Run-earned SPD
caps at PLAYER_SPD_MAX = 12 (2.4 px/f). Movement is applied one
collision-checked pixel at a time, so even SPD 15 (3 px/f, beyond the cap
plus Haste) must stop flush against walls and pillars.
"""

from test_will_max import PLAYER, TILEMAP, boot, clear_arena, put16

SPD = 7
X, Y = 9, 11
MOVE_ACC = 23
BGT_WALL = 2
BGT_PILLAR = 21
EXPECTED_START = (6, 4, 4, 4, 6)   # Wolfkin, Sauran, Corvin, Picsean, Vespine


def pos(pb):
    def s16(a):
        v = pb.memory[a] | (pb.memory[a + 1] << 8)
        return v - 0x10000 if v & 0x8000 else v
    return s16(PLAYER + X), s16(PLAYER + Y)


def place(pb, x, y, spd):
    put16(pb, PLAYER + X, x)
    put16(pb, PLAYER + Y, y)
    pb.memory[PLAYER + MOVE_ACC] = 0
    pb.memory[PLAYER + SPD] = spd
    pb.tick(16)   # expire any double-tap dash window


def tile(pb, tx, ty, t):
    pb.memory[TILEMAP + ty * 20 + tx] = t


def hold(pb, buttons, frames, each=None):
    for b in buttons:
        pb.button_press(b)
    for _ in range(frames):
        pb.tick()
        if each:
            each(pos(pb))
    for b in buttons:
        pb.button_release(b)
    pb.tick(2)


def main():
    for hero, spd in enumerate(EXPECTED_START):
        pb = boot(hero)
        try:
            assert pb.memory[PLAYER + SPD] == spd, (hero, pb.memory[PLAYER + SPD], spd)
        finally:
            pb.stop(save=False)
    assert EXPECTED_START[0] == max(EXPECTED_START), "Wolfkin lost top speed"

    pb = boot(1)
    try:
        # Measured rate: 30 frames at SPD s covers s*30/5 pixels.
        rates = {}
        for spd in (4, 5, 6, 9, 12):
            clear_arena(pb)
            place(pb, 16, 72, spd)
            x0, _ = pos(pb)
            hold(pb, ["right"], 30)
            moved = pos(pb)[0] - x0
            want = spd * 30 // 5
            assert abs(moved - want) <= 2, (spd, moved, want)
            rates[spd] = moved / 30
        print("[speed-cap] px/frame", {k: round(v, 2) for k, v in rates.items()})

        # Walls at 3 px/f (SPD 15: above the cap, equal to cap + Haste).
        for spd in (12, 15):
            # Brick column at tile x=12 (px 96..103): feet box x+2..x+13.
            clear_arena(pb)
            for ty in range(17):
                tile(pb, 12, ty, BGT_WALL)
            place(pb, 16, 72, spd)
            hold(pb, ["right"], 50, lambda p: _assert(p[0] + 13 < 96, ("wall E", spd, p)))
            assert pos(pb)[0] == 82, ("not flush east", spd, pos(pb))
            place(pb, 120, 72, spd)
            hold(pb, ["left"], 50, lambda p: _assert(p[0] + 2 > 103, ("wall W", spd, p)))
            assert pos(pb)[0] == 102, ("not flush west", spd, pos(pb))

            # Brick row at tile y=6 (px 48..55): feet box y+8..y+15.
            clear_arena(pb)
            for tx in range(20):
                tile(pb, tx, 6, BGT_WALL)
            place(pb, 72, 100, spd)
            hold(pb, ["up"], 50, lambda p: _assert(p[1] + 8 > 55, ("wall N", spd, p)))
            assert pos(pb)[1] == 48, ("not flush north", spd, pos(pb))
            place(pb, 72, 4, spd)
            hold(pb, ["down"], 50, lambda p: _assert(p[1] + 15 < 48, ("wall S", spd, p)))
            assert pos(pb)[1] == 32, ("not flush south", spd, pos(pb))

            # A lone one-tile pillar is a full-body obstacle from every side.
            for buttons, start in ((["up"], (76, 110)), (["right"], (8, 76)),
                                   (["down"], (76, 4)), (["left"], (140, 76)),
                                   (["up", "right"], (40, 110))):
                clear_arena(pb)
                tile(pb, 10, 10, BGT_PILLAR)   # px 80..87, 80..87
                place(pb, start[0], start[1], spd)

                def no_overlap(p, spd=spd, buttons=buttons):
                    x, y = p
                    hit = any(80 <= x + dx <= 87 and 80 <= y + dy <= 87
                              for dx in (2, 8, 13) for dy in (0, 7, 8, 15))
                    assert not hit, ("pillar", spd, buttons, p)
                hold(pb, buttons, 50, no_overlap)
    finally:
        pb.stop(save=False)
    print("[speed-cap] PASS starters 6/4/4/4/6, SPD 4..12 rates, no clipping at 3 px/f")


def _assert(ok, msg):
    assert ok, msg


if __name__ == "__main__":
    main()
