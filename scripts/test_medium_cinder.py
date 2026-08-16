#!/usr/bin/env python3
"""ROM contract: Ember owns a real middle-scale Cinder Maw enemy tier."""
import re
from pathlib import Path

from test_stage_archetypes import EN, PL, TM, generated_room


ROOT = Path(__file__).resolve().parent.parent
SPRITES = (ROOT / "src/render/sprites_gen.c").read_text()
ENTITY_SIZE = 28
ENEMY_CINDER_MAW = 14
SPR_MEDIUM_CINDER_MAW = 64


def put_fix8(pb, address, pixels):
    value = pixels << 8
    for byte in range(4):
        pb.memory[address + byte] = (value >> (byte * 8)) & 0xFF


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = value >> 8


def generated_medium():
    match = re.search(
        r"const u8 sprite_medium_cinder_maw\[64\] = \{([^}]+)\};", SPRITES)
    assert match, "generated medium Cinder Maw art is missing"
    return bytes(int(token.strip(), 0) for token in match.group(1).split(",")
                 if token.strip())


def visible_bounds(data):
    pixels = []
    for tile in range(4):
        tx, ty = tile & 1, tile >> 1
        for row in range(8):
            lo, hi = data[tile * 16 + row * 2:tile * 16 + row * 2 + 2]
            for col in range(8):
                mask = 0x80 >> col
                if (lo | hi) & mask:
                    pixels.append((tx * 8 + col, ty * 8 + row))
    xs, ys = [p[0] for p in pixels], [p[1] for p in pixels]
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1, len(pixels)


def main():
    expected = generated_medium()
    width, height, ink = visible_bounds(expected)
    assert (width, height) == (10, 15), (
        f"Cinder Maw left the intended middle scale: {width}x{height}")
    assert 64 < width * height < 256 and ink > 64, (
        f"Cinder Maw is not between an 8x8 swarm body and a full 16x16 mass: {ink}")
    seen = []

    def probe(pb, _tiles):
        maw = next((EN + i * ENTITY_SIZE for i in range(32)
                    if pb.memory[EN + i * ENTITY_SIZE] == 2
                    and pb.memory[EN + i * ENTITY_SIZE + 1] & 1
                    and pb.memory[EN + i * ENTITY_SIZE + 17] == ENEMY_CINDER_MAW),
                   None)
        if maw is None:
            return
        seen.append(1)
        assert pb.memory[maw + 12] == SPR_MEDIUM_CINDER_MAW, (
            f"spawned Cinder Maw used tile {pb.memory[maw + 12]}, not medium slot 64")
        assert pb.memory[maw + 25] == 0x8D, (
            f"medium Cinder Maw hitbox drifted: {pb.memory[maw + 25]:02x}")
        actual = bytes(pb.memory[0x8000 + SPR_MEDIUM_CINDER_MAW * 16:
                                 0x8000 + (SPR_MEDIUM_CINDER_MAW + 4) * 16])
        assert actual == expected, "Ember did not install all four medium Maw tiles"

        # Isolate it and inspect hardware OAM after the real renderer runs.
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            if ep != maw:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        for i in range(20 * 17):
            pb.memory[TM + i] = 1
        put_fix8(pb, maw + 2, 64)
        put_fix8(pb, maw + 6, 56)
        pb.memory[maw + 1] |= 0x04
        pb.memory[maw + 16] = 200
        put16(pb, PL + 9, 120)
        put16(pb, PL + 11, 96)
        for _ in range(5):
            pb.tick()
        oam_tiles = {pb.memory[0xFE00 + slot * 4 + 2] for slot in range(4, 40)
                     if pb.memory[0xFE00 + slot * 4] != 0}
        assert set(range(64, 68)) <= oam_tiles, (
            f"Cinder Maw renderer did not allocate its 2x2 body: {sorted(oam_tiles)}")

    for seed in range(0xC1DE1000, 0xC1DE1020):
        generated_room(2, seed, probe=probe, local_room=4)
        if seen:
            break
    assert seen, "Cinder Maw did not appear in 32 deterministic Ember rooms"
    print(f"[medium-cinder] PASS live 10x15 body ({ink} ink pixels), 2x2 OAM, "
          "8x13 combat hitbox")


if __name__ == "__main__":
    main()
