#!/usr/bin/env python3
"""Native summon tells, resolved placement and encounter-specific cast identities."""
import hashlib
import json
from pathlib import Path
from test_boss_identity import ROM, PL, EN, TM, addr, enter_boss, put16


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    script = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = Path('builds') / f'boss-summons-{sha[:8]}-{script[:8]}'
    out.mkdir(parents=True, exist_ok=True)
    report = dict(rom_sha256=sha, script_sha256=script, records=[])
    try:
        for stage, mode in [(3,'normal'), (4,'normal'), (8,'normal'),
                            (3,'late'), (4,'late'), (8,'late'),
                            (3,'occupied'), (4,'blocked')]:
            pb, boss = enter_boss(stage, keep_open=True)
            record = dict(stage=stage, mode=mode, trace=[], warnings={}, born=[])
            report['records'].append(record)
            try:
                put16(pb, PL+9, 72)
                put16(pb, PL+11, 104)
                pb.memory[boss+14] = pb.memory[boss+23]//(4 if mode == 'late' else 2)
                clock = addr('_boss_phase_clock')
                tick = addr('_entity_anim_counter')
                previous, elapsed = pb.memory[tick], 0
                seen, target = set(), None
                for frame in range(1200):
                    pb.memory[PL+2] = pb.memory[PL+1]
                    if target and mode == 'occupied':
                        put16(pb, PL+9, target[0])
                        put16(pb, PL+11, target[1])
                    pb.tick()
                    now = pb.memory[tick]
                    elapsed += (now-previous)&255
                    previous = now
                    current = pb.memory[clock]
                    markers, enemies = [], []
                    for slot in range(32):
                        e = EN+slot*28
                        if not pb.memory[e+1]&1 or e == boss:
                            continue
                        x, y = pb.memory[e+3], pb.memory[e+7]
                        if pb.memory[e] == 4 and pb.memory[e+12] == 127 and 160 <= current < 192:
                            markers.append([x,y])
                            record['warnings'].setdefault(f'{x},{y}', elapsed)
                            if target is None and x < 144:
                                target = [x,y]
                                if mode == 'blocked':
                                    pb.memory[TM+(y//8)*20+x//8+1] = 2
                        if pb.memory[e] == 2:
                            enemies.append([slot,x,y,pb.memory[e+17],pb.memory[e+21]])
                            if slot not in seen and current >= 193:
                                seen.add(slot)
                                record['born'].append([elapsed,x,y,pb.memory[e+17],pb.memory[e+21]])
                    record['trace'].append([frame,elapsed,current,markers,enemies])
                    assert len(enemies) <= 2, ('escort cap exceeded',stage,frame,enemies)
                    if current in (163,196):
                        pb.screen.image.save(str(out/f'{stage}-{mode}-{current}.png'))
                    if current >= 200 and elapsed >= 480:
                        break
                else:
                    raise AssertionError('summon cycle did not complete')
                assert record['warnings'], ('no advance warning', stage, mode)
                if mode in ('normal','late'):
                    assert 1 <= len(record['born']) <= 2, record['born']
                else:
                    assert target is not None, 'placement fixture missed a western warning'
                for elapsed,x,y,kind,pattern in record['born']:
                    candidates = [(tuple(map(int, point.split(','))), when)
                                  for point,when in record['warnings'].items()]
                    matches = [(p,t) for p,t in candidates if abs(p[0]-x)<=2 and abs(p[1]-y)<=2]
                    assert matches and elapsed-matches[0][1] >= 30, ('unwarned spawn', record['born'])
                    if mode not in ('normal','late'):
                        assert abs(target[0]-x)>2 or abs(target[1]-y)>2, ('unsafe spawn',mode,target)
                    assert kind == (2 if stage == 3 else 0)
                    if stage != 3:
                        assert pattern == (2 if stage == 4 else 3), ('wrong escort cast', stage,pattern)
                print('[boss-summons]',stage,mode,'PASS',flush=True)
            finally:
                pb.stop(save=False)
    finally:
        (out/'capture.json').write_text(json.dumps(report))


if __name__ == '__main__':
    main()
