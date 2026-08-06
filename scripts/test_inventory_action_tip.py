#!/usr/bin/env python3
"""Live-ROM contract: PACK explains every B skill and the full-MP A/B chord."""
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
    # The B effect owns one indented plain-language line with no second B/ACT
    # pseudo-binding, and the full-MP chord remains explicit.
    for class_id in range(5):
        pb = boot(class_id)
        assert pb.memory[screen] == 9, f"class {class_id} did not open PACK"
        row = list(pb.memory[0x9800 + 12 * 32:0x9800 + 12 * 32 + 20])
        assert row[0] == 0 and any(row[2:]), (
            f"class {class_id} lost its indented B explanation: {row}")
        assert not any(row[2 + 18:]), (
            f"class {class_id} B explanation clips the PACK edge: {row}")
        chord = bytes(pb.memory[0x9800 + 16 * 32:0x9800 + 16 * 32 + 18])
        assert any(chord), f"class {class_id} lost the full-MP chord tip"
        pb.stop(save=False)
    print("[inventory-action-tip] PASS five B reminders + full-MP A/B chord")


if __name__ == "__main__":
    main()
