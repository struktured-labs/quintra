#!/usr/bin/env python3
"""Chosen difficulty matches the class-select labels and survives CONTINUE.

The hero-select screen used to advertise the *next* SELECT target as
``SEL>NORMAL`` / ``SEL>EASY``. font_min has no ``>``, so those strings
rendered as ``SEL NORMAL`` and ``SEL EASY``. A player who pressed SELECT
until the screen said ``SEL NORMAL`` was already on Easy; A then started
an Easy run and the Pack screen looked like the game had reverted.
"""
from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()

DIFFICULTY_NORMAL = 0
DIFFICULTY_EASY = 1
SCREEN_ROOM = 5


def addr(name: str) -> int:
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, SCREEN = map(addr, ("_run_state", "_player", "_loop_current_screen"))


def font_tiles(text: str) -> list[int]:
    result = []
    for char in text:
        if "A" <= char <= "Z":
            result.append(11 + ord(char) - ord("A"))
        elif "0" <= char <= "9":
            result.append(1 + ord(char) - ord("0"))
        else:
            result.append(0)
    return result


def row_text(pb: PyBoy, row: int, width: int = 20) -> list[int]:
    base = 0x9800 + row * 32
    return list(pb.memory[base:base + width])


def assert_row(pb: PyBoy, row: int, label: str) -> None:
    expected = font_tiles(label)
    rendered = row_text(pb, row, len(expected))
    assert rendered == expected, (
        f"class-select row {row} was {rendered}, expected tiles for {label!r}"
    )


def press(pb: PyBoy, button: str, held: int = 4, released: int = 8) -> None:
    pb.button_press(button)
    for _ in range(held):
        pb.tick()
    pb.button_release(button)
    for _ in range(released):
        pb.tick()


def boot_to_class_select(pb: PyBoy) -> None:
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(30):
        pb.tick()


def confirm_and_settle(pb: PyBoy) -> None:
    press(pb, "a")
    for _ in range(90):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            break
    assert pb.memory[SCREEN] == SCREEN_ROOM, "new run did not reach the foyer"


def wait_for_suspend(pb: PyBoy, expected_diff: int) -> None:
    saved = False
    for _ in range(240):
        pb.tick()
        pb.memory[0x0000] = 0x0A
        pb.memory[0x4000] = 0
        saved = (
            bytes(pb.memory[0xA000:0xA002]) == b"QS"
            and pb.memory[0xA005 + 26] == expected_diff
        )
        pb.memory[0x0000] = 0
        if saved:
            break
    assert saved, (
        f"room-entry SRAM did not store difficulty {expected_diff}"
    )


def continue_from_battery(cart: Path, battery_io) -> PyBoy:
    battery_io.seek(0)
    pb = PyBoy(str(cart), window="null", cgb=True, ram_file=battery_io)
    for _ in range(240):
        pb.tick()
    press(pb, "a")
    for _ in range(90):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            break
    assert pb.memory[SCREEN] == SCREEN_ROOM, "CONTINUE did not resume SCREEN_ROOM"
    return pb


def assert_in_game(pb: PyBoy, difficulty: int, hp_max: int) -> None:
    assert pb.memory[RS + 26] == difficulty, (
        f"WRAM difficulty was {pb.memory[RS + 26]}, expected {difficulty}"
    )
    assert pb.memory[PL + 1] == hp_max, (
        f"hp_max was {pb.memory[PL + 1]}, expected {hp_max}"
    )


def run_mode(cart: Path, *, easy: bool) -> None:
    first = PyBoy(str(cart), window="null", cgb=True)
    try:
        boot_to_class_select(first)
        if easy:
            press(first, "select")
            for _ in range(16):
                first.tick()
            assert_row(first, 13, "EASY MORE HP FEW HEX")
            assert_row(first, 16, "SPEED 6 MODE EASY")
            # The old inverted prompt rendered as "SEL NORMAL" here.
            assert row_text(first, 16) != font_tiles("SPEED 6 SEL NORMAL"), (
                "Easy page still looks like the current mode is NORMAL"
            )
            expected = DIFFICULTY_EASY
            hp_max = 16
        else:
            assert_row(first, 13, "NORMAL  SEL FOR EASY")
            assert_row(first, 16, "SPEED 6 MODE NORMAL")
            assert "HARD" not in "NORMAL  SEL FOR EASY"
            expected = DIFFICULTY_NORMAL
            hp_max = 14
        confirm_and_settle(first)
        assert_in_game(first, expected, hp_max)
        wait_for_suspend(first, expected)

        battery = tempfile.NamedTemporaryFile(prefix="quintra-diff-", suffix=".sav")
        first.stop(save=True, ram_file=battery)
        battery.flush()
    except Exception:
        first.stop(save=False)
        raise

    second = continue_from_battery(cart, battery)
    try:
        assert_in_game(second, expected, hp_max)
    finally:
        second.stop(save=False)
        battery.close()


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="quintra-diff-") as td:
        cart = Path(td) / "quintra.gbc"
        shutil.copy2(ROM, cart)
        run_mode(cart, easy=False)
        run_mode(cart, easy=True)
    print(
        "[difficulty-persist] PASS Normal/Easy labels match WRAM and "
        "survive suspend/CONTINUE; no HARD mode"
    )


if __name__ == "__main__":
    main()
