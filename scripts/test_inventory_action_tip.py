#!/usr/bin/env python3
"""Live-ROM contract: the framed visual PACK explains all five hero verbs."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


def press(pb, button, held=5, released=5):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def boot(class_moves):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    press(pb, "start")
    for _ in range(20):
        pb.tick()
    for _ in range(class_moves):
        press(pb, "down")
        for _ in range(8):
            pb.tick()
    press(pb, "a")
    for _ in range(60):
        pb.tick()
    press(pb, "start")
    for _ in range(20):
        pb.tick()
    return pb


def main():
    screen = addr("_loop_current_screen")
    player = addr("_player")
    surge = addr("_room_weapon_surge_ticks")
    ascension = addr("_room_transform_ticks")
    # The B effect owns one short line, the footer keeps the A+B Spirit chord,
    # and OBJ icons distinguish A, B, quest, currency, tool, and Oath.
    for class_id in range(5):
        pb = boot(class_id)
        assert pb.memory[screen] == 9, f"class {class_id} did not open PACK"
        row = list(pb.memory[0x9800 + 12 * 32:0x9800 + 12 * 32 + 20])
        assert any(row[2:19]), (
            f"class {class_id} lost its indented B explanation: {row}")
        chord = bytes(pb.memory[0x9800 + 17 * 32:0x9800 + 17 * 32 + 19])
        assert any(chord), f"class {class_id} lost the full-MP chord tip"
        # These are raw, dedicated 2bpp frame tiles, not printable '+-|'
        # glyphs. Verify the outer corners, section junctions, side rails,
        # and closing corners survive later text writes.
        assert pb.memory[0x9800] == 0xF9
        assert pb.memory[0x9800 + 19] == 0xFA
        assert pb.memory[0x9800 + 4 * 32] == 0xFD
        assert pb.memory[0x9800 + 4 * 32 + 19] == 0xFE
        assert pb.memory[0x9800 + 5 * 32] == 0xF7
        assert pb.memory[0x9800 + 5 * 32 + 19] == 0xF8
        assert pb.memory[0x9800 + 17 * 32] == 0xFB
        assert pb.memory[0x9800 + 17 * 32 + 19] == 0xFC
        icon_tiles = tuple(pb.memory[0xFE00 + sprite * 4 + 2]
                           for sprite in range(4, 10))
        assert all(icon_tiles), (
            f"class {class_id} visual Pack lost semantic icons: {icon_tiles}")
        tool_y = pb.memory[0xFE00 + 8 * 4]
        oath_y = pb.memory[0xFE00 + 9 * 4]
        assert oath_y - tool_y >= 9, (
            f"class {class_id} tool/Oath icons lost their blank scanline: "
            f"tool_y={tool_y}, oath_y={oath_y}")
        if class_id == 0:
            pb.screen.image.save(ROOT / "tmp" / "pack-visual.png")
            ordinary_header = bytes(
                pb.memory[0x9800 + 32 + 12:0x9800 + 32 + 19])
            press(pb, "b")
            assert pb.memory[screen] == 5
            pb.tick(30)
            pb.memory[surge] = 120
            pb.memory[ascension] = 135
            press(pb, "start")
            for _ in range(20):
                pb.tick()
            boosted_header = bytes(
                pb.memory[0x9800 + 32 + 12:0x9800 + 32 + 19])
            assert boosted_header != ordinary_header, (
                "Pack health header did not expose temporary boosts")
            # Add a three-room Hunger curse, then visit Gear -> Status. Menu
            # frames must not consume any active-play duration.
            pb.memory[player + 46] = 0x08
            pb.memory[player + 47] = 3
            press(pb, "select")
            for _ in range(12):
                pb.tick()
            press(pb, "select")
            for _ in range(12):
                pb.tick()
            assert pb.memory[screen] == 9, "Status page left the Pack screen"
            pb.tick(120)
            assert (pb.memory[surge], pb.memory[ascension]) == (120, 135), (
                "Status page consumed paused temporary-effect time")
            pb.screen.image.save(ROOT / "tmp" / "pack-status.png")
            press(pb, "select")
            for _ in range(12):
                pb.tick()
            assert pb.memory[screen] == 9, "Combat Help left the Pack screen"
            help_map = 0x9C00 if pb.memory[0xFF40] & 0x08 else 0x9800
            help_rows = [bytes(pb.memory[help_map + row * 32 + 1:
                                         help_map + row * 32 + 19])
                         for row in (1, 3, 5, 7, 9, 10, 11, 12, 14, 15, 16)]
            assert all(any(row) for row in help_rows), \
                "Combat Help lost an input or equipment instruction"
            assert not (pb.memory[0xFF40] & 0x02), \
                "Combat Help leaked Pack sprites over its copy"
            pb.screen.image.save(ROOT / "tmp" / "pack-combat-help.png")
            press(pb, "b")
            assert pb.memory[screen] == 5, "Combat Help B did not return to play"
        pb.stop(save=False)
    print("[inventory-action-tip] PASS framed Pack + Status + truthful Combat Help")


if __name__ == "__main__":
    main()
