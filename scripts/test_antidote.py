#!/usr/bin/env python3
"""Live-ROM contract: Poison is lethal, and the Antidote tool cures it.

Covers the poison tick (damage + repeating POISON notice), the lethal
last-half-heart rule, the automatic Antidote rescue, manual use from the
Pack TOOL row, and Antidote stock at the dungeon merchant and the Riftwild
wayside trader (restocked, no sold-out bit, three-vial pouch cap).
"""
import os
from pathlib import Path

from quintra_topology import STAGE_BOSS_ROOM
from test_shop_surge import boot_shop
from test_will_max import (
    ENTITIES, PLAYER, SCREEN, addr, boot, clear_arena, press, put16,
)

ROOT = Path(__file__).resolve().parent.parent
SHOTS = Path(os.environ.get("QUINTRA_SHOTS", ROOT / "tmp"))
SHOTS.mkdir(parents=True, exist_ok=True)

QSTATUS_NONE, QSTATUS_POISON = 0, 1
ITEM_ID_ANTIDOTE = 49
WARE_ANTIDOTE = 22
PICKUP_SHOP, PICKUP_MERCHANT = 4, 8
ENT_PICKUP, ENTITY_SIZE = 3, 28
SCREEN_ROOM = 5
INV = PLAYER + 24
STATUS = addr("_player_status_kind")
TICKS = addr("_player_status_ticks")
NOTICE = addr("_hud_notice_ticks")
RS = addr("_run_state")
LARGE = addr("_procgen_current_room_is_large")
WORLD_W, WORLD_H = addr("_room_world_width"), addr("_room_world_height")
CAMERA_X, CAMERA_Y = addr("_room_camera_x"), addr("_room_camera_y")
TM = addr("_room_tilemap")
SHOP_BOUGHT = 58
# Window row 0, columns 10..15: HUD notice lane. C U R E D glyph tiles.
CURED_TILES = (94, 65, 76, 86, 82)


def tick(pb, frames):
    for _ in range(frames):
        pb.tick()


def antidotes(pb):
    return sum(1 for i in range(16) if pb.memory[INV + i] == ITEM_ID_ANTIDOTE)


def set_inventory(pb, ids):
    for i in range(16):
        pb.memory[INV + i] = ids[i] if i < len(ids) else 0xFF


def coins(pb):
    return pb.memory[PLAYER + 16] | (pb.memory[PLAYER + 17] << 8)


def poison(pb, ticks):
    pb.memory[STATUS] = QSTATUS_POISON
    pb.memory[TICKS] = ticks


def window_notice(pb):
    pb.memory[0xFF4F] = 0
    return tuple(pb.memory[0x9C00 + 10 + i] for i in range(5))


def wares(pb, ware=None):
    out = []
    for i in range(32):
        e = ENTITIES + i * ENTITY_SIZE
        if (pb.memory[e] == ENT_PICKUP and pb.memory[e + 17] == PICKUP_SHOP
                and (ware is None or pb.memory[e + 18] == ware)):
            out.append(e)
    return out


def buy(pb, ware_entity):
    put16(pb, PLAYER + 9, pb.memory[ware_entity + 3])
    put16(pb, PLAYER + 11, max(0, pb.memory[ware_entity + 7] - 8))
    pb.memory[PLAYER + 15] = 120   # i-frames: no stray contact damage
    tick(pb, 8)
    # Step away so a second purchase needs a fresh contact.
    put16(pb, PLAYER + 11, max(0, pb.memory[ware_entity + 7] - 40))
    tick(pb, 4)


def test_poison_tick_and_rescue():
    pb = boot(0)
    try:
        clear_arena(pb)
        set_inventory(pb, [])
        # One beat before a damage tick: ticks 17 -> 16 lands a half-heart.
        pb.memory[PLAYER + 2] = 8
        pb.memory[NOTICE] = 0
        poison(pb, 17)
        tick(pb, 12)
        assert pb.memory[PLAYER + 2] == 7, (
            f"poison tick did not deal a half-heart: hp={pb.memory[PLAYER + 2]}")
        assert pb.memory[NOTICE] > 0, "poison tick did not re-show POISON"
        pb.screen.image.save(SHOTS / "antidote-poison-notice.png")

        # Last half-heart with an Antidote carried: spent instead of HP.
        tick(pb, 60)
        set_inventory(pb, [ITEM_ID_ANTIDOTE])
        pb.memory[PLAYER + 2] = 1
        pb.memory[NOTICE] = 0
        poison(pb, 17)
        tick(pb, 12)
        assert pb.memory[PLAYER + 2] == 1, "Antidote rescue still took the last HP"
        assert pb.memory[STATUS] == QSTATUS_NONE, "Antidote rescue did not cure"
        assert antidotes(pb) == 0, "Antidote rescue did not spend the vial"
        assert window_notice(pb) == CURED_TILES, (
            f"rescue did not show CURED: {window_notice(pb)}")
        pb.screen.image.save(SHOTS / "antidote-cured.png")

        # Without one, Poison is lethal: the same tick takes the last HP.
        tick(pb, 60)
        pb.memory[PLAYER + 2] = 1
        poison(pb, 17)
        tick(pb, 12)
        assert pb.memory[PLAYER + 2] == 0, "poison no longer takes the last HP"
    finally:
        pb.stop(save=False)


