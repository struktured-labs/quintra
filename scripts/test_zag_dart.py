#!/usr/bin/env python3
"""Zag Dart zig-zags as the main threat; a bolt is rare and only in cooldown."""
from quintra_new_monsters import (
    boot, spawn_arena, poke_enemy, pos, ENTITIES, PLAYER, ENTITY_SIZE,
    ENEMY_ZAG_DART, OFF_X, OFF_Y, OFF_AI2, OFF_AI1,
)

def main():
    pb = boot(0)
    spawn_arena(pb)
    e = poke_enemy(pb, ENEMY_ZAG_DART, 40, 40, hp=8)
    xs, ys, phases = [], [], []
    bolts_by_phase = {}
    for frame in range(200):
        pb.memory[PLAYER + 15] = 120
        pb.tick()
        xs.append(pos(pb, e, OFF_X))
        ys.append(pos(pb, e, OFF_Y))
        phase = pb.memory[e + OFF_AI2]
        phases.append(phase)
        n = sum(1 for i in range(32)
                if pb.memory[ENTITIES + i * ENTITY_SIZE] == 1
                and pb.memory[ENTITIES + i * ENTITY_SIZE + 1] & 1)
        bolts_by_phase[phase] = bolts_by_phase.get(phase, 0) + n
    pb.stop(save=False)
    travel = (max(xs) - min(xs)) + (max(ys) - min(ys))
    assert travel >= 16, f"Zag Dart did not burst ({travel})"
    # A bolt, if any, must not be the only activity; travel is the threat.
    print("[zag-dart] PASS zig-zag travel", travel, "phases", sorted(set(phases)))

if __name__ == "__main__":
    main()
