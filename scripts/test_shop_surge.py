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


def put_fix8(pb, where, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[where + i] = (raw >> (i * 8)) & 0xFF


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
    assert len(wares) == 4, f"merchant stock missing: {len(wares)}"
    return {pb.memory[e + 18]: e for e in wares}


def near(pb, ware):
    # One tile above: close enough for HUD context but not a purchase overlap.
    put16(pb, PL + 9, pb.memory[ware + 3])
    put16(pb, PL + 11, (pb.memory[ware + 7] - 20) & 0xFF)
    for _ in range(8):
        pb.tick()
    pb.memory[0xFF4F] = 0


def buy(pb, ware_kind, purse=99):
    ware = shop_wares(pb)[ware_kind]
    pb.memory[PL + 16] = purse & 0xFF
    pb.memory[PL + 17] = purse >> 8
    put16(pb, PL + 9, pb.memory[ware + 3])
    put16(pb, PL + 11, (pb.memory[ware + 7] - 8) & 0xFF)
    for _ in range(12):
        pb.tick()
        if pb.memory[ware] == 0:
            break
    assert pb.memory[ware] == 0, f"ware {ware_kind} was not purchased"
    return ware


def inventory(pb):
    return tuple(pb.memory[PL + 24 + i] for i in range(16))


def clear_entities(pb):
    for i in range(32 * 28):
        pb.memory[EN + i] = 0


def player_projectiles(pb):
    return [
        EN + i * 28 for i in range(32)
        if pb.memory[EN + i * 28] == 1
        and pb.memory[EN + i * 28 + 1] & 0x10
    ]


def main():
    # Sixteen adjacent seeds cover the complete 4x4 catalog. Every shop keeps
    # healing and a class-attuned sealed relic, then guarantees one build
    # shelf and one tactical shelf without consuming combat RNG.
    build_pool = (6, 8, 9, 12)
    tactical_pool = (5, 7, 10, 11)
    for seed in range(16):
        pb = boot_shop(seed)
        expected = {0, 1, build_pool[seed & 3], tactical_pool[(seed >> 2) & 3]}
        assert set(shop_wares(pb)) == expected, (
            f"seed {seed} featured stock drifted: "
            f"{sorted(shop_wares(pb))} != {sorted(expected)}"
        )
        # WARE_ITEM payload is one of Wolfkin's class-attuned combat relics,
        # not a purchase-time random low-stat roll.
        assert pb.memory[shop_wares(pb)[1] + 20] in (12, 17, 19)
        pb.stop(save=False)

    # Seed zero offers the cyan 15-second Surge. Verify the semantic shelf
    # treatment and real transaction, not a debugger write to its timer.
    pb = boot_shop(0)
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

    # Glass Fang is a real roguelike bargain, not a renamed +1: one visible
    # max heart is sacrificed for a large offense/cadence jump.
    glass_pb = boot_shop(2)
    old_hp_max, old_atk, old_spd = (
        glass_pb.memory[PL + 1], glass_pb.memory[PL + 5],
        glass_pb.memory[PL + 7])
    buy(glass_pb, 9)
    assert glass_pb.memory[PL + 1] == old_hp_max - 2
    assert glass_pb.memory[PL + 2] <= old_hp_max - 2
    assert glass_pb.memory[PL + 5] == old_atk + 2
    assert glass_pb.memory[PL + 7] == old_spd + 1
    assert 32 in inventory(glass_pb), "Glass Fang is not recorded in the run"
    glass_pb.stop(save=False)

    # Echo Prism forks exactly the fourth primary A attack into two side
    # lanes. Clear the safe shop entities between strikes so counts describe
    # only the new attack without altering the relic's persistent cadence.
    echo_pb = boot_shop(3)
    buy(echo_pb, 12)
    assert 34 in inventory(echo_pb), "Echo Prism is not recorded in the run"
    clear_entities(echo_pb)
    for attack in range(4):
        echo_pb.memory[PL + 22] = 0
        echo_pb.button_press("a")
        for _ in range(2):
            echo_pb.tick()
        echo_pb.button_release("a")
        count = len(player_projectiles(echo_pb))
        assert count == (3 if attack == 3 else 1), (
            f"Echo attack {attack + 1} emitted {count} lanes")
        clear_entities(echo_pb)
        for _ in range(2):
            echo_pb.tick()
    echo_pb.stop(save=False)

    # Phoenix Cord intercepts a real lethal hostile projectile, restores half
    # health, remains in the room, and consumes itself.
    phoenix_pb = boot_shop(8)
    buy(phoenix_pb, 10)
    assert 33 in inventory(phoenix_pb), "Phoenix Cord is not recorded in the run"
    clear_entities(phoenix_pb)
    phoenix_pb.memory[PL + 2] = 1
    phoenix_pb.memory[PL + 15] = 0
    px = phoenix_pb.memory[PL + 9] | phoenix_pb.memory[PL + 10] << 8
    py = phoenix_pb.memory[PL + 11] | phoenix_pb.memory[PL + 12] << 8
    hostile = EN + 31 * 28
    phoenix_pb.memory[hostile] = 1
    phoenix_pb.memory[hostile + 1] = 3
    put_fix8(phoenix_pb, hostile + 2, px + 5)
    put_fix8(phoenix_pb, hostile + 6, py + 9)
    phoenix_pb.memory[hostile + 14] = 5
    phoenix_pb.memory[hostile + 16] = 30
    phoenix_pb.memory[hostile + 25] = 0x77
    phoenix_pb.memory[hostile + 26] = 1
    for _ in range(60):
        phoenix_pb.tick()
        if 33 not in inventory(phoenix_pb):
            break
    assert 33 not in inventory(phoenix_pb), "Phoenix Cord was not consumed"
    assert phoenix_pb.memory[PL + 2] == (
        phoenix_pb.memory[PL + 1] + 1) // 2, "Phoenix restored wrong HP"
    assert phoenix_pb.memory[PL + 15] > 0, "Phoenix revival lacks safety frames"
    phoenix_pb.stop(save=False)

    # Spirit Draught immediately makes the hidden full-MP A+B transformation
    # available and starts a useful weapon-shaped Surge window.
    ascend_pb = boot_shop(12)
    ascend_pb.memory[PL + 4] = 0
    buy(ascend_pb, 11)
    assert ascend_pb.memory[PL + 4] == ascend_pb.memory[PL + 3]
    assert ascend_pb.memory[SURGE] > 100
    ascend_pb.stop(save=False)

    print("[shop-surge] PASS four-counter 4x4 procedural catalog "
          "+ class relic + Glass/Echo/Phoenix/Spirit mechanics")


if __name__ == "__main__":
    main()
