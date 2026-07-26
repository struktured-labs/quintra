#!/usr/bin/env python3
"""ROM contract: dungeon merchants offer readable procedural build choices."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_BOSS_ROOM, dungeon_direction

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


RS, PL, EN, TM, SURGE, LARGE, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_weapon_surge_ticks", "_procgen_current_room_is_large",
    "_room_world_width", "_room_world_height",
    "_room_camera_x", "_room_camera_y"))


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

    # Make the next real graph transaction land in the opening shop two rooms
    # before its boss. The low seed byte selects both featured shelves.
    target = STAGE_BOSS_ROOM[0] - 2
    source = target - 1
    pb.memory[RS + 1] = source
    pb.memory[RS + 2] = seed_low
    pb.memory[RS + 3] = pb.memory[RS + 4] = pb.memory[RS + 5] = 0
    # The synthetic predecessor is compact even though the actual opening
    # foyer is now a scrolling field.
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
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


def shop_wares(pb):
    wares = []
    for i in range(32):
        e = EN + i * 28
        if pb.memory[e] == 3 and pb.memory[e + 17] == 4:
            wares.append(e)
    assert len(wares) == 3, f"merchant stock missing: {len(wares)}"
    return {pb.memory[e + 18]: e for e in wares}


def near(pb, ware):
    # One tile above: close enough for HUD context but not a purchase overlap.
    put16(pb, PL + 9, pb.memory[ware + 3])
    put16(pb, PL + 11, (pb.memory[ware + 7] - 20) & 0xFF)
    for _ in range(8):
        pb.tick()
    pb.memory[0xFF4F] = 0


def main():
    # Eight adjacent seeds cover the complete featured pool. Every shop keeps
    # healing and a mystery relic, then adds a seed-stable run-shaping offer
    # without consuming combat RNG.
    expected = (2, 5, 6, 3, 4, 7, 8, 2)
    for seed, featured in enumerate(expected):
        pb = boot_shop(seed)
        assert set(shop_wares(pb)) == {0, 1, featured}, (
            f"seed {seed} featured stock drifted: "
            f"{sorted(shop_wares(pb))} != {sorted({0, 1, featured})}"
        )
        pb.stop(save=False)

    # Seed one offers the cyan 15-second Surge. Verify the semantic shelf
    # treatment and real transaction, not a debugger write to its timer.
    pb = boot_shop(1)
    wares = shop_wares(pb)
    surge = wares[5]
    assert pb.memory[surge + 12] == 126 and pb.memory[surge + 13] == 6, \
        "Surge shelf does not use its distinct cyan orb"
    assert pb.memory[surge + 19] == 20, "Surge shelf price drifted"
    near(pb, surge)
    assert pb.memory[0x9C00 + 12] == 45, "Surge shelf lacks lightning HUD icon"
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
        "purchased Surge remained in stock "
        f"player={list(pb.memory[PL + 9:PL + 18])} "
        f"ware={list(pb.memory[surge:surge + 26])}")
    assert pb.memory[SURGE] > 100, "Surge did not start temporary weapon burst"
    assert pb.memory[PL + 16] == 79, "Surge charged the wrong price"
    pb.stop(save=False)
    print("[shop-surge] PASS seven-family procedural shelf + semantic HUD + Surge purchase")


if __name__ == "__main__":
    main()
