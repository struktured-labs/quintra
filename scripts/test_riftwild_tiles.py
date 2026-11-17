#!/usr/bin/env python3
"""Riftwild tile tidy regression (docs/superpowers/specs/2026-11-17-riftwild-tile-tidy.md).

Walks all 36 Riftwild fields over real seams for several seeds (Waking and
Hollow) and checks, from VRAM:
  * no orphan 2x2 quarter: every tree/crag quarter sits in a whole metatile;
  * BG palette slots 0-4 share one colour 0 (no dark 8px prop boxes);
  * the field stays open and calm: open-floor minimum, prop clusters and
    one/two-cell props per field, and the share of marked ground cells.

  uv run --with pyboy==2.7.0 --with pillow python scripts/test_riftwild_tiles.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from riftwild_tile_audit import run  # noqa: E402

CASES = [(0x1234ABCD, False), (0x00C0FFEE, False), (0x7E57BEEF, False),
         (0x1234ABCD, True)]
OPEN_MIN = 78.0          # per field; was 77.5 before the tidy pass
OPEN_MEAN = 85.0         # was 83.1-83.9
PROPS_MEAN = {False: 9.0, True: 14.0}     # was 15.1 / 37.8
SINGLES_MEAN = {False: 4.0, True: 9.0}    # was 11.8 / 34.2
DETAIL_MEAN = 25.0       # was 100 (every ground cell carried texture)


def main():
    bad = []
    for seed, hollow in CASES:
        tag = f"{seed:08x}" + ("-hollow" if hollow else "")
        res = run(seed, hollow, None)
        n = len(res)
        if n != 36:
            bad.append(f"{tag}: visited {n}/36 fields")
        for screen, v in sorted(res.items()):
            for f in v["fragments"]:
                bad.append(f"{tag} field {screen}: orphan quarter {f}")
            if v["open_pct"] < OPEN_MIN:
                bad.append(f"{tag} field {screen}: open floor {v['open_pct']}% "
                           f"< {OPEN_MIN}%")
            if len(set(v["colour0"])) != 1:
                bad.append(f"{tag} field {screen}: BG colour 0 differs across "
                           f"slots 0-4: {[hex(c) for c in v['colour0']]}")
        mean = lambda k: sum(v[k] for v in res.values()) / max(n, 1)  # noqa: E731
        stats = (mean("open_pct"), mean("props"), mean("prop_singles"),
                 mean("detail_pct"))
        print(f"{tag}: open_mean={stats[0]:.1f}% props={stats[1]:.1f} "
              f"singles={stats[2]:.1f} marked={stats[3]:.1f}%")
        if stats[0] < OPEN_MEAN:
            bad.append(f"{tag}: open floor mean {stats[0]:.1f}% < {OPEN_MEAN}%")
        if stats[1] > PROPS_MEAN[hollow]:
            bad.append(f"{tag}: {stats[1]:.1f} prop clusters/field "
                       f"> {PROPS_MEAN[hollow]}")
        if stats[2] > SINGLES_MEAN[hollow]:
            bad.append(f"{tag}: {stats[2]:.1f} one/two-cell props/field "
                       f"> {SINGLES_MEAN[hollow]}")
        if stats[3] > DETAIL_MEAN:
            bad.append(f"{tag}: {stats[3]:.1f}% marked ground > {DETAIL_MEAN}%")
    if bad:
        print(f"FAIL: {len(bad)} problem(s)")
        for b in bad[:40]:
            print("  " + b)
        sys.exit(1)
    print("PASS: riftwild tiles tidy (0 orphan quarters, shared colour 0, open fields)")


if __name__ == "__main__":
    main()
