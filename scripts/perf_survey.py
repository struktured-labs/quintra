#!/usr/bin/env python3
"""Headless frame-rate survey across Quintra's hot scenarios.

fps = loop_frame_counter advance per LCD frame x 60 (the room loop runs at
most once per frame in CGB double speed, so 60 means no slowdown). For each
scenario we report the average over its window and the worst sliding window
(30 frames = half a second), which is what a player feels as a hitch.

    QUINTRA_TEST_ROM=... python scripts/perf_survey.py [--json out.json] [filter...]
"""
import json
import sys
import traceback

from test_will_max import (PLAYER, ENTITIES, ENTITY_SIZE, WILL_OFFSET,
                           LEVEL_OFFSET, WILL_MAX, addr, boot, clear_arena,
                           put16)

CLOCK = addr("_loop_frame_counter")
ENEMY_COUNT = addr("_entity_enemy_count")
WINDOW = 30


def loops(pb):
    return pb.memory[CLOCK] | (pb.memory[CLOCK + 1] << 8)


def keep_alive(pb):
    pb.memory[PLAYER + 2] = pb.memory[PLAYER + 1]     # hp = max


def measure(pb, frames, each=None, until=None):
    """Tick `frames` LCD frames; returns per-frame loop advances."""
    adv, prev = [], loops(pb)
    for f in range(frames):
        keep_alive(pb)
        if each:
            each(f)
        pb.tick()
        cur = loops(pb)
        adv.append((cur - prev) & 0xFFFF)
        prev = cur
        if until and f >= WINDOW and until():
            break
    return adv


def summarize(adv):
    n = len(adv)
    avg = 60.0 * sum(adv) / max(1, n)
    w = min(WINDOW, n)
    worst = min(sum(adv[i:i + w]) for i in range(0, n - w + 1)) * 60.0 / w
    return round(avg, 1), round(worst, 1), n


def put_fix8(pb, a, px):
    raw = (px & 0xFFFF) << 8
    for i in range(4):
        pb.memory[a + i] = (raw >> (i * 8)) & 0xFF


def enemy(pb, slot, x, y, eid=0, tile=20, hp=200, phase=0):
    e = ENTITIES + slot * ENTITY_SIZE
    for i in range(ENTITY_SIZE):
        pb.memory[e + i] = 0
    pb.memory[e] = 2
    pb.memory[e + 1] = 0x07
    put_fix8(pb, e + 2, x)
    put_fix8(pb, e + 6, y)
    pb.memory[e + 12] = tile
    pb.memory[e + 13] = 4
    pb.memory[e + 14] = hp
    pb.memory[e + 16] = 120
    pb.memory[e + 17] = eid
    pb.memory[e + 18] = phase
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = 1
    pb.memory[e + 27] = 4 + slot
    return e