def test_pack_tool():
    pb = boot(0)
    try:
        clear_arena(pb)
        set_inventory(pb, [ITEM_ID_ANTIDOTE, ITEM_ID_ANTIDOTE])
        pb.memory[PLAYER + 2] = 8
        poison(pb, 110)
        press(pb, "start", held=4, released=40)
        assert pb.memory[SCREEN] != SCREEN_ROOM, "Pack did not open"
        pb.screen.image.save(SHOTS / "antidote-pack.png")
        press(pb, "a", held=4, released=60)
        assert pb.memory[SCREEN] == SCREEN_ROOM, "Antidote use did not resume"
        assert pb.memory[STATUS] == QSTATUS_NONE, "Pack Antidote did not cure"
        assert antidotes(pb) == 1, f"Pack use spent {2 - antidotes(pb)} vials"

        # Healthy: the Antidote refuses instead of wasting a vial.
        press(pb, "start", held=4, released=40)
        assert pb.memory[SCREEN] != SCREEN_ROOM
        press(pb, "a", held=4, released=30)
        assert pb.memory[SCREEN] != SCREEN_ROOM, "healthy A left the Pack"
        assert antidotes(pb) == 1, "healthy Pack A spent an Antidote"
        press(pb, "start", held=4, released=40)
    finally:
        pb.stop(save=False)


def test_dungeon_merchant():
    pb = boot_shop(1)
    try:
        stock = wares(pb, WARE_ANTIDOTE)
        assert len(stock) == 1, "dungeon merchant lacks the Antidote shelf"
        shelf = stock[0]
        assert pb.memory[shelf + 19] == 12, "Antidote price drifted"
        assert len(wares(pb)) == 5, "Antidote displaced a featured shelf"
        pb.screen.image.save(SHOTS / "antidote-merchant.png")
        set_inventory(pb, [])
        put16(pb, PLAYER + 16, 50)
        bought_before = pb.memory[RS + SHOP_BOUGHT]
        buy(pb, shelf)
        assert antidotes(pb) == 1 and coins(pb) == 38, (
            f"purchase failed: vials={antidotes(pb)} coins={coins(pb)}")
        assert pb.memory[RS + SHOP_BOUGHT] == bought_before, (
            "Antidote purchase marked a featured shelf sold")
        assert not wares(pb, WARE_ANTIDOTE), "bought Antidote stayed on the counter"
    finally:
        pb.stop(save=False)


def test_riftwild_trader():
    pb = boot(0)
    try:
        pb.memory[RS + 1] = STAGE_BOSS_ROOM[0]
        pb.memory[RS + 11] = 1
        pb.memory[LARGE] = 0
        pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
        pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
        pb.memory[0xFF43] = pb.memory[0xFF42] = 0
        pb.memory[TM + 16 * 20 + 9] = 3
        pb.memory[TM + 16 * 20 + 10] = 3
        put16(pb, PLAYER + 9, 72)
        put16(pb, PLAYER + 11, 120)
        tick(pb, 180)
        assert pb.memory[RS + 17] == 1, "did not enter the Riftwild"
        put16(pb, PLAYER + 9, 232)
        put16(pb, PLAYER + 11, 60)
        tick(pb, 90)
        assert pb.memory[RS + 18] == 1, "did not reach the Riftwell crossing"
        stock = wares(pb, WARE_ANTIDOTE)
        assert len(stock) == 1, "Riftwild trader lacks the Antidote"
        assert any(pb.memory[ENTITIES + i * ENTITY_SIZE] == ENT_PICKUP
                   and pb.memory[ENTITIES + i * ENTITY_SIZE + 17] == PICKUP_MERCHANT
                   for i in range(32)), "Riftwild trader has no keeper"
        pb.screen.image.save(SHOTS / "antidote-riftwild-trader.png")
        set_inventory(pb, [])
        put16(pb, PLAYER + 16, 30)
        # Bought while poisoned: used on the spot.
        pb.memory[PLAYER + 2] = 6
        poison(pb, 110)
        buy(pb, stock[0])
        assert coins(pb) == 18, f"Riftwild purchase coins={coins(pb)}"
        assert pb.memory[STATUS] == QSTATUS_NONE, "poisoned purchase did not cure"
        assert antidotes(pb) == 0, "poisoned purchase kept the used vial"
        # Restocked on every visit: leave west and come back.
        put16(pb, PLAYER + 9, 0); put16(pb, PLAYER + 11, 60); tick(pb, 90)
        assert pb.memory[RS + 18] == 0
        put16(pb, PLAYER + 9, 232); put16(pb, PLAYER + 11, 60); tick(pb, 90)
        stock = wares(pb, WARE_ANTIDOTE)
        assert pb.memory[RS + 18] == 1 and len(stock) == 1, \
            "Riftwild Antidote did not restock"
        # A full three-vial pouch refuses without taking coins.
        set_inventory(pb, [ITEM_ID_ANTIDOTE] * 3)
        pb.memory[STATUS] = QSTATUS_NONE
        buy(pb, stock[0])
        assert coins(pb) == 18 and antidotes(pb) == 3, (
            f"full pouch bought anyway: coins={coins(pb)} vials={antidotes(pb)}")
        assert len(wares(pb, WARE_ANTIDOTE)) == 1, "refused Antidote vanished"
        # And it sits off the trail: walking the east-west lane at y=60
        # past the trader must not buy it by accident.
        set_inventory(pb, [])
        put16(pb, PLAYER + 9, 100); put16(pb, PLAYER + 11, 60)
        pb.button_press("right"); tick(pb, 40); pb.button_release("right")
        tick(pb, 4)
        assert coins(pb) == 18 and antidotes(pb) == 0, \
            "walking the trail bought the Riftwild Antidote"
    finally:
        pb.stop(save=False)


def main():
    test_poison_tick_and_rescue()
    test_pack_tool()
    test_dungeon_merchant()
    test_riftwild_trader()
    print("[antidote] PASS lethal poison tick + notice, auto rescue, Pack cure, "
          "merchant and Riftwild trader stock")


if __name__ == "__main__":
    main()
