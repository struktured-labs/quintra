#!/usr/bin/env python3
"""Veil Magus blinks away from the hero, never into a wall, and fires one bolt."""
from quintra_new_monsters import (
    boot, spawn_arena, poke_enemy, pos, ENTITIES, PLAYER, TILEMAP,
    ENEMY_VEIL_MAGUS, OFF_X, OFF_Y, OFF_AI2, ENTITY_SIZE,
)
from test_will_max import put16

def projectile_slots(pb):
    out = []
    for i in range(32):
        e = ENTITIES + i * ENTITY_SIZE
        if pb.memory[e] == 1 and pb.memory[e + 1] & 1:
            out.append(e)
    return out

def main():
    pb = boot(0)
    spawn_arena(pb)
    for i in range(20 * 17):
        pb.memory[TILEMAP + i] = 1
    for x in range(20):
        pb.memory[TILEMAP + x] = 2
        pb.memory[TILEMAP + 16 * 20 + x] = 2
    for y in range(17):
        pb.memory[TILEMAP + y * 20] = 2
        pb.memory[TILEMAP + y * 20 + 19] = 2
    put16(pb, PLAYER + 9, 80)
    put16(pb, PLAYER + 11, 72)
    e = poke_enemy(pb, ENEMY_VEIL_MAGUS, 40, 40, hp=12)
    appeared = []
    bolts = 0
    px, py = 80, 72
    vanished = False
    for frame in range(260):
        pb.memory[PLAYER + 15] = 120
        pb.tick()
        x, y = pos(pb, e, OFF_X), pos(pb, e, OFF_Y)
        phase = pb.memory[e + OFF_AI2]
        if phase == 2 or y >= 160:
            vanished = True
            continue
        # Phase 0 is the visible tell after a reappear (or the opening pose).
        if vanished and phase == 0:
            assert 8 <= x <= 152 and 8 <= y <= 128, (frame, x, y)
            dist = abs(x - px) + abs(y - py)
            if (x, y) != (40, 40):
                assert dist >= 24, f"reappeared too close: {(x,y)} d={dist}"
            appeared.append((x, y))
        bolts = max(bolts, len(projectile_slots(pb)))
    pb.stop(save=False)
    assert vanished, "Veil Magus never vanished"
    assert appeared, "Veil Magus never reappeared on a walkable cell"
    assert bolts >= 1, "Veil Magus never fired a bolt"
    print("[veil-magus] PASS spawn, wall-safe blink, one bolt", appeared[0])

if __name__ == "__main__":
    main()
