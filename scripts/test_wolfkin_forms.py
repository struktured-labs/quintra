#!/usr/bin/env python3
"""ROM contract: Wolfkin A is stab/sweep/Max Strike, never a shot stream."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")  # Wolfkin is the default highlighted champion
    for _ in range(60):
        pb.tick()
    return pb


def clear_entities(pb, entities):
    for i in range(32 * 28):
        pb.memory[entities + i] = 0


def player_projectiles(pb, entities):
    return [entities + i * 28 for i in range(32)
            if pb.memory[entities + i * 28] == 1
            and (pb.memory[entities + i * 28 + 1] & 0x10)]


def main():
    player, entities = map(addr, ("_player", "_entities"))
    pb = boot()
    assert pb.memory[player] == 0, "did not enter as Wolfkin"

    # A with a D-pad direction is the narrow contact stab.
    clear_entities(pb, entities)
    pb.memory[player + 22] = 0  # fire cooldown
    pb.button_press("right")
    pb.button("a")
    for _ in range(3):
        pb.tick()
    pb.button_release("right")
    stab = player_projectiles(pb, entities)
    assert len(stab) == 1, f"directed A spawned {len(stab)} attacks"
    assert pb.memory[stab[0] + 12] == 122, "stab lost physical arc art"
    assert pb.memory[stab[0] + 16] <= 6, "stab travels like a projectile"
    assert pb.memory[stab[0] + 25] == 0x77, "directed stab became the broad sweep"

    # Neutral A is the wider sweep, still a single physical hitbox.
    clear_entities(pb, entities)
    pb.memory[player + 22] = 0
    pb.button("a")
    for _ in range(3):
        pb.tick()
    sweep = player_projectiles(pb, entities)
    assert len(sweep) == 1, f"neutral A spawned {len(sweep)} overlapping arcs"
    assert pb.memory[sweep[0] + 25] == 0xBB, "neutral A did not widen into a sweep"

    # Holding a directed A long enough creates the cooldown-gated Max Strike:
    # the player travels down the lane and emits the authored spear visual.
    clear_entities(pb, entities)
    pb.memory[player + 22] = 0
    before_x = pb.memory[player + 9] | (pb.memory[player + 10] << 8)
    pb.button_press("right")
    pb.button_press("a")
    for _ in range(22):
        pb.tick()
    pb.button_release("a")
    pb.button_release("right")
    after_x = pb.memory[player + 9] | (pb.memory[player + 10] << 8)
    assert after_x >= before_x + 24, "Max Strike did not dash through its lane"
    assert any(pb.memory[e + 12] == 123 for e in player_projectiles(pb, entities)), \
        "Max Strike did not create its spear-lane hit"
    pb.stop(save=False)
    print("[wolfkin-forms] PASS directed stab, neutral sweep, and Max Strike")


if __name__ == "__main__":
    main()
