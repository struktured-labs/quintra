#!/usr/bin/env python3
"""Gear selection stays framed and contained; footer never scrolls the page."""
from test_dungeon_tools import boot, press, PLAYER


def tile(pb, x, y):
    return pb.memory[0x9800 + y * 32 + x]


def check_page(pb, selected):
    assert tile(pb, 0, 0) == 0xF9, "footer scrolled the page"
    assert tile(pb, 0, 13) == 0xFD, "RULE divider moved"
    for i in range(4):
        col, row = (10 if i & 1 else 1), (11 if i & 2 else 9)
        frame = [tile(pb, col + x, row + y) for y in range(2) for x in range(2)]
        assert frame == ([0xF2, 0xF3, 0xF4, 0xF5] if i == selected else [0]*4)
        oam = 0xFE00 + (4 + i) * 4
        sy = pb.memory[oam] - 16
        sx = pb.memory[oam + 1] - 8
        assert col*8 < sx and sx + 8 < (col+2)*8
        assert row*8 < sy and sy + 8 < (row+2)*8 <= 13*8
        assert any(tile(pb, col+3+x, row) for x in range(4)), "missing gear label"
    assert all(pb.memory[0xFE00+i*4] == 0 for i in range(4)), "hero overlaps header"


def main():
    pb = boot()
    try:
        pb.memory[PLAYER + 44] = 15
        pb.memory[PLAYER + 45] = 0
        press(pb, 'start')
        pb.tick(90)
        press(pb, 'select')
        pb.tick(90)
        check_page(pb, 0)
        for key, selected in [('right', 1), ('down', 3), ('left', 2), ('up', 0)]:
            press(pb, key)
            check_page(pb, selected)
            press(pb, 'a')
            check_page(pb, selected)
            assert pb.memory[PLAYER + 45] == 0, "inspection changed legacy slot"
        pb.screen.image.save('/tmp/quintra-waygear-after.png')
        pb.memory[PLAYER + 44] = 0
        press(pb, 'right')
        check_page(pb, 1)
        press(pb, 'a')
        assert pb.memory[PLAYER + 45] == 0, "locked gear equipped"
        press(pb, 'select')
        assert not (pb.memory[0xFF40] & 2), "icons visible on status page"
        print('[waygear-layout] PASS all slots, equip, locked gear, divider, footer, status')
    finally:
        pb.stop(save=False)


if __name__ == '__main__':
    main()
