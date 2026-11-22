#!/usr/bin/env python3
"""Corvin (and every champion) keeps their max-Will signature after any
merchant purchase or floor drop, including an A-weapon swap.

A held implement still changes ordinary A fire. The authored MAX — Murderstorm
Eclipse for Corvin, and the other four champion arts — is bound to class_id,
not to whether starter_weapon still equals the class starter.
"""

from test_performance import EN, PL, put32
from test_will_max import (
    PLAYER, WILL_OFFSET, LEVEL_OFFSET, WILL_MAX,
    addr, boot, clear_arena,
)
from test_will_max_v2 import arm, press_max, run_art, NAMES

LIVE = addr("_will_maxfx_live")
SLOW = addr("_picsean_vortex_slow_charge")
VORTEX = addr("_picsean_vortex_ticks")
SCREEN = addr("_loop_current_screen")
REWARD = addr("_room_major_reward_pending")
POSE = addr("_room_player_pose_locked")
SCREEN_ROOM, SCREEN_DIALOG = 5, 9

WEAPON = 21
COINS = 16
INV = 24
HPMAX, HP, MPMAX, MP = 1, 2, 3, 4
ATK, CURSE = 5, 46

# pickup.h
PICKUP_HEART_HALF, PICKUP_COIN_1, PICKUP_COIN_5 = 0, 1, 2
PICKUP_ITEM, PICKUP_SHOP, PICKUP_WEAPON, PICKUP_MP = 3, 4, 5, 6
PICKUP_SURGE = 14
PICKUP_FARFOLD_RELIC, PICKUP_BOON_CHOICE = 19, 20
PICKUP_WAYGEAR, PICKUP_WILDCARD = 22, 24
PICKUP_HOLLOW_RELIC, PICKUP_ANTIDOTE = 25, 26
PICKUP_POWERUP, PICKUP_ROULETTE = 27, 28
PICKUP_RIFT_SIGIL, PICKUP_COMPANION = 11, 23

# Merchant wares (skip WARE_SECRET: it opens the Veil shelf, not a buy).
WARES = [
    (0, "heart"),
    (1, "stat item"),
    (2, "Iron Heart"),
    (3, "Power Stone"),
    (4, "Mana Gem"),
    (5, "Surge"),
    (6, "Vampiric Sigil"),
    (7, "Chart"),
    (8, "A weapon"),
    (9, "Glass Fang"),
    (10, "Phoenix Thread"),
    (11, "Spirit Draught"),
    (12, "Echo Prism"),
    (13, "Ricochet Rune"),
    (14, "Thorn Crown"),
    (15, "War Drum"),
    (16, "Moon Flask"),
    (17, "Blast Seed"),
    (18, "Boomerang"),
    (19, "Hookshot"),
    (20, "Morningstar"),
    (21, "Bombs"),
    (22, "Antidote"),
]

# Generated items[] indices of every ITEM_KIND_WEAPON used in test_will_max.
# 0-4 are the five starters; 20 Rift Flail; 21 Astral Spear.
WEAPONS = [0, 1, 2, 3, 4, 20, 21]


def unlock(pb):
    pb.memory[SLOW] = 0


def dismiss_to_room(pb, label):
    """Major-reward ceremonies freeze room_tick and then open a dialog.
    Clear that presentation so A can fire the MAX."""
    pb.memory[REWARD] = 0
    pb.memory[POSE] = 0
    try:
        greet = addr("_companion_greeting")
        pb.memory[greet] = 0
    except RuntimeError:
        pass
    for _ in range(200):
        scr = pb.memory[SCREEN]
        if scr == SCREEN_ROOM:
            return
        # Reward dialogs and leftover menus close on B or Start.
        pb.button_press("b")
        pb.tick(3)
        pb.button_release("b")
        pb.tick(3)
        if pb.memory[SCREEN] == SCREEN_ROOM:
            return
        pb.button_press("start")
        pb.tick(3)
        pb.button_release("start")
        pb.tick(8)
    raise AssertionError(f"{label}: stuck on screen {pb.memory[SCREEN]}")


