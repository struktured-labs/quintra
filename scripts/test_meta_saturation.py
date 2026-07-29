#!/usr/bin/env python3
"""Live-ROM contract: lifetime run and win records never wrap to zero."""
import io
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_BOSS_ROOM


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SCREEN_ROOM = 5
SCREEN_GAMEOVER = 11
SCREEN_VICTORY = 12


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, SCREEN = map(
    addr, ("_run_state", "_player", "_entities", "_loop_current_screen"))


def press(pb, button, held=4, released=4):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def boot_run():
    pb = PyBoy(
        str(ROM), window="null", cgb=True,
        ram_file=io.BytesIO(bytes(32 * 1024)),
    )
    pb.tick(240)
    press(pb, "start")
    pb.tick(30)
    press(pb, "a")
    pb.tick(100)
    assert pb.memory[SCREEN] == SCREEN_ROOM
    return pb


def write_meta(pb, runs, wins):
    pb.memory[0x0000] = 0x0A
    pb.memory[0x4000] = 1
    data = bytearray((0, 0, runs & 0xFF, runs >> 8,
                      wins & 0xFF, wins >> 8, 0xFF, 0xFF))
    pb.memory[0xA000] = ord("Q")
    pb.memory[0xA001] = ord("M")
    pb.memory[0xA002] = 2
    for i, value in enumerate(data):
        pb.memory[0xA003 + i] = value
    pb.memory[0xA00B] = sum(data) & 0xFF
    pb.memory[0x0000] = 0


def read_meta(pb):
    pb.memory[0x0000] = 0x0A
    pb.memory[0x4000] = 1
    runs = pb.memory[0xA005] | pb.memory[0xA006] << 8
    wins = pb.memory[0xA007] | pb.memory[0xA008] << 8
    pb.memory[0x0000] = 0
    return runs, wins


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (8 * i)) & 0xFF


def kill_player(pb):
    for slot in range(32):
        entity = EN + slot * 28
        pb.memory[entity] = pb.memory[entity + 1] = 0
    pb.memory[PL + 2] = 1
    pb.memory[PL + 15] = 0
    px = pb.memory[PL + 9] | pb.memory[PL + 10] << 8
    py = pb.memory[PL + 11] | pb.memory[PL + 12] << 8
    shot = EN
    pb.memory[shot] = 1
    pb.memory[shot + 1] = 3
    put_fix8(pb, shot + 2, px + 5)
    put_fix8(pb, shot + 6, py + 9)
    pb.memory[shot + 14] = 1
    pb.memory[shot + 16] = 30
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 26] = 8
    for _ in range(300):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_GAMEOVER:
            pb.tick(30)
            return
    raise AssertionError("fatal fixture did not enter GAME OVER")


def main():
    death = boot_run()
    try:
        write_meta(death, 0xFFFF, 17)
        kill_player(death)
        assert read_meta(death) == (0xFFFF, 17), \
            f"lifetime run counter wrapped: {read_meta(death)}"
    finally:
        death.stop(save=False)

    victory = boot_run()
    try:
        write_meta(victory, 0xFFFF, 0xFFFF)
        victory.memory[RS + 1] = STAGE_BOSS_ROOM[-1]
        victory.memory[RS + 10] = 1
        victory.memory[RS + 11] = 9
        victory.memory[RS + 12] = 1
        for _ in range(120):
            victory.tick()
            if victory.memory[SCREEN] == SCREEN_VICTORY:
                victory.tick(30)
                break
        assert victory.memory[SCREEN] == SCREEN_VICTORY, \
            "victory fixture did not enter ending"
        assert read_meta(victory) == (0xFFFF, 0xFFFF), \
            f"lifetime victory counters wrapped: {read_meta(victory)}"
    finally:
        victory.stop(save=False)

    print("[meta-saturation] PASS lifetime runs/wins hold at 65,535")


if __name__ == "__main__":
    main()
