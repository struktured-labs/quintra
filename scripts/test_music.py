#!/usr/bin/env python3
"""ROM regression: nine stage tracks and nine dedicated boss tracks."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W = 20


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, TM, MUSIC, REQUEST = map(
    addr, ("_run_state", "_player", "_entities", "_room_tilemap",
           "_music_track_id", "_music_stage_number")
)


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def boot_run():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    assert pb.memory[MUSIC] == 18, "title did not select music number 18"
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()
    return pb


def runtime_track(stage, boss):
    pb = boot_run()
    desired_room = (stage + 1) * 6 if boss else stage * 6 + 1
    pb.memory[RS + 1] = desired_room - 1
    pb.memory[RS + 11] = stage       # bosses_beaten drives stage identity
    pb.memory[RS + 12] = 0
    pb.memory[RS + 13] = 0
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    assert pb.memory[RS + 11] == stage, "stage identity write did not stick"
    if boss:
        pb.memory[RS + 6] = 0xFF      # no backtracking direction
        pb.memory[RS + 17] = 0
        pb.memory[TM + 9 * ROOM_W + 19] = 3  # east BGT_DOOR
        put16(pb, PL + 9, 144)
        put16(pb, PL + 11, 60)
    else:
        pb.memory[RS + 17] = 1        # Riftwild dungeon gate
        pb.memory[RS + 18] = 6
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 60)
        pb.memory[TM + 9 * ROOM_W + 10] = 1
        pb.tick()                      # settle synthetic state
        pb.memory[TM + 9 * ROOM_W + 10] = 34  # BGT_PORTAL under feet
    for _ in range(30):
        pb.tick()
        if pb.memory[RS + 1] == desired_room:
            break
    assert pb.memory[RS + 1] == desired_room, (
        f"could not enter stage {stage} {'boss' if boss else 'room'}"
    )
    assert pb.memory[RS + 11] == stage, "transition changed stage identity"
    assert pb.memory[RS + 17] == 0, "transition did not enter a dungeon"
    track = pb.memory[MUSIC]
    assert pb.memory[REQUEST] == stage, (
        f"audio request drifted for stage {stage}: {pb.memory[REQUEST]}"
    )
    pb.stop(save=False)
    return track


def main():
    stages = [runtime_track(stage, False) for stage in range(9)]
    bosses = [runtime_track(stage, True) for stage in range(9)]
    assert stages == list(range(9)), f"stage music numbers drifted: {stages}"
    assert bosses == list(range(9, 18)), f"boss music numbers drifted: {bosses}"
    assert set(stages).isdisjoint(bosses), "boss music reused an exploration id"
    print(f"[music] PASS stages={stages}, bosses={bosses}, title=18")


if __name__ == "__main__":
    main()
