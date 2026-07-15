#!/usr/bin/env python3
"""ROM contract for intro/ending story presentation and persistent records."""
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


def press(pb, button, held=4, released=4):
    """Hold across several cartridge polls, then create a clean release edge."""
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def main():
    rs = addr("_run_state")
    screen = addr("_loop_current_screen")
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(60):
        pb.tick()
    title_page_0 = bytes(pb.memory[0x9800:0x9C00])
    for _ in range(180):
        pb.tick()
    title_page_1 = bytes(pb.memory[0x9800:0x9C00])
    assert title_page_0 != title_page_1, "animated title story did not advance"
    press(pb, "start")
    for _ in range(22):
        pb.tick()
    press(pb, "a")
    for _ in range(52):
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

    # The ending is a skippable three-tableau cutscene followed by results.
    # Compare BG tilemaps rather than palettes so this cannot pass solely from
    # the ambient colour pulse.
    ending_pages = [bytes(pb.memory[0x9800:0x9C00])]
    for _ in range(180):
        pb.tick()
    ending_pages.append(bytes(pb.memory[0x9800:0x9C00]))
    for _ in range(180):
        pb.tick()
    ending_pages.append(bytes(pb.memory[0x9800:0x9C00]))
    for _ in range(180):
        pb.tick()
    ending_pages.append(bytes(pb.memory[0x9800:0x9C00]))
    assert len(set(ending_pages)) == 4, \
        "ending did not advance through three lore tableaux to results"

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

    press(pb, "a")
    for _ in range(12):
        pb.tick()
    assert pb.memory[screen] == 5, "A did not enter endless descent from results"
    assert pb.memory[rs + 10] == 0, "endless descent left victory flag latched"
    pb.stop(save=False)

    # A fresh cartridge session proves the advertised early-skip contract:
    # START advances to results without leaving victory, A cannot accidentally
    # enter endless descent during a tableau, and a second START retires.
    skip = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        skip.tick()
    press(skip, "start")
    for _ in range(22):
        skip.tick()
    press(skip, "a")
    for _ in range(52):
        skip.tick()
    skip.memory[rs + 1] = 54
    skip.memory[rs + 10] = 1
    skip.memory[rs + 11] = 9
    for _ in range(20):
        skip.tick()
    assert skip.memory[screen] == 12, "skip fixture did not enter victory"
    tableau = bytes(skip.memory[0x9800:0x9C00])
    press(skip, "a")
    assert skip.memory[screen] == 12, "A entered endless descent before results"
    press(skip, "start")
    assert skip.memory[screen] == 12, "START skipped past results to title"
    results = bytes(skip.memory[0x9800:0x9C00])
    assert results != tableau, "START did not advance ending to results"
    press(skip, "start")
    assert skip.memory[screen] == 1, "second START did not retire to title"
    skip.stop(save=False)
    print("[victory] PASS full ending + safe skip + endless/title result choices")


if __name__ == "__main__":
    main()
