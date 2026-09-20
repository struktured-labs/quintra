#!/usr/bin/env python3
"""Bounded, telegraphed projectile casts and distinct return movement."""
import hashlib
import json
import os
from test_will_max import boot, clear_arena, addr, put16, PLAYER, ENTITIES, ROM

def run(enemy_id, stage, clock, variant, frames):
    pb = boot(0)
    clear_arena(pb)
    rs = addr('_run_state')
    pb.memory[rs + 11] = stage
    pb.memory[addr('_room_encounter_kind')] = 0
    pb.memory[addr('_room_encounter_phase')] = 1
    pb.memory[addr('_room_return_echo_kind')] = 5 if enemy_id == 34 else 0
    pb.memory[addr('_room_encounter_target')] = 0
    put16(pb, PLAYER + 9, 120)
    put16(pb, PLAYER + 11, 100)
    e = ENTITIES
    pb.memory[e] = 2
    pb.memory[e + 1] = 0x27
    put16(pb, e + 3, 72)
    put16(pb, e + 7, 56)
    pb.memory[e + 12] = 125
    pb.memory[e + 14] = 200
    pb.memory[e + 17] = enemy_id
    pb.memory[e + 18] = clock if enemy_id == 22 else 0
    pb.memory[e + 20] = clock if enemy_id != 22 else 0
    pb.memory[e + 21] = variant
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = 1
    trace, births, previous = [], [], set()
    for frame in range(frames):
        pb.memory[PLAYER + 15] = 120
        pb.tick()
        shots = []
        current = set()
        for slot in range(1, 32):
            s = ENTITIES + slot * 28
            if pb.memory[s] != 1 or not pb.memory[s + 1] & 1: continue
            vx, vy = (pb.memory[s + off] for off in (10, 11))
            vx = vx - 256 if vx >= 128 else vx
            vy = vy - 256 if vy >= 128 else vy
            current.add(slot)
            shot = [slot, pb.memory[s + 3], pb.memory[s + 7], vx, vy]
            shots.append(shot)
            if slot not in previous: births.append([frame, *shot])
        previous = current
        trace.append(dict(frame=frame, x=pb.memory[e + 3], y=pb.memory[e + 7],
                          phase=pb.memory[e + 19], shots=shots))
    pb.stop(save=False)
    return dict(enemy=enemy_id, stage=stage, trace=trace, births=births)

def main():
    spiral = run(22, 0, 16, 0, 145)
    fan = run(0, 0, 144, 2, 70)
    results = [spiral, fan, run(34, 1, 1, 0, 150), run(34, 2, 1, 0, 150)]
    from pathlib import Path
    Path(os.environ.get('QUINTRA_PATTERN_REPORT', '/tmp/quintra-enemy-patterns.json')).write_text(
        json.dumps(dict(rom_sha256=hashlib.sha256(ROM.read_bytes()).hexdigest(),
        fixture='fresh boot; isolated enemy; native update loop', results=results), indent=2))
    assert all(abs(s[-2]) <= 1 and abs(s[-1]) <= 1 for r in results for s in r['births'])
    assert len(spiral['births']) == 8, spiral['births']
    assert len({tuple(s[-2:]) for s in spiral['births']}) == 8
    assert spiral['births'][0][0] >= 16
    assert len({(r['x'], r['y']) for r in spiral['trace'][-30:]}) > 1
    assert len(fan['births']) == 5, fan['births']
    assert len({tuple(s[-2:]) for s in fan['births']}) == 5
    assert len({(r['x'], r['y']) for r in fan['trace'][:40]}) == 1
    for stage in (1, 2):
        result = results[stage + 1]
        phases = {r['phase'] for r in result['trace']}
        assert {1, 2, 3} <= phases, (stage, phases)
        active = [r for r in result['trace'] if r['phase'] == 2]
        distance = max(r['x'] for r in active) - min(r['x'] for r in active)
        distance += max(r['y'] for r in active) - min(r['y'] for r in active)
        assert distance == 0 if stage == 1 else distance >= 12, (stage, distance)
    print('[enemy-patterns] PASS spiral, locked sweeping fan, orbit/cast and charge/recover')

if __name__ == '__main__': main()
