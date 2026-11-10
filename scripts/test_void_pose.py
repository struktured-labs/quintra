#!/usr/bin/env python3
"""Void Lord shows a bank-1 collapsed pose before its existing blink."""
from test_boss_identity import enter_boss


def void_sprites(pb):
    found = []
    for i in range(4, 40):
        base = 0xFE00 + i * 4
        y, x, tile, prop = (pb.memory[base + k] for k in range(4))
        if not (y and x):
            continue
        bank = prop & 0x08
        if bank == 0 and 40 <= tile <= 55:
            found.append(0)
        elif bank and 128 <= tile <= 143:
            found.append(8)
    return found


def main():
    pb, _boss = enter_boss(8, keep_open=True)
    bits = set()
    counts = set()
    for _ in range(140):
        pb.tick(1, render=True, sound=False)
        sprites = void_sprites(pb)
        if len(sprites) != 16:
            if sprites:
                counts.add(len(sprites))
            continue
        counts.add(16)
        bits.add(sprites[0])
    assert 16 in counts, f"void body is not 16 sprites: {sorted(counts)}"
    assert bits == {0, 8}, f"both poses must appear, saw {sorted(bits)}"

    pb.memory[0xFF40] &= 0x7F
    pb.memory[0xFF4F] = 0
    idle = bytes(pb.memory[0x8000 + 40 * 16:0x8000 + 56 * 16])
    pb.memory[0xFF4F] = 1
    blink = bytes(pb.memory[0x8000 + 128 * 16:0x8000 + 144 * 16])
    forbidden = bytes(pb.memory[0x8000 + 40 * 16:0x8000 + 56 * 16])
    differ = sum(a != b for a, b in zip(idle, blink))
    pb.stop(save=False)
    assert differ > 32, f"bank-1 blink matches the idle upload ({differ} bytes)"
    assert forbidden != blink, "blink was uploaded over bank-1 tiles 40..55"
    print(f"void poses ok, vram bytes differ {differ}")


if __name__ == "__main__":
    main()
