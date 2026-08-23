#!/usr/bin/env python3
"""Live-ROM contract: the ordinary double-tap dash supports all diagonals."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PL, EN, TM, SCREEN, DIRECTOR_KIND = map(addr, (
    "_player", "_entities", "_room_tilemap", "_loop_current_screen",
    "_room_encounter_kind"))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def read16(pb, address):
    return pb.memory[address] | (pb.memory[address + 1] << 8)


def set_buttons(pb, buttons, down):
    for button in buttons:
        (pb.button_press if down else pb.button_release)(button)


def quiet_tick(pb):
    # Hold this across the cartridge boundary: dense frames may span more
    # than one host VBlank after the fixture first clears the room.
    pb.memory[DIRECTOR_KIND] = 0
    pb.tick()


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")  # Wolfkin; dash movement is shared by all champions.
    for _ in range(120):
        pb.tick()
    assert pb.memory[SCREEN] == 5, "fixture did not enter gameplay"
    for i in range(32 * 28):
        pb.memory[EN + i] = 0
    for i in range(20 * 17):
        pb.memory[TM + i] = 1  # guaranteed open dash floor
    # Keep the fixture's audio lane isolated from a seed-selected trap clock.
    pb.memory[DIRECTOR_KIND] = 0
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 64)
    pb.memory[PL + 15] = 0
    pb.memory[PL + 23] = 0
    for _ in range(90):
        quiet_tick(pb)
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 64)
    pb.memory[PL + 15] = 0
    return pb


def dash(buttons):
    pb = boot()
    # Tap the whole vector twice just as a player would on a diagonal d-pad.
    set_buttons(pb, buttons, True)
    for _ in range(2):
        quiet_tick(pb)
    set_buttons(pb, buttons, False)
    for _ in range(3):
        quiet_tick(pb)
    before = (read16(pb, PL + 9), read16(pb, PL + 11))
    set_buttons(pb, buttons, True)
    dash_noise = None
    for _ in range(7):
        quiet_tick(pb)
        noise = (pb.memory[0xFF22], pb.memory[0xFF21])
        if noise == (0x27, 0x72):
            dash_noise = noise
    set_buttons(pb, buttons, False)
    for _ in range(2):
        quiet_tick(pb)
    after = (read16(pb, PL + 9), read16(pb, PL + 11))
    iframes = pb.memory[PL + 15]
    pb.stop(save=False)
    return after[0] - before[0], after[1] - before[1], iframes, dash_noise


def main():
    expected_signs = {
        ("up", "right"): (1, -1),
        ("down", "right"): (1, 1),
        ("down", "left"): (-1, 1),
        ("up", "left"): (-1, -1),
    }
    vectors = {}
    for buttons, signs in expected_signs.items():
        dx, dy, iframes, dash_noise = dash(buttons)
        vectors["+".join(buttons)] = (dx, dy)
        assert (dx > 0) - (dx < 0) == signs[0], (
            f"{'/'.join(buttons)} dash lost horizontal direction: {dx},{dy}")
        assert (dy > 0) - (dy < 0) == signs[1], (
            f"{'/'.join(buttons)} dash lost vertical direction: {dx},{dy}")
        assert 12 <= abs(dx) <= 16 and 12 <= abs(dy) <= 16, (
            f"{'/'.join(buttons)} dash is not normalized: {dx},{dy}")
        assert iframes >= 6, (
            f"{'/'.join(buttons)} dash lost its dodge window: {iframes}")
        assert dash_noise == (0x27, 0x72), (
            f"{'/'.join(buttons)} dash lost wind-cut SFX: {dash_noise}")

    cardinal_dx, cardinal_dy, _, cardinal_noise = dash(("right",))
    assert cardinal_dy == 0 and 19 <= cardinal_dx <= 23, (
        f"cardinal dash baseline drifted: {cardinal_dx},{cardinal_dy}")
    assert max(abs(dx) for dx, _ in vectors.values()) < cardinal_dx, (
        "diagonal dash axes were not vector-normalized")
    assert cardinal_noise == (0x27, 0x72)
    print(f"[diagonal-dash] PASS four vectors {vectors}; "
          f"cardinal=({cardinal_dx},{cardinal_dy})")


if __name__ == "__main__":
    main()