def wait_art(pb, cid):
    run_art(pb, cid, limit=160)
    # Picsean's spiral can outlive the short run_art window; just unlock.
    unlock(pb)
    if cid != 3:
        for _ in range(20):
            if pb.memory[LIVE] == 0:
                break
            pb.tick()
        assert pb.memory[LIVE] == 0, f"{NAMES[cid]} art did not end"


def fire_signature(pb, cid, label):
    """Charge, fire, and assert this champion's authored MAX started."""
    clear_arena(pb)
    unlock(pb)
    dismiss_to_room(pb, label)
    arm(pb)
    assert press_max(pb), (
        f"{label}: MAX did not fire (screen={pb.memory[SCREEN]} "
        f"level={pb.memory[PLAYER + LEVEL_OFFSET]} live={pb.memory[LIVE]} "
        f"slow={pb.memory[SLOW]}"
    )
    if cid == 3:
        assert pb.memory[VORTEX] > 0, f"{label}: Tide Vortex did not start"
    else:
        assert pb.memory[LIVE] == cid + 1, (
            f"{label}: expected {NAMES[cid]} art "
            f"(live={cid + 1}), got live={pb.memory[LIVE]}"
        )
    wait_art(pb, cid)


def prep_collect(pb):
    m = pb.memory
    m[PL + HPMAX], m[PL + HP] = 10, 8
    m[PL + MPMAX], m[PL + MP] = 8, 4
    m[PL + ATK] = 4
    m[PL + COINS] = 0xE7
    m[PL + COINS + 1] = 0x03  # 999 coins
    m[PL + CURSE] = 0
    m[PL + WILL_OFFSET] = 0
    m[PL + LEVEL_OFFSET] = 0
    m[PL + 19] = 0  # active_charge
    for i in range(16):
        m[PL + INV + i] = 0xFF
    # Leave a couple of slots empty even after later grants by resetting
    # only at the start of each collect. Callers may pre-fill if needed.


def spawn_on_player(pb, kind, a1=0, a2=0, a3=0, tile=35, pal=5):
    ep = EN
    m = pb.memory
    px = m[PL + 9] | (m[PL + 10] << 8)
    py = m[PL + 11] | (m[PL + 12] << 8)
    for k in range(28):
        m[ep + k] = 0
    m[ep] = 3
    m[ep + 1] = 0x03
    put32(pb, ep + 2, px << 8)
    put32(pb, ep + 6, py << 8)
    m[ep + 12] = tile
    m[ep + 13] = pal
    m[ep + 14] = 1
    m[ep + 16] = 200
    m[ep + 17] = kind
    m[ep + 18] = a1
    m[ep + 19] = a2
    m[ep + 20] = a3
    m[ep + 24] = 0x40
    m[ep + 25] = 0x66
    m[ep + 27] = 1
    return ep


def tick_collect(pb, frames=90, press_a=False):
    if press_a:
        pb.button_press("a")
    for _ in range(frames):
        pb.tick()
    if press_a:
        pb.button_release("a")
        pb.tick(4)


def collect(pb, kind, a1=0, a2=0, a3=0, press_a=False, frames=90):
    prep_collect(pb)
    # Keep current A weapon; prep_collect does not touch starter_weapon.
    spawn_on_player(pb, kind, a1, a2, a3)
    tick_collect(pb, frames=frames, press_a=press_a)
    # Ceremonies / notices should not leave us muted for the MAX press.
    pb.memory[PL + CURSE] = 0


def assert_still_corvin(pb, label):
    assert pb.memory[PLAYER] == 2, f"{label}: class_id became {pb.memory[PLAYER]}"


