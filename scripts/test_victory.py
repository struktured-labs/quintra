#!/usr/bin/env python3
"""ROM contract for intro/ending story presentation and persistent records."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_BOSS_ROOM

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
    pl = addr("_player")
    en = addr("_entities")
    tm = addr("_room_tilemap")
    screen = addr("_loop_current_screen")
    pb = PyBoy(str(ROM), window="null", cgb=True)

    def wait_for_room():
        previous = None
        stable = 0
        for _ in range(240):
            pb.tick()
            tiles = bytes(pb.memory[tm + i] for i in range(20 * 17))
            lcd_on = bool(pb.memory[0xFF40] & 0x80)
            committed = not any(value & 0x80 for value in tiles)
            stable = stable + 1 if lcd_on and committed and tiles == previous else 0
            previous = tiles
            if stable >= 10:
                return
        raise AssertionError("post-victory room generation did not settle")

    def clear_hostiles():
        for i in range(32):
            entity = en + i * 28
            if pb.memory[entity] == 2:
                pb.memory[entity] = pb.memory[entity + 1] = 0

    def exit_at(x, y, clear=True):
        if clear:
            clear_hostiles()
        pb.memory[pl + 9] = x & 0xFF
        pb.memory[pl + 10] = (x >> 8) & 0xFF
        pb.memory[pl + 11] = y & 0xFF
        pb.memory[pl + 12] = (y >> 8) & 0xFF
        for _ in range(45):
            pb.tick()
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
    pb.memory[rs + 1] = STAGE_BOSS_ROOM[-1]
    pb.memory[rs + 10] = 1      # victory flag set by combat
    pb.memory[rs + 11] = 9      # BOSSES_TO_WIN
    pb.memory[rs + 12] = 1      # same boss-kill transaction opens descent
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
    wait_for_room()

    # Dawn's Verge is not dead postgame lore: results reopen Riftwild screen
    # zero directly, avoiding a regenerated/clamped final-boss arena. Cross
    # the authored 0->1->2->6 route and use its gate.
    assert pb.memory[rs + 17] == 1 and pb.memory[rs + 18] == 0, (
        "post-victory descent did not reopen Riftwild "
        f"(room={pb.memory[rs + 1]} world={pb.memory[rs + 17]} "
        f"cell={pb.memory[rs + 18]} screen={pb.memory[screen]})"
    )
    exit_at(208, 60, clear=False)
    assert pb.memory[rs + 18] == 1
    exit_at(208, 60)
    assert pb.memory[rs + 18] == 2
    exit_at(72, 120)
    assert pb.memory[rs + 18] == 6
    pb.memory[pl + 9] = 72
    pb.memory[pl + 10] = 0
    pb.memory[pl + 11] = 52
    pb.memory[pl + 12] = 0
    for _ in range(12):
        pb.tick()
    assert pb.memory[rs + 17] == 0 \
        and pb.memory[rs + 1] == STAGE_BOSS_ROOM[-1] + 1, (
        "post-victory Riftwild gate did not reach final town"
    )
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
    skip.memory[rs + 1] = STAGE_BOSS_ROOM[-1]
    skip.memory[rs + 10] = 1
    skip.memory[rs + 11] = 9
    skip.memory[rs + 12] = 1
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
    print("[victory] PASS ending + safe skip + endless route to final town")


if __name__ == "__main__":
    main()
