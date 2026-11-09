#!/usr/bin/env python3
"""Hexa Dragmar body art: silhouette, reserved VRAM, and luminance."""
from test_hexa_dragmar import (
    EN,
    HEXA_CORE,
    PHASE,
    SPOT,
    SPOT_T,
    hold_safe,
    qualified_sanctum,
)

HEXA_BG = 40
HEXA_LAST = 55
SL = 51
CC, CO, CP = 52, 53, 54
FLOOR = 1
# Sockets are 2x2, top-left tile, in TL/TR/BL/BR order.
SOCKETS = ((9, 2), (3, 4), (15, 4), (4, 9), (14, 9))
CORE = (9, 5)
CORVIN_WIN = (2, 3)


def y_of(color):
    red = color & 31
    green = (color >> 5) & 31
    blue = (color >> 10) & 31
    return 0.299 * red + 0.587 * green + 0.114 * blue


def bg_color(pb, slot, index):
    base = slot * 8 + index * 2
    pb.memory[0xFF68] = base
    lo = pb.memory[0xFF69]
    pb.memory[0xFF68] = base + 1
    hi = pb.memory[0xFF69]
    return lo | (hi << 8)


def obj_color(pb, slot, index):
    base = slot * 8 + index * 2
    pb.memory[0xFF6A] = base
    lo = pb.memory[0xFF6B]
    pb.memory[0xFF6A] = base + 1
    hi = pb.memory[0xFF6B]
    return lo | (hi << 8)


def cell(pb, x, y):
    return pb.memory[0x9800 + y * 32 + x]


def attr(pb, x, y):
    return pb.memory[1, 0x9800 + y * 32 + x]


def main():
    pb = qualified_sanctum()
    try:
        pattern = bytes(pb.memory[1, 0x9000 + HEXA_BG * 16:0x9000 + HEXA_BG * 16 + 16])
        assert pattern[:2] == bytes((0xEF, 0x10)), (
            f"body patterns missing from VRAM bank 1 tile {HEXA_BG}: {pattern[:4].hex()}"
        )
        bank0 = bytes(pb.memory[0, 0x9000 + HEXA_BG * 16:0x9000 + HEXA_BG * 16 + 2])
        assert bank0 != pattern[:2], "body art overwrote VRAM bank 0"
        for tile in (64, 88, 208):
            slot = bytes(pb.memory[1, 0x8000 + tile * 16:0x8000 + tile * 16 + 16])
            assert slot != pattern, f"body art landed on bank-1 OBJ tile {tile}"

        floors = 0
        seen = set()
        for y in range(1, 14):
            for x in range(2, 18):
                tile = cell(pb, x, y)
                bits = attr(pb, x, y)
                if tile == FLOOR:
                    floors += 1
                    assert (bits & 0x08) == 0, f"floor {(x, y)} used VRAM bank 1"
                    continue
                assert HEXA_BG <= tile <= HEXA_LAST, f"tile {(x, y)} is {tile}"
                assert bits & 0x08, f"dragon {(x, y)} is not on VRAM bank 1"
                assert (bits & 7) == 5, f"dragon {(x, y)} pal {bits & 7}"
                seen.add(tile)
        assert floors >= 36, f"only {floors} perimeter floor cells"
        assert len(seen) <= 16
        flips = (0x00, 0x20, 0x40, 0x60)
        for origin in SOCKETS:
            for dy, dx in ((0, 0), (0, 1), (1, 0), (1, 1)):
                x, y = origin[0] + dx, origin[1] + dy
                assert cell(pb, x, y) == SL, f"socket {(x, y)} tile {cell(pb, x, y)}"
                assert (attr(pb, x, y) & 0x60) == flips[dy * 2 + dx]

        bg5 = [y_of(bg_color(pb, 5, i)) for i in range(4)]
        assert bg5[0] <= 4.0 and bg5[1] <= 6.5 and bg5[2] <= 10.5 and bg5[3] <= 15.0, bg5
        limb = y_of(obj_color(pb, 5, 3))
        shot3 = y_of(obj_color(pb, 3, 3))
        shot4 = y_of(obj_color(pb, 4, 3))
        assert limb - bg5[1] >= 18.0, (limb, bg5[1])
        assert shot3 - bg5[2] >= 19.0 and shot4 - bg5[2] >= 19.0, (shot3, shot4, bg5[2])

        pb.memory[SPOT] = 2
        pb.memory[SPOT_T] = 120
        hold_safe(pb)
        pb.tick(2)
        assert pb.memory[SPOT] == 2
        for y in range(CORVIN_WIN[1], CORVIN_WIN[1] + 4):
            for x in range(CORVIN_WIN[0], CORVIN_WIN[0] + 4):
                if not (HEXA_BG <= cell(pb, x, y) <= HEXA_LAST):
                    continue
                assert (attr(pb, x, y) & 7) == 6, f"corvin {(x, y)} pal {attr(pb, x, y) & 7}"
                assert attr(pb, x, y) & 0x08
        for y in range(1, 14):
            for x in range(2, 18):
                if not (HEXA_BG <= cell(pb, x, y) <= HEXA_LAST):
                    continue
                inside = (CORVIN_WIN[0] <= x < CORVIN_WIN[0] + 4
                          and CORVIN_WIN[1] <= y < CORVIN_WIN[1] + 4)
                core = CORE[0] <= x < CORE[0] + 2 and CORE[1] <= y < CORE[1] + 2
                pal = attr(pb, x, y) & 7
                if inside or core:
                    assert pal == 6, f"{(x, y)} pal {pal}"
                else:
                    assert pal == 5, f"{(x, y)} pal {pal}"
                assert (attr(pb, x, y) & 0x60) in flips

        ent = pb.memory[HEXA_CORE]
        base = EN + ent * 28
        assert cell(pb, 9, 5) == CC
        pb.memory[base + 14] = 100
        pb.memory[base + 23] = 255
        hold_safe(pb)
        pb.tick()
        assert pb.memory[PHASE] == 1
        assert cell(pb, 9, 5) == CO and cell(pb, 10, 6) == CO
        pb.memory[base + 14] = 40
        hold_safe(pb)
        pb.tick()
        assert pb.memory[PHASE] == 2
        assert cell(pb, 9, 5) == CP and cell(pb, 10, 6) == CP
        print("[hexa-art] PASS silhouette, reserved VRAM, contrast, spotlight, phase core")
    finally:
        pb.stop(save=False)


if __name__ == "__main__":
    main()
