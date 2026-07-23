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


RS, PL, COMBAT, PUZZLE, MUSIC_ROW = map(addr, (
    "_run_state", "_player", "_room_combat_sealed", "_room_puzzle_locked",
    "_music_row",
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
    positions = ((72, 0), (144, 60), (72, 120), (0, 60))
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
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)

    rows_while_scrolling = set()
    started = False
    elapsed = None
    slide_frames = 0
    for frame in range(180):
        pb.tick()
        if pb.memory[0xFF42] or pb.memory[0xFF43]:
            started = True
            slide_frames += 1
            rows_while_scrolling.add(pb.memory[MUSIC_ROW])
        if (started and pb.memory[RS + 1] == target and pb.memory[0xFF42] == 0
                and pb.memory[0xFF43] == 0 and (pb.memory[0xFF40] & 0x80)):
            elapsed = frame + 1
            break
    pb.stop(save=False)
    assert elapsed is not None, "room slide did not settle within 180 frames"
    # This includes destination procgen, safe enemy placement, role fixtures,
    # streamed camera motion, palettes, HUD, and restored sprites. The former
    # quadratic cross-bank reachability scan measured 103 frames here.
    assert elapsed <= 45, f"complete same-stage doorway regressed to {elapsed} frames"
    # The cartridge performs exactly twenty 8px horizontal scroll steps.
    # PyBoy may expose the final non-zero SCX value for one outer tick before
    # observing the same transaction's LCD-off normalization, so the
    # externally visible bound is twenty-one observations.
    assert slide_frames <= 21, f"camera slide regressed to {slide_frames} frames"
    assert len(rows_while_scrolling) >= 2, (
        f"music row droned during slide: {sorted(rows_while_scrolling)}")
    print(f"[transition-audio] PASS total={elapsed}f slide={slide_frames}f "
          f"music_rows={sorted(rows_while_scrolling)}")


if __name__ == "__main__":
    main()
