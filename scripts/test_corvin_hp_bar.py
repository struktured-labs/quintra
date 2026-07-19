#!/usr/bin/env python3
"""Live-ROM contract: Corvin's sight bar includes regular-room HP scaling."""

import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SCREEN_ROOM = 5
HUD_BAR_FULL, HUD_BAR_EMPTY = 26, 27


def addr(name: str) -> int:
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def main() -> None:
    run_state, player, entities, screen = map(addr, (
        "_run_state", "_player", "_entities", "_loop_current_screen"))
    pb = PyBoy(str(ROM), window="null", cgb=True)

    def tick(count: int) -> None:
        for _ in range(count):
            pb.tick()

    tick(240)
    pb.button("start"); tick(30)
    pb.button("down"); tick(8)
    pb.button("down"); tick(8)  # Corvin
    pb.button("a"); tick(90)
    assert pb.memory[screen] == SCREEN_ROOM and pb.memory[player] == 2, \
        "could not enter a Corvin room"

    # Create the exact regular-room Skeleton model without invoking any debug
    # combat shortcut. Its base HP is 10; at four cleared bosses procgen adds
    # 1 + floor(4/2), so 9 HP is three quarters of its genuine 13 HP maximum.
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    pb.memory[run_state + 1] = 25     # local dungeon room 1: ordinary combat
    pb.memory[run_state + 11] = 4     # stage-scaling source of truth
    enemy = entities
    pb.memory[enemy] = 2              # ENT_ENEMY
    pb.memory[enemy + 1] = 1          # EF_ACTIVE
    pb.memory[enemy + 3] = 120        # x integer byte in fix8_t
    pb.memory[enemy + 7] = 96         # y integer byte in fix8_t
    pb.memory[enemy + 14] = 9
    pb.memory[enemy + 17] = 3         # ENEMY_SKELETON
    tick(3)

    # HUD window is at 0x9C00; the four HP segments live in columns 12..15.
    bar = list(pb.memory[0x9C00 + 12:0x9C00 + 16])
    assert bar == [HUD_BAR_FULL, HUD_BAR_FULL, HUD_BAR_FULL, HUD_BAR_EMPTY], \
        f"Corvin HP bar ignored scaled 13 HP maximum: {bar}"
    pb.stop(save=False)
    print("[corvin-hp-bar] PASS sight bar uses scaled regular-enemy maximum")


if __name__ == "__main__":
    main()
