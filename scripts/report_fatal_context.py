#!/usr/bin/env python3
"""Summarize controller-only fatal-event telemetry from a balance CSV."""

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


CLASSES = ("Wolfkin", "Sauran", "Corvin", "Picsean", "Vespine")


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "tmp/endurance-runs.csv")
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {"class", "min_hp", "death_room", "death_bosses", "death_giant"}
    if not rows or not required.issubset(rows[0]):
        raise SystemExit("[fatal-report] CSV lacks fatal-event telemetry")

    by_class: dict[int, Counter[tuple[int, int, int]]] = defaultdict(Counter)
    for row in rows:
        if int(row["min_hp"]) != 0:
            continue
        class_id = int(row["class"])
        context = (int(row["death_room"]), int(row["death_bosses"]), int(row["death_giant"]))
        by_class[class_id][context] += 1

    print("[fatal-report] death contexts: room / bosses-cleared / giant-active")
    for class_id, name in enumerate(CLASSES):
        contexts = by_class[class_id]
        if not contexts:
            print(f"  {name}: no fatal rows")
            continue
        summary = ", ".join(
            f"r{room}/b{bosses}/g{giant} ×{count}"
            for (room, bosses, giant), count in sorted(contexts.items())
        )
        print(f"  {name}: {summary}")


if __name__ == "__main__":
    main()
