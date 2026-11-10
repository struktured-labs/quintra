#!/usr/bin/env python3
"""The serpent opens its jaw on the meal and the charge, and the coil matches the hood."""
from pathlib import Path

from PIL import Image

from test_boss_identity import enter_boss

ART = Path("/opt/cursor/artifacts")
VERDANT = bytes([0x00, 0x00, 0x6A, 0x3C, 0x1B, 0x61, 0xFF, 0x3B])


def hood(pb):
    found = []
    for i in range(4, 16):
        base = 0xFE00 + i * 4
        y, x, tile, prop = (pb.memory[base + k] for k in range(4))
        if not (y and x):
            continue
        bank = prop & 0x08
        if bank == 0 and 40 <= tile <= 51:
            found.append(0)
        elif bank and 128 <= tile <= 139:
            found.append(8)
    return found


def pal_slot(pb, reg, data, slot):
    raw = bytearray()
    for index in range(slot * 8, slot * 8 + 8):
        pb.memory[reg] = index
        raw.append(pb.memory[data])
    return bytes(raw)


def main():
    pb, boss = enter_boss(1, keep_open=True)
    ART.mkdir(parents=True, exist_ok=True)
    closed = hood(pb)
    assert closed and set(closed) == {0}, f"idle hood is not the bank-0 head: {closed}"
    pb.screen.image.save(ART / "serpent-after-closed.png")

    pb.memory[boss + 15] = 1
    for _ in range(8):
        pb.tick(1, render=True, sound=False)
    opened = hood(pb)
    assert opened and set(opened) == {8}, f"charge did not open the jaw: {opened}"
    pb.screen.image.save(ART / "serpent-after-open.png")

    pb.memory[boss + 15] = 0
    pb.memory[boss + 11] = 0
    for _ in range(4):
        pb.tick(1, render=True, sound=False)
    shut = hood(pb)
    assert shut and set(shut) == {0}, f"jaw stayed open after the charge: {shut}"

    bg = pal_slot(pb, 0xFF68, 0xFF69, 6)
    obj = pal_slot(pb, 0xFF6A, 0xFF6B, pb.memory[boss + 13])
    assert bg == VERDANT, f"coil palette {bg.hex()} is not the Verdant boss ramp"
    assert obj == VERDANT, f"hood palette {obj.hex()} drifted from the coil"

    pb.memory[0xFF40] &= 0x7F
    pb.memory[0xFF4F] = 0
    idle = bytes(pb.memory[0x8000 + 40 * 16:0x8000 + 52 * 16])
    pb.memory[0xFF4F] = 1
    jaw = bytes(pb.memory[0x8000 + 128 * 16:0x8000 + 140 * 16])
    forbidden = bytes(pb.memory[0x8000 + 40 * 16:0x8000 + 56 * 16])
    empty = bytes(pb.memory[0x8000 + 140 * 16:0x8000 + 144 * 16])
    differ = sum(a != b for a, b in zip(idle, jaw))
    pb.stop(save=False)
    assert differ > 8, f"open jaw matches the closed hood ({differ} bytes)"
    assert forbidden != jaw[: len(forbidden)], "jaw was uploaded over bank-1 tiles 40..55"
    assert empty == bytes(64), "tiles 140..143 were not left empty"
    print(f"serpent jaw ok, vram bytes differ {differ}")


if __name__ == "__main__":
    main()
