#!/usr/bin/env python3
"""ROM contract: common combat relics visibly mutate the live A attack."""

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


PL, EN, TM, TRAITS = map(addr, (
    "_player", "_entities", "_room_tilemap", "_g_player_attack_traits",
))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    pb.button("a")
    pb.tick(60)
    for i in range(20 * 17):
        pb.memory[TM + i] = 1
    return pb


def clear_entities(pb):
    for i in range(32 * 28):
        pb.memory[EN + i] = 0


def collect_item(pb, item_index):
    clear_entities(pb)
    e = EN
    e_x = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    e_y = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    pb.memory[e] = 3
    pb.memory[e + 1] = 0x03
    put16(pb, e + 3, e_x + 5)
    put16(pb, e + 7, e_y + 9)
    pb.memory[e + 14] = 1
    pb.memory[e + 16] = 60
    pb.memory[e + 17] = 3       # PICKUP_ITEM
    pb.memory[e + 18] = item_index
    pb.memory[e + 25] = 0x66
    pb.tick(3)
    assert pb.memory[e] == 0, f"item index {item_index} was not collected"


def directed_fang(pb):
    clear_entities(pb)
    pb.memory[PL + 22] = 0
    pb.memory[PL + 42] = 0
    pb.button_press("right")
    pb.button_press("a")
    pb.tick(3)
    pb.button_release("a")
    pb.button_release("right")
    return next(EN + i * 28 for i in range(32)
                if pb.memory[EN + i * 28] == 1
                and pb.memory[EN + i * 28 + 1] & 0x10)


def main():
    # generated items[] indices: PowerStone 12, Swift Fang 17, VampSigil 19.
    power = boot()
    collect_item(power, 12)
    assert power.memory[TRAITS] & 1
    shot = directed_fang(power)
    assert power.memory[shot + 25] == 0x99, "PowerStone did not broaden Fang"
    assert power.memory[shot + 26] == 4 and power.memory[shot + 13] == 4, \
        "PowerStone did not visibly strengthen/recolor Fang"
    power.stop(save=False)

    swift = boot()
    collect_item(swift, 17)
    assert swift.memory[TRAITS] & 2
    shot = directed_fang(swift)
    assert swift.memory[shot + 10] == 4 and swift.memory[shot + 13] == 5, \
        "Swift Fang did not accelerate/gild the live attack"
    swift.stop(save=False)

    blood = boot()
    collect_item(blood, 19)
    assert blood.memory[TRAITS] & 4
    shot = directed_fang(blood)
    assert blood.memory[shot + 26] == 4 and blood.memory[shot + 13] == 4, \
        "VampSigil did not stain its strengthened attack red"
    blood.stop(save=False)
    print("[attack-relics] PASS Power width + Swift velocity + Vamp attack identity")


if __name__ == "__main__":
    main()
