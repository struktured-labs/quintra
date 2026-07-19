#!/usr/bin/env python3
"""Summarize controller-only fatal-event telemetry from a balance CSV."""

import csv
import sys
from collections import Counter, defaultdict
from pathlib import Path


CLASSES = ("Wolfkin", "Sauran", "Corvin", "Picsean", "Vespine")

# Controller CSVs deliberately store compact content IDs, not strings. Keep
# their human-readable decoding in this host-only report so balance diagnosis
# never consumes cartridge ROM or changes a dense gameplay frame. The order is
# the typed registry order in content/src/enemies.rs.
ENEMY_NAMES = (
    "B. Crawler", "S. Sentinel", "Hornet", "Skeleton", "Orc", "Wisp",
    "Bomber", "Shade", "Warlock", "Rope", "Sentry", "Fold Star",
    "Flutterbat", "Gloom Leech", "Cinder Maw", "Rift Ooze", "Mirror Moth",
    "Mire Spore", "Echo Guard", "Rune Lantern", "Dread Bell", "Rift Warden",
    "Prism Skitter", "Dusk Midge", "Sunwheel", "Cinder Kite", "Bog Toad",
    "Gloam Bramble", "Frost Lancer", "Vine Coil",
)


def source_name(source: int) -> str:
    if source == 254:
        return "floor hazard"
    if source == 253:
        return "unresolved hostile"
    if 0 <= source < len(ENEMY_NAMES):
        return ENEMY_NAMES[source]
    return f"enemy-{source}"


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "tmp/endurance-runs.csv")
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    required = {
        "class", "min_hp", "death_source", "death_room", "death_bosses",
        "death_giant",
    }
    if not rows or not required.issubset(rows[0]):
        raise SystemExit("[fatal-report] CSV lacks fatal-event telemetry")

    by_class: dict[int, Counter[tuple[int, int, int, int, str]]] = defaultdict(Counter)
    for row in rows:
        if int(row["min_hp"]) != 0:
            continue
        class_id = int(row["class"])
        context = (
            int(row["death_room"]), int(row["death_bosses"]),
            int(row["death_giant"]), int(row["death_source"]),
            row.get("death_giant_overlap", "?"),
        )
        by_class[class_id][context] += 1

    print("[fatal-report] death contexts: room / bosses-cleared / giant-active / source")
    for class_id, name in enumerate(CLASSES):
        contexts = by_class[class_id]
        if not contexts:
            print(f"  {name}: no fatal rows")
            continue
        summary = ", ".join(
            f"r{room}/b{bosses}/g{giant}/{source_name(source)}"
            f"{' body' if overlap == '1' else ' pattern/nearby' if overlap == '0' and giant else ''} ×{count}"
            for (room, bosses, giant, source, overlap), count in sorted(contexts.items())
        )
        print(f"  {name}: {summary}")


if __name__ == "__main__":
    main()
