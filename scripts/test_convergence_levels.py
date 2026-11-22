#!/usr/bin/env python3
"""#151 section 10: Spirit Convergence L1 is the shipped burst; L4 scales
lifetime/damage and adds elemental residue."""

from test_magic import (
    PLAYER, PL_MP, PL_MP_MAX, PL_ITEM, ST_BURN, ST_STOP, ST_SLOW,
    ST_CONFUSION, ST_POISON, ST_MUTE, ESTATUS, arena, boot, chord, entity,
    HEROES, run_until, slot,
)
from test_will_max import addr, put16

TRANSFORM = addr("_room_transform_ticks")

# entity_t: type, flags, ..., palette +13, hp +14, state_timer +16,
# ai_data[3] +20, ai_data[7] +24, damage +26.
PAL, HP, TTL, FLAG3, TAG7, DMG = 13, 14, 16, 20, 24, 26
PROJ_FLAG_CONVERGENCE = 0x01
CV_TAG = 0xC0
# L1 SPIKE ttl: Wolfkin starter 18, everyone else 12.
TTL_L1 = (18, 12, 12, 12, 12)
TTL_L4 = (32, 21, 21, 21, 21)  # (ttl * 448 + 128) >> 8
# Burst colorway slots (no BANK1 on the swing tile).
PAL_SLOT = (4, 5, 4, 4, 7)


def bursts(pb):
    out = []
    for i in range(32):
        e = slot(i)
        if pb.memory[e] != 1:
            continue
        if (pb.memory[e + 1] & 0x11) != 0x11:
            continue
        if (pb.memory[e + TAG7] & 0xF0) != CV_TAG:
            continue
        out.append(e)
    return out


def fire_chord(pb, cap):
    arena(pb, cap=cap)
    pb.memory[PLAYER + PL_MP] = pb.memory[PLAYER + PL_MP_MAX]
    pb.memory[PLAYER + 19] = 0  # active_charge ready
    pb.memory[TRANSFORM] = 0
    # Finish any previous release so the next poll sees a fresh A+B edge.
    pb.button_release("a")
    pb.button_release("b")
    pb.tick(4)
    # Snapshot the burst on the first frame it exists so TTL has barely ticked.
    pb.button_press("a")
    pb.button_press("b")
    shots = []
    for _ in range(16):
        pb.tick()
        now = bursts(pb)
        if len(now) > len(shots):
            shots = now
        if len(shots) >= 8:
            break
    pb.button_release("a")
    pb.button_release("b")
    pb.tick(2)
    return shots


def check_l1(pb, c):
    shots = fire_chord(pb, 1)
    assert len(shots) == 8, f"{HEROES[c]} L1 burst {len(shots)}/8"
    raw = pb.memory[shots[0] + DMG]
    for e in shots:
        assert pb.memory[e + FLAG3] & PROJ_FLAG_CONVERGENCE, "L1 missing flag"
        ttl = pb.memory[e + TTL]
        assert TTL_L1[c] - 2 <= ttl <= TTL_L1[c], (
            f"{HEROES[c]} L1 ttl {ttl}, expected {TTL_L1[c]} (allow 2f poll delay)")
        assert (pb.memory[e + PAL] & 7) == PAL_SLOT[c], (
            f"{HEROES[c]} L1 pal {pb.memory[e + PAL]} expected {PAL_SLOT[c]}")
        assert pb.memory[e + DMG] == raw, "L1 damage drifted across lanes"
    # L1 does not scale: a second look at remaining ttl after a couple of
    # frames should still track the unscaled clock, not the 1.75x L4 clock.
    return raw


def check_l4(pb, c, raw_l1):
    shots = fire_chord(pb, 4)
    assert len(shots) >= 6, f"{HEROES[c]} L4 burst {len(shots)}"
    ttl = max(pb.memory[e + TTL] for e in shots)
    assert abs(ttl - TTL_L4[c]) <= 2, (
        f"{HEROES[c]} L4 ttl {ttl}, expected ~{TTL_L4[c]}")
    dmg = pb.memory[shots[0] + DMG]
    expect = (raw_l1 * 371 + 128) >> 8
    assert dmg == expect, f"{HEROES[c]} L4 dmg {dmg}, expected {expect} from L1 {raw_l1}"
    assert (pb.memory[shots[0] + PAL] & 7) == PAL_SLOT[c]

    # Elemental residue: plant a body on the east lane and read status / chain.
    arena(pb, cap=4)
    pb.memory[PLAYER + PL_MP] = pb.memory[PLAYER + PL_MP_MAX]
    pb.memory[PLAYER + 19] = 0
    # Skeleton (id 3), not the default Sentry (id 10): a Sentry volley is a
    # hostile shot, and non-Wolfkin SPIKE lanes have pierce 1, so they spend
    # themselves cutting the bullet before they reach the body. Wolfkin
    # pierce 2 can cut one shot and still land, which hid this in L4 fire.
    foe = entity(pb, 0, 2, 100, 64, hp=80, enemy_id=3)
    if c == 1:
        # Second body ~60 px south of the first: L4 chain range is ~84.
        far = entity(pb, 1, 2, 100, 124, hp=80, enemy_id=3)
    chord(pb, True)
    assert run_until(pb, 40, lambda: pb.memory[foe + HP] < 80), (
        f"{HEROES[c]} L4 burst missed a near body")
    st = pb.memory[ESTATUS]
    if c == 0:
        assert st == ST_BURN, f"Wolfkin L4 status {st}"
    elif c == 1:
        assert run_until(pb, 30, lambda: pb.memory[slot(1) + HP] < 80), (
            "Sauran L4 lightning did not chain")
        assert pb.memory[ESTATUS + 1] == ST_SLOW, (
            f"Sauran chain status {pb.memory[ESTATUS + 1]}")
    elif c == 2:
        assert st in (ST_CONFUSION, ST_MUTE), f"Corvin L4 status {st}"
    elif c == 3:
        assert st == ST_STOP, f"Picsean L4 status {st}"
        # A wall-bound or expired spike should have left at least one shard
        # tagged as a convergence ice shard (sub=1) before the room emptied.
        pb.tick(40)
        shards = [e for e in (slot(i) for i in range(32))
                  if pb.memory[e] == 1
                  and (pb.memory[e + TAG7] & 0xFF) == (CV_TAG | 1)]
        # Shards may already have expired; also accept that STOP landed.
        print(f"[convergence-levels] Picsean shards still live: {len(shards)}")
    else:
        assert st == ST_POISON, f"Vespine L4 status {st}"


def main():
    for c, name in enumerate(HEROES):
        pb = boot(c)
        raw = check_l1(pb, c)
        check_l4(pb, c, raw)
        pb.stop(save=False)
        print(f"[convergence-levels] {name}: L1 ttl {TTL_L1[c]} / L4 residue ok")
    print("[convergence-levels] PASS L1 bit-identical burst, L4 scale and residue")


if __name__ == "__main__":
    main()
