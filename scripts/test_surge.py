#!/usr/bin/env python3
"""ROM contract: Surge Spark is a visible, temporary primary-weapon boon."""
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


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def first_player_shot(pb, entities):
    for i in range(32):
        e = entities + i * 28
        if pb.memory[e] == 1 and (pb.memory[e + 1] & 0x10):
            return e
    raise AssertionError("no player projectile")


def main():
    player, entities, screen = map(addr, ("_player", "_entities", "_loop_current_screen"))
    surge_ticks = addr("_room_weapon_surge_ticks")
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    pb.button("a")
    for _ in range(80): pb.tick()
    assert pb.memory[screen] == 5

    # Keep the interaction isolated: the temporary pickup still travels
    # through the real pickup/combat path, rather than a test-only timer write.
    for i in range(32 * 28): pb.memory[entities + i] = 0
    # PyBoy presents WRAM on a VBlank boundary; one previously scheduled
    # entity update can still finish with registers from the old room. Let
    # that frame drain, then inject into an empty table on a clean boundary.
    pb.tick()
    for i in range(32 * 28): pb.memory[entities + i] = 0
    px = pb.memory[player + 9] | (pb.memory[player + 10] << 8)
    py = pb.memory[player + 11] | (pb.memory[player + 12] << 8)
    surge = entities
    pb.memory[surge] = 3
    pb.memory[surge + 1] = 3
    put_fix8(pb, surge + 2, px + 4)
    put_fix8(pb, surge + 6, py + 8)
    pb.memory[surge + 12] = 126
    pb.memory[surge + 13] = 6
    pb.memory[surge + 16] = 255
    pb.memory[surge + 17] = 14
    pb.memory[surge + 25] = 0x66
    for _ in range(3): pb.tick()
    assert pb.memory[surge] == 0, "Surge Spark was not collected"
    assert pb.memory[surge_ticks] > 100, "Surge Spark did not start its temporary timer"
    assert any(pb.memory[0x8000 + 126 * 16 + i] for i in range(16)), \
        "Surge Spark OBJ art was not loaded"

    # Wolfkin's normal primary damage is item 2 + ATK 2. While surged it is
    # exactly one higher; nothing permanent is written to the ATK stat.
    base_atk = pb.memory[player + 5]
    pb.memory[player + 22] = 0
    pb.button("a")
    for _ in range(3): pb.tick()
    shot = first_player_shot(pb, entities)
    assert pb.memory[shot + 26] == base_atk + 3, "surged A attack lacked +1 damage"
    assert pb.memory[player + 5] == base_atk, "Surge Spark mutated permanent ATK"

    # The effect expires in active gameplay and normal primary damage returns.
    for _ in range(1200): pb.tick()
    assert pb.memory[surge_ticks] == 0, "Surge Spark timer did not expire"
    for i in range(32 * 28): pb.memory[entities + i] = 0
    pb.memory[player + 22] = 0
    pb.button("a")
    for _ in range(3): pb.tick()
    shot = first_player_shot(pb, entities)
    assert pb.memory[shot + 26] == base_atk + 2, "expired Surge Spark still boosted damage"
    pb.stop(save=False)
    print("[surge] PASS temporary primary damage + expiry + unique art")


if __name__ == "__main__":
    main()
