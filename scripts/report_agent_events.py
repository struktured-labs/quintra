#!/usr/bin/env python3
"""Summarize controller debug events without treating final CSV guesses as truth.

Usage: python3 scripts/report_agent_events.py tmp/agent-debug
"""

import re
import sys
from collections import Counter
from pathlib import Path


HIT = re.compile(
    r"BOTHIT f=(\d+) room=(\d+)(?: world=(\d+):(\d+))? "
    r"hp=(\d+)->(\d+) src=(\d+)"
)
ABILITY = re.compile(r"BOTABILITY f=(\d+) class=(\d+) charge=(\d+) uses=(\d+)")
STATE = re.compile(r"BOTSTATE f=(\d+) room=(\d+).*?target=(\d+)@.*? slot=(\d+) stuck=(\d+)")


def describe(path: Path) -> str:
    hits = []
    abilities = 0
    worst_stuck = None
    for line in path.read_text(errors="replace").splitlines():
        if match := HIT.search(line):
            frame, room, world, _screen, before, after, source = match.groups()
            hits.append((int(frame), int(room), int(before) - int(after),
                         int(source), int(world or 0)))
        elif ABILITY.search(line):
            abilities += 1
        elif match := STATE.search(line):
            frame, room, kind, slot, stuck = map(int, match.groups())
            if worst_stuck is None or stuck > worst_stuck[-1]:
                worst_stuck = (frame, room, kind, slot, stuck)

    damage = sum(hit[2] for hit in hits)
    early = sum(hit[2] for hit in hits if hit[1] <= 2 and hit[4] == 0)
    boss_rooms = {9, 20, 32, 45, 58, 72, 87, 102, 118}
    boss = sum(hit[2] for hit in hits
               if hit[1] in boss_rooms and hit[4] == 0)
    world = sum(hit[2] for hit in hits if hit[4] != 0)
    dungeon = damage - world
    rooms = Counter(hit[1] for hit in hits)
    sources = Counter(hit[3] for hit in hits)
    room_text = "|".join(f"{room}:{count}" for room, count in sorted(rooms.items())) or "-"
    source_text = "|".join(f"{source}:{count}" for source, count in sorted(sources.items())) or "-"
    stuck_text = "-" if worst_stuck is None else (
        f"f{worst_stuck[0]} r{worst_stuck[1]} e{worst_stuck[2]}"
        f"#{worst_stuck[3]}:{worst_stuck[4]}")
    return (f"{path.name}: hits={len(hits)} damage={damage} dungeon={dungeon} "
            f"riftwild={world} early={early} boss={boss} ability_uses={abilities} "
            f"rooms={room_text} sources={source_text} worst_stuck={stuck_text}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: report_agent_events.py DEBUG_DIR")
    directory = Path(sys.argv[1])
    logs = sorted(directory.glob("*.log"))
    if not logs:
        raise SystemExit(f"no controller debug logs in {directory}")
    for path in logs:
        print("[agent-events] " + describe(path))


if __name__ == "__main__":
    main()
