#!/usr/bin/env python3
"""Director timing fixtures, not a player difficulty or performance verdict."""
import hashlib
import json
import os
from pathlib import Path
from test_stage_archetypes import ROM, generated_room, addr, PL, RS, EN
from test_dungeon_director import enemies, erase, tick_safe, seed_for, KIND, PHASE, TIMER, put16

sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
out = Path('builds') / f'opening-dynamics-{sha[:8]}'
out.mkdir(parents=True, exist_ok=True)
report = dict(rom_sha256=sha, fixture='Real generated room; staged enemy count, protection and approach position',
              script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

def wave(pb, tiles):
    assert pb.memory[KIND] == 2
    erase(pb, enemies(pb)[2:])
    original = set(enemies(pb))
    pb.memory[PL+9] = 72
    pb.memory[PL+11] = 120
    trace = []
    for frame in range(150):
        tick_safe(pb, 1)
        trace.append([frame, len(enemies(pb)), pb.memory[PHASE], pb.memory[TIMER]])
        if pb.memory[PHASE] == 1:
            break
    report['wave_trace'] = trace
    assert any(t[3] > 0 for t in trace), 'No reinforcement warning'
    assert pb.memory[PHASE] == 1 and len(enemies(pb)) >= 5, 'Wave waited for an empty room'
    for e in set(enemies(pb)) - original:
        x = pb.memory[e+3] | pb.memory[e+4] << 8
        y = pb.memory[e+7] | pb.memory[e+8] << 8
        px = pb.memory[PL+9] | pb.memory[PL+10] << 8
        py = pb.memory[PL+11] | pb.memory[PL+12] << 8
        assert abs(x-px) >= 40 or abs(y-py) >= 40, 'Reinforcement spawned on hero'
    pb.screen.image.save(str(out/'wave.png'))
    erase(pb, enemies(pb)); tick_safe(pb, 20)
    assert pb.memory[PHASE] == 2
    tick_safe(pb, 120)
    assert not enemies(pb), 'Repeated reinforcement wave'

def nook(pb, tiles):
    assert pb.memory[KIND] == 0
    erase(pb, enemies(pb))
    put16(pb, PL+9, 112); put16(pb, PL+11, 112)
    before = pb.memory[PL+16] | pb.memory[PL+17] << 8
    tick_safe(pb, 40)
    assert (pb.memory[PL+16] | pb.memory[PL+17] << 8) == before, 'Cache fired in the main path'
    # A deliberately staged corner approach; room's normal controller and
    # pickup system still execute, but this does not prove every corner reachable.
    put16(pb, PL+9, 16); put16(pb, PL+11, 24)
    before = pb.memory[PL+16] | pb.memory[PL+17] << 8
    pb.memory[PL+4] = max(0, pb.memory[PL+3]-1)
    tick_safe(pb, 40)
    after = pb.memory[PL+16] | pb.memory[PL+17] << 8
    assert after == before + 5, (before, after)
    assert pb.memory[PL+4] == pb.memory[PL+3]
    tick_safe(pb, 160)
    assert (pb.memory[PL+16] | pb.memory[PL+17] << 8) == after, 'Cache farmed twice'
    pb.screen.image.save(str(out/'cache.png'))
    report['cache'] = dict(before=before, after=after, repeat=False)

def easy_wave(pb, tiles):
    assert pb.memory[KIND] == 2
    erase(pb, enemies(pb)[2:])
    tick_safe(pb, 150)
    assert pb.memory[PHASE] == 0 and len(enemies(pb)) == 2, 'Easy gained overlap pressure'
    erase(pb, enemies(pb)); tick_safe(pb, 20)
    assert pb.memory[PHASE] == 1 and len(enemies(pb)) >= 2
    report['easy_wave'] = 'unchanged'

try:
    if not os.environ.get('QUINTRA_NOOK_ONLY'):
        generated_room(0, seed_for(3), local_room=8, probe=wave)
    generated_room(0, seed_for(7), local_room=8, probe=nook)
    generated_room(0, seed_for(3), local_room=8, probe=easy_wave,
                   pre_cross=lambda pb, a: pb.memory.__setitem__(RS+26, 1))
    report['status'] = 'PASS'
    print('[opening-dynamics] PASS warned overlapping wave, clear, optional one-shot corner supplies')
finally:
    (out/'capture.json').write_text(json.dumps(report, indent=2))
