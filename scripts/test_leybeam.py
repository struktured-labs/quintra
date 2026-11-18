#!/usr/bin/env python3
"""Basilisk tiers: the locked lane band is 16/24/32 px wide, the tell is long
enough to read, and a hero outside the band is never hit.

Caster at (40,72) facing east: mouth y = 66, so the lanes are
  Ley   (2 lanes) rows 7..8  -> y 56..71
  Sun   (3 lanes) rows 7..9  -> y 56..79
  Nox   (4 lanes) rows 6..9  -> y 48..79
The beam test uses the hero hurtbox rows y+10..y+13 (1-px inset).
"""
from quintra_new_monsters import (
    boot, spawn_arena, poke_enemy, PLAYER,
    ENEMY_LEYBEAM, ENEMY_SUN_BASILISK, ENEMY_NOX_BASILISK, OFF_AI2,
)
from test_will_max import put16

TIERS = [
    # id, name, cooldown, tell, band (y0, y1) in px
    (ENEMY_LEYBEAM, "ley", 100, 40, (56, 71)),
    (ENEMY_SUN_BASILISK, "sun", 96, 44, (56, 79)),
    (ENEMY_NOX_BASILISK, "nox", 90, 48, (48, 79)),
]
HERO_YS = (36, 44, 52, 60, 64, 72)


def run(enemy_id, cool, hero_y):
    pb = boot(0)
    spawn_arena(pb)
    e = poke_enemy(pb, enemy_id, 40, 72, hp=30, timer=cool - 1)
    hp0 = 14
    pb.memory[PLAYER + 2] = hp0
    tell = 0
    fired = False
    hit = False
    for _ in range(260):
        put16(pb, PLAYER + 9, 96)
        put16(pb, PLAYER + 11, hero_y)
        pb.memory[PLAYER + 15] = 0
        phase = pb.memory[e + OFF_AI2]
        if phase == 1:
            tell += 1
        if phase == 2:
            fired = True
        pb.tick()
        if pb.memory[PLAYER + 2] < hp0:
            if phase == 2:
                hit = True
            pb.memory[PLAYER + 2] = hp0
        if fired and pb.memory[e + OFF_AI2] == 0:
            break
    pb.stop(save=False)
    return fired, tell, hit


def main():
    for enemy_id, name, cool, tell_min, (y0, y1) in TIERS:
        hits = {}
        for hy in HERO_YS:
            fired, tell, hit = run(enemy_id, cool, hy)
            assert fired, f"{name}: never fired"
            assert tell >= tell_min, f"{name}: tell {tell} < {tell_min} frames"
            hits[hy] = hit
            hurt_lo, hurt_hi = hy + 10, hy + 13
            in_band = not (hurt_hi < y0 or hurt_lo > y1)
            assert hit == in_band, (
                f"{name}: hero y={hy} (hurt {hurt_lo}..{hurt_hi}) band {y0}..{y1} "
                f"expected hit={in_band} got {hit}")
        width = y1 - y0 + 1
        print(f"[basilisk] PASS {name} band {width}px tell>={tell_min}", hits)


if __name__ == "__main__":
    main()
