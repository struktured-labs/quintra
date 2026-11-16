#!/usr/bin/env python3
"""Merchant rooms stay unmarked until visited, then the Compass shows a gold coin.

A Chart (dungeon_seen without dungeon_visited) must not leak the shop icon.
The Riftwild trader uses the same rule: ASK can reveal the Riftwell cell,
but the coin appears only after the field is entered.
"""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_START, dungeon_size


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SHOTS = ROOT / "tmp"
SHOTS.mkdir(exist_ok=True)

SCREEN_ROOM = 5
SCREEN_MAP = 8
BGT_VOID = 0
BGT_MAP_RIFT = 90
BGT_MAP_BIG_ROOM = 102
BGT_MAP_BIG_SHOP = 106
BGT_MAP_BIG_HERE = 110
BGT_MAP_SHOP = 127
BGT_MAP_LABEL_S = 67
BGT_MAP_LABEL_H = 101
BGT_MAP_LABEL_O = 65
BGT_MAP_LABEL_P = 94

# Stage-1 shop is local cell 17, a 2x2 node whose top-left is (4, 11).
GX = (1, 4, 7, 10, 13, 16,
      16, 13, 10, 7, 4, 1,
      1, 4, 7, 10, 13, 16,
      16, 13, 10, 7, 4, 1,
      1, 4, 7, 10, 13, 16)
GY = (2, 2, 2, 2, 2, 2,
      5, 5, 5, 5, 5, 5,
      8, 8, 8, 8, 8, 8,
      11, 11, 11, 11, 11, 11,
      14, 14, 14, 14, 14, 14)

# run_state field offsets. dungeon_visited starts at 53; world flags at 47.
RS_ROOM = 1
RS_BOSSES = 11
RS_WORLD_MODE = 17
RS_WORLD_SCREEN = 18
RS_SEEN = 20
RS_WORLD_SEEN = 21
RS_SEEN_HI = 29
RS_SEEN_XHI = 31
RS_SEEN_XXHI = 33
RS_FLAGS = 47
RS_VISITED = 53
RS_VISITED_HI = 54
RS_VISITED_XHI = 55
RS_VISITED_XXHI = 56
RIFT_TRADER_FOUND = 0x40
RIFTWELL_SCREEN = 1
# World grid: cell 1 is row 0, col 1 -> (3, 2).
WORLD_SHOP_X = 3
WORLD_SHOP_Y = 2


def addr(name: str) -> int:
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def map_tile(pb: PyBoy, x: int, y: int) -> int:
    return pb.memory[0x9800 + y * 32 + x]


def node_tile(pb: PyBoy, cell: int) -> int:
    return map_tile(pb, GX[cell], GY[cell])


def open_compass(pb: PyBoy, screen: int) -> None:
    pb.button_press("select")
    try:
        for _ in range(180):
            pb.tick()
            if pb.memory[screen] == SCREEN_MAP:
                for _ in range(90):
                    pb.tick()
                return
    finally:
        pb.button_release("select")
    raise AssertionError("SELECT did not enter Spirit Compass")


def close_compass(pb: PyBoy, screen: int, player: int) -> None:
    pb.button_press("b")
    try:
        for _ in range(180):
            pb.tick()
            if pb.memory[screen] == SCREEN_ROOM:
                break
        else:
            raise AssertionError("B did not return from Spirit Compass")
    finally:
        pb.button_release("b")
    for _ in range(90):
        pb.memory[player + 2] = 14
        pb.memory[player + 15] = 60
        pb.tick()


def set_cell_bit(pb: PyBoy, rs: int, seen_off: tuple, visited_off: tuple, cell: int, seen: bool, visited: bool) -> None:
    if cell < 8:
        s_off, v_off, bit = seen_off[0], visited_off[0], cell
    elif cell < 16:
        s_off, v_off, bit = seen_off[1], visited_off[1], cell - 8
    elif cell < 24:
        s_off, v_off, bit = seen_off[2], visited_off[2], cell - 16
    else:
        s_off, v_off, bit = seen_off[3], visited_off[3], cell - 24
    mask = 1 << bit
    if seen:
        pb.memory[rs + s_off] = pb.memory[rs + s_off] | mask
    else:
        pb.memory[rs + s_off] = pb.memory[rs + s_off] & (0xFF ^ mask)
    if visited:
        pb.memory[rs + v_off] = pb.memory[rs + v_off] | mask
    else:
        pb.memory[rs + v_off] = pb.memory[rs + v_off] & (0xFF ^ mask)


def boot() -> tuple[PyBoy, int, int, int]:
    screen = addr("_loop_current_screen")
    rs = addr("_run_state")
    player = addr("_player")
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
    return pb, screen, rs, player


def assert_shop_legend(pb: PyBoy) -> None:
    assert tuple(map_tile(pb, x, 16) for x in range(5)) == (
        BGT_MAP_SHOP, BGT_MAP_LABEL_S, BGT_MAP_LABEL_H,
        BGT_MAP_LABEL_O, BGT_MAP_LABEL_P), \
        "dungeon Compass lost its SHOP key"


