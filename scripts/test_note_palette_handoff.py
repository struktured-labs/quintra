#!/usr/bin/env python3
"""Note-plate colours never leak onto doors or a neighbouring room (#252).

The music puzzle borrows the crystal and door BG palette slots for its
plates. Two paths used to let those borrowed colours escape:

  * Solving the phrase unsealed the exits on the crystal/door slots, so the
    opened objective door (two tiles side by side) turned plate blue until
    the next full redraw put it back on the amber slot.
  * A door slide shows both rooms at once. The note colours stayed loaded
    while leaving, and were loaded early while entering, so the other
    room's crystals, doors and pots flashed in note colours for the slide.

This locks both: an opened door keeps the attribute every redraw gives it,
and the two slots hold the stage palettes for the whole of any slide.
"""
from test_puzzles import (
    KIND, LOCKED, PL, RS, RUNE_PAL_HIGH, RUNE_PAL_LOW, TM, addr,
    cgb_bg_palette, clear_hostiles, feet_on, find_rune_plates,
    load_rune_room, put16, room_tile_attr, solve_runes, step_off,
    wait_rune_flash,
)

OBJECTIVE_DIR = addr("_room_objective_dir")
BGT_DOOR, BGPAL_CRACK = 3, 4
DOOR_CELLS = {0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
              2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9))}
SCX, SCY = 0xFF43, 0xFF42


def prep(pb):
    clear_hostiles(pb)
    pb.memory[PL + 15] = 0
    pb.memory[PL + 2] = 14
    step_off(pb)
    wait_rune_flash(pb)


def slots(pb):
    return cgb_bg_palette(pb, 2), cgb_bg_palette(pb, 3)


def open_doors(pb, addrs):
    return {d: [room_tile_attr(pb, x, y, addrs) for x, y in cells]
            for d, cells in DOOR_CELLS.items()
            if all(pb.memory[TM + y * 20 + x] == BGT_DOOR for x, y in cells)}


def door_contract():
    """Every objective direction: the solve must not repaint the exits."""
    order = None
    for objective in range(4):
        pb, addrs = load_rune_room(0, "waystone")
        prep(pb)
        pb.memory[OBJECTIVE_DIR] = objective
        before = open_doors(pb, addrs)
        assert before, "the Waystone room has no door to check"
        if order is None:
            order = solve_runes(pb, find_rune_plates(pb))
        else:
            for plate in order:
                pb.memory[PL + 2] = 14
                feet_on(pb, *plate)
                wait_rune_flash(pb)
                step_off(pb)
                wait_rune_flash(pb)
        assert not pb.memory[LOCKED], "the phrase did not solve the Waystone"
        for _ in range(30):
            pb.tick()
        after = open_doors(pb, addrs)
        for direction, attrs in after.items():
            assert set(attrs) == {BGPAL_CRACK}, (
                f"objective {objective}: opened door {direction} is on BG "
                f"palette(s) {attrs}, the note plates' borrowed slot")
        assert after == before, (objective, before, after)
        pb.stop(save=False)
    return order


def walk_out(pb, direction, frames=200):
    """Cross a side door; per-frame (room, scx, scy, slots)."""
    put16(pb, PL + 9, 16 if direction == "left" else pb.memory[
        addr("_room_world_width")] - 32)
    put16(pb, PL + 11, 60)
    pb.button_press(direction)
    timeline = []
    for _ in range(frames):
        pb.tick()
        timeline.append((pb.memory[RS + 1], pb.memory[SCX], pb.memory[SCY],
                         slots(pb)))
    pb.button_release(direction)
    return timeline


def slide_frames(timeline, start_room):
    """Frames of the door slide: the BG steps a whole tile per frame.

    The room camera never moves more than 2px a frame, so an 8px step is
    the slide. Both frames either side of each step show two rooms.
    """
    crossed = next(i for i, row in enumerate(timeline) if row[0] != start_room)

    def step(i):
        return max((timeline[i + 1][k] - timeline[i][k]) & 0xFF for k in (1, 2))

    moving = [i for i in range(crossed, len(timeline) - 1)
              if 4 <= step(i) <= 252]
    assert len(moving) >= 16, f"the door did not slide between rooms: {moving}"
    return range(moving[0], moving[-1] + 2)


def slide_contract():
    """Leave an unsolved note room by its entry door, then walk back in."""
    pb, _addrs = load_rune_room(0, "waystone")
    prep(pb)
    note_room = pb.memory[RS + 1]
    assert pb.memory[KIND] == 2 and pb.memory[LOCKED]
    assert slots(pb) == (RUNE_PAL_LOW, RUNE_PAL_HIGH), (
        "the note room is not showing its packed note palettes")

    # The harness lands here over a synthetic graph edge. Mark the west door
    # as the way the hero came in: a locked puzzle room keeps only its
    # return door open.
    pb.memory[RS + 6] = 1
    out = walk_out(pb, "left")
    stage = out[-1][3]
    assert out[-1][0] != note_room, "could not leave the note room"
    assert stage[0] != RUNE_PAL_LOW and stage[1] != RUNE_PAL_HIGH
    sliding = slide_frames(out, note_room)
    leaked = [i for i in sliding if out[i][3] != stage]
    assert not leaked, (
        f"note colours stayed loaded for {len(leaked)} of {len(sliding)} "
        f"slide frames while leaving the note room")

    back = walk_out(pb, "right")
    assert back[-1][0] == note_room, "could not walk back into the note room"
    sliding = slide_frames(back, out[-1][0])
    leaked = [i for i in sliding if back[i][3] != stage]
    assert not leaked, (
        f"note colours were loaded for {len(leaked)} of {len(sliding)} "
        f"slide frames while entering the note room")
    assert back[-1][3] == (RUNE_PAL_LOW, RUNE_PAL_HIGH), (
        "the plates did not get their note palettes on arrival")
    pb.stop(save=False)
    return len(sliding)


def main():
    order = door_contract()
    frames = slide_contract()
    print(f"[note-palette-handoff] PASS opened doors keep the amber slot for "
          f"all 4 objective directions (phrase {order}); crystal/door slots "
          f"hold the stage palettes for all {frames} slide frames, both ways")


if __name__ == "__main__":
    main()
