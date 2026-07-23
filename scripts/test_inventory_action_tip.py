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
    # font_min maps ACT to these tiles. The remaining action reminder must
    # fit before the 20-column edge rather than clipping a prose description.
    action_prefix = [11, 13, 30, 0]
    convergence_tip = [
        16, 31, 22, 22, 0, 23, 26, 0, 11, 0, 12, 0, 13, 18, 25, 28, 14
    ]  # FULL MP A B CHORD in font_min
    for class_id in range(5):
        pb = boot(class_id)
        assert pb.memory[screen] == 9, f"class {class_id} did not open PACK"
        row = list(pb.memory[0x9800 + 13 * 32 + 1:0x9800 + 13 * 32 + 21])
        assert row[:4] == action_prefix, (
            f"class {class_id} retained an ambiguous/repeated B action line: {row}")
        assert any(row[4:15]), f"class {class_id} lost its active reminder"
        assert not any(row[15:]), (
            f"class {class_id} action reminder clips the PACK screen edge: {row}")
        chord = list(pb.memory[0x9800 + 17 * 32 + 1:0x9800 + 17 * 32 + 18])
        assert chord == convergence_tip, (
            f"class {class_id} lost the readable full-MP chord tip: {chord}")
        pb.stop(save=False)
    print("[inventory-action-tip] PASS five B reminders + full-MP A/B chord")


if __name__ == "__main__":
    main()