def crowd(pb, n, eid=0, tile=20, x0=16, y0=16, skip_slots=()):
    slot = 0
    placed = 0
    while placed < n:
        if slot not in skip_slots:
            enemy(pb, slot, x0 + (placed % 5) * 28, y0 + (placed // 5) * 28,
                  eid=eid, tile=tile, phase=(placed * 7) % 60)
            placed += 1
        slot += 1
    pb.memory[ENEMY_COUNT] = n


# ---------------------------------------------------------------- scenarios

def sc_crowd(n, eid=0, tile=20):
    def run():
        pb = boot(0)
        try:
            clear_arena(pb)
            crowd(pb, n, eid, tile)
            pb.tick(30)
            return measure(pb, 300)
        finally:
            pb.stop(save=False)
    return run


def sc_opening():
    pb = boot(0)
    try:
        pb.tick(30)
        return measure(pb, 300)
    finally:
        pb.stop(save=False)


def sc_maxwill(cid, foes=8):
    def run():
        from test_will_max_v2 import arm, press_max, LIVE
        pb = boot(cid)
        try:
            clear_arena(pb)
            crowd(pb, foes, x0=40, y0=24)
            pb.tick(10)
            arm(pb)
            start = loops(pb)
            if not press_max(pb):
                raise RuntimeError("MAX did not fire")
            # press_max ticks up to 32 frames itself; measure the art.
            return measure(pb, 150, until=lambda: pb.memory[LIVE] == 0)
        finally:
            pb.stop(save=False)
    return run


def sc_spell(cid, hold, foes=6):
    def run():
        import test_magic as tm
        pb = boot(cid)
        try:
            tm.arena(pb)
            crowd(pb, foes, x0=96, y0=24, skip_slots=(31,))
            pb.memory[ENEMY_COUNT] = foes + 1
            pb.tick(4)
            if hold:
                pb.button_press("b")
                adv = measure(pb, tm.HOLD_FRAMES + 6)
                pb.button_release("b")
            else:
                pb.button_press("right"); pb.tick(2)
                pb.button_press("b"); pb.tick(3)
                pb.button_release("b"); pb.tick(1)
                pb.button_release("right")
                adv = []
            return adv + measure(pb, 90)
        finally:
            pb.stop(save=False)
    return run


def sc_bweapon(item, foes=6):
    def run():
        P = PLAYER
        pb = boot(0)
        try:
            clear_arena(pb)
            pb.memory[P + 24] = item
            pb.memory[P + 18] = item
            pb.memory[P + 19] = 0
            pb.memory[P + 13] = 1
            put16(pb, P + 9, 24)
            put16(pb, P + 11, 64)
            crowd(pb, foes, x0=72, y0=24)
            pb.tick(2)
            pb.memory[P + LEVEL_OFFSET] = 4
            pb.memory[P + WILL_OFFSET] = WILL_MAX
            pb.button_press("b"); pb.tick(2); pb.button_release("b")
            return measure(pb, 90)
        finally:
            pb.stop(save=False)
    return run


def sc_boss(stage):
    def run():
        from test_boss_identity import enter_boss
        pb, boss = enter_boss(stage, keep_open=True)
        try:
            put16(pb, PLAYER + 9, 72)
            put16(pb, PLAYER + 11, 104)
            # Phase 2 pressure: the busiest native pattern set.
            pb.memory[boss + 14] = pb.memory[boss + 23] >> 1
            # Let the forced phase change finish (S8/S9 rebuild the arena
            # with the display off for ~27 frames) before timing combat.
            measure(pb, 120)
            return measure(pb, 600)
        finally:
            pb.stop(save=False)
    return run


ITEM_BOOM, ITEM_HOOK, ITEM_STAR = 45, 46, 47
HEROES = ("Wolfkin", "Sauran", "Corvin", "Picsean", "Vespine")
BOSSES = {2: "Cinder Rex (S3)", 8: "Hexa Dragmar (S9)"}

SCENARIOS = [("opening room (generated)", sc_opening),
             ("16 crawlers fixed", sc_crowd(16)),
             ("Fold Star x6 (stage 3)", sc_crowd(6, eid=11, tile=72)),
             ("Fold Star x10 (stage 3)", sc_crowd(10, eid=11, tile=72))]
SCENARIOS += [(f"max-Will {h} +8 foes", sc_maxwill(c)) for c, h in enumerate(HEROES)]
SCENARIOS += [(f"spell {h} {'hold' if hd else 'tap'} +6 foes", sc_spell(c, hd))
              for c, h in enumerate(HEROES) for hd in (0, 1)]
SCENARIOS += [("B max boomerang +6", sc_bweapon(ITEM_BOOM)),
              ("B max hookshot +6", sc_bweapon(ITEM_HOOK)),
              ("B max morning star +6", sc_bweapon(ITEM_STAR))]
SCENARIOS += [(f"boss S{s + 1} {BOSSES.get(s, '')}".strip(), sc_boss(s)) for s in range(9)]


def main(argv):
    out = None
    if "--json" in argv:
        k = argv.index("--json")
        out = argv[k + 1]
        argv = argv[:k] + argv[k + 2:]
    filt = [a.lower() for a in argv]
    rows = []
    for name, fn in SCENARIOS:
        if filt and not any(f in name.lower() for f in filt):
            continue
        try:
            avg, worst, n = summarize(fn())
            rows.append(dict(scenario=name, avg=avg, worst=worst, frames=n))
            print(f"[survey] {name:38s} avg {avg:5.1f}  worst0.5s {worst:5.1f}  ({n}f)", flush=True)
        except Exception as exc:
            rows.append(dict(scenario=name, error=repr(exc)))
            print(f"[survey] {name:38s} ERROR {exc!r}", flush=True)
            traceback.print_exc()
    if out:
        with open(out, "w") as fh:
            json.dump(rows, fh, indent=1)
    return rows


if __name__ == "__main__":
    main(sys.argv[1:])
