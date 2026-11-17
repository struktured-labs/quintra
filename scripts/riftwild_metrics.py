#!/usr/bin/env python3
"""Audit metrics over capture_riftwild_wins.py JSON dumps.

  python3 scripts/riftwild_metrics.py DIR SEED_A SEED_B [SEED...]  (bosses=1)
"""
import json
import statistics
import sys
from collections import Counter
from pathlib import Path


def load(d, seed, b=1):
    data = json.loads((Path(d) / f"riftwild-{seed.lower()}-b{b}.json").read_text())
    return {int(k): v for k, v in data.items()}


def flat(tiles):
    return [t & 0x7F for row in tiles for t in row]


def same(a, b):
    return sum(x == y for x, y in zip(a, b)) / len(a)


def report(d, seeds):
    runs = [load(d, s) for s in seeds]
    cross = []
    for i in range(len(runs)):
        for j in range(i + 1, len(runs)):
            for f in range(36):
                cross.append(same(flat(runs[i][f]["tiles"]), flat(runs[j][f]["tiles"])))
    nearest, distinct, common, hostiles, poi = [], [], [], [], 0
    for r in runs:
        fl = {f: flat(r[f]["tiles"]) for f in r}
        for f in fl:
            nearest.append(max(same(fl[f], fl[g]) for g in fl if g != f))
            c = Counter(fl[f])
            distinct.append(len(c))
            common.append(c.most_common(1)[0][1] / len(fl[f]))
            hostiles.append(r[f]["hostiles"])
            if any(e["type"] == 3 for e in r[f]["entities"]):
                poi += 1
    n = len(runs)
    return {
        "cross_seed_identical_pct": round(100 * statistics.mean(cross), 1),
        "cross_seed_identical_min_pct": round(100 * min(cross), 1),
        "nearest_field_identical_pct": round(100 * statistics.mean(nearest), 1),
        "distinct_tile_types_mean": round(statistics.mean(distinct), 1),
        "most_common_tile_pct": round(100 * statistics.mean(common), 1),
        "hostiles_median": statistics.median(hostiles),
        "hostiles_max": max(hostiles),
        "quiet_fields_per_run": round(sum(h <= 2 for h in hostiles) / n, 1),
        "fields_with_poi_per_run": round(poi / n, 1),
        "empty_fields_per_run": round(36 - poi / n, 1),
    }


if __name__ == "__main__":
    print(json.dumps(report(sys.argv[1], sys.argv[2:]), indent=1))
