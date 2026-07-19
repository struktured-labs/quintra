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


PLAYER, ENTITIES, SCREEN = map(addr, ("_player", "_entities", "_loop_current_screen"))


def tick_safe(pb, frames):
    """Advance live room frames without allowing fixture enemies to hurt us."""
    for _ in range(frames):
        pb.memory[PLAYER + 15] = 120  # public player iframe field
        pb.tick()


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (8 * i)) & 0xFF


def enter_sauran(pb):
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("down")
    for _ in range(8):
        pb.tick()
    pb.button("a")
    for _ in range(80):
        pb.tick()
    assert pb.memory[SCREEN] == 5 and pb.memory[PLAYER] == 1, "did not enter as Sauran"


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    enter_sauran(pb)
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

    # Advance a half-cycle, then die and start a genuine new Sauran run. The
    # new run must not inherit the old static counter and heal 900 frames
    # early. This uses the public hostile/projectile → GAMEOVER → title path.
    pb.memory[PLAYER + 2] = 10
    tick_safe(pb, 900)
    for i in range(32 * 28):
        pb.memory[ENTITIES + i] = 0
    pb.memory[PLAYER + 2] = 1
    pb.memory[PLAYER + 15] = 0
    px = pb.memory[PLAYER + 9] | (pb.memory[PLAYER + 10] << 8)
    py = pb.memory[PLAYER + 11] | (pb.memory[PLAYER + 12] << 8)
    pb.memory[ENTITIES] = 1       # ENT_PROJECTILE
    pb.memory[ENTITIES + 1] = 3   # active hostile
    put_fix8(pb, ENTITIES + 2, px + 5)
    put_fix8(pb, ENTITIES + 6, py + 9)
    pb.memory[ENTITIES + 14] = 1
    pb.memory[ENTITIES + 16] = 20
    pb.memory[ENTITIES + 25] = 0x77
    pb.memory[ENTITIES + 26] = 1
    for _ in range(180):
        pb.tick()
        if pb.memory[SCREEN] == 11:
            break
    assert pb.memory[SCREEN] == 11, "fatal hit did not enter GAMEOVER"
    pb.button("start")
    for _ in range(30):
        pb.tick()
    assert pb.memory[SCREEN] == 1, "GAMEOVER did not return to title"
    enter_sauran(pb)
    pb.memory[PLAYER + 2] = 10
    tick_safe(pb, 900)
    assert pb.memory[PLAYER + 2] == 10, "new Sauran run inherited prior regen progress"
    tick_safe(pb, 900)
    assert pb.memory[PLAYER + 2] == 11, "new Sauran run lost its fresh regen cadence"
    pb.stop(save=False)
    print("[sauran-regen] PASS 1,800-frame cap + no cross-run timer leakage")


if __name__ == "__main__":
    main()
