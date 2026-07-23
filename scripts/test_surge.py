#!/usr/bin/env python3
"""ROM contract: Surge Spark is visible, temporary, and class-shaped."""
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


def player_shots(pb, entities):
    return [entities + i * 28 for i in range(32)
            if pb.memory[entities + i * 28] == 1
            and pb.memory[entities + i * 28 + 1] & 0x10]


def clear_entities(pb, entities):
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    pb.tick()
    for i in range(32 * 28):
        pb.memory[entities + i] = 0


def boot_class(class_id, screen, player):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240): pb.tick()
    pb.button("start")
    for _ in range(30): pb.tick()
    for _ in range(class_id):
        pb.button("down")
        for _ in range(16): pb.tick()
    pb.button("a")
    for _ in range(80): pb.tick()
    assert pb.memory[screen] == 5 and pb.memory[player] == class_id, (
        f"could not enter live class-{class_id} room")
    return pb


def collect_surge(pb, player, entities, surge_ticks):
    clear_entities(pb, entities)
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


def main():
    player, entities, screen = map(addr, ("_player", "_entities", "_loop_current_screen"))
    surge_ticks = addr("_room_weapon_surge_ticks")
    # Item-authored base A damages for Wolfkin, Sauran, Corvin, Picsean,
    # Vespine.  Every one receives the shared +1 damage, then its own
    # geometry expression below.  Permanent ATK must never change.
    base_weapon_damage = (2, 4, 1, 2, 2)
    for class_id in range(5):
        pb = boot_class(class_id, screen, player)
        collect_surge(pb, player, entities, surge_ticks)
        base_atk = pb.memory[player + 5]
        pb.memory[player + 22] = 0
        pb.button("a")
        for _ in range(3): pb.tick()
        shots = player_shots(pb, entities)
        assert shots, f"class-{class_id} did not fire a surged A attack"
        assert all(pb.memory[shot + 26] == base_atk + base_weapon_damage[class_id] + 1
                   for shot in shots), f"class-{class_id} lacked shared Surge damage"
        assert pb.memory[player + 5] == base_atk, "Surge Spark mutated permanent ATK"
        if class_id == 0:
            assert len(shots) == 1 and pb.memory[shots[0] + 14] == 3, \
                "Wolfkin Razor Surge did not cleave an extra body"
        elif class_id == 1:
            # PyBoy may expose the queued A edge on the first or second tick.
            # Either sampling phase leaves 13/14 of the surged 16-frame life;
            # an ordinary 12-frame spike cannot satisfy this contract.
            assert len(shots) == 1 and pb.memory[shots[0] + 16] in (13, 14), \
                "Sauran Longtail Surge lost its extra reach"
        elif class_id == 2:
            assert len(shots) == 2, "Corvin Gale Surge did not open a feather lane"
            velocities = {(pb.memory[shot + 10], pb.memory[shot + 11]) for shot in shots}
            assert len(velocities) == 2, "Corvin Surge feathers overlap instead of widening"
        elif class_id == 3:
            assert len(shots) == 1 and pb.memory[shots[0] + 14] == 3 \
                and pb.memory[shots[0] + 25] == 0x99, \
                "Picsean Tide Surge lost its broad piercing bubble"
        else:
            assert len(shots) == 1 and pb.memory[shots[0] + 14] == 2, \
                "Vespine Thorn Surge did not pierce a second target"

        # One class also proves the boon really expires in live gameplay.
        if class_id == 0:
            for _ in range(1200): pb.tick()
            assert pb.memory[surge_ticks] == 0, "Surge Spark timer did not expire"
            clear_entities(pb, entities)
            pb.memory[player + 22] = 0
            pb.button("a")
            for _ in range(3): pb.tick()
            shot = first_player_shot(pb, entities)
            assert pb.memory[shot + 26] == base_atk + 2, \
                "expired Surge Spark still boosted damage"
        pb.stop(save=False)
    print("[surge] PASS shared temporary damage + five class-shaped A boons + expiry")


if __name__ == "__main__":
    main()
