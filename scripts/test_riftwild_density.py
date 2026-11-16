#!/usr/bin/env python3
"""Live-ROM contract: Riftwild fields hold a handful of foes, some none (audit L5).

Walks all 36 fields over real seams for three seeds and counts hostiles at
arrival. Waking fields stay within the seeded 3..6 band (region 1), about one
in four is quiet, and the band is seed-stable (a second walk of the same seed
matches). The Hollow counterpart stays the dangerous one.
"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture_riftwild_wins import cross_to, settle  # noqa: E402
from capture_riftwild_atlas import boot, entities  # noqa: E402
from test_overworld import RS  # noqa: E402
from test_riftwild_landmarks import ROUTE  # noqa: E402

SEEDS = (0x1234ABCD, 0x00C0FFEE, 0x7E57BEEF)
# Fixtures with their own population: Riftwell trader, arches (sealed or
# awake), the vault, Warden mini-boss fields and the old boss landmark.
FIXTURE_FIELDS = {1, 3, 8, 17, 21, 27, 29, 30, 34}


def walk(seed, hollow=False):
    pb = boot(seed, 1)
    counts = {}
    try:
        if hollow:
            pb.memory[RS + 57] |= 1
        else:
            settle(pb, 40)
            counts[0] = sum(e["type"] == 2 for e in entities(pb))
        for screen, x, y in ROUTE:
            cross_to(pb, screen, x, y)
            if screen not in counts:
                settle(pb, 40)
                counts[screen] = sum(e["type"] == 2 for e in entities(pb))
    finally:
        pb.stop(save=False)
    return counts


def main():
    summary = []
    for seed in SEEDS:
        counts = walk(seed)
        ordinary = {f: n for f, n in counts.items() if f not in FIXTURE_FIELDS}
        quiet = sum(1 for n in ordinary.values() if n == 0)
        busy = [n for n in ordinary.values() if n]
        assert max(ordinary.values()) <= 6, (hex(seed), ordinary)
        assert all(n >= 1 for n in busy), (hex(seed), ordinary)
        assert 3 <= quiet <= 13, (hex(seed), quiet, ordinary)
        assert 3 <= statistics.median(busy) <= 6, (hex(seed), busy)
        summary.append((hex(seed), quiet, statistics.median(list(counts.values())),
                        max(counts.values())))
    again = walk(SEEDS[0])
    first = walk(SEEDS[0])
    assert again == first, "density is not seed-stable"
    hollow = walk(SEEDS[0], hollow=True)
    hollow_ordinary = [n for f, n in hollow.items() if f not in FIXTURE_FIELDS]
    waking = [n for f, n in first.items() if f not in FIXTURE_FIELDS]
    assert sum(hollow_ordinary) > sum(waking), (hollow_ordinary, waking)
    assert max(hollow_ordinary) <= 8, hollow_ordinary
    assert statistics.median(hollow_ordinary) >= 5, hollow_ordinary
    print("[riftwild-density] PASS (seed, quiet fields, median, max):",
          summary, "hollow median", statistics.median(hollow_ordinary))


if __name__ == "__main__":
    main()
