#!/usr/bin/env python3
"""Headless MP economy vs bomb spam.

Measures throw rate, time-to-empty, trickle regen, and crystal-wisp
drops against continuous B-button bomb fire for every starting class.

Only mashes B when the current MP pool can afford the configured cost,
and re-asserts the equipped bomb so a failed press cannot park the
B-item picker. Bombs are thrown to the right so they do not explode
on the player.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("QUINTRA_ROOT", Path(__file__).resolve().parent))
if (ROOT / "scripts").is_dir():
    sys.path.insert(0, str(ROOT / "scripts"))
else:
    sys.path.insert(0, str(ROOT))
    ROOT = ROOT.parent

from test_will_max import (  # noqa: E402
    ROM, PLAYER as P, ENTITIES as E, TILEMAP as T,
    boot, clear_arena, put16, addr,
)

ITEM_BOMBS = 48
AUX_BOMB = 0xF7
BGT_CRYSTAL = 22
ENTITY_SIZE = 28
FPS = 60.0

# class_id: (name, mp_max, regen_frames)
CLASSES = {
    0: ("Wolfkin", 4, 144),
    1: ("Sauran", 3, 144),
    2: ("Corvin", 8, 144),
    3: ("Picsean", 10, 96),
    4: ("Vespine", 5, 144),
}


def bomb_slots(pb):
    return [
        E + i * ENTITY_SIZE
        for i in range(32)
        if pb.memory[E + i * ENTITY_SIZE] == 1
        and pb.memory[E + i * ENTITY_SIZE + 23] == AUX_BOMB
    ]


def give_bombs(pb, x=64, y=72, facing=1):
    clear_arena(pb)
    pb.memory[addr("_entity_enemy_count")] = 0
    pb.memory[P + 24] = ITEM_BOMBS  # inventory[0]
    pb.memory[P + 18] = ITEM_BOMBS  # active_item
    pb.memory[P + 19] = 0           # active_charge
    pb.memory[P + 13] = facing      # FACE_E
    put16(pb, P + 9, x)
    put16(pb, P + 11, y)
    pb.memory[P + 4] = pb.memory[P + 3]
    # Survive stray splash; keep the run ticking.
    pb.memory[P + 1] = 20
    pb.memory[P + 2] = 20
    pb.memory[P + 15] = 200  # iframes
    pb.tick(2)


def fire_right(pb):
    """Throw (not drop) a bomb to the east and leave B released."""
    pb.button_press("right")
    pb.button_press("b")
    pb.tick(2)
    pb.button_release("b")
    pb.button_release("right")
    pb.tick(1)


def place_crystals(pb, count=8):
    """Crystals along the east throw path from (64, 72)."""
    # Player at pixel (64, 72) ≈ tile (8, 9). Travel is only a short
    # outbound (state_timer starts at 48, movement while > 32).
    spots = [
        (10, 9), (11, 9), (12, 9), (13, 9),
        (11, 8), (12, 8), (11, 10), (12, 10),
    ]
    for tx, ty in spots[:count]:
        pb.memory[T + ty * 20 + tx] = BGT_CRYSTAL


def run_spam(pb, frames, cost):
    """Spam B whenever charge is 0 and MP can afford `cost`."""
    start_mp = pb.memory[P + 4]
    mp_max = pb.memory[P + 3]
    bombs = 0
    regen_gains = 0
    spent = 0
    first_empty = None
    first_cant_afford = None
    frames_at_zero = 0
    frames_cant_afford = 0
    prev_mp = start_mp
    prev_live = len(bomb_slots(pb))
    throws_at = []
    mp_series = []
    refused = 0

    f = 0
    while f < frames:
        # Keep bombs equipped and the player alive.
        pb.memory[P + 24] = ITEM_BOMBS
        pb.memory[P + 18] = ITEM_BOMBS
        if pb.memory[P + 2] < 10:
            pb.memory[P + 2] = 20
            pb.memory[P + 15] = 200

        charge = pb.memory[P + 19]
        mp = pb.memory[P + 4]
        if charge == 0 and mp >= cost:
            fire_right(pb)
            f += 3
        else:
            pb.tick(1)
            f += 1
            if charge == 0 and mp < cost:
                refused += 1

        mp = pb.memory[P + 4]
        live = len(bomb_slots(pb))
        if live > prev_live:
            bombs += live - prev_live
            throws_at.append(f)
        prev_live = live

        if mp < prev_mp:
            spent += prev_mp - mp
        elif mp > prev_mp:
            regen_gains += mp - prev_mp
        prev_mp = mp

        if mp == 0:
            frames_at_zero += 1
            if first_empty is None:
                first_empty = f
        if mp < cost:
            frames_cant_afford += 1
            if first_cant_afford is None:
                first_cant_afford = f
        if f == 1 or f % 30 == 0 or f >= frames:
            mp_series.append((min(f, frames), mp))

    elapsed = f
    minutes = elapsed / FPS / 60.0
    return {
        "frames": elapsed,
        "seconds": elapsed / FPS,
        "start_mp": start_mp,
        "mp_max": mp_max,
        "end_mp": pb.memory[P + 4],
        "bombs": bombs,
        "spent": spent,
        "mp_gains": regen_gains,
        "first_empty_s": None if first_empty is None else first_empty / FPS,
        "first_cant_afford_s": (
            None if first_cant_afford is None else first_cant_afford / FPS
        ),
        "seconds_at_zero": frames_at_zero / FPS,
        "seconds_cant_afford": frames_cant_afford / FPS,
        "bombs_per_min": bombs / minutes if minutes else 0.0,
        "cost_per_bomb": (spent / bombs) if bombs else None,
        "throws_at": throws_at,
        "mp_series": mp_series,
        "refused": refused,
    }


def fmt_row(name, r):
    empty = "never" if r["first_empty_s"] is None else f"{r['first_empty_s']:.2f}s"
    starve = (
        "never"
        if r["first_cant_afford_s"] is None
        else f"{r['first_cant_afford_s']:.2f}s"
    )
    cost = "n/a" if r["cost_per_bomb"] is None else f"{r['cost_per_bomb']:.2f}"
    return (
        f"{name:<22} {r['seconds']:6.1f}s  bombs={r['bombs']:3d}  "
        f"bpm={r['bombs_per_min']:5.1f}  spent={r['spent']:3d}  "
        f"gains={r['mp_gains']:3d}  start={r['start_mp']:2d}/{r['mp_max']:<2d}  "
        f"end={r['end_mp']:2d}  empty={empty:<8}  starve={starve:<8}  "
        f"at0={r['seconds_at_zero']:5.1f}s  cant={r['seconds_cant_afford']:5.1f}s  "
        f"cost/bomb={cost}"
    )


def measure_regen_only(class_id, seconds=30):
    """No bombs: confirm trickle interval. Temporarily raise cap so the
    rate is visible instead of clipping on a 3–10 MP starter pool."""
    pb = boot(class_id)
    clear_arena(pb)
    pb.memory[P + 3] = 20
    pb.memory[P + 4] = 0
    frames = int(seconds * FPS)
    gains = 0
    prev = 0
    ticks = []
    for f in range(frames):
        pb.tick(1)
        mp = pb.memory[P + 4]
        if mp > prev:
            gains += mp - prev
            ticks.append(f)
        prev = mp
    pb.stop()
    intervals = [b - a for a, b in zip(ticks, ticks[1:])]
    avg = (sum(intervals) / len(intervals)) if intervals else None
    return {
        "class_id": class_id,
        "seconds": seconds,
        "start_mp": 0,
        "end_mp": prev,
        "gains": gains,
        "intervals": intervals,
        "avg_interval": avg,
        "mp_per_min": gains / (seconds / 60.0),
    }


def measure_spam(class_id, seconds, cost, crystals=0, mp_max=None):
    pb = boot(class_id)
    give_bombs(pb)
    if mp_max is not None:
        pb.memory[P + 3] = mp_max
        pb.memory[P + 4] = mp_max
    if crystals:
        place_crystals(pb, crystals)
        pb.tick(2)
    result = run_spam(pb, int(seconds * FPS), cost)
    result["class_id"] = class_id
    result["name"] = CLASSES[class_id][0]
    result["crystals"] = crystals
    left = 0
    if crystals:
        for i in range(20 * 17):
            if pb.memory[T + i] == BGT_CRYSTAL:
                left += 1
    result["crystals_left"] = left
    result["crystals_broken"] = (crystals - left) if crystals else 0
    pb.stop()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=60.0)
    ap.add_argument("--regen-seconds", type=float, default=30.0)
    ap.add_argument("--cost", type=int, default=1, help="MP required to mash B")
    ap.add_argument("--label", default="before")
    args = ap.parse_args()

    print(f"ROM={ROM}  label={args.label}  mash_cost={args.cost}", flush=True)
    print("=== trickle regen (no bombs, cap=20, start MP=0) ===", flush=True)
    regen_rows = []
    for cid, (name, mp_max, expect) in CLASSES.items():
        r = measure_regen_only(cid, seconds=args.regen_seconds)
        regen_rows.append(r)
        avg = "n/a" if r["avg_interval"] is None else f"{r['avg_interval']:.1f}f"
        print(
            f"  {name:<8} gains={r['gains']:2d} in {r['seconds']:.0f}s  "
            f"mp/min={r['mp_per_min']:.1f}  avg_interval={avg}  "
            f"(code expects {expect}f / {60.0 * FPS / expect:.1f} mp/min)  "
            f"end={r['end_mp']}",
            flush=True,
        )

    print(
        f"=== empty-room bomb spam ({args.seconds:.0f}s, regen only) ===",
        flush=True,
    )
    spam_rows = []
    for cid, (name, mp_max, expect) in CLASSES.items():
        r = measure_spam(cid, seconds=args.seconds, cost=args.cost, crystals=0)
        spam_rows.append(r)
        print("  " + fmt_row(name, r), flush=True)

    print(
        f"=== crystal-room bomb spam ({args.seconds:.0f}s, 8 crystals, 25% wisp) ===",
        flush=True,
    )
    crystal_rows = []
    for cid in (0, 3, 4):
        r = measure_spam(
            cid, seconds=args.seconds, cost=args.cost, crystals=8
        )
        crystal_rows.append(r)
        print(
            "  "
            + fmt_row(CLASSES[cid][0] + "+8xtal", r)
            + f"  broke={r['crystals_broken']}/{r['crystals']}",
            flush=True,
        )

    print("=== late-run Picsean (mp_max=16) empty-room spam ===", flush=True)
    late = measure_spam(
        3, seconds=args.seconds, cost=args.cost, crystals=0, mp_max=16
    )
    print("  " + fmt_row("Picsean@16", late), flush=True)

    print("=== TSV ===")
    print(
        "label\tscenario\tclass\tmp_max\tseconds\tbombs\tbpm\tspent\t"
        "gains\tend_mp\tfirst_empty_s\tfirst_cant_afford_s\t"
        "seconds_at_zero\tseconds_cant_afford\tcost_per_bomb\tcrystals_broken"
    )

    def emit(scenario, r, name=None):
        empty = "" if r["first_empty_s"] is None else f"{r['first_empty_s']:.2f}"
        starve = (
            ""
            if r.get("first_cant_afford_s") is None
            else f"{r['first_cant_afford_s']:.2f}"
        )
        cost = "" if r["cost_per_bomb"] is None else f"{r['cost_per_bomb']:.2f}"
        print(
            f"{args.label}\t{scenario}\t{name or r.get('name','')}\t"
            f"{r['mp_max']}\t{r['seconds']:.1f}\t{r['bombs']}\t"
            f"{r['bombs_per_min']:.2f}\t{r['spent']}\t{r['mp_gains']}\t"
            f"{r['end_mp']}\t{empty}\t{starve}\t"
            f"{r['seconds_at_zero']:.2f}\t{r.get('seconds_cant_afford', 0):.2f}\t"
            f"{cost}\t{r.get('crystals_broken', 0)}"
        )

    for cid, r in zip(CLASSES, regen_rows):
        fake = {
            "mp_max": 20,
            "seconds": r["seconds"],
            "bombs": 0,
            "bombs_per_min": 0.0,
            "spent": 0,
            "mp_gains": r["gains"],
            "end_mp": r["end_mp"],
            "first_empty_s": None,
            "first_cant_afford_s": None,
            "seconds_at_zero": 0.0,
            "seconds_cant_afford": 0.0,
            "cost_per_bomb": None,
            "crystals_broken": 0,
        }
        emit("regen-only", fake, CLASSES[cid][0])
    for r in spam_rows:
        emit("empty-spam", r)
    for r in crystal_rows:
        emit("crystal-spam", r)
    emit("empty-spam-late", late, "Picsean")


if __name__ == "__main__":
    main()
