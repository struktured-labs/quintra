#!/usr/bin/env python3
"""Fuse Hurler lobs a fused bomb with a visible tell; blast is never a one-shot."""
from quintra_new_monsters import (
    boot, spawn_arena, poke_enemy, addr, PLAYER, ENTITIES,
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
    # Close-range wind-up: park on top of it and wait for phase 3.
    pb.memory[PLAYER + 2] = 8
    put16(pb, PLAYER + 9, 40)
    put16(pb, PLAYER + 11, 72)
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

if __name__ == "__main__":
    main()
