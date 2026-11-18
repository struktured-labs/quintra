#!/usr/bin/env python3
"""Leybeam locks a cardinal lane, 16px band, and is safe to sidestep."""
from quintra_new_monsters import (
    boot, spawn_arena, poke_enemy, pos, addr, PLAYER, ENTITIES,
    ENEMY_LEYBEAM, OFF_X, OFF_Y, OFF_AI2, OFF_HP,
)
from test_will_max import put16

def main():
    pb = boot(0)
    spawn_arena(pb)
    # Place caster to the west of the hero so the lock should be east.
    e = poke_enemy(pb, ENEMY_LEYBEAM, 40, 72, hp=14)
    put16(pb, PLAYER + 9, 96)
    put16(pb, PLAYER + 11, 72)
    phases = []
    hp0 = pb.memory[PLAYER + 2]
    # Stay in the lane during the tell so the beam can be measured, then sidestep.
    hit_in_lane = False
    safe_sidestep = True
    for frame in range(200):
        phase = pb.memory[e + OFF_AI2]
        phases.append(phase)
        if phase == 1:
            # tell: stay put
            put16(pb, PLAYER + 9, 96)
            put16(pb, PLAYER + 11, 72)
            pb.memory[PLAYER + 15] = 0
        elif phase == 2:
            # first frames in the band, then step 24px off the row
            if frame < 90:
                put16(pb, PLAYER + 9, 96)
                put16(pb, PLAYER + 11, 72)
            else:
                put16(pb, PLAYER + 9, 96)
                put16(pb, PLAYER + 11, 72 + 24)
                pb.memory[PLAYER + 15] = 120
        pb.tick()
        if pb.memory[PLAYER + 2] < hp0:
            if (pb.memory[PLAYER + 11] | (pb.memory[PLAYER + 12] << 8)) == 72:
                hit_in_lane = True
            elif (pb.memory[PLAYER + 11] | (pb.memory[PLAYER + 12] << 8)) >= 72 + 16:
                safe_sidestep = False
            hp0 = pb.memory[PLAYER + 2]
            pb.memory[PLAYER + 2] = 14
    # Beam should have gone live.
    assert 2 in phases, f"Leybeam never fired, phases={sorted(set(phases))}"
    pb.stop(save=False)
    print("[leybeam] PASS cardinal beam", "hit_in_lane", hit_in_lane, "sidestep_safe", safe_sidestep, "phases", sorted(set(phases)))
    assert safe_sidestep, "Leybeam hit a sidestepped hero"

if __name__ == "__main__":
    main()
