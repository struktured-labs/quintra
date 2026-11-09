#!/usr/bin/env python3
"""Live-ROM contract: every accepted six-room suspend migrates its location."""
import io
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_START


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SRAM_SIZE = 32 * 1024
PLAYER_SIZE = 42       # accepted pre-Will player layout
CURRENT_PLAYER_SIZE = 49
CURRENT_RUN_SIZE = 60
SCREEN_ROOM = 5


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, SCREEN = map(
    addr, ("_run_state", "_player", "_loop_current_screen"))


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def legacy_sram(run_size):
    run = bytearray(run_size)
    run[1] = 15        # stage-3 local room 2 in the old six-room topology
    run[6] = 0xFF      # safe centre arrival
    run[11] = 2        # two Colossi defeated
    player = bytearray(PLAYER_SIZE)
    player[0:9] = bytes((0, 8, 8, 6, 6, 4, 2, 5, 2))
    player[13] = 0
    player[24:40] = bytes((0xFF,)) * 16
    payload = bytes(run + player)
    record = b"QS" + bytes((1, run_size, PLAYER_SIZE))
    record += payload + bytes((sum(payload) & 0xFF,))
    return io.BytesIO(record + bytes(SRAM_SIZE - len(record)))


def main():
    # All four early layouts and their last six-room successor are explicitly
    # accepted by sram_run_valid(). They therefore must all receive topology
    # migration, not merely deserialize into an unrelated modern stage cell.
    expected = STAGE_START[2] + 2
    for run_size in (20, 23, 26, 27, 29):
        battery = legacy_sram(run_size)
        pb = PyBoy(str(ROM), window="null", cgb=True, ram_file=battery)
        try:
            pb.tick(240)
            press(pb, "a")
            for _ in range(360):
                pb.memory[PL + 2] = 8
                pb.memory[PL + 15] = 120
                pb.tick()
                if pb.memory[SCREEN] == SCREEN_ROOM:
                    break
            assert pb.memory[SCREEN] == SCREEN_ROOM, \
                f"{run_size}-byte suspend did not resume"
            assert pb.memory[RS + 1] == expected, (
                f"{run_size}-byte six-room suspend resumed at "
                f"{pb.memory[RS + 1]}, expected migrated room {expected}"
            )
            # The resumed room entry upgrades old records to the current ABI.
            for _ in range(180):
                pb.tick()
            pb.memory[0x0000] = 0x0A
            pb.memory[0x4000] = 0
            assert pb.memory[0xA003] == CURRENT_RUN_SIZE, \
                f"{run_size}-byte suspend was not rewritten as current ABI"
            assert pb.memory[0xA004] == CURRENT_PLAYER_SIZE, \
                f"{run_size}-byte player suspend was not upgraded"
            pb.memory[0x0000] = 0
        finally:
            pb.stop(save=False)
    print("[sram-compat] PASS all accepted six-room suspend layouts migrate")
    for size, charge, level, expected in ((48, 180, 0, 1), (48, 120, 0, 0),
                                          (49, 70, 3, 3)):
        run = bytearray(CURRENT_RUN_SIZE)
        run[6] = 0xFF
        player = bytearray(size)
        player[:9] = bytes((0, 8, 8, 6, 6, 4, 2, 5, 2))
        player[24:40] = bytes((0xFF,)) * 16
        player[42] = charge
        player[44] = 7
        if size == 49:
            player[48] = level
        payload = run + player
        record = b"QS" + bytes((1, len(run), size)) + payload
        record += bytes((sum(payload) & 255,))
        battery = io.BytesIO(record + bytes(SRAM_SIZE - len(record)))
        pb = PyBoy(str(ROM), window="null", cgb=True, ram_file=battery)
        try:
            pb.tick(240)
            press(pb, "a")
            for _ in range(360):
                pb.tick()
                if pb.memory[SCREEN] == SCREEN_ROOM:
                    break
            assert pb.memory[SCREEN] == SCREEN_ROOM
            assert pb.memory[PL + 48] == expected, (size, charge, level)
            if size == 49:
                assert 70 <= pb.memory[PL + 42] < 80
            elif charge == 120:
                assert 60 <= pb.memory[PL + 42] < 70
        finally:
            pb.stop(save=False)
    print("[sram-compat] PASS legacy Will migration and tiered suspend")


if __name__ == "__main__":
    main()
