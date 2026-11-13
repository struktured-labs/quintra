#!/usr/bin/env python3
"""Wolfkin's full-Will Moonfang Rush throws a wave and guards only his front.

Spec: docs/superpowers/specs/2026-11-12-wolfkin-will-wave.md
"""
import os
import re
from pathlib import Path

from test_will_max import (
    ENTITIES, ENTITY_SIZE, LEVEL_OFFSET, PLAYER, WILL_OFFSET,
    boot, clear_arena, fire_right, player_shots, put16,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


GUARD = addr("_wolfkin_wave_guard_ticks")
STATUS_KIND = addr("_enemy_status_kind")
STATUS_TICKS = addr("_enemy_status_ticks")
WAVE_TILES = range(200, 204)
QSTATUS_STOP = 4
ENEMY_BLUE_CRAWLER = 0
HP, IFRAMES, SHIELD = PLAYER + 2, PLAYER + 15, PLAYER + 20
PX, PY = 80, 72


def put_fix8(pb, address, pixels):
    raw = (pixels & 0xFFFF) << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def ent_x(pb, e):
    return pb.memory[e + 3] | (pb.memory[e + 4] << 8)


def ent_y(pb, e):
    return pb.memory[e + 7] | (pb.memory[e + 8] << 8)


def make_crawler(pb, slot, x, y, hp=200):
    """A poise-0 body, frozen by STOP so only hits can move it."""
    e = ENTITIES + slot * ENTITY_SIZE
    for i in range(ENTITY_SIZE):
        pb.memory[e + i] = 0
    pb.memory[e] = 2
    pb.memory[e + 1] = 0x07
    put_fix8(pb, e + 2, x)
    put_fix8(pb, e + 6, y)
    pb.memory[e + 12] = 20
    pb.memory[e + 14] = hp
    pb.memory[e + 16] = 120
    pb.memory[e + 17] = ENEMY_BLUE_CRAWLER
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = 1
    pb.memory[STATUS_KIND + slot] = QSTATUS_STOP
    pb.memory[STATUS_TICKS + slot] = 200
    return e


def make_shot(pb, slot, x, y, vx, vy):
    e = ENTITIES + slot * ENTITY_SIZE
    for i in range(ENTITY_SIZE):
        pb.memory[e + i] = 0
    pb.memory[e] = 1
    pb.memory[e + 1] = 0x03
    put_fix8(pb, e + 2, x)
    put_fix8(pb, e + 6, y)
    pb.memory[e + 10] = vx & 0xFF
    pb.memory[e + 11] = vy & 0xFF
    pb.memory[e + 12] = 28
    pb.memory[e + 14] = 1
    pb.memory[e + 16] = 90
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = 1
    return e


def arm(pb, will=True):
    pb.tick(60)                         # let rush/dash cooldowns expire
    clear_arena(pb)
    put16(pb, PLAYER + 9, PX)
    put16(pb, PLAYER + 11, PY)
    pb.memory[PLAYER + 13] = 1          # facing east
    pb.memory[HP] = pb.memory[PLAYER + 1]
    pb.memory[IFRAMES] = 0
    pb.memory[SHIELD] = 0
    pb.memory[PLAYER + WILL_OFFSET] = 90 if will else 0
    pb.memory[PLAYER + LEVEL_OFFSET] = 1 if will else 0
    pb.tick(2)
    pb.memory[IFRAMES] = 0


def fire_max(pb):
    """Fire east and stop on the frame the MAX commits (Will spent)."""
    pb.button_press("right")
    pb.button_press("a")
    for _ in range(40):
        pb.tick()
        if pb.memory[PLAYER + LEVEL_OFFSET] == 0:
            break
    pb.button_release("a")
    pb.button_release("right")
    assert pb.memory[PLAYER + LEVEL_OFFSET] == 0 and pb.memory[PLAYER + WILL_OFFSET] < 8, (
        "MAX did not fire")


def wave_pieces(pb):
    return [s for s in player_shots(pb) if pb.memory[s + 12] in WAVE_TILES]


def check(label, cond, detail=""):
    assert cond, f"{label} FAILED {detail}"
    print(f"  ok  {label}")


def main():
    pb = boot(0)
    try:
        # 1) The wave is a wide, strong hit in front, and does not shove.
        arm(pb)
        control = make_crawler(pb, 10, PX + 34, PY + 34)  # claw's 45deg lane
        flank = make_crawler(pb, 11, PX + 40, PY + 16)    # wave flank only
        cx, cy = ent_x(pb, control), ent_y(pb, control)
        fx, fy = ent_x(pb, flank), ent_y(pb, flank)
        fire_max(pb)
        pieces = wave_pieces(pb)
        check("wave: three crescent pieces in front", len(pieces) == 3,
              f"pieces={len(pieces)}")
        check("wave: pieces lead the hero eastward",
              all(ent_x(pb, s) > PX + 4 for s in pieces))
        check("wave: crescent art loaded into OBJ tiles 200-203",
              any(pb.memory[0, 0x8000 + 200 * 16 + i] for i in range(16)))
        tiles = set()
        # Knockback would shove a surviving body 3px along the hit's travel
        # on the very tick its HP drops; record each hit's displacement.
        flank_hits, control_hits = [], []
        last = {flank: (fx, fy, 200), control: (cx, cy, 200)}
        for _ in range(30):
            pb.tick()
            tiles |= {pb.memory[s + 12] for s in wave_pieces(pb)}
            for e, hits in ((flank, flank_hits), (control, control_hits)):
                x, y, hp = ent_x(pb, e), ent_y(pb, e), pb.memory[e + 14]
                px, py, php = last[e]
                if hp < php:
                    hits.append((x - px, y - py))
                last[e] = (x, y, hp)
        check("wave: two-cel animation", len(tiles & set(WAVE_TILES)) >= 2,
              f"tiles={sorted(tiles)}")
        check("wave: flank target off the claw lanes is hit", flank_hits,
              f"hp={pb.memory[flank + 14]}")
        check("wave: no knockback on a surviving target",
              all(d == (0, 0) for d in flank_hits), f"hits={flank_hits}")
        check("control: the ordinary claw lane still nudges (test is live)",
              any(d != (0, 0) for d in control_hits), f"hits={control_hits}")

        # 2) Frontal shield: a shot from the front is eaten during the rush.
        arm(pb)
        shot = make_shot(pb, 12, PX + 30, PY + 8, -2, 0)
        hp = pb.memory[HP]
        fire_max(pb)
        check("rush: no blanket i-frames", pb.memory[IFRAMES] == 0,
              f"iframes={pb.memory[IFRAMES]}")
        check("rush: frontal guard is up", pb.memory[GUARD] > 0)
        pb.tick(10)
        check("shield: frontal shot absorbed",
              not (pb.memory[shot] == 1 and pb.memory[shot + 1] & 1
                   and not pb.memory[shot + 1] & 0x10)
              and pb.memory[HP] == hp, f"hp {hp}->{pb.memory[HP]}")

        # 3) Frontal shield: a body met head-on during the rush deals nothing.
        arm(pb)
        body = make_crawler(pb, 13, PX + 14, PY + 8)
        hp = pb.memory[HP]
        fire_max(pb)
        # Step until the guard drops, tracking when the body dash stops.
        xs, guard_frames = [], 0
        for _ in range(80):
            pb.tick()
            xs.append(pb.memory[PLAYER + 9] | pb.memory[PLAYER + 10] << 8)
            if pb.memory[GUARD] == 0:
                break
            guard_frames += 1
            assert pb.memory[HP] == hp, "frontal body contact hurt during rush"
        check("shield: frontal body contact absorbed during the rush",
              guard_frames > 0, f"guard frames={guard_frames}")
        for _ in range(8):
            pb.tick()
            xs.append(pb.memory[PLAYER + 9] | pb.memory[PLAYER + 10] << 8)
        moving = [i for i in range(1, len(xs)) if xs[i] != xs[i - 1]]
        dash_end = moving[-1] if moving else 0
        # 5) The guard is the rush and only the rush: it holds through the
        # body dash's last step and falls on the next logic tick (room logic
        # runs every 2-4 host frames under a MAX's load).
        check("guard lasts exactly the rush",
              0 < (guard_frames + 1) - (dash_end + 1) <= 6,
              f"guard drop frame {guard_frames + 1}, last dash step {dash_end + 1}")
        check("after rush: no leftover i-frames", pb.memory[IFRAMES] == 0,
              f"iframes={pb.memory[IFRAMES]}")
        put_fix8(pb, body + 2,
                 (pb.memory[PLAYER + 9] | pb.memory[PLAYER + 10] << 8) + 6)
        put_fix8(pb, body + 6,
                 (pb.memory[PLAYER + 11] | pb.memory[PLAYER + 12] << 8) + 9)
        for _ in range(12):
            pb.tick()
            if pb.memory[HP] < hp:
                break
        check("after rush: contact hurts", pb.memory[HP] < hp,
              f"hp {hp}->{pb.memory[HP]}")

        # 4) Rear and side still hurt during the rush.
        for label, sx, sy, vx, vy in (("rear", PX, PY + 8, 3, 0),
                                      ("side", PX + 6, PY + 13, 3, 0)):
            arm(pb)
            hp = pb.memory[HP]
            fire_max(pb)
            # Drop the shot onto his body on the first dash frame.
            x = pb.memory[PLAYER + 9] | pb.memory[PLAYER + 10] << 8
            make_shot(pb, 14, x + (sx - PX), sy, vx, vy)
            for _ in range(6):
                pb.tick()
                if pb.memory[HP] < hp:
                    break
            check(f"shield: {label} shot hurts during the rush",
                  pb.memory[HP] < hp and pb.memory[GUARD] > 0,
                  f"hp {hp}->{pb.memory[HP]} guard={pb.memory[GUARD]}")

        # 6) Non-MAX play is unchanged: ordinary A has no wave or guard, and
        # the double-tap dodge keeps its own i-frames.
        arm(pb, will=False)
        fire_right(pb)
        check("non-MAX A: no wave, no guard",
              not wave_pieces(pb) and pb.memory[GUARD] == 0)
        arm(pb, will=False)
        pb.tick(30)
        for _ in range(2):
            pb.button_press("right"); pb.tick(2)
            pb.button_release("right"); pb.tick(2)
        check("dodge dash: keeps its i-frames", pb.memory[IFRAMES] >= 8,
              f"iframes={pb.memory[IFRAMES]}")
        check("dodge dash: no wave guard", pb.memory[GUARD] == 0)
    finally:
        pb.stop(save=False)
    print("[wolfkin-will-wave] PASS wave hits wide in front without knockback; "
          "frontal guard only during the rush; rear/side and post-rush hurt")


if __name__ == "__main__":
    main()
