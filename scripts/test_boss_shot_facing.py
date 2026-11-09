#!/usr/bin/env python3
"""Bolt and crescent metasprites mirror east and west.

North and south use a second glyph in VRAM bank 1. OAM cannot rotate.
"""
from test_boss_identity import EN, enter_boss, put16

FLIPX = 0x20
FLIPY = 0x40
BANK = 0x08
ENTITY = 28


def place(pb, slot, x, y, shape, tile, angle):
    e = EN + slot * ENTITY
    for offset in range(ENTITY):
        pb.memory[e + offset] = 0
    pb.memory[e] = 1
    pb.memory[e + 1] = 0x87
    put16(pb, e + 3, x)
    put16(pb, e + 7, y)
    pb.memory[e + 12] = tile
    pb.memory[e + 13] = 4
    pb.memory[e + 14] = 1
    pb.memory[e + 16] = 150
    pb.memory[e + 17] = angle
    pb.memory[e + 18] = 5  # BOSS_SHOT_BOLT: angle stays put
    pb.memory[e + 21] = shape
    pb.memory[e + 23] = 0xD0
    pb.memory[e + 25] = 0xE6 if shape == 3 else 0xEE


def sprites(pb, tiles):
    found = []
    for i in range(40):
        oam = 0xFE00 + i * 4
        tile = pb.memory[oam + 2]
        if pb.memory[oam] and tile in tiles:
            found.append((pb.memory[oam + 1], pb.memory[oam], tile, pb.memory[oam + 3]))
    return sorted(found)


def main():
    pb, _boss = enter_boss(6, keep_open=True)
    try:
        for i in range(32):
            pb.memory[EN + i * ENTITY] = 0
        # Slot 0 is the boss and is reclaimed if cleared. East, west, then
        # north. North uses the bank-1 vertical glyph.
        place(pb, 2, 32, 48, 3, 214, 8)
        place(pb, 3, 80, 48, 3, 214, 24)
        place(pb, 4, 120, 48, 3, 214, 0)
        place(pb, 5, 32, 80, 4, 216, 8)
        place(pb, 6, 80, 80, 4, 216, 24)
        place(pb, 7, 120, 80, 4, 216, 0)
        for _ in range(6):
            pb.tick()
        bolts = sprites(pb, {208, 209, 214, 215})
        crescents = sprites(pb, {210, 211, 212, 213, 216, 217, 218, 219})
        assert len(bolts) == 6, bolts
        assert len(crescents) == 12, crescents

        def pair(group, x_min, x_max):
            rows = [row for row in group if x_min <= row[0] <= x_max]
            return sorted(rows)

        east = pair(bolts, 0, 75)
        west = pair(bolts, 76, 120)
        north = pair(bolts, 121, 180)
        assert [tile for _x, _y, tile, _prop in east] == [214, 215], east
        assert all((prop & FLIPX) == 0 for *_, prop in east), east
        assert [tile for _x, _y, tile, _prop in west] == [215, 214], west
        assert all(prop & FLIPX for *_, prop in west), west
        assert [tile for _x, _y, tile, _prop in north] == [208, 209], north
        assert len({x for x, _y, _tile, _prop in north}) == 1, north
        assert all((prop & FLIPX) == 0 and (prop & FLIPY) == 0 and (prop & BANK)
                   for *_, prop in north), north

        def top_row(x_min, x_max):
            rows = pair(crescents, x_min, x_max)
            top = min(y for _x, y, _tile, _prop in rows)
            return [row for row in rows if row[1] == top]

        east_c = top_row(0, 75)
        west_c = top_row(76, 120)
        north_c = top_row(121, 180)
        assert [tile for _x, _y, tile, _prop in east_c] == [217, 216], east_c
        assert all(prop & FLIPX for *_, prop in east_c), east_c
        assert [tile for _x, _y, tile, _prop in west_c] == [216, 217], west_c
        assert all((prop & FLIPX) == 0 for *_, prop in west_c), west_c
        assert [tile for _x, _y, tile, _prop in north_c] == [210, 211], north_c
        assert all((prop & FLIPX) == 0 and (prop & FLIPY) == 0 and (prop & BANK)
                   for *_, prop in north_c), north_c
        print('[shot-facing] PASS east/west mirror, north uses bank-1 art')
    finally:
        pb.stop(save=False)


if __name__ == '__main__':
    main()
