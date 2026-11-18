#!/usr/bin/env python3
"""Fuse Hurler lobs a fused bomb with a visible tell; blast is never a one-shot.

The blast is a 4-frame 32x32 burst. Damage is the Chebyshev square of
FUSE_RADIUS (18) from the blast centre to the hero centre (x+8, y+12) and is
live only while the fireball frames are drawn, so the hitbox matches the art.
"""
from quintra_new_monsters import (
    boot, spawn_arena, poke_enemy, pos, addr, PLAYER, ENTITIES,
    ENEMY_FUSE_HURLER, OFF_AI2, OFF_HP,
)
from test_will_max import put16

def main():
    pb = boot(0)
    spawn_arena(pb)
    e = poke_enemy(pb, ENEMY_FUSE_HURLER, 40, 72, hp=12, damage=1)
    put16(pb, PLAYER + 9, 96)
    put16(pb, PLAYER + 11, 72)
    pb.memory[PLAYER + 2] = 8
    phases = []
    saw_phase3 = False
    hp0 = 8
    hits = 0
    min_hp = 8
    # First, stay at mid range so it lobs rather than explodes in place.
    for frame in range(260):
        phase = pb.memory[e + OFF_AI2]
        phases.append(phase)
        pb.memory[PLAYER + 15] = 0  # no iframes unless the game set them
        pb.tick()
        hp = pb.memory[PLAYER + 2]
        if hp < hp0:
            hits += 1
            min_hp = min(min_hp, hp)
            hp0 = hp
        # refill so later hits stay measurable, but keep a floor of 1 once
        if hp >= 2:
            pb.memory[PLAYER + 2] = 8
            hp0 = 8
    assert 1 in phases or 2 in phases, f"Hurler never told/lobbed, phases={sorted(set(phases))}"
    # Close-range wind-up: park on top of it (it may have wandered) and wait.
    pb.memory[PLAYER + 2] = 8
    hx, hy = pos(pb, e, 3), pos(pb, e, 7)
    put16(pb, PLAYER + 9, hx)
    put16(pb, PLAYER + 11, hy)
    pb.memory[e + OFF_AI2] = 0
    pb.memory[e + 18] = 0  # TIMER
    for frame in range(80):
        phase = pb.memory[e + OFF_AI2]
        if phase == 3:
            saw_phase3 = True
        pb.tick()
    assert saw_phase3, "close-range wind-up never started (phase 3)"
    # Lethal floor: sit in a forced self-burst at 1 HP and survive.
    pb.memory[PLAYER + 2] = 1
    pb.memory[PLAYER + 15] = 0
    put16(pb, PLAYER + 9, 40)
    put16(pb, PLAYER + 11, 72)
    pb.memory[e + OFF_AI2] = 3
    pb.memory[e + 18] = 26  # almost done winding up
    for _ in range(20):
        pb.tick()
    assert pb.memory[PLAYER + 2] >= 1, "Fuse Hurler blast was a one-shot"
    pb.stop(save=False)
    print("[fuse-hurler] PASS", "phases", sorted(set(phases)),
          "hits", hits, "windup", saw_phase3, "min_hp_seen", min_hp)

def blast_hits(dx):
    """Self-burst centred on the Hurler at (40,72) -> blast centre (44,76)."""
    pb = boot(0)
    spawn_arena(pb)
    e = poke_enemy(pb, ENEMY_FUSE_HURLER, 40, 72, hp=12, damage=1)
    pb.memory[e + OFF_AI2] = 3
    pb.memory[e + 18] = 27
    hit = False
    for _ in range(30):
        put16(pb, PLAYER + 9, 44 + dx - 8)
        put16(pb, PLAYER + 11, 76 - 12)
        pb.memory[PLAYER + 15] = 0
        pb.memory[PLAYER + 2] = 8
        pb.tick()
        if pb.memory[PLAYER + 2] < 8:
            hit = True
    pb.stop(save=False)
    return hit


def blast_geometry():
    inside = [blast_hits(d) for d in (12, 16, 18)]
    outside = [blast_hits(d) for d in (20, 24)]
    assert all(inside), f"blast missed a hero inside the burst: {inside}"
    assert not any(outside), f"blast hit a hero outside the burst: {outside}"
    print("[fuse-hurler] PASS blast radius 18: inside", inside, "outside", outside)


if __name__ == "__main__":
    blast_geometry()
    main()
