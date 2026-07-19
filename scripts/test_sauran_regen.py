#!/usr/bin/env python3
"""ROM contract: Sauran's Scaled Hide restores one half-heart per 1,800 room frames."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PLAYER, SCREEN = map(addr, ("_player", "_loop_current_screen"))


def tick_safe(pb, frames):
    """Advance live room frames without allowing fixture enemies to hurt us."""
    for _ in range(frames):
        pb.memory[PLAYER + 15] = 120  # public player iframe field
        pb.tick()


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("down")  # Sauran, the second champion
    for _ in range(8):
        pb.tick()
    pb.button("a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[SCREEN] == 5 and pb.memory[PLAYER] == 1, "did not enter as Sauran"
    assert pb.memory[PLAYER + 1] == 14, "Sauran's seven-heart Scaled Hide base drifted"

    pb.memory[PLAYER + 2] = 10
    tick_safe(pb, 1799)
    assert pb.memory[PLAYER + 2] == 10, "Scaled Hide regenerated before 1,800 room frames"
    tick_safe(pb, 1)
    assert pb.memory[PLAYER + 2] == 11, "Scaled Hide did not restore one half-heart at 1,800 frames"
    tick_safe(pb, 1800)
    assert pb.memory[PLAYER + 2] == 12, "Scaled Hide regenerated the wrong amount on its second cycle"

    pb.memory[PLAYER + 2] = pb.memory[PLAYER + 1]
    tick_safe(pb, 1800)
    assert pb.memory[PLAYER + 2] == pb.memory[PLAYER + 1], "Scaled Hide exceeded max health"
    pb.stop(save=False)
    print("[sauran-regen] PASS one half-heart/1,800 active room frames, capped")


if __name__ == "__main__":
    main()