def corvin_cases(pb):
    fire_signature(pb, 2, "baseline Featherbarb")

    for ware, name in WARES:
        a3 = 20 if ware == 8 else (12 if ware == 1 else 0)
        collect(pb, PICKUP_SHOP, ware, 10, a3, press_a=False, frames=80)
        assert_still_corvin(pb, f"buy {name}")
        fire_signature(pb, 2, f"after buying {name}")

    # Every swappable A weapon, including other starters, Flail, and Spear.
    starter_before = pb.memory[PL + WEAPON]
    for weapon in WEAPONS:
        if weapon == starter_before:
            continue
        collect(pb, PICKUP_WEAPON, weapon, press_a=True, frames=20)
        assert pb.memory[PL + WEAPON] == weapon, (
            f"weapon orb {weapon} did not swap A "
            f"(still {pb.memory[PL + WEAPON]})"
        )
        assert_still_corvin(pb, f"swap to weapon {weapon}")
        fire_signature(pb, 2, f"after swapping to weapon {weapon}")
        # Swap back through another orb so the next pass starts clean.
        collect(pb, PICKUP_WEAPON, starter_before, press_a=True, frames=20)

    drops = [
        (PICKUP_HEART_HALF, 0, 0, 0, False, "half heart"),
        (PICKUP_COIN_1, 0, 0, 0, False, "coin"),
        (PICKUP_COIN_5, 0, 0, 0, False, "five-coin"),
        (PICKUP_ITEM, 12, 0, 0, False, "floor relic"),
        (PICKUP_MP, 0, 0, 0, False, "MP wisp"),
        (PICKUP_SURGE, 0, 0, 0, False, "Surge drop"),
        (PICKUP_ANTIDOTE, 0, 0, 0, False, "Antidote"),
        (PICKUP_FARFOLD_RELIC, 12, 0, 0, False, "Farfold relic"),
        (PICKUP_BOON_CHOICE, 12, 0, 0, True, "boon choice"),
        (PICKUP_WAYGEAR, 0, 0, 0, False, "Waygear"),
        (PICKUP_WILDCARD, 0, 0, 0, False, "wildcard"),
        (PICKUP_HOLLOW_RELIC, 36, 0, 0, False, "Hollow relic"),
        (PICKUP_RIFT_SIGIL, 0, 0, 0, False, "Rift Sigil"),
        (PICKUP_COMPANION, 0, 0, 0, False, "companion"),
        (PICKUP_ROULETTE, 1, 0, 0, False, "roulette"),
    ]
    for kind, a1, a2, a3, press, name in drops:
        collect(pb, kind, a1, a2, a3, press_a=press, frames=100)
        assert_still_corvin(pb, f"drop {name}")
        fire_signature(pb, 2, f"after {name} drop")

    for puid in range(1, 9):
        collect(pb, PICKUP_POWERUP, puid, press_a=False, frames=80)
        assert_still_corvin(pb, f"power-up {puid}")
        fire_signature(pb, 2, f"after power-up {puid}")


def other_heroes():
    """A Flail/Spear swap must not steal any champion's authored MAX."""
    for cid in range(5):
        if cid == 2:
            continue
        pb = boot(cid)
        try:
            fire_signature(pb, cid, f"{NAMES[cid]} baseline")
            for weapon in (20, 21):
                collect(pb, PICKUP_WEAPON, weapon, press_a=True, frames=20)
                assert pb.memory[PL + WEAPON] == weapon, (
                    f"{NAMES[cid]} did not equip weapon {weapon}"
                )
                fire_signature(pb, cid, f"{NAMES[cid]} after weapon {weapon}")
        finally:
            pb.stop(save=False)


def main():
    pb = boot(2)
    try:
        corvin_cases(pb)
    finally:
        pb.stop(save=False)
    other_heroes()
    print("[corvin-max-will-pickup] PASS Corvin keeps Murderstorm after every "
          "merchant ware and drop; other champions keep their MAX after "
          "Flail/Spear swaps")


if __name__ == "__main__":
    main()
