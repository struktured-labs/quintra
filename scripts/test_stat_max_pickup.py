#!/usr/bin/env python3
"""Live-ROM: capped stat boosts stay put and name the cap (SPDMAX)."""

from test_performance import EN, PL, boot_room, put32


WIN = 0x9C00
VBK = 0xFF4F
HUD_BLANK = 8
DIGIT_1 = 10
A, T, K = 84, 79, 88
S, P, D = 93, 90, 82
M, A_LETTER, X = 87, 84, 66
PLUS = 95
PICKUP_ITEM = 3
PICKUP_SHOP = 4
WARE_ITEM = 1
ITEM_SPEED_RING = 11
ITEM_SWIFT_FANG = 17
ITEM_ID_SPEED_RING = 21
ITEM_ID_SWIFT_FANG = 27
SPDMAX = (S, P, D, M, A_LETTER, X)
ATKPLUS = (A, T, K, PLUS, DIGIT_1, HUD_BLANK)
INV = 24
SPD = 7
ATK = 5
COINS = 16


def clear_entities(pb):
    for i in range(32):
        ep = EN + i * 28
        pb.memory[ep] = 0
        pb.memory[ep + 1] = 0


def spawn_on_player(pb, kind, a1=0, a2=0, a3=0):
    ep = EN
    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    pb.memory[ep] = 3
    pb.memory[ep + 1] = 0x03
    put32(pb, ep + 2, px << 8)
    put32(pb, ep + 6, py << 8)
    pb.memory[ep + 12] = 35
    pb.memory[ep + 13] = 5
    pb.memory[ep + 14] = 1
    pb.memory[ep + 15] = 0
    pb.memory[ep + 16] = 200
    pb.memory[ep + 17] = kind
    pb.memory[ep + 18] = a1
    pb.memory[ep + 19] = a2
    pb.memory[ep + 20] = a3
    pb.memory[ep + 21] = 0
    pb.memory[ep + 25] = 0x66
    return ep


def hud_row(pb):
    tiles = tuple(pb.memory[WIN + x] for x in range(10, 16))
    pb.memory[VBK] = 1
    attrs = tuple(pb.memory[WIN + x] & 7 for x in range(10, 16))
    pb.memory[VBK] = 0
    return tiles, attrs


def wait_notice(pb):
    for _ in range(55):
        pb.tick()


def pickup_alive(pb):
    return bool(pb.memory[EN + 1] & 1) and pb.memory[EN] == 3


def prep_stats(pb, spd, atk=4, coins=99):
    clear_entities(pb)
    pb.memory[PL + SPD] = spd
    pb.memory[PL + ATK] = atk
    pb.memory[PL + COINS] = coins & 0xFF
    pb.memory[PL + COINS + 1] = coins >> 8
    for i in range(16):
        pb.memory[PL + INV + i] = 0xFF


def main():
    pb = boot_room()
    try:
        # Floor Speed Ring at SPD 9: stays, names the cap, no inventory grant.
        prep_stats(pb, 9)
        spawn_on_player(pb, PICKUP_ITEM, ITEM_SPEED_RING)
        pb.tick()
        tiles, attrs = hud_row(pb)
        assert pickup_alive(pb), "floor Speed Ring at SPD 9 was swallowed"
        assert pb.memory[PL + SPD] == 9
        assert pb.memory[PL + INV] == 0xFF
        assert tiles == SPDMAX, tiles
        wait_notice(pb)

        # Floor Swift Fang at SPD 9: ATK still applies, item is taken.
        prep_stats(pb, 9, atk=4)
        spawn_on_player(pb, PICKUP_ITEM, ITEM_SWIFT_FANG)
        pb.tick()
        tiles, attrs = hud_row(pb)
        assert not pickup_alive(pb), "floor Swift Fang at SPD 9 stayed"
        assert pb.memory[PL + SPD] == 9
        assert pb.memory[PL + ATK] == 5
        assert pb.memory[PL + INV] == ITEM_ID_SWIFT_FANG
        assert tiles == ATKPLUS, tiles
        wait_notice(pb)

        # Shop Speed Ring at SPD 9: refused, coins kept, SPDMAX notice.
        prep_stats(pb, 9, coins=99)
        spawn_on_player(pb, PICKUP_SHOP, WARE_ITEM, 25, ITEM_SPEED_RING)
        pb.tick()
        tiles, attrs = hud_row(pb)
        assert pickup_alive(pb), "shop Speed Ring at SPD 9 was sold"
        assert pb.memory[PL + SPD] == 9
        assert pb.memory[PL + COINS] == 99
        assert pb.memory[PL + INV] == 0xFF
        assert tiles == SPDMAX, tiles
        wait_notice(pb)

        # Shop Swift Fang at SPD 9: sold, ATK+1, coins deducted.
        prep_stats(pb, 9, atk=4, coins=99)
        spawn_on_player(pb, PICKUP_SHOP, WARE_ITEM, 25, ITEM_SWIFT_FANG)
        pb.tick()
        tiles, attrs = hud_row(pb)
        assert not pickup_alive(pb), "shop Swift Fang at SPD 9 stayed"
        assert pb.memory[PL + SPD] == 9
        assert pb.memory[PL + ATK] == 5
        assert pb.memory[PL + COINS] == 74
        assert pb.memory[PL + INV] == ITEM_ID_SWIFT_FANG
        assert tiles == ATKPLUS, tiles
    finally:
        pb.stop(save=False)

    print("[stat-max-pickup] PASS floor/shop Speed Ring refuse + SPDMAX; Swift Fang still applies ATK")


if __name__ == "__main__":
    main()
