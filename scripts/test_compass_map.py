#!/usr/bin/env python3
"""Live-ROM contract: SELECT renders the explored dungeon as a tile grid."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

SCREEN_ROOM = 5
SCREEN_MAP = 8
BGT_VOID = 0
BGT_FLOOR = 1
BGT_WALL = 2
BGT_SWITCH = 33


def addr(name: str) -> int:
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def map_tile(pb: PyBoy, x: int, y: int) -> int:
    # `set_bkg_tiles` writes the 0x9800 map. The Compass owns this map while
    # SELECT is open, so inspecting it proves a real tile-built grid rather
    # than a text-only status page or a host screenshot interpretation.
    return pb.memory[0x9800 + y * 32 + x]


def main() -> None:
    screen = addr("_loop_current_screen")
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(90):
        pb.tick()
    assert pb.memory[screen] == SCREEN_ROOM, "could not reach a live dungeon room"

    pb.button("select")
    for _ in range(30):
        pb.tick()
    assert pb.memory[screen] == SCREEN_MAP, "SELECT did not enter Spirit Compass"

    # Room 0 is the first seen dungeon node. Its 3x3 box begins at (1,3),
    # and the center is a bright switch/current-position marker. An unseen
    # later node remains blank, so the map visibly fills during exploration.
    assert map_tile(pb, 1, 3) == BGT_WALL, "Compass lost first-room tile border"
    assert map_tile(pb, 2, 4) == BGT_SWITCH, "Compass lost current-room marker"
    assert map_tile(pb, 3, 5) == BGT_WALL, "Compass room box is not 3x3"
    assert map_tile(pb, 7, 3) == BGT_VOID, "Compass revealed an unexplored room"
    assert map_tile(pb, 0, 0) == BGT_VOID, "Compass retained text-page background"

    pb.button("b")
    for _ in range(30):
        pb.tick()
    assert pb.memory[screen] == SCREEN_ROOM, "B did not return from Spirit Compass"
    pb.stop(save=False)
    print("[compass-map] PASS SELECT renders explored-room tile grid")


if __name__ == "__main__":
    main()
