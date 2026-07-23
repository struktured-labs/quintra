#!/usr/bin/env python3
"""ROM contract: the free Chartwright scout survives the town north gate."""

import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_BOSS_ROOM, STAGE_START, VILLAGE_ROOM


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def main():
    run_state, player, entities, screen, tilemap = map(addr, (
        "_run_state", "_player", "_entities", "_loop_current_screen",
        "_room_tilemap"))
    pb = PyBoy(str(ROM), window="null", cgb=True)

    def tick(count):
        for _ in range(count):
            pb.tick()

    def place(x, y):
        for offset, value in ((9, x), (10, 0), (11, y), (12, 0)):
            pb.memory[player + offset] = value

    def clear_hostiles():
        for index in range(32):
            entity = entities + index * 28
            if pb.memory[entity] == 2:
                pb.memory[entity] = pb.memory[entity + 1] = 0

    tick(240)
    pb.button("start"); tick(30)
    pb.button("down"); tick(8)  # Sauran: distinct from the default hero
    pb.button("a"); tick(60)
    assert pb.memory[screen] == 5 and pb.memory[player] == 1

    # Enter through the real post-boss Riftwild gate, with no debug reveal
    # written to run state. A village is not a sequential dungeon room under
    # the reciprocal graph; the post-stage route transaction owns its arrival.
    town_room = VILLAGE_ROOM[3]
    pb.memory[run_state + 1] = STAGE_BOSS_ROOM[2]
    pb.memory[run_state + 11] = 3
    pb.memory[run_state + 17] = 1
    pb.memory[run_state + 18] = 6
    pb.memory[run_state + 19] = 0
    clear_hostiles()
    pb.memory[tilemap + 8 * 20 + 10] = 34
    place(72, 52)
    tick(45)
    assert pb.memory[run_state + 1] == town_room \
        and pb.memory[run_state + 19] == 0
    assert pb.memory[run_state + 25] == 0, "town inherited stale route knowledge"

    chartwright = None
    for index in range(32):
        entity = entities + index * 28
        if pb.memory[entity] == 3 and pb.memory[entity + 17] == 12:
            chartwright = entity
            break
    assert chartwright is not None, "arrival square lacks Chartwright"

    # Touch the resident normally. The queued knowledge is deliberately
    # separate from the town compass, then consumed by the real north gate.
    place(pb.memory[chartwright + 3], (pb.memory[chartwright + 7] - 8) & 0xFF)
    tick(6)
    assert pb.memory[run_state + 25] == 0x03, "Chartwright did not queue two cells"

    place(72, 0)
    tick(45)
    assert pb.memory[run_state + 1] == STAGE_START[3], \
        "town north gate did not enter dungeon"
    # The entrance itself is marked by normal fog-of-war. Require the
    # Chartwright's two promised bits without rejecting that discovery mark.
    assert pb.memory[run_state + 20] & 0x03 == 0x03, \
        f"free scout did not reveal first two cells (seen={pb.memory[run_state + 20]:02x})"
    assert pb.memory[run_state + 25] == 0, "free scout leaked beyond one dungeon"

    pb.stop(save=False)
    print("[cartographer-scout] PASS free two-cell route survives north gate")


if __name__ == "__main__":
    main()
