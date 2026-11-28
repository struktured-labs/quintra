#!/usr/bin/env python3
"""The Basilisk family is tanky: several hits from any hero, damage unchanged (#272).

The 32x32 coiled serpent used to have 14 / 20 / 26 HP (Ley / Sun / Nox).
A fresh hero's basic weapon killed the Ley Basilisk in 3-6 hits, and a
geared one in one or two. It now has 48 / 72 / 96 HP. Its contact and beam
damage stat stays exactly 1.

Checks:
  * the generated table the ROM is built from carries the new HP and the
    unchanged damage for all three tiers;
  * a pack alpha (HP doubled after the deepest stage bonus) still fits in
    a byte;
  * live ROM: the hardest-hitting basic weapon at late-run ATK still needs
    at least four hits on a Ley Basilisk at its stage 3 HP, and a base
    Wolfkin needs at least twelve.
"""
import re
from pathlib import Path

from quintra_new_monsters import (
    ENEMY_LEYBEAM, ENEMY_NOX_BASILISK, ENEMY_SUN_BASILISK, OFF_HP, PLAYER,
    boot, poke_enemy, spawn_arena,
)
from test_will_max import put16

ROOT = Path(__file__).resolve().parent.parent
HP = {ENEMY_LEYBEAM: 48, ENEMY_SUN_BASILISK: 72, ENEMY_NOX_BASILISK: 96}
OLD_HP = {ENEMY_LEYBEAM: 14, ENEMY_SUN_BASILISK: 20, ENEMY_NOX_BASILISK: 26}
DAMAGE = 1
LEY_STAGE3_BONUS = 2      # dungeon_director_configure_initial at stage 3
DEEPEST_BONUS = 6         # 1 + (8 >> 1) at stage 9, +1 outside a skirmish


def generated_stats():
    text = (ROOT / "src/generated/enemies.c").read_text()
    out = {}
    for enemy_id in HP:
        block = text.split(f".id={enemy_id},", 1)[1].split("}", 1)[0]
        out[enemy_id] = (int(re.search(r"\.hp=(\d+)", block).group(1)),
                         int(re.search(r"\.damage=(\d+)", block).group(1)))
    return out


def hits_to_kill(class_id, atk_bonus, hp):
    pb = boot(class_id)
    spawn_arena(pb, class_id)
    atk = min(15, pb.memory[PLAYER + 5] + atk_bonus)
    e = poke_enemy(pb, ENEMY_LEYBEAM, 72, 96, hp=hp, hitbox=0xFF, timer=1)
    hits, last = 0, hp
    for frame in range(1500):
        put16(pb, PLAYER + 9, 76)
        put16(pb, PLAYER + 11, 56)
        pb.memory[PLAYER + 13] = 0           # face south, at the coil
        pb.memory[PLAYER + 15] = 200         # stay unhurt
        pb.memory[PLAYER + 2] = pb.memory[PLAYER + 1]
        pb.memory[PLAYER + 5] = atk
        if frame % 6 == 0:
            pb.button_press("a")
        elif frame % 6 == 3:
            pb.button_release("a")
        pb.tick()
        alive = pb.memory[e] == 2 and pb.memory[e + 1] & 1
        cur = pb.memory[e + OFF_HP] if alive else 0
        if cur < last:
            hits += 1
            last = cur
        if not cur:
            break
    pb.stop(save=False)
    assert not last, f"class {class_id} never killed the basilisk ({last} HP left)"
    return hits


def main():
    stats = generated_stats()
    for enemy_id, (hp, damage) in stats.items():
        assert hp == HP[enemy_id], (
            f"enemy {enemy_id}: HP {hp}, want {HP[enemy_id]}")
        assert hp >= 3 * OLD_HP[enemy_id], f"enemy {enemy_id} is not tanky"
        assert damage == DAMAGE, (
            f"enemy {enemy_id}: damage changed to {damage}; #272 is HP only")
        assert (hp + DEEPEST_BONUS) * 2 <= 255, (
            f"enemy {enemy_id}: an alpha's doubled HP overflows a byte")

    ley = HP[ENEMY_LEYBEAM] + LEY_STAGE3_BONUS
    geared = hits_to_kill(1, 6, ley)         # Sauran, ATK +6: 14 a hit
    assert geared >= 4, f"a geared Sauran kills a Ley Basilisk in {geared} hits"
    fresh = hits_to_kill(0, 0, ley)          # base Wolfkin: 3 a hit
    assert fresh >= 12, f"a fresh Wolfkin kills a Ley Basilisk in {fresh} hits"
    print(f"[basilisk-tanky] PASS HP 48/72/96 (was 14/20/26), damage 1; "
          f"Ley at stage 3 ({ley} HP): geared Sauran {geared} hits, "
          f"fresh Wolfkin {fresh} hits")


if __name__ == "__main__":
    main()
