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


RS, PL, EN, TM, SURGE, LARGE, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y, ESTATUS, HNOTICE = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_weapon_surge_ticks", "_procgen_current_room_is_large",
    "_room_world_width", "_room_world_height",
    "_room_camera_x", "_room_camera_y", "_enemy_status_kind",
    "_hud_notice_ticks"))


def put16(pb, where, value):
    pb.memory[where] = value & 0xFF
    pb.memory[where + 1] = (value >> 8) & 0xFF


def put_fix8(pb, where, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[where + i] = (raw >> (i * 8)) & 0xFF


def boot_shop(seed_low, owned=()):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(90):
        pb.tick()
    for i, item_id in enumerate(owned):
        pb.memory[PL + 24 + i] = item_id

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


def touch_ware(pb, ware, purse=99):
    pb.memory[PL + 16] = purse & 0xFF
    pb.memory[PL + 17] = purse >> 8
    put16(pb, PL + 9, pb.memory[ware + 3])
    put16(pb, PL + 11, (pb.memory[ware + 7] - 8) & 0xFF)
    for _ in range(12):
        pb.tick()


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

def signed8(value):
    return value - 256 if value & 0x80 else value


def get16(pb, where):
    return pb.memory[where] | pb.memory[where + 1] << 8


def inject_lethal_crawler(pb):
    clear_entities(pb)
    px = pb.memory[PL + 9] | pb.memory[PL + 10] << 8
    py = pb.memory[PL + 11] | pb.memory[PL + 12] << 8
    enemy, shot = EN, EN + 28
    pb.memory[enemy] = 2
    pb.memory[enemy + 1] = 7  # active + alive + on-screen
    put16(pb, enemy + 3, px)
    put16(pb, enemy + 7, py)
    pb.memory[enemy + 14] = 1
    pb.memory[enemy + 17] = 0
    pb.memory[enemy + 25] = 0x88
    pb.memory[shot] = 1
    pb.memory[shot + 1] = 0x13
    put16(pb, shot + 3, px)
    put16(pb, shot + 7, py)
    pb.memory[shot + 14] = 1
    pb.memory[shot + 16] = 30
    pb.memory[shot + 25] = 0x77
    pb.memory[shot + 26] = 20
    for _ in range(8):
        pb.tick()
        if pb.memory[enemy] == 0:
            return
    raise AssertionError("synthetic fifth kill did not resolve")


def main():
    # Forty-two adjacent seeds cover the complete 6x7 catalog. Every shop keeps
    # healing and a class-attuned sealed relic, then guarantees one build
    # shelf and one tactical shelf without consuming combat RNG.
    build_pool = (6, 8, 9, 12, 13, 14)
    tactical_pool = (5, 7, 10, 11, 15, 16, 18)
    ware_art = {
        0: 30, 5: 143, 6: 140, 7: 142, 8: 141, 9: 138,
        10: 144, 11: 150, 12: 145, 13: 146, 14: 147,
        15: 148, 16: 149, 18: 128,
    }
    for seed in range(42):
        pb = boot_shop(seed)
        expected = {
            0, 1, build_pool[seed % 6], tactical_pool[(seed // 6) % 7],
        }
        assert set(shop_wares(pb)) == expected, (
            f"seed {seed} featured stock drifted: "
            f"{sorted(shop_wares(pb))} != {sorted(expected)}"
        )
        wares = shop_wares(pb)
        for ware, tile in ware_art.items():
            if ware in wares:
                assert pb.memory[wares[ware] + 12] == tile, (
                    f"ware {ware} lost its semantic world silhouette"
                )
        assert 131 <= pb.memory[wares[1] + 12] <= 140, \
            "class-attuned relic fell back to a generic orb"
        # WARE_ITEM payload is one of Wolfkin's class-attuned combat relics,
        # not a purchase-time random low-stat roll.
        assert pb.memory[shop_wares(pb)[1] + 20] in (12, 17, 19)
        pb.stop(save=False)

    # A later merchant must advance past a unique relic already carried.
    # Seed three normally selects Echo; carrying Echo rotates that build
    # shelf to Ricochet rather than presenting an unusable duplicate.
    owned_pb = boot_shop(3, owned=(34,))
    assert 12 not in shop_wares(owned_pb) and 13 in shop_wares(owned_pb), \
        "owned unique relic left a dead merchant counter"
    owned_pb.stop(save=False)

    # Paid healing is a transaction, not an ambient pickup: at full health
    # the merchant must leave both the ware and the purse untouched.
    full_hp_pb = boot_shop(0)
    heart_ware = shop_wares(full_hp_pb)[0]
    full_hp_pb.memory[PL + 2] = full_hp_pb.memory[PL + 1]
    touch_ware(full_hp_pb, heart_ware)
    assert full_hp_pb.memory[heart_ware] == 3, \
        "full-health merchant heal vanished without helping"
    assert (full_hp_pb.memory[PL + 16]
            | full_hp_pb.memory[PL + 17] << 8) == 99, \
        "full-health merchant heal still charged coins"
    full_hp_pb.stop(save=False)

    # A full Pack cannot accept another persistent contract. Refuse the sale
    # before taking coins instead of destroying the Echo Prism on delivery.
    full_pack_pb = boot_shop(3)
    echo_ware = shop_wares(full_pack_pb)[12]
    for slot in range(16):
        full_pack_pb.memory[PL + 24 + slot] = 40 + slot
    touch_ware(full_pack_pb, echo_ware)
    assert full_pack_pb.memory[echo_ware] == 3, \
        "full-Pack unique relic vanished without entering inventory"
    assert (full_pack_pb.memory[PL + 16]
            | full_pack_pb.memory[PL + 17] << 8) == 99, \
        "full-Pack unique relic still charged coins"
    assert 34 not in inventory(full_pack_pb)
    full_pack_pb.stop(save=False)

    # Blood Sigil is behavioral, not merely +ATK/+HP. A full Pack must refuse
    # it before payment if id 29 cannot be stored for the fifth-kill hook.
    full_vamp_pb = boot_shop(0)
    vamp_ware = shop_wares(full_vamp_pb)[6]
    for slot in range(16):
        full_vamp_pb.memory[PL + 24 + slot] = 40 + slot
    touch_ware(full_vamp_pb, vamp_ware)
    assert full_vamp_pb.memory[vamp_ware] == 3
    assert (full_vamp_pb.memory[PL + 16]
            | full_vamp_pb.memory[PL + 17] << 8) == 99
    assert 29 not in inventory(full_vamp_pb)
    full_vamp_pb.stop(save=False)

    # Fully capped stats make the class-attuned relic a no-op. It must remain
    # on the counter rather than charging for no mechanical change.
    capped_pb = boot_shop(0)
    capped_item = shop_wares(capped_pb)[1]
    for offset, value in ((1, 16), (3, 20), (5, 15),
                          (6, 10), (7, 9), (8, 10)):
        capped_pb.memory[PL + offset] = value
    touch_ware(capped_pb, capped_item)
    assert capped_pb.memory[capped_item] == 3, \
        "fully capped merchant relic vanished without changing a stat"
    assert (capped_pb.memory[PL + 16]
            | capped_pb.memory[PL + 17] << 8) == 99
    capped_pb.stop(save=False)

    # A dungeon merchant's chart is useful immediately: it reveals the
    # active route and does not accidentally queue an unrelated future map.
    chart_pb = boot_shop(8)
    buy(chart_pb, 7)
    assert tuple(chart_pb.memory[RS + offset]
                 for offset in (20, 29, 31, 33)) == (0xFF, 0xFF, 0xFF, 0x3F), \
        "dungeon chart did not reveal the active 30-cell route"
    assert tuple(chart_pb.memory[RS + offset]
                 for offset in (25, 30, 32, 34)) == (0, 0, 0, 0), \
        "dungeon chart leaked into the next-dungeon reveal queue"
    chart_pb.stop(save=False)

    # The same chart cannot be repurchased once the active route is already
    # completely known.
    known_pb = boot_shop(8)
    known_chart = shop_wares(known_pb)[7]
    for offset, value in zip((20, 29, 31, 33),
                             (0xFF, 0xFF, 0xFF, 0x3F)):
        known_pb.memory[RS + offset] = value
    touch_ware(known_pb, known_chart)
    assert known_pb.memory[known_chart] == 3
    assert (known_pb.memory[PL + 16]
            | known_pb.memory[PL + 17] << 8) == 99
    known_pb.stop(save=False)

    # Seed zero offers the cyan 15-second Surge. Verify its lightning-bolt
    # silhouette (color is now a secondary cue) and the real transaction,
    # not a debugger write to its timer.
    pb = boot_shop(0)
    wares = shop_wares(pb)
    surge = wares[5]
    assert pb.memory[surge + 12] == 143 and pb.memory[surge + 13] == 6, \
        "Surge shelf does not use its distinct cyan lightning silhouette"
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
    phoenix_pb = boot_shop(16)
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
    ascend_pb = boot_shop(18)
    ascend_pb.memory[PL + 4] = 0
    buy(ascend_pb, 11)
    assert ascend_pb.memory[PL + 4] == ascend_pb.memory[PL + 3]
    assert ascend_pb.memory[SURGE] > 100
    ascend_pb.stop(save=False)

    # Ricochet Rune gives the next physical or ranged attack exactly one
    # visible stone rebound. Use the shop's own west wall as the fixture.
    ricochet_pb = boot_shop(4)
    buy(ricochet_pb, 13)
    assert 35 in inventory(ricochet_pb), "Ricochet Rune is not recorded"
    clear_entities(ricochet_pb)
    put16(ricochet_pb, PL + 9, 40)
    put16(ricochet_pb, PL + 11, 60)
    ricochet_pb.memory[PL + 13] = 1  # face east
    ricochet_pb.memory[PL + 22] = 0
    ricochet_pb.memory[TM + 8 * 20 + 7] = 2
    ricochet_pb.button_press("a")
    for _ in range(2):
        ricochet_pb.tick()
    ricochet_pb.button_release("a")
    bounced = False
    for _ in range(20):
        ricochet_pb.tick()
        shots = player_projectiles(ricochet_pb)
        if shots and signed8(ricochet_pb.memory[shots[0] + 10]) < 0:
            assert ricochet_pb.memory[shots[0] + 20] == 0
            bounced = True
            break
    assert bounced, "Ricochet Rune attack never returned from stone"
    ricochet_pb.stop(save=False)

    # Thorn Crown answers a real hostile impact with four player-owned lanes.
    thorn_pb = boot_shop(5)
    buy(thorn_pb, 14)
    assert 36 in inventory(thorn_pb), "Thorn Crown is not recorded"
    clear_entities(thorn_pb)
    thorn_pb.memory[PL + 2] = thorn_pb.memory[PL + 1]
    thorn_pb.memory[PL + 15] = 0
    px = thorn_pb.memory[PL + 9] | thorn_pb.memory[PL + 10] << 8
    py = thorn_pb.memory[PL + 11] | thorn_pb.memory[PL + 12] << 8
    hostile = EN
    thorn_pb.memory[hostile] = 1
    thorn_pb.memory[hostile + 1] = 3
    put_fix8(thorn_pb, hostile + 2, px + 5)
    put_fix8(thorn_pb, hostile + 6, py + 9)
    thorn_pb.memory[hostile + 14] = 1
    thorn_pb.memory[hostile + 16] = 30
    thorn_pb.memory[hostile + 25] = 0x77
    thorn_pb.memory[hostile + 26] = 2
    for _ in range(4):
        thorn_pb.tick()
    assert thorn_pb.memory[PL + 2] < thorn_pb.memory[PL + 1]
    assert len(player_projectiles(thorn_pb)) == 4, \
        "Thorn Crown did not answer damage with four lanes"
    thorn_pb.stop(save=False)

    # War Drum makes each fifth real kill a B-refresh + A+B-resource beat.
    drum_pb = boot_shop(24)
    buy(drum_pb, 15)
    assert 37 in inventory(drum_pb), "War Drum is not recorded"
    drum_pb.memory[RS + 16] = 4
    drum_pb.memory[PL + 4] = 0
    drum_pb.memory[PL + 19] = 100
    drum_pb.memory[PL + 15] = 60
    inject_lethal_crawler(drum_pb)
    assert drum_pb.memory[RS + 16] == 5
    assert drum_pb.memory[PL + 19] == 0, "War Drum did not ready B"
    assert drum_pb.memory[PL + 4] == 1, "War Drum did not restore MP"
    drum_pb.stop(save=False)

    # Moon Flask consumes a surplus heart only when it can distill that
    # otherwise-dead recovery into MP.
    flask_pb = boot_shop(30)
    buy(flask_pb, 16)
    assert 38 in inventory(flask_pb), "Moon Flask is not recorded"
    clear_entities(flask_pb)
    flask_pb.memory[PL + 2] = flask_pb.memory[PL + 1]
    flask_pb.memory[PL + 4] = 0
    px = flask_pb.memory[PL + 9] | flask_pb.memory[PL + 10] << 8
    py = flask_pb.memory[PL + 11] | flask_pb.memory[PL + 12] << 8
    heart = EN
    flask_pb.memory[heart] = 3
    flask_pb.memory[heart + 1] = 3
    put_fix8(flask_pb, heart + 2, px + 5)
    put_fix8(flask_pb, heart + 6, py + 9)
    flask_pb.memory[heart + 14] = 1
    flask_pb.memory[heart + 16] = 30
    flask_pb.memory[heart + 17] = 0
    flask_pb.memory[heart + 25] = 0x66
    for _ in range(4):
        flask_pb.tick()
    assert flask_pb.memory[heart] == 0, "Moon Flask left surplus heart behind"
    assert flask_pb.memory[PL + 4] == 1, "Moon Flask did not distill MP"
    flask_pb.stop(save=False)

    # Boomerang fills B's cooldown with one reusable utility projectile. It
    # stops ordinary bodies, ignores bosses, cuts shots, fetches loose loot,
    # and must return before another one can exist.
    boom_pb = boot_shop(36)
    boom_ware = shop_wares(boom_pb)[18]
    assert boom_pb.memory[boom_ware + 19] == 30
    buy(boom_pb, 18)
    assert 45 in inventory(boom_pb), "Boomerang is not recorded in the run"
    assert boom_pb.memory[HNOTICE] > 0, "Boomerang purchase lacks a HUD notice"
    assert bytes(boom_pb.memory[0x9C00 + 10:0x9C00 + 16]) == bytes(
        (64, 89, 89, 87, 86, 76)), "Boomerang purchase notice is not BOOMER"
    clear_entities(boom_pb)
    for tile in range(20 * 17):
        boom_pb.memory[TM + tile] = 1
    put16(boom_pb, PL + 9, 64)
    put16(boom_pb, PL + 11, 64)
    boom_pb.memory[PL + 13] = 1
    boom_pb.memory[PL + 19] = 80
    boom_pb.button_press("b")
    for _ in range(2):
        boom_pb.tick()
    boom_pb.button_release("b")
    booms = [shot for shot in player_projectiles(boom_pb)
             if boom_pb.memory[shot + 23] == 0xF4]
    assert len(booms) == 1, "cooling B did not throw one Boomerang"
    boom = booms[0]
    assert boom_pb.memory[boom + 12] == 128
    assert boom_pb.memory[boom + 26] == 0
    boom_pb.button_press("b")
    for _ in range(2):
        boom_pb.tick()
    boom_pb.button_release("b")
    assert sum(boom_pb.memory[shot + 23] == 0xF4
               for shot in player_projectiles(boom_pb)) == 1

    enemy = next(EN + i * 28 for i in range(32)
                 if not boom_pb.memory[EN + i * 28 + 1])
    enemy_slot = (enemy - EN) // 28
    bx = get16(boom_pb, boom + 3) + signed8(boom_pb.memory[boom + 10])
    by = get16(boom_pb, boom + 7) + signed8(boom_pb.memory[boom + 11])
    boom_pb.memory[enemy] = 2
    boom_pb.memory[enemy + 1] = 7
    put16(boom_pb, enemy + 3, bx)
    put16(boom_pb, enemy + 7, by)
    boom_pb.memory[enemy + 14] = 9
    boom_pb.memory[enemy + 17] = 0
    boom_pb.memory[enemy + 25] = 0x88
    boom_pb.tick()
    assert boom_pb.memory[ESTATUS + enemy_slot] == 4, (
        f"Boomerang did not stop ordinary enemy: status="
        f"{boom_pb.memory[ESTATUS + enemy_slot]} "
        f"boom={list(boom_pb.memory[boom:boom + 28])} "
        f"enemy={list(boom_pb.memory[enemy:enemy + 28])}")
    assert boom_pb.memory[enemy + 14] == 9, "Boomerang dealt damage"

    boom_pb.memory[ESTATUS + enemy_slot] = 0
    boom_pb.memory[enemy + 17] = 1
    boom_pb.memory[enemy + 20] = 1
    bx = get16(boom_pb, boom + 3) + signed8(boom_pb.memory[boom + 10])
    by = get16(boom_pb, boom + 7) + signed8(boom_pb.memory[boom + 11])
    put16(boom_pb, enemy + 3, bx)
    put16(boom_pb, enemy + 7, by)
    boom_pb.tick()
    assert boom_pb.memory[ESTATUS + enemy_slot] == 0, \
        "Colossus body was stopped by Boomerang"
    boom_pb.memory[enemy] = boom_pb.memory[enemy + 1] = 0

    hostile = next(EN + i * 28 for i in range(32)
                   if not boom_pb.memory[EN + i * 28 + 1])
    for offset in range(28):
        boom_pb.memory[hostile + offset] = 0
    bx = get16(boom_pb, boom + 3) + signed8(boom_pb.memory[boom + 10])
    by = get16(boom_pb, boom + 7) + signed8(boom_pb.memory[boom + 11])
    boom_pb.memory[hostile] = 1
    boom_pb.memory[hostile + 1] = 3
    put16(boom_pb, hostile + 3, bx)
    put16(boom_pb, hostile + 7, by)
    boom_pb.memory[hostile + 14] = 1
    boom_pb.memory[hostile + 16] = 30
    boom_pb.memory[hostile + 25] = 0x77
    boom_pb.memory[hostile + 26] = 1
    for _ in range(3):
        boom_pb.tick()
        if boom_pb.memory[hostile] == 0:
            break
    assert boom_pb.memory[hostile] == 0, (
        f"Boomerang did not cut hostile shot: "
        f"boom={list(boom_pb.memory[boom:boom + 28])} "
        f"hostile={list(boom_pb.memory[hostile:hostile + 28])}")

    coin = next(EN + i * 28 for i in range(32)
                if not boom_pb.memory[EN + i * 28 + 1])
    for offset in range(28):
        boom_pb.memory[coin + offset] = 0
    bx = get16(boom_pb, boom + 3) + signed8(boom_pb.memory[boom + 10])
    by = get16(boom_pb, boom + 7) + signed8(boom_pb.memory[boom + 11])
    boom_pb.memory[coin] = 3
    boom_pb.memory[coin + 1] = 3
    put16(boom_pb, coin + 3, bx)
    put16(boom_pb, coin + 7, by)
    boom_pb.memory[coin + 14] = 1
    boom_pb.memory[coin + 16] = 30
    boom_pb.memory[coin + 17] = 1
    boom_pb.memory[coin + 25] = 0x66
    old_coins = get16(boom_pb, PL + 16)
    for _ in range(3):
        boom_pb.tick()
        if boom_pb.memory[coin] == 0:
            break
    assert boom_pb.memory[coin] == 0 and get16(boom_pb, PL + 16) == old_coins + 1, \
        (f"Boomerang did not fetch loose coin: "
         f"boom={list(boom_pb.memory[boom:boom + 28])} "
         f"coin={list(boom_pb.memory[coin:coin + 28])}")

    turned = False
    for _ in range(80):
        boom_pb.tick()
        if boom_pb.memory[boom] == 0:
            break
        turned |= boom_pb.memory[boom + 15] == 1
    assert turned and boom_pb.memory[boom] == 0, \
        "Boomerang did not turn and return to the champion"
    boom_pb.stop(save=False)

    print("[shop-surge] PASS four-counter 6x7 procedural catalog "
          "+ atomic heal/chart/full-Pack transactions "
          "+ Glass/Echo/Phoenix/Spirit/Ricochet/Thorn/Drum/Flask/Boomerang mechanics")


if __name__ == "__main__":
    main()
