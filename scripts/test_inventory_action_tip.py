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


def boot(class_moves):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(20):
        pb.tick()
    for _ in range(class_moves):
        pb.button("down")
        for _ in range(8):
            pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()
    pb.button("start")
    for _ in range(20):
        pb.tick()
    return pb


def main():
    screen = addr("_loop_current_screen")
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
        icon_tiles = tuple(pb.memory[0xFE00 + sprite * 4 + 2]
                           for sprite in range(4, 10))
        assert all(icon_tiles), (
            f"class {class_id} visual Pack lost semantic icons: {icon_tiles}")
        if class_id == 0:
            pb.screen.image.save(ROOT / "tmp" / "pack-visual.png")
        pb.stop(save=False)
    print("[inventory-action-tip] PASS framed Pack + six semantic icons + five B reminders")


if __name__ == "__main__":
    main()
