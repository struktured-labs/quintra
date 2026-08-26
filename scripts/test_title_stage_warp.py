#!/usr/bin/env python3
"""Exercise the hidden Rift Index entirely through controller input."""

import io
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
NOI = ROM.with_suffix(".noi")
BLANK_SRAM = bytes(32 * 1024)
STAGE_START = (0, 20, 41, 64, 87, 111, 137, 163, 191)
CODE = ("up", "right", "down", "left", "right",
        "up", "left", "down", "b", "a")


def symbol(name):
    match = re.search(rf"DEF _{name} 0x([0-9A-Fa-f]+)", NOI.read_text())
    assert match, f"missing linker symbol {name}"
    return int(match.group(1), 16)


def press(pb, button, frames=4):
    pb.button(button)
    pb.tick(frames)


def enter_index(pb):
    for button in CODE:
        press(pb, button)
    # The cold renderer must own the actual LCD, not merely an internal flag.
    # RIFT begins at column 5 of "- RIFT INDEX -" in GBDK's compact font.
    rift = [28, 19, 16, 30]
    row = 0x9800 + 32
    assert list(pb.memory[row + 5:row + 9]) == rift, \
        "title code did not reveal the rendered Rift Index"


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True,
               ram_file=io.BytesIO(BLANK_SRAM))
    pb.tick(240)

    # Cancellation returns to the untouched title rather than starting a run
    # on the terminal A or leaving the champion tableau parked.
    enter_index(pb)
    press(pb, "b", 12)
    title_row = 0x9800 + 4 * 32
    assert any(pb.memory[title_row + col] for col in range(20)), \
        "closing Rift Index did not restore the title"

    # UP wraps Stage 1 to Stage 9. Confirm, choose Easy and Wolfkin, then let
    # the normal RUN_INIT -> ROOM path construct the selected dungeon.
    enter_index(pb)
    screenshot = ROOT / "tmp" / "title-rift-index.png"
    screenshot.parent.mkdir(exist_ok=True)
    pb.screen.image.save(screenshot)
    press(pb, "up")
    press(pb, "a", 20)
    press(pb, "select")
    press(pb, "a")
    screen = symbol("loop_current_screen")
    for _ in range(900):
        pb.tick()
        if pb.memory[screen] == 5:
            break
    else:
        raise AssertionError("Rift Index did not reach gameplay")

    rs = symbol("run_state")
    player = symbol("player")
    assert pb.memory[rs + 11] == 8, \
        f"Rift Index selected wrong stage: {pb.memory[rs + 11]}"
    assert pb.memory[rs + 1] == STAGE_START[8], \
        f"Stage 9 opened in wrong room: {pb.memory[rs + 1]}"
    assert list(pb.memory[player + 24:player + 32]) == \
        [22, 27, 29, 22, 27, 29, 22, 27], \
        "Stage 9 did not receive its deterministic prior-boss build"
    assert pb.memory[player + 2] == pb.memory[player + 1], \
        "warped champion did not begin at full health"
    assert pb.memory[rs + 26] == 1, "Easy selection was lost during warp"

    pb.stop(save=False)

    # Exercise every remaining destination through the same public controller
    # path. This pins the complete selector mapping, not only its endpoints.
    for stage in range(8):
        pb = PyBoy(str(ROM), window="null", cgb=True,
                   ram_file=io.BytesIO(BLANK_SRAM))
        pb.tick(240)
        enter_index(pb)
        for _ in range(stage):
            press(pb, "down")
        press(pb, "a", 20)
        press(pb, "a")
        for _ in range(900):
            pb.tick()
            if pb.memory[screen] == 5:
                break
        else:
            raise AssertionError(f"Stage {stage + 1} did not reach gameplay")
        assert pb.memory[rs + 11] == stage, \
            f"selector destination {stage + 1} became {pb.memory[rs + 11] + 1}"
        assert pb.memory[rs + 1] == STAGE_START[stage], \
            f"Stage {stage + 1} opened in room {pb.memory[rs + 1]}"
        pb.stop(save=False)

    print("[title-stage-warp] PASS code, cancel, all 9 stages, class/Easy flow, progression")


if __name__ == "__main__":
    main()
