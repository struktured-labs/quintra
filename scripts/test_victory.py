#!/usr/bin/env python3
"""ROM contract for final victory presentation and persistent records."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


def main():
    rs = addr("_run_state")
    screen = addr("_loop_current_screen")
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()

    # The endurance bot proves a controller-only ninth-boss clear. Here we
    # isolate the ending contract by presenting the exact post-kill state to
    # room_tick, then inspect the cartridge's UI and MBC5 SRAM side effects.
    pb.memory[rs + 1] = 54       # final boss room
    pb.memory[rs + 10] = 1      # victory flag set by combat
    pb.memory[rs + 11] = 9      # BOSSES_TO_WIN
    for _ in range(20):
        pb.tick()
    assert pb.memory[screen] == 12, "victory flag did not enter SCREEN_VICTORY"

    # victory_enter clears the resumable run in SRAM bank 0 and records the
    # win in meta bank 1. Enable cart RAM explicitly for readback.
    pb.memory[0x0000] = 0x0A
    pb.memory[0x4000] = 0
    assert pb.memory[0xA000] != ord("Q"), "victory left suspend save valid"
    pb.memory[0x4000] = 1
    assert bytes((pb.memory[0xA000], pb.memory[0xA001])) == b"QM", \
        "victory did not initialize meta records"
    wins = pb.memory[0xA007] | (pb.memory[0xA008] << 8)
    assert wins >= 1, "victory did not persist a win"
    pb.memory[0x0000] = 0

    pb.button("start")
    for _ in range(20):
        pb.tick()
    assert pb.memory[screen] == 1, "START did not return victory screen to title"
    pb.stop(save=False)
    print("[victory] PASS ending screen + SRAM record + title return")


if __name__ == "__main__":
    main()
