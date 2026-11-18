#!/usr/bin/env python3
"""Oracle for Quintra ATK/SPD drop weights, class tables, and the explorer curve.

Mirrors:
  src/game/pickup_stat_relic.c
  src/game/treasure_guard.c
  src/game/powerup.c          relic band 5/256
  content/src/classes.rs      + Wolfkin +1 SPD perk
  src/game/player.h           caps ATK 15, SPD 12
  src/game/run_state.c        dungeon sizes

Used by scripts/test_stat_drop_curve.py. Run this file to print the curve.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

ATK_CAP, SPD_CAP, DEF_CAP, LCK_CAP = 15, 12, 10, 10
W_FULL, W_MID, W_HIGH = 4, 2, 1
ATK_MID, ATK_HIGH = 2, 5
SPD_EARNED_MID, SPD_ABS_HIGH = 1, 8
LCK_HIGH = 6
RELIC_BAND, DROP_MOD = 5, 256

NAMES = ("Wolfkin", "Sauran", "Corvin", "Picsean", "Vespine")
BASE_ATK = (2, 2, 2, 1, 4)
BASE_SPD = (6, 4, 4, 4, 6)  # Wolfkin 5 + perk
BASE_DEF = (1, 2, 1, 1, 1)

IRON, SPEED, POWER, TOUGH, LUCKY, MANA, WARD, SWIFT, HUNTER, BLOOD = range(10, 20)

# After Carbon review: no structured Speed for any hero; Vespine gets
# Power / Tough / Mana (keeps her low HP); Wolfkin Power / Iron / Ward.
POOLS: Dict[int, Tuple[int, int, int]] = {
    0: (POWER, IRON, WARD),
    1: (IRON, WARD, BLOOD),
    2: (POWER, MANA, TOUGH),
    3: (POWER, MANA, WARD),
    4: (POWER, TOUGH, MANA),
}
BOON_POOL = (IRON, TOUGH, LUCKY, MANA, WARD)

DELTAS = {
    IRON:   (0, 0, 0, 0),
    SPEED:  (0, 1, 0, 0),
    POWER:  (1, 0, 0, 0),
    TOUGH:  (0, 0, 1, 0),
    LUCKY:  (0, 0, 0, 2),
    MANA:   (0, 0, 0, 0),
    WARD:   (0, 0, 1, 1),
    SWIFT:  (1, 1, 0, 0),
    HUNTER: (0, 0, 0, 3),
    BLOOD:  (1, 0, 0, 0),
}

STAGE_SIZES = (20, 21, 22, 23, 24, 25, 26, 28, 30)

# Historical pools, used only for the "before" printout.
POOLS_BEFORE = {
    0: (POWER, SWIFT, BLOOD),
    1: (IRON, WARD, BLOOD),
    2: (SPEED, POWER, SWIFT),
    3: (POWER, MANA, WARD),
    4: (POWER, SWIFT, BLOOD),
}


def relic_deltas(idx: int) -> Tuple[int, int, int, int]:
    return DELTAS[idx]


def relic_weights(atk: int, spd: int, lck: int, base_atk: int, base_spd: int) -> List[int]:
    atk_r = max(0, atk - base_atk)
    spd_r = max(0, spd - base_spd)
    atk_w = W_HIGH if atk_r >= ATK_HIGH else (W_MID if atk_r >= ATK_MID else W_FULL)
    spd_w = W_HIGH if spd >= SPD_ABS_HIGH else (W_MID if spd_r >= SPD_EARNED_MID else W_FULL)
    lck_w = W_HIGH if lck >= LCK_HIGH else W_FULL
    w = [W_FULL] * 10
    w[SPEED - 10] = spd_w
    w[POWER - 10] = atk_w
    w[LUCKY - 10] = lck_w
    w[HUNTER - 10] = lck_w
    w[BLOOD - 10] = atk_w
    w[SWIFT - 10] = 0 if (atk_w <= W_HIGH or spd_w <= W_HIGH) else min(atk_w, spd_w)
    return w


def map_stat_relic(r: int, atk: int, spd: int, lck: int,
                   base_atk: int, base_spd: int) -> int:
    """Exact oracle for pickup_map_stat_relic. r is an rng_next_u8() value."""
    w = relic_weights(atk, spd, lck, base_atk, base_spd)
    total = sum(w)
    if total == 40:
        return 10 + (r % 10)
    slot = (r * total) >> 8
    acc = 0
    for i, wi in enumerate(w):
        acc += wi
        if slot < acc:
            return 10 + i
    return 10


def boon_relic(roll: int) -> int:
    return BOON_POOL[roll % 5]


def expected_combat_kills(stage: int) -> int:
    size = STAGE_SIZES[stage]
    last = size - 1
    waypoints = sum(1 for loc in (5, 11, 17, 23) if loc < last)
    puzzles = 2
    combat = size - 3 - waypoints - puzzles
    if combat < 0:
        combat = 0
    depth = 2 if stage >= 3 else (1 if stage else 0)
    opening = 2 if stage == 0 else 0
    pack = 11 + 2 + depth + opening + 0.65
    if stage:
        ordinary = combat - 1
        kills = 13.5 + ordinary * pack
    else:
        ordinary = combat
        kills = combat * pack
    kills += puzzles * (4 + (1 if stage >= 3 else 0))
    kills += waypoints * 3
    eligible = max(ordinary if stage else max(combat - 2, 0), 0) * 0.7
    wave_frac = 2 / 8 if stage == 0 else 1 / 8
    kills += eligible * wave_frac * (3 + (1 if stage >= 4 else 0))
    kills += eligible * (1 / 8) * 3
    return int(round(kills))


def expected_riftwild_kills(region: int) -> int:
    band = 4.5 + (1 if region >= 2 else 0)
    return int(round(36 * 0.75 * band))


def expected_boons(stage: int) -> float:
    size = STAGE_SIZES[stage]
    last = size - 1
    waypoints = sum(1 for loc in (5, 11, 17, 23) if loc < last)
    combat = size - 3 - waypoints - 2
    eligible = max(combat - (1 if stage else 0), 0) * 0.7
    return eligible * (2 / 8)


@dataclass
class Stats:
    atk: int
    spd: int
    defense: int = 1
    lck: int = 0
    base_atk: int = 0
    base_spd: int = 0

    def apply(self, idx: int) -> None:
        da, ds, dd, dl = relic_deltas(idx)
        self.atk = min(ATK_CAP, self.atk + da)
        self.spd = min(SPD_CAP, self.spd + ds)
        self.defense = min(DEF_CAP, self.defense + dd)
        self.lck = min(LCK_CAP, self.lck + dl)

    def add_atk(self, n: int = 1) -> None:
        self.atk = min(ATK_CAP, self.atk + n)

    def add_spd(self, n: int = 1) -> None:
        self.spd = min(SPD_CAP, self.spd + n)

    def copy(self) -> "Stats":
        return Stats(self.atk, self.spd, self.defense, self.lck,
                     self.base_atk, self.base_spd)


def simulate_run(class_id: int, *, seed: int, diminishing: bool = True,
                 pools: Dict[int, Tuple[int, int, int]] | None = None,
                 boon_sustain: bool = True, buy_village: bool = False,
                 buy_glass: bool = False, kill_scale: float = 1.0,
                 class_boons_prefer_atk: bool = False) -> List[Stats]:
    """Thorough first-visit Normal run. Shop, Farfold, and boss each give one
    random item from the class pool (the player does not pick which). Boons
    use the sustain table unless class_boons_prefer_atk is set (legacy)."""
    rng = random.Random(seed)
    pool = (pools or POOLS)[class_id]
    st = Stats(atk=BASE_ATK[class_id], spd=BASE_SPD[class_id],
               defense=BASE_DEF[class_id], lck=0,
               base_atk=BASE_ATK[class_id], base_spd=BASE_SPD[class_id])
    snaps = [st.copy()]

    def take_structured():
        st.apply(rng.choice(list(pool)))

    def take_boon():
        if class_boons_prefer_atk:
            roll = rng.randrange(3)
            a, b = pool[roll], pool[(roll + 1) % 3]
            for pref in (a, b):
                if relic_deltas(pref)[0] and st.atk < ATK_CAP:
                    st.apply(pref)
                    return
            for pref in (a, b):
                if relic_deltas(pref)[1] and st.spd < SPD_CAP:
                    st.apply(pref)
                    return
            st.apply(a)
            return
        if boon_sustain:
            st.apply(boon_relic(rng.randrange(256)))

    def roll_item():
        r = rng.randrange(256)
        if not diminishing:
            return 10 + (r % 10)
        return map_stat_relic(r, st.atk, st.spd, st.lck, st.base_atk, st.base_spd)

    def drops(n: int):
        n = int(round(n * kill_scale))
        for _ in range(n):
            if rng.randrange(DROP_MOD) < RELIC_BAND:
                st.apply(roll_item())

    for stage in range(9):
        take_structured()  # shop WARE_ITEM
        take_structured()  # Farfold
        if buy_glass:
            feat = rng.randrange(6)
            if feat == 0:
                st.add_atk(2)
                st.add_spd(1)
            elif feat == 1:
                st.add_atk(1)
        mean = expected_boons(stage)
        n_boons = sum(1 for _ in range(12) if rng.random() < mean / 12)
        for _ in range(n_boons):
            take_boon()
        st.apply(roll_item())  # secret vault
        drops(expected_combat_kills(stage))
        take_structured()  # boss
        if stage in (2, 5):
            if buy_village:
                st.add_atk(1)
                st.add_atk(1)
            drops(expected_riftwild_kills(stage // 3))
            st.apply(roll_item())
        else:
            drops(expected_riftwild_kills(stage // 3) // 3)
        snaps.append(st.copy())
    return snaps


def summarize(label: str, n: int = 400, **kw) -> None:
    print(f"\n## {label}")
    print(f"{'Hero':<10} " + " ".join(f"{'S'+str(s):>8}" for s in range(1, 10)))
    for cid, name in enumerate(NAMES):
        atk = [0] * 10
        spd = [0] * 10
        na = [0] * 10
        ns = [0] * 10
        fa, fs = [], []
        for i in range(n):
            snaps = simulate_run(cid, seed=8000 + i * 31 + cid, **kw)
            a = s = 10
            for stg in range(1, 10):
                atk[stg] += snaps[stg].atk
                spd[stg] += snaps[stg].spd
                if snaps[stg].atk >= ATK_CAP - 2:
                    na[stg] += 1
                if snaps[stg].spd >= SPD_CAP - 2:
                    ns[stg] += 1
                if a == 10 and snaps[stg].atk >= ATK_CAP - 2:
                    a = stg
                if s == 10 and snaps[stg].spd >= SPD_CAP - 2:
                    s = stg
            fa.append(a)
            fs.append(s)
        print(f"{name:<10} " + " ".join(
            f"{atk[s]/n:5.1f}/{spd[s]/n:.1f}" for s in range(1, 10)))
        print(f"{'':10} " + " ".join(
            f"{100*na[s]/n:4.0f}/{100*ns[s]/n:.0f}%" for s in range(1, 10))
              + f"   near%  first {sum(fa)/n:.1f}/{sum(fs)/n:.1f}")


def main() -> None:
    summarize("BEFORE (legacy class boons prefer ATK, uniform 10-orb)",
              diminishing=False, pools=POOLS_BEFORE,
              class_boons_prefer_atk=True, boon_sustain=False)
    summarize("AFTER explorer (no village, no Glass)")
    summarize("AFTER shopper (village Forge+Vamp)", buy_village=True)
    summarize("AFTER shopper + Glass, Vespine +15% kills",
              buy_village=True, buy_glass=True,
              kill_scale=1.0)  # per-hero scale applied only if caller sets it
    # Vespine sensitivity is a separate pass
    print("\n## AFTER explorer, Vespine +15% kills only")
    # reuse summarize but only meaningful for Vespine; print all anyway
    summarize("AFTER explorer +15% kills (all heroes; only Vespine should move)",
              kill_scale=1.15)


if __name__ == "__main__":
    main()
