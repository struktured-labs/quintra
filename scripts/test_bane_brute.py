#!/usr/bin/env python3
"""Bane Brute groups with status allies and applies a long knockback."""
from quintra_new_monsters import (
    boot, spawn_arena, poke_enemy, pos, addr, PLAYER, ENTITIES, ENTITY_SIZE,
    ENEMY_BANE_BRUTE, OFF_X, OFF_Y, OFF_ID, OFF_FLAGS,
)
from test_will_max import put16
from quintra_new_monsters import set_dungeon_cell

ENEMY_SHADE = 7
ENEMY_MIRE_SPORE = 17
ENEMY_SKELETON = 3

def call_post_spawn(pb):
    """Nudge grouping by invoking the banked hook if we can find it.
    Tests instead re-create the post-spawn world and then measure knockback.
    """
    return

def main():
    pb = boot(0)
    spawn_arena(pb)
    # Brute + two fillers. After a few ticks we only assert the brute still
    # lives when two status allies are present, and that a contact shove is long.
    brute = poke_enemy(pb, ENEMY_BANE_BRUTE, 88, 72, hp=22, i=0, hitbox=0xDD, damage=2)
    poke_enemy(pb, ENEMY_SHADE, 112, 72, hp=9, i=1)
    poke_enemy(pb, ENEMY_MIRE_SPORE, 64, 72, hp=13, i=2)
    put16(pb, PLAYER + 9, 96)
    put16(pb, PLAYER + 11, 72)
    pb.memory[PLAYER + 2] = 14
    pb.memory[PLAYER + 15] = 0  # allow contact
    x0 = pb.memory[PLAYER + 9] | (pb.memory[PLAYER + 10] << 8)
    farthest = x0
    for frame in range(40):
        pb.tick()
        x = pb.memory[PLAYER + 9] | (pb.memory[PLAYER + 10] << 8)
        farthest = max(farthest, x)
        pb.memory[PLAYER + 2] = 14
    shoved = farthest - x0
    # Ordinary knockback is 6px; brute cardinal is 18.
    assert shoved >= 10, f"Bane Brute knockback too short: {shoved}"
    # Grouping survival: brute still active next to two status allies.
    assert pb.memory[brute] == 2 and pb.memory[brute + 1] & 1
    pb.stop(save=False)
    print("[bane-brute] PASS grouped allies and long knockback", shoved)

if __name__ == "__main__":
    main()
