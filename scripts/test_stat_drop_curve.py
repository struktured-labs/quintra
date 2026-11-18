#!/usr/bin/env python3
"""Headless oracle + curve test for the ATK/SPD drop tune.

Asserts pickup_map_stat_relic identity at full weights, the high-taper
Swift/LCK rules, class and boon tables, and that a thorough Normal
explorer run no longer near-maxes by stage 2 while still reaching
near-max around stage 6-7. Does not need a ROM.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sim_stat_drop_curve import (
    ATK_CAP, BASE_ATK, BASE_SPD, BOON_POOL, NAMES, POOLS, SPD_CAP,
    boon_relic, map_stat_relic, relic_deltas, relic_weights, simulate_run,
    SPEED, POWER, SWIFT, LUCKY, HUNTER, BLOOD,
)


def test_full_weight_is_seed_identical():
    # Vespine at her starting line: every weight is 4, total 40.
    atk, spd, lck = BASE_ATK[4], BASE_SPD[4], 0
    ba, bs = BASE_ATK[4], BASE_SPD[4]
    for r in range(256):
        got = map_stat_relic(r, atk, spd, lck, ba, bs)
        assert got == 10 + (r % 10), (r, got)
    assert relic_weights(atk, spd, lck, ba, bs) == [4] * 10


def test_underflow_stays_full_weight():
    # A cursed or pacted read must never wrap unsigned and trip the taper.
    atk, spd, lck = 0, 0, 0
    w = relic_weights(atk, spd, lck, base_atk=4, base_spd=6)
    assert w == [4] * 10
    assert map_stat_relic(11, atk, spd, lck, 4, 6) == 10 + (11 % 10)


def test_high_taper_rules():
    # Vespine at SPD 8: Speed is high (1), Swift is zeroed, Power still full
    # (earned ATK is 0).
    w = relic_weights(atk=4, spd=8, lck=0, base_atk=4, base_spd=6)
    assert w[SPEED - 10] == 1
    assert w[SWIFT - 10] == 0
    assert w[POWER - 10] == 4
    # Earned ATK +5: Power and Blood go to 1, Swift stays 0.
    w = relic_weights(atk=9, spd=6, lck=0, base_atk=4, base_spd=6)
    assert w[POWER - 10] == 1
    assert w[BLOOD - 10] == 1
    assert w[SWIFT - 10] == 0
    # LCK 6 tapers Lucky and Hunter only.
    w = relic_weights(atk=4, spd=6, lck=6, base_atk=4, base_spd=6)
    assert w[LUCKY - 10] == 1
    assert w[HUNTER - 10] == 1
    assert w[POWER - 10] == 4


def test_tables():
    assert POOLS[0] == (12, 10, 16)
    assert POOLS[1] == (10, 16, 19)
    assert POOLS[2] == (12, 15, 13)
    assert POOLS[3] == (12, 15, 16)
    assert POOLS[4] == (12, 13, 15)
    # No class pool has more than one ATK or one SPD relic.
    for cid, pool in POOLS.items():
        atk = sum(1 for i in pool if relic_deltas(i)[0])
        spd = sum(1 for i in pool if relic_deltas(i)[1])
        assert atk <= 1 and spd <= 1, (NAMES[cid], pool, atk, spd)
        assert SWIFT not in pool
    # Boons: five sustain/utility entries, no stacking ATK/SPD, full wrap.
    assert BOON_POOL == (10, 13, 14, 15, 16)
    assert len(BOON_POOL) == 5
    for i in BOON_POOL:
        da, ds, _, _ = relic_deltas(i)
        assert da == 0 and ds == 0, i
    assert {boon_relic(r) for r in range(5)} == set(BOON_POOL)
    assert boon_relic(5) == BOON_POOL[0]
    assert boon_relic(6) == boon_relic(1)


def test_explorer_curve():
    n = 200
    # Per hero: list of (s2_atk_lo, s2_atk_hi, s2_spd_lo, s2_spd_hi,
    #                   s6_atk_lo, s2_near_atk_max_rate, s6_near_atk_min_rate)
    # Bounds are loose around the 400-run means from the oracle.
    for cid, name in enumerate(NAMES):
        s2_atk, s2_spd, s6_atk, s6_spd = [], [], [], []
        s2_near, s6_near = 0, 0
        for i in range(n):
            snaps = simulate_run(cid, seed=9000 + i * 17 + cid)
            s2_atk.append(snaps[2].atk)
            s2_spd.append(snaps[2].spd)
            s6_atk.append(snaps[6].atk)
            s6_spd.append(snaps[6].spd)
            if snaps[2].atk >= ATK_CAP - 2:
                s2_near += 1
            if snaps[6].atk >= ATK_CAP - 2:
                s6_near += 1
        m2a, m2s = sum(s2_atk) / n, sum(s2_spd) / n
        m6a, m6s = sum(s6_atk) / n, sum(s6_spd) / n
        r2, r6 = s2_near / n, s6_near / n
        # Early game is not stingy: at least some growth, but not near-max.
        assert m2a >= BASE_ATK[cid] + 1.5, (name, "s2 atk stingy", m2a)
        assert m2s >= BASE_SPD[cid], (name, "s2 spd stingy", m2s)
        assert r2 <= 0.10, (name, "near-max ATK by stage 2", r2, m2a)
        assert m2a <= ATK_CAP - 3, (name, "s2 atk too high", m2a)
        # By stage 6-7 a thorough explorer is near the cap on ATK
        # (Vespine, the fastest starter, may already be there; Picsean is
        # the slowest and only has to be clearly on the way).
        if cid == 4:
            assert m6a >= 13.0 and r6 >= 0.70, (name, m6a, r6)
        elif cid == 3:
            assert m6a >= 11.0 and r6 >= 0.35, (name, m6a, r6)
        else:
            assert m6a >= 12.0 and r6 >= 0.50, (name, m6a, r6)
        # SPD must not be capped by stage 2 for anyone.
        assert sum(1 for v in s2_spd if v >= SPD_CAP - 2) / n <= 0.15, (
            name, "near-max SPD by stage 2", m2s)
        print(f"  {name:<10} S2 {m2a:.1f}/{m2s:.1f} (near ATK {100*r2:.0f}%)  "
              f"S6 {m6a:.1f}/{m6s:.1f} (near ATK {100*r6:.0f}%)")


def main():
    test_full_weight_is_seed_identical()
    test_underflow_stays_full_weight()
    test_high_taper_rules()
    test_tables()
    test_explorer_curve()
    print("[stat-drop-curve] PASS identity, tapers, tables, explorer curve")


if __name__ == "__main__":
    main()
