#!/usr/bin/env python3
"""Room slides stay bounded and keep the cartridge music sequencer alive."""

import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_START, dungeon_neighbor, dungeon_size

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
STATE = ROOT / "tmp/stage-states/quintra-stage-01-entry-wolfkin.pyboy"


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, COMBAT, PUZZLE, MUSIC_ROW, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y, \
    ORIGIN_X, ORIGIN_Y = map(addr, (
    "_run_state", "_player", "_room_combat_sealed", "_room_puzzle_locked",
    "_music_row", "_room_world_width", "_room_world_height",
    "_room_camera_x", "_room_camera_y", "_room_bg_origin_x",
    "_room_bg_origin_y",
))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    with STATE.open("rb") as handle:
        pb.load_state(handle)
    for _ in range(6):
        pb.tick()

    # This contract isolates the transition itself from either room-lock kind.
    pb.memory[COMBAT] = 0
    pb.memory[PUZZLE] = 0
    entered = pb.memory[RS + 6]
    back = ((entered + 2) & 3) if entered != 0xFF else 0xFF
    positions = (
        (72, 0),
        (pb.memory[WORLD_W] - 16, 60),
        (72, pb.memory[WORLD_H] - 16),
        (0, 60),
    )
    stage = pb.memory[RS + 11]
    local = pb.memory[RS + 1] - STAGE_START[stage]
    direction = next(
        d for d in range(4)
        if d != back and dungeon_neighbor(local, dungeon_size(stage), d)
        is not None
    )
    target = STAGE_START[stage] + dungeon_neighbor(
        local, dungeon_size(stage), direction)
    x, y = positions[direction]
    old_origin_x = pb.memory[ORIGIN_X]
    old_origin_y = pb.memory[ORIGIN_Y]
    expected_origin_x = old_origin_x
    expected_origin_y = old_origin_y
    expected_camera_x = 0
    expected_camera_y = 0
    if direction == 0:
        expected_origin_y = (old_origin_y + 1) & 31
        expected_camera_y = 112
    elif direction == 1:
        expected_origin_x = (old_origin_x + 31) & 31
    elif direction == 2:
        expected_origin_y = (old_origin_y + 31) & 31
    else:
        expected_origin_x = (old_origin_x + 1) & 31
        expected_camera_x = 88
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)

    rows_while_scrolling = set()
    started = False
    elapsed = None
    slide_frames = 0
    for frame in range(180):
        pb.tick()
        if (pb.memory[RS + 1] != local + STAGE_START[stage]
                or pb.memory[0xFF42] !=
                    ((old_origin_y << 3) + pb.memory[CAMERA_Y]) & 0xFF
                or pb.memory[0xFF43] !=
                    ((old_origin_x << 3) + pb.memory[CAMERA_X]) & 0xFF):
            started = True
        if started:
            slide_frames += 1
            rows_while_scrolling.add(pb.memory[MUSIC_ROW])
        if (started and pb.memory[RS + 1] == target
                and pb.memory[ORIGIN_X] == expected_origin_x
                and pb.memory[ORIGIN_Y] == expected_origin_y
                and pb.memory[CAMERA_X] == expected_camera_x
                and pb.memory[CAMERA_Y] == expected_camera_y
                and pb.memory[0xFF43]
                    == ((expected_origin_x << 3)
                        + expected_camera_x) & 0xFF
                and pb.memory[0xFF42]
                    == ((expected_origin_y << 3)
                        + expected_camera_y) & 0xFF
                and (pb.memory[0xFF40] & 0x80)):
            elapsed = frame + 1
            break
    pb.stop(save=False)
    assert elapsed is not None, "room slide did not settle within 180 frames"
    # This includes destination procgen, safe enemy placement, role fixtures,
    # streamed camera motion, palettes, HUD, and restored sprites. The former
    # quadratic cross-bank reachability scan measured 103 frames here.
    assert elapsed <= 60, f"complete same-stage doorway regressed to {elapsed} frames"
    # A wide seam visibly streams the destination half, then fills its
    # offscreen half before publishing the rotated background origin. Keep the
    # complete generation-and-stream transaction below one second.
    assert slide_frames <= 60, f"camera slide regressed to {slide_frames} frames"
    assert len(rows_while_scrolling) >= 2, (
        f"music row droned during slide: {sorted(rows_while_scrolling)}")
    print(f"[transition-audio] PASS total={elapsed}f slide={slide_frames}f "
          f"music_rows={sorted(rows_while_scrolling)}")


if __name__ == "__main__":
    main()
