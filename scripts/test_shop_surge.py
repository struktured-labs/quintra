#!/usr/bin/env python3
"""ROM contract: seeded dungeon shops offer a readable Surge premium variant."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import dungeon_direction

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, TM, SURGE = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_weapon_surge_ticks"))


def put16(pb, where, value):
    pb.memory[where] = value & 0xFF
    pb.memory[where + 1] = (value >> 8) & 0xFF


def boot_shop(seed_low):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(90):
        pb.tick()

    # Make the next real graph transaction land in expanded opening shop room
    # 11. The low seed byte alone selects vitality (even) versus Surge (odd).
    source, target = 10, 11
    pb.memory[RS + 1] = source
    pb.memory[RS + 2] = seed_low
    pb.memory[RS + 3] = pb.memory[RS + 4] = pb.memory[RS + 5] = 0
    direction = dungeon_direction(source, target)
    for tx, ty in {
        0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
        2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
    }[direction]:
        pb.memory[TM + ty * 20 + tx] = 3
    x, y = {
        0: (72, 0), 1: (144, 60),
        2: (72, 120), 3: (0, 60),
    }[direction]
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    for _ in range(240):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, "could not enter seeded merchant room"
    for _ in range(60):
        pb.tick()
    return pb


def premium_ware(pb):
    wares = []
    for i in range(32):
        e = EN + i * 28
        if pb.memory[e] == 3 and pb.memory[e + 17] == 4:
            wares.append(e)
    assert len(wares) == 3, f"merchant stock missing: {len(wares)}"
    premium = [e for e in wares if pb.memory[e + 18] in (2, 5)]
    assert len(premium) == 1, "premium shelf did not have exactly one variant"
    return premium[0]


def near(pb, ware):
    # One tile above: close enough for HUD context but not a purchase overlap.
    put16(pb, PL + 9, pb.memory[ware + 3])
    put16(pb, PL + 11, (pb.memory[ware + 7] - 20) & 0xFF)
    for _ in range(8):
        pb.tick()
    pb.memory[0xFF4F] = 0


def main():
    # Even seed keeps the permanent vitality premium, including its old HUD
    # contract, so seed variation adds a choice rather than removes a build.
    pb = boot_shop(0)
    vital = premium_ware(pb)
    assert pb.memory[vital + 18] == 2
    assert pb.memory[vital + 12] == 35 and pb.memory[vital + 13] == 4
    near(pb, vital)
    assert pb.memory[0x9C00 + 12] == 42, "Iron Heart premium lost vital HUD icon"
    assert bytes(pb.memory[0x9C00 + 13:0x9C00 + 16]) == bytes((7, 13, 9))
    pb.stop(save=False)

    # Odd seed selects the cyan, temporary 15-second premium. Verify the real
    # walk-into transaction (currency, entity removal, HUD, and timer), not a
    # debugger write to the effect state.
    pb = boot_shop(1)
    surge = premium_ware(pb)
    assert pb.memory[surge + 18] == 5
    assert pb.memory[surge + 12] == 126 and pb.memory[surge + 13] == 6, \
        "Surge premium does not use its distinct cyan orb"
    assert pb.memory[surge + 19] == 20, "Surge premium price drifted"
    near(pb, surge)
    assert pb.memory[0x9C00 + 12] == 45, "Surge premium lacks lightning HUD icon"
    assert bytes(pb.memory[0x9C00 + 13:0x9C00 + 16]) == bytes((7, 11, 9))
    pb.memory[PL + 16] = 99
    pb.memory[PL + 17] = 0
    put16(pb, PL + 9, pb.memory[surge + 3])
    # Pickup collision is feet-anchored: stand with the hero's feet over the
    # orb, rather than aligning its visual top-left with the hero's top-left.
    put16(pb, PL + 11, (pb.memory[surge + 7] - 8) & 0xFF)
    for _ in range(8):
        pb.tick()
    assert pb.memory[surge] == 0, (
        "purchased Surge premium remained in stock "
        f"player={list(pb.memory[PL + 9:PL + 18])} "
        f"ware={list(pb.memory[surge:surge + 26])}")
    assert pb.memory[SURGE] > 100, "Surge premium did not start temporary weapon burst"
    assert pb.memory[PL + 16] == 79, "Surge premium charged the wrong price"
    pb.stop(save=False)
    print("[shop-surge] PASS seeded vitality/Surge shelves + visible purchase contract")


if __name__ == "__main__":
    main()
