#!/usr/bin/env python3
"""ROM regression: run time follows active VBlanks and menus cannot shave it."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W = 20
SCREEN_ROOM, SCREEN_MAP, SCREEN_INVENTORY = 5, 8, 9


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, EN, TM, SCREEN = map(
    addr, ("_run_state", "_entities", "_room_tilemap", "_loop_current_screen")
)


def timer(pb):
    return pb.memory[RS + 7] | (pb.memory[RS + 8] << 8)


def boot_room():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    pb.button("a")
    pb.tick(90)
    assert pb.memory[SCREEN] == SCREEN_ROOM, "run did not reach a room"
    return pb


def align_second(pb):
    before = timer(pb)
    for _ in range(70):
        pb.tick()
        if timer(pb) != before:
            return timer(pb)
    raise AssertionError("active room clock did not advance")


def open_menu(pb, button, expected):
    pb.button(button)
    for _ in range(20):
        pb.tick()
        if pb.memory[SCREEN] == expected:
            pb.tick(20)  # allow the new screen's entry renderer to commit VRAM
            return
    raise AssertionError(f"{button} did not open screen {expected}")


def assert_menu_palette_contract(pb, button):
    # Read CGB VRAM bank 1 with the LCD disabled so active-transfer blocking
    # cannot turn cells into false 0xFF samples.
    lcdc = pb.memory[0xFF40]
    bg_map = 0x9C00 if lcdc & 0x08 else 0x9800
    pb.memory[0xFF40] = lcdc & 0x7F
    pb.memory[0xFF4F] = 1
    attrs = {
        pb.memory[bg_map + y * 32 + x]
        for y in range(18) for x in range(20)
    }
    pb.memory[0xFF4F] = 0
    pb.memory[0xFF40] = lcdc
    # Inventory text is deliberately uniform. The SELECT field map is a
    # tile-built diagram: floor, walls, and the current-room marker. The
    # unrecovered Sigil now lives in its actual (still-unseen) fixture room,
    # rather than leaking a floating crack marker into every map view.
    # Require the exact set so stale room attributes cannot leak through.
    expected = {0} if button == "start" else {0, 1, 3}
    assert attrs == expected, (
        f"{button} menu palette contract changed: expected {expected}, got {attrs}"
    )


def resume(pb):
    pb.button("b")
    for _ in range(25):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            return
    raise AssertionError("menu did not resume the room")


def test_menu_fraction(button, expected):
    pb = boot_room()
    base = align_second(pb)
    pb.tick(40)                  # bank a visible subsecond fraction
    open_menu(pb, button, expected)
    assert_menu_palette_contract(pb, button)
    entered = timer(pb)
    pb.tick(180)                 # three seconds reading: clock must hold
    assert timer(pb) == entered, f"{button} menu counted paused time"
    resume(pb)
    pb.tick(25)                  # 40 + 25 active frames must cross a second
    gained = timer(pb) - base
    pb.stop(save=False)
    assert gained == 1, (
        f"{button} discarded or inflated active fraction: gained {gained}s"
    )


def test_dense_wall_time():
    pb = boot_room()
    base = align_second(pb)
    for y in range(3, 14):
        for x in range(3, 17):
            pb.memory[TM + y * ROOM_W + x] = 1
    for i in range(32):
        ep = EN + i * 28
        pb.memory[ep] = pb.memory[ep + 1] = 0
    for i in range(12):
        ep = EN + i * 28
        pb.memory[ep] = 1
        pb.memory[ep + 1] = 0x03
        x, y = 32 + (i % 7) * 16, 24 + (i // 7) * 24
        pb.memory[ep + 2] = x & 0xFF
        pb.memory[ep + 3] = (x >> 8) & 0xFF
        pb.memory[ep + 6] = y & 0xFF
        pb.memory[ep + 7] = (y >> 8) & 0xFF
        pb.memory[ep + 12] = 28
        pb.memory[ep + 13] = 2
        pb.memory[ep + 14] = 1
        pb.memory[ep + 16] = 255
        pb.memory[ep + 25] = 0x77
        pb.memory[ep + 26] = 1
    pb.tick(180)
    gained = timer(pb) - base
    pb.stop(save=False)
    assert gained == 3, f"dense room clock drifted: {gained}s over 180 VBlanks"


def main():
    test_menu_fraction("start", SCREEN_INVENTORY)
    test_menu_fraction("select", SCREEN_MAP)
    test_dense_wall_time()
    print("[run-clock] PASS menus palette contracts + paused fractions=retained dense=3s")


if __name__ == "__main__":
    main()
