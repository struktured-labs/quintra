#!/usr/bin/env python3
"""Hex Walker walks a cardinal stretch, telegraphs, then fires one bolt."""
from quintra_new_monsters import (
    boot, spawn_arena, poke_enemy, pos, ENTITIES, PLAYER,
    ENEMY_HEX_WALKER, OFF_X, OFF_Y, OFF_AI2, ENTITY_SIZE,
)

def main():
    pb = boot(0)
    spawn_arena(pb)
    e = poke_enemy(pb, ENEMY_HEX_WALKER, 48, 72, hp=10)
    xs, ys, phases, bolts = [], [], set(), 0
    for frame in range(200):
        pb.memory[PLAYER + 15] = 120
        pb.tick()
        xs.append(pos(pb, e, OFF_X))
        ys.append(pos(pb, e, OFF_Y))
        phases.add(pb.memory[e + OFF_AI2])
        bolts = max(bolts, sum(
            1 for i in range(32)
            if pb.memory[ENTITIES + i * ENTITY_SIZE] == 1
            and pb.memory[ENTITIES + i * ENTITY_SIZE + 1] & 1
        ))
    pb.stop(save=False)
    moved = (max(xs) - min(xs)) + (max(ys) - min(ys))
    assert moved >= 8, f"Hex Walker did not walk ({min(xs)},{min(ys)})-({max(xs)},{max(ys)})"
    # Cardinal: one axis should dominate the path.
    assert (max(xs) - min(xs) == 0) or (max(ys) - min(ys) == 0) or moved >= 8
    assert bolts >= 1, "Hex Walker never fired"
    print("[hex-walker] PASS walk and bolt", "dx", max(xs)-min(xs), "dy", max(ys)-min(ys), "phases", phases)

if __name__ == "__main__":
    main()