def main() -> None:
    pb, screen, rs, player = boot()
    size = dungeon_size(0)
    shop = size - 3
    assert shop == 17, f"stage-1 merchant is no longer cell 17: {shop}"
    seen_off = (RS_SEEN, RS_SEEN_HI, RS_SEEN_XHI, RS_SEEN_XXHI)
    visited_off = (RS_VISITED, RS_VISITED_HI, RS_VISITED_XHI, RS_VISITED_XXHI)

    # Before any visit or chart, the merchant cell is blank.
    open_compass(pb, screen)
    assert_shop_legend(pb)
    assert node_tile(pb, shop) == BGT_VOID, \
        f"unvisited merchant cell already drawn: {node_tile(pb, shop)}"
    pb.screen.image.save(SHOTS / "merchant-map-before.png")
    close_compass(pb, screen, player)

    # A Chart reveals the room identity as an ordinary square, never the coin.
    set_cell_bit(pb, rs, seen_off, visited_off, shop, seen=True, visited=False)
    # Stay in the entry cell so HERE cannot be mistaken for the shop mark.
    pb.memory[rs + RS_ROOM] = STAGE_START[0]
    open_compass(pb, screen)
    assert node_tile(pb, shop) == BGT_MAP_BIG_ROOM, \
        f"charted unvisited merchant was {node_tile(pb, shop)}, not a plain room"
    assert node_tile(pb, shop) != BGT_MAP_BIG_SHOP, \
        "Chart leaked the merchant coin before the room was visited"
    pb.screen.image.save(SHOTS / "merchant-map-charted.png")
    close_compass(pb, screen, player)

    # After a real visit, looking from another room, the gold coin is present.
    set_cell_bit(pb, rs, seen_off, visited_off, shop, seen=True, visited=True)
    pb.memory[rs + RS_ROOM] = STAGE_START[0]
    open_compass(pb, screen)
    assert node_tile(pb, shop) == BGT_MAP_BIG_SHOP, \
        f"visited merchant cell was {node_tile(pb, shop)}, not the gold coin"
    assert node_tile(pb, 0) == BGT_MAP_BIG_HERE, \
        "entry marker was lost after the merchant visit"
    pb.screen.image.save(SHOTS / "merchant-map-after.png")
    close_compass(pb, screen, player)

    # Standing in the shop itself keeps the HERE pin; the coin waits until you leave.
    pb.memory[rs + RS_ROOM] = STAGE_START[0] + shop
    open_compass(pb, screen)
    assert node_tile(pb, shop) == BGT_MAP_BIG_HERE, \
        "standing in the shop hid the HERE pin"
    close_compass(pb, screen, player)

    # Riftwild: revealing the Riftwell by sight (ASK/chart equivalent) is not
    # enough. The coin appears only after the trader-found bit, which is set
    # on a real entry to that field.
    pb.memory[rs + RS_WORLD_MODE] = 1
    pb.memory[rs + RS_WORLD_SCREEN] = 0
    pb.memory[rs + RS_WORLD_SEEN] = pb.memory[rs + RS_WORLD_SEEN] | 0x03
    pb.memory[rs + RS_FLAGS] = pb.memory[rs + RS_FLAGS] & (0xFF ^ RIFT_TRADER_FOUND)
    open_compass(pb, screen)
    assert map_tile(pb, WORLD_SHOP_X, WORLD_SHOP_Y) == BGT_MAP_RIFT, \
        f"unvisited Riftwell trader leaked a shop mark: {map_tile(pb, WORLD_SHOP_X, WORLD_SHOP_Y)}"
    pb.screen.image.save(SHOTS / "merchant-map-riftwell-before.png")
    close_compass(pb, screen, player)

    pb.memory[rs + RS_FLAGS] = pb.memory[rs + RS_FLAGS] | RIFT_TRADER_FOUND
    open_compass(pb, screen)
    assert map_tile(pb, WORLD_SHOP_X, WORLD_SHOP_Y) == BGT_MAP_SHOP, \
        f"visited Riftwell trader was {map_tile(pb, WORLD_SHOP_X, WORLD_SHOP_Y)}, not the gold coin"
    assert tuple(map_tile(pb, x, 14) for x in range(13, 18)) == (
        BGT_MAP_SHOP, BGT_MAP_LABEL_S, BGT_MAP_LABEL_H,
        BGT_MAP_LABEL_O, BGT_MAP_LABEL_P), \
        "Riftwild Compass lost its SHOP key"
    pb.screen.image.save(SHOTS / "merchant-map-riftwell-after.png")

    pb.stop(save=False)
    print("[merchant-map] PASS coin hidden until visit, Chart does not leak, "
          f"Riftwild trader uses found-bit, shop_cell={shop}")


if __name__ == "__main__":
    main()
