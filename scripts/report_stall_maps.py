#!/usr/bin/env python3
"""Render controller ``BOTTILES`` debug records as compact ASCII room maps.

The balance pilot remains read-only: it records a tile snapshot after a live
combat room exceeds its watchdog. This helper decodes those snapshots offline,
so a policy investigation can distinguish a blocked lane from an aim/input
mistake without launching a frontend or mutating cartridge state.
"""

from __future__ import annotations

import argparse
import re
from collections.abc import Mapping
from pathlib import Path


TILES = {
    0: " ", 1: ".", 2: "#", 3: "D", 19: ".", 20: ".", 21: "P",
    22: "C", 23: ",", 24: "X", 25: "B", 28: "B", 29: "B", 30: "B",
    31: "^", 32: "O", 33: "S", 34: "@", 35: "g", 36: "+", 37: "R",
    38: "#", 39: "#",
}
RECORD = re.compile(
    r"BOTTILES f=(?P<frame>\d+) room=(?P<room>\d+) "
    r"p=(?P<px>\d+),(?P<py>\d+) cell=(?P<pcx>\d+),(?P<pcy>\d+) "
    r"target=(?P<kind>\d+)@(?P<tx>\d+),(?P<ty>\d+) "
    r"cell=(?P<tcx>\d+),(?P<tcy>\d+) map=(?P<map>[0-9A-F/]+)"
)


def decode(record: Mapping[str, str]) -> str:
    rows = [[int(row[i:i + 2], 16) for i in range(0, len(row), 2)]
            for row in record["map"].split("/")]
    if len(rows) != 17 or any(len(row) != 20 for row in rows):
        raise ValueError("BOTTILES map is not a 20x17 tile room")
    for y, row in enumerate(rows):
        for x, tile in enumerate(row):
            row[x] = TILES.get(tile, "?")
    # The controller uses feet-center cells; a target marker wins only when it
    # does not conceal the player marker, keeping immediate overlap obvious.
    px, py = int(record["pcx"]), int(record["pcy"])
    tx, ty = int(record["tcx"]), int(record["tcy"])
    if 0 <= ty < len(rows) and 0 <= tx < len(rows[ty]):
        rows[ty][tx] = "t"
    if 0 <= py < len(rows) and 0 <= px < len(rows[py]):
        rows[py][px] = "P" if (px, py) != (tx, ty) else "*"
    header = (
        f"{record['path']} frame={record['frame']} room={record['room']} "
        f"target={record['kind']}@{record['tx']},{record['ty']} "
        f"player={record['px']},{record['py']}"
    )
    return "\n".join([header, *("".join(row) for row in rows)])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("debug_dir", type=Path,
                        help="directory passed as QUINTRA_BALANCE_DEBUG_DIR")
    parser.add_argument("--last", action="store_true",
                        help="show only the final snapshot from each trial log")
    args = parser.parse_args()
    logs = sorted(args.debug_dir.glob("*.log"))
    if not logs:
        raise SystemExit(f"no debug logs in {args.debug_dir}")
    rendered: list[str] = []
    for log in logs:
        matches = list(RECORD.finditer(log.read_text(errors="replace")))
        if args.last:
            matches = matches[-1:]
        for match in matches:
            values = match.groupdict()
            values["path"] = log.name
            rendered.append(decode(values))
    if not rendered:
        raise SystemExit("no BOTTILES records found")
    print("\n\n".join(rendered))

if __name__ == "__main__":
    main()
