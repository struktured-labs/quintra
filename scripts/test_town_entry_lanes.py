#!/usr/bin/env python3
"""No village ware stands in the way in (#281).

Walking from the village square into the forge quarter used to land the
hero on the Antidote shelf: it stood at the east door, on the tiles the
hero arrives on, so every visit began by touching a ware.

For every door-to-door walk between the three village screens, the hero's
arrival spot and the lane leading inward from it must be free of shop
wares and their price tags. The lane is the hero's own body rows, a tile
of margin above and below, and two tiles of open floor beyond the body.
"""
from pathlib import Path

from quintra_pyboy_env import QuintraPyBoyEnv
import test_merchant_stock as tms
from test_merchant_stock import EN, PL, RS

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "tmp/stage-states/quintra-village-after-stage-03-wolfkin.pyboy"
ENT_PICKUP, PICKUP_SHOP, PICKUP_SHOP_TAG = 3, 4, 13
ARRIVAL, MARKET, QUARTER = 0, 1, 2
NAMES = {ARRIVAL: "square", MARKET: "market", QUARTER: "forge quarter"}
EAST, WEST = 1, 3
LANE_DEPTH = 16          # two tiles of open floor inward of the hero's body
LANE_MARGIN = 8          # one tile above and below the hero's body
# (leave from, walk direction, arrive in)
WALKS = ((ARRIVAL, WEST, QUARTER), (QUARTER, EAST, ARRIVAL),
         (ARRIVAL, EAST, MARKET), (MARKET, WEST, ARRIVAL))


def u16(pb, a):
    return pb.memory[a] | (pb.memory[a + 1] << 8)


def wares(pb):
    out = []
    for i in range(32):
        e = EN + i * 28
        if (pb.memory[e] == ENT_PICKUP and pb.memory[e + 1] & 1
                and pb.memory[e + 17] in (PICKUP_SHOP, PICKUP_SHOP_TAG)):
            out.append((u16(pb, e + 3), u16(pb, e + 7), pb.memory[e + 17]))
    return out


def lane(hx, hy, direction):
    """Rectangle (x0, y0, x1, y1): the arrival body plus the way inward."""
    y0, y1 = hy - LANE_MARGIN, hy + 16 + LANE_MARGIN
    if direction == WEST:            # arrived at the east door, heading west
        return hx - LANE_DEPTH, y0, hx + 16, y1
    return hx, y0, hx + 16 + LANE_DEPTH, y1


def main():
    env = QuintraPyBoyEnv(window="null")
    env.load_state(STATE)
    pb = env.pb
    pb.memory[RS + 19] = ARRIVAL
    checked = []
    for source, direction, target in WALKS:
        assert pb.memory[RS + 19] == source, (
            f"expected to start in the {NAMES[source]}")
        tms.walk_town(pb, direction, target)
        hx, hy = u16(pb, PL + 9), u16(pb, PL + 11)
        x0, y0, x1, y1 = lane(hx, hy, direction)
        stock = wares(pb)
        assert any(kind == PICKUP_SHOP for _x, _y, kind in stock) or \
            target == ARRIVAL, f"{NAMES[target]} has no wares at all"
        blocked = [(x, y, kind) for x, y, kind in stock
                   if x < x1 and x + 8 > x0 and y < y1 and y + 8 > y0]
        assert not blocked, (
            f"entering the {NAMES[target]} from the {NAMES[source]}: hero "
            f"arrives at {(hx, hy)} and the lane {(x0, y0, x1, y1)} holds "
            f"ware(s)/tag(s) at {blocked}")
        checked.append(f"{NAMES[source]} -> {NAMES[target]}")
    env.pb.stop(save=False)
    print(f"[town-entry-lanes] PASS no ware or price tag in the arrival lane "
          f"for {len(checked)} village door walks: {', '.join(checked)}")


if __name__ == "__main__":
    main()
