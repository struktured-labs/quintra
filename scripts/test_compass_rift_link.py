#!/usr/bin/env python3
"""The Compass rift-well mark sits on the rooms it joins, and is named (#265).

From the second dungeon on, local rooms 2 and 8 hold the two ends of a
rift-well warp. The Compass used to draw one violet diamond at map tile
(9, 4), the gap between those two nodes, as soon as either room was known.
With one end known that was a lone, unexplained marker floating between
rooms, and the dungeon legend had no entry for it.

Now each known end wears the diamond in the corner of its own node that
faces the other end ((8, 3) for room 2, (10, 5) for room 8). The gap tile
is drawn only when both ends are known, completing a diagonal that touches
both rooms. The hero's own node keeps its full YOU mark, and the legend
shows the diamond with the word RIFT whenever a diamond is on the map.
"""
from test_compass_map import (
    BGT_MAP_BIG_HERE, BGT_MAP_LABEL_F, BGT_MAP_LABEL_I, BGT_MAP_LABEL_R,
    BGT_MAP_LABEL_T, BGT_MAP_RIFT, ROOT, addr, close_compass, map_tile,
    node_tile, open_compass,
)
from quintra_topology import STAGE_START
from test_stage_archetypes import generated_room

BGPAL_CRYSTAL = 2
MARKS = {"room2": (8, 3), "gap": (9, 4), "room8": (10, 5)}
RIFT_KEY = [BGT_MAP_RIFT, BGT_MAP_LABEL_R, BGT_MAP_LABEL_I,
            BGT_MAP_LABEL_F, BGT_MAP_LABEL_T]
STAGE = 1          # second dungeon: the first with a rift well
SEEN_LO, SEEN_HI = 20, 29   # run_state dungeon cells 0..7 / 8..15 seen


def marks(pb):
    return {name: map_tile(pb, x, y) == BGT_MAP_RIFT
            for name, (x, y) in MARKS.items()}


def key(pb):
    return [map_tile(pb, 6 + i, 16) for i in range(5)]


def attr(pb, x, y):
    return pb.memory[1, 0x9800 + y * 32 + x] & 7


def main():
    screen, rs, player = map(addr, ("_loop_current_screen", "_run_state",
                                    "_player"))
    pb = generated_room(STAGE, 0xCAFE1234, local_room=1, keep_running=True)
    assert pb.memory[rs + 11] == STAGE, "not in the second dungeon"

    def view(here, lo, hi):
        pb.memory[rs + 1] = STAGE_START[STAGE] + here
        pb.memory[rs + SEEN_LO] = lo
        pb.memory[rs + SEEN_HI] = hi
        open_compass(pb, screen)
        got = marks(pb), key(pb), node_tile(pb, here)
        image = pb.screen.image.copy()
        close_compass(pb, screen, player)
        return (*got, image)

    none = {"room2": False, "gap": False, "room8": False}

    # Neither end known: nothing, and no key.
    got, legend, _here, _img = view(1, 0x03, 0x00)
    assert got == none, f"rift marks with neither end known: {got}"
    assert legend != RIFT_KEY, "RIFT key shown with no diamond to explain"

    # Only room 2 known, hero next door: the diamond is on room 2's node.
    # This is the reported case: it used to float in the gap at (9, 4).
    got, legend, _here, image = view(1, 0x07, 0x00)
    assert got == {"room2": True, "gap": False, "room8": False}, (
        f"a single known rift end must mark its own room, not the gap "
        f"between rooms: {got}")
    assert legend == RIFT_KEY, f"dungeon legend does not name RIFT: {legend}"
    image.save(ROOT / "tmp" / "compass-rift-one-end.png")

    # Only room 8 known.
    got, legend, _here, _img = view(1, 0x03, 0x01)
    assert got == {"room2": False, "gap": False, "room8": True}, got
    assert legend == RIFT_KEY

    # Standing in the only known end: its node stays a full YOU mark.
    got, legend, here, _img = view(2, 0x07, 0x00)
    assert got == none, f"rift mark drawn over the hero's node: {got}"
    assert here == BGT_MAP_BIG_HERE
    assert legend != RIFT_KEY

    # Both known, hero elsewhere: a three-diamond diagonal joins the rooms.
    pb.memory[rs + 1] = STAGE_START[STAGE] + 1
    pb.memory[rs + SEEN_LO], pb.memory[rs + SEEN_HI] = 0x07, 0x01
    open_compass(pb, screen)
    assert marks(pb) == {"room2": True, "gap": True, "room8": True}, marks(pb)
    assert key(pb) == RIFT_KEY
    for x, y in (*MARKS.values(), (6, 16)):
        assert attr(pb, x, y) == BGPAL_CRYSTAL, (
            f"rift mark at {(x, y)} is not on the violet palette")
    pb.screen.image.save(ROOT / "tmp" / "compass-rift-link.png")
    close_compass(pb, screen, player)

    # Standing on the far end: the rest of the link stays.
    got, legend, here, _img = view(8, 0x07, 0x01)
    assert got == {"room2": True, "gap": True, "room8": False}, got
    assert here == BGT_MAP_BIG_HERE and legend == RIFT_KEY

    pb.stop(save=False)
    print("[compass-rift-link] PASS rift diamonds sit on rooms 3 and 9, the "
          "gap fills only when both are known, YOU is never covered, and "
          "the legend names RIFT")


if __name__ == "__main__":
    main()
