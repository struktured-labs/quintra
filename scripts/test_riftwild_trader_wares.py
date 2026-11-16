#!/usr/bin/env python3
"""Live-ROM contract: the Riftwild wayside trader always shows its wares.

Regression for "in riftwild, merchant with no wares" (615a4963): the
Antidote vial sat directly between the east-west trail and its keeper, so
walking up to talk bought it on contact and the keeper's TODAYS WARES page
came up empty until the field was re-entered. World fields also reloaded
the Colossus shot atlas over resident tiles 208..223, so the trader itself
drew as a fireball.

Across seeds and regions this checks: the keeper uses the town merchant
art, walking straight up from the trail to talk never buys, the talk page
lists the Antidote, a deliberate purchase leaves the restocked vial on the
counter (one purchase per contact), and an empty shelf reads SOLD OUT.
"""
import os
import re
from pathlib import Path

from quintra_topology import STAGE_BOSS_ROOM
from test_will_max import ENTITIES, PLAYER, addr, boot, press, put16

ROOT = Path(__file__).resolve().parent.parent
SHOTS = Path(os.environ.get("QUINTRA_SHOTS", ROOT / "tmp"))
SHOTS.mkdir(parents=True, exist_ok=True)

ITEM_ID_ANTIDOTE = 49
WARE_ANTIDOTE = 22
PICKUP_SHOP, PICKUP_MERCHANT = 4, 8
ENT_PICKUP, ENTITY_SIZE = 3, 28
INV = PLAYER + 24
RS = addr("_run_state")
LARGE = addr("_procgen_current_room_is_large")
WORLD_W, WORLD_H = addr("_room_world_width"), addr("_room_world_height")
CAMERA_X, CAMERA_Y = addr("_room_camera_x"), addr("_room_camera_y")
TM = addr("_room_tilemap")
STATUS = addr("_player_status_kind")
SPR_TOWN_MERCHANT_BIG = 212
RIFTWELL_SCREEN = 1


def tick(pb, frames):
    for _ in range(frames):
        pb.tick()


def coins(pb):
    return pb.memory[PLAYER + 16] | (pb.memory[PLAYER + 17] << 8)


def antidotes(pb):
    return sum(1 for i in range(16) if pb.memory[INV + i] == ITEM_ID_ANTIDOTE)


def set_inventory(pb, ids):
    for i in range(16):
        pb.memory[INV + i] = ids[i] if i < len(ids) else 0xFF


def pickups(pb, kind):
    return [ENTITIES + i * ENTITY_SIZE for i in range(32)
            if pb.memory[ENTITIES + i * ENTITY_SIZE] == ENT_PICKUP
            and pb.memory[ENTITIES + i * ENTITY_SIZE + 17] == kind]


def obj_tiles(pb, tile, count=4):
    old = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 0
    data = bytes(pb.memory[0x8000 + tile * 16 + i] for i in range(16 * count))
    pb.memory[0xFF4F] = old
    return data


def bg_row(pb, row):
    old = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 0
    data = [pb.memory[0x9800 + row * 32 + c] for c in range(20)]
    pb.memory[0xFF4F] = old
    return data


def reach_riftwell(seed, bosses):
    pb = boot(seed % 5)
    merchant_art = obj_tiles(pb, SPR_TOWN_MERCHANT_BIG)
    for k in range(4):
        pb.memory[RS + 2 + k] = (seed * 37 + k * 91) & 0xFF
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[bosses - 1]
    pb.memory[RS + 11] = bosses
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    pb.memory[TM + 16 * 20 + 9] = 3
    pb.memory[TM + 16 * 20 + 10] = 3
    put16(pb, PLAYER + 9, 72)
    put16(pb, PLAYER + 11, 120)
    tick(pb, 180)
    assert pb.memory[RS + 17] == 1, f"seed {seed}: did not enter the Riftwild"
    put16(pb, PLAYER + 9, 232)
    put16(pb, PLAYER + 11, 60)
    tick(pb, 90)
    assert pb.memory[RS + 18] == RIFTWELL_SCREEN, \
        f"seed {seed}: did not reach the Riftwell crossing"
    return pb, merchant_art


def talk_page(pb):
    """Open the keeper's dialogue, return its stock page rows, close it."""
    press(pb, "a")
    tick(pb, 30)
    press(pb, "a")
    tick(pb, 30)
    rows = [bg_row(pb, r) for r in range(18)]
    # The TODAYS WARES header anchors the console font offset.
    offset = rows[3][1] - ord("T")
    # Letters only: blanks and digits use other glyph slots.
    texts = [re.sub(r"[^A-Z]", " ", "".join(
        chr(t - offset) if 32 <= t - offset < 127 else " " for t in row))
        for row in rows]
    shot = pb.screen.image.copy()
    press(pb, "b")
    tick(pb, 30)
    return texts, shot


