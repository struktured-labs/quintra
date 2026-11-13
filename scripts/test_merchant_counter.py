#!/usr/bin/env python3
"""Shopkeepers answer A from across their counter; wares keep the purchase.

Spec: docs/superpowers/specs/2026-11-12-merchant-counter-reach.md
"""
from test_dialogue import (
    DIALOG_KIND, EN, PL, RS, SCREEN, SCREEN_DIALOG, SCREEN_ROOM,
    clear_hostiles, pickups, put16, tap, tick,
)
from test_merchant_stock import buy_at, walk_town
from test_shop_surge import boot_shop

FACE_S, FACE_E, FACE_N, FACE_W = 0, 1, 2, 3
PICKUP_SHOP, PICKUP_MERCHANT, PICKUP_SMITH = 4, 8, 9
PICKUP_APOTHECARY, PICKUP_CARTOGRAPHER = 10, 12
ENT_PROJECTILE = 1


def xy(pb, entity):
    return (pb.memory[entity + 3] | (pb.memory[entity + 4] << 8),
            pb.memory[entity + 7] | (pb.memory[entity + 8] << 8))


def place(pb, x, y, facing, purse=0):
    pb.memory[PL + 16] = purse & 0xFF
    pb.memory[PL + 17] = purse >> 8
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    pb.memory[PL + 13] = facing
    pb.memory[PL + 22] = 0
    tick(pb, 3)
    got = (pb.memory[PL + 9] | pb.memory[PL + 10] << 8,
           pb.memory[PL + 11] | pb.memory[PL + 12] << 8)
    assert got == (x, y), f"stance {(x, y)} was pushed to {got}"


def projectile_live(pb):
    return any(pb.memory[EN + i * 28] == ENT_PROJECTILE
               and (pb.memory[EN + i * 28 + 1] & 0x11)
               for i in range(32))


def press_a(pb):
    pb.button_press("a")
    shot = False
    for _ in range(12):
        pb.tick()
        shot = shot or projectile_live(pb)
    pb.button_release("a")
    tick(pb, 4)
    return shot


def leave_dialog(pb):
    tap(pb, "b")
    tick(pb, 22)
    assert pb.memory[SCREEN] == SCREEN_ROOM, "B did not close the dialogue"


def talks(pb, x, y, facing, kind, label):
    place(pb, x, y, facing)
    press_a(pb)
    assert pb.memory[SCREEN] == SCREEN_DIALOG, f"{label}: A did not talk"
    assert pb.memory[DIALOG_KIND] == kind, (
        f"{label}: talked to {pb.memory[DIALOG_KIND]}, wanted {kind}")
    leave_dialog(pb)
    print(f"  ok  {label}: A talks to keeper {kind}")


def attacks(pb, x, y, facing, label):
    tick(pb, 30)   # let the previous swing cool down
    place(pb, x, y, facing)
    shot = press_a(pb)
    assert pb.memory[SCREEN] == SCREEN_ROOM, f"{label}: A opened dialogue"
    assert shot, f"{label}: A did not attack"
    print(f"  ok  {label}: A attacks")


def keeper(pb, kind):
    found = pickups(pb, kind)
    assert len(found) == 1, f"keeper {kind}: {len(found)}"
    return xy(pb, found[0])


def ware_below(pb, kx, ky):
    """The ware directly across the counter from a keeper."""
    wares = [w for w in pickups(pb, PICKUP_SHOP)]
    return min(wares, key=lambda w: abs(xy(pb, w)[0] - kx)
               + abs(xy(pb, w)[1] - ky))


def ware_row(pb, kx, ky, label, kind=PICKUP_MERCHANT):
    ware = ware_below(pb, kx, ky)
    wx, wy = xy(pb, ware)
    front = wy + 16 if wy > ky else wy - 16
    toward = FACE_N if wy > ky else FACE_S
    away = FACE_S if toward == FACE_N else FACE_N
    print(f"[{label}] keeper ({kx},{ky}) ware ({wx},{wy}) front y={front}"
          f" dy={abs(front - ky)}")
    # (1) Far side of the ware row, facing the keeper: talk.
    talks(pb, kx, front, toward, kind, f"{label} across counter")
    # Off to the side of the keeper's ware but still at the counter.
    talks(pb, kx + 16, front, toward, kind, f"{label} counter offset")
    # (4) Same stance facing away, or sideways: A attacks.
    attacks(pb, kx, front, away, f"{label} across counter facing away")
    attacks(pb, kx, front, FACE_E, f"{label} across counter facing east")
    # (5) Far down the room: A still attacks even facing the keeper.
    far = front + 24 if toward == FACE_N else front - 24
    attacks(pb, kx, far, toward, f"{label} far from keeper")
    return ware, wx, wy


def stand_on_ware(pb, ware, wx, wy, label):
    # (2) Standing on an unaffordable ware: A must not open dialogue.
    place(pb, wx, wy - 8, FACE_N, purse=0)
    press_a(pb)
    assert pb.memory[SCREEN] == SCREEN_ROOM, f"{label}: ware stance talked"
    assert pb.memory[ware] == 3, f"{label}: unaffordable ware vanished"
    print(f"  ok  {label}: A on the ware stays with the shelf")
    # With coins, the same stance buys the ware (step off first so the
    # refusal latch re-arms, exactly as a player would).
    place(pb, wx, wy + 40, FACE_N)
    tick(pb, 20)
    pb.memory[PL + 2] = max(1, pb.memory[PL + 1] - 2)   # room for a heart
    pb.button_press("a")
    buy_at(pb, wx)
    pb.button_release("a")
    tick(pb, 4)
    assert pb.memory[SCREEN] == SCREEN_ROOM, f"{label}: buying talked"
    assert pb.memory[ware] == 0, f"{label}: ware was not bought"
    print(f"  ok  {label}: A on the ware with coins buys it")


def main():
    pb = boot_shop(0)
    try:
        clear_hostiles(pb)
        mx, my = keeper(pb, PICKUP_MERCHANT)
        ware, wx, wy = ware_row(pb, mx, my, "dungeon merchant")
        stand_on_ware(pb, ware, wx, wy, "dungeon merchant")
        # Old close talk still works.
        talks(pb, mx, my - 20, FACE_S, PICKUP_MERCHANT, "dungeon close talk")

        # (3) Town market, east of arrival.
        pb.memory[RS + 19] = 0
        walk_town(pb, 1, 1)
        clear_hostiles(pb)
        mx, my = keeper(pb, PICKUP_MERCHANT)
        ware, wx, wy = ware_row(pb, mx, my, "town market")
        stand_on_ware(pb, ware, wx, wy, "town market")

        # Same counter pattern for the other village shelves.
        walk_town(pb, 3, 0)
        walk_town(pb, 3, 2)
        clear_hostiles(pb)
        sx, sy = keeper(pb, PICKUP_SMITH)
        ware_row(pb, sx, sy, "village smith", PICKUP_SMITH)
        ax, ay = keeper(pb, PICKUP_APOTHECARY)
        rune = min(pickups(pb, PICKUP_SHOP),
                   key=lambda w: abs(xy(pb, w)[0] - ax))
        rx, ry = xy(pb, rune)
        talks(pb, ax, ry - 16, FACE_S, PICKUP_APOTHECARY,
              "rune tender across counter (north side)")
        attacks(pb, ax, ry - 16, FACE_N, "rune tender facing away")
    finally:
        pb.stop(save=False)
    print("[merchant-counter] PASS across-counter talk; wares keep A; "
          "facing away and far A attack")


if __name__ == "__main__":
    main()