def check_seed(seed, bosses, shots=False):
    pb, merchant_art = reach_riftwell(seed, bosses)
    tag = f"seed {seed}/bosses {bosses}"
    try:
        keeper = pickups(pb, PICKUP_MERCHANT)
        stock = [e for e in pickups(pb, PICKUP_SHOP)
                 if pb.memory[e + 18] == WARE_ANTIDOTE]
        assert len(keeper) == 1 and len(stock) == 1, \
            f"{tag}: trader keeper={len(keeper)} stock={len(stock)}"
        kx, ky = pb.memory[keeper[0] + 3], pb.memory[keeper[0] + 7]
        vx, vy = pb.memory[stock[0] + 3], pb.memory[stock[0] + 7]
        assert obj_tiles(pb, SPR_TOWN_MERCHANT_BIG) == merchant_art, \
            f"{tag}: Riftwild trader drawn with the boss shot atlas"
        # The vial sits clear of the keeper column, north of the trail.
        assert abs(vx - kx) >= 16 and vy + 16 <= 56, \
            f"{tag}: vial at ({vx},{vy}) blocks keeper at ({kx},{ky})"

        set_inventory(pb, [])
        put16(pb, PLAYER + 16, 50)
        # Poison would spend a bought vial on the spot; keep the count clear.
        pb.memory[STATUS] = 0
        # Walk straight up the keeper column from the trail to talk.
        put16(pb, PLAYER + 9, kx)
        put16(pb, PLAYER + 11, 60)
        pb.memory[PLAYER + 15] = 200
        tick(pb, 2)
        if shots:
            pb.screen.image.save(SHOTS / "riftwild-trader-arrive.png")
        pb.button_press("up")
        tick(pb, 60)
        pb.button_release("up")
        tick(pb, 4)
        assert coins(pb) == 50 and antidotes(pb) == 0, (
            f"{tag}: walking up to the trader bought the vial "
            f"(coins={coins(pb)} vials={antidotes(pb)})")
        assert len(pickups(pb, PICKUP_SHOP)) == 1, \
            f"{tag}: vial vanished on the walk up"
        if shots:
            pb.screen.image.save(SHOTS / "riftwild-trader-walkup.png")
        texts, shot = talk_page(pb)
        if shots:
            shot.save(SHOTS / "riftwild-trader-wares.png")
        assert any("PSN/BURN/BLEED" in t for t in texts), \
            f"{tag}: TODAYS WARES lists nothing: {texts[3:12]}"

        # A deliberate purchase keeps the restocked vial on the counter and
        # takes exactly one payment per contact.
        stock = pickups(pb, PICKUP_SHOP)[0]
        vx, vy = pb.memory[stock + 3], pb.memory[stock + 7]
        pb.memory[STATUS] = 0
        put16(pb, PLAYER + 9, vx)
        put16(pb, PLAYER + 11, max(0, vy - 8))
        pb.memory[PLAYER + 15] = 200
        tick(pb, 60)
        assert coins(pb) == 38 and antidotes(pb) == 1, \
            f"{tag}: purchase coins={coins(pb)} vials={antidotes(pb)}"
        assert len(pickups(pb, PICKUP_SHOP)) == 1, \
            f"{tag}: the bought vial left the counter empty"
        put16(pb, PLAYER + 11, max(0, vy - 48))
        tick(pb, 6)
        put16(pb, PLAYER + 11, max(0, vy - 8))
        tick(pb, 10)
        assert coins(pb) == 26 and antidotes(pb) == 2, (
            f"{tag}: a fresh contact did not buy again "
            f"(coins={coins(pb)} vials={antidotes(pb)})")
    finally:
        pb.stop(save=False)


def check_sold_out_copy():
    pb, _ = reach_riftwell(0, 1)
    try:
        keeper = pickups(pb, PICKUP_MERCHANT)[0]
        for e in pickups(pb, PICKUP_SHOP):
            for k in range(ENTITY_SIZE):
                pb.memory[e + k] = 0
        tick(pb, 4)
        put16(pb, PLAYER + 9, pb.memory[keeper + 3])
        put16(pb, PLAYER + 11, 44)
        pb.memory[PLAYER + 15] = 200
        pb.button_press("up")
        tick(pb, 3)
        pb.button_release("up")
        texts, shot = talk_page(pb)
        shot.save(SHOTS / "riftwild-trader-sold-out.png")
        assert any("SOLD OUT" in t for t in texts), \
            f"an empty shelf did not say SOLD OUT: {texts[3:12]}"
    finally:
        pb.stop(save=False)


def main():
    # Seed 3 enters the first field on a blocked edge; these cross cleanly.
    cases = [(s, b) for b in (1, 4, 7) for s in (0, 1, 2, 4, 5)]
    for i, (seed, bosses) in enumerate(cases):
        check_seed(seed, bosses, shots=(i == 0))
    check_sold_out_copy()
    print(f"[riftwild-trader] PASS {len(cases)} seed/region cases: merchant "
          "art, walk-up never buys, wares listed, restocked vial, SOLD OUT")


if __name__ == "__main__":
    main()
