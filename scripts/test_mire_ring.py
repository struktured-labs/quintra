#!/usr/bin/env python3
"""Isolated native ring damage and a held-direction escape through its warning."""
import hashlib
import json
from pathlib import Path
from test_boss_identity import ROM, PL, EN, addr, enter_boss, put16


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    script = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = Path('builds')/f'mire-ring-{sha[:8]}-{script[:8]}'
    out.mkdir(parents=True, exist_ok=True)
    report = dict(rom_sha256=sha, script_sha256=script, records=[],
        fixture='Fresh boss entry; half HP and clock 63; unrelated attacks suppressed; '
                'fixed initial positions. Escape thereafter uses held right, not position writes.')
    cases = [('center',0,0,False), ('inner',12,0,False), ('band',24,0,True),
             ('diagonal_band',14,14,True), ('outside',48,0,False),
             ('diagonal_outside',24,24,False), ('escape',0,0,False),
             ('crowded',24,0,False)]
    try:
        for name,dx,dy,damaged in cases:
            pb,boss = enter_boss(4, keep_open=True)
            record = dict(case=name, trace=[])
            report['records'].append(record)
            try:
                for slot in range(32):
                    e = EN+slot*28
                    if e != boss:
                        pb.memory[e] = pb.memory[e+1] = 0
                        if name == 'crowded':
                            pb.memory[e] = 4
                            pb.memory[e+1] = 7
                            pb.memory[e+12] = 29
                            pb.memory[e+16] = 200
                put16(pb,PL+9,64)
                put16(pb,PL+11,72)
                put16(pb,boss+3,160)
                put16(pb,boss+7,24)
                pb.memory[boss+14] = pb.memory[boss+23]//2
                pb.memory[boss+2] = 2
                pb.memory[boss+5] = 0
                pb.memory[boss+6] = 63
                pb.memory[PL+2] = pb.memory[PL+1]
                pb.memory[PL+15] = pb.memory[PL+20] = 0
                hp = pb.memory[PL+2]
                moved = False
                captured = False
                before_resolution = hp
                for frame in range(120):
                    pb.memory[boss+18] = 250
                    pb.memory[boss+20] = 1
                    pb.tick()
                    clock = pb.memory[addr('_boss_phase_clock')]
                    marks = [(pb.memory[EN+i*28+3],pb.memory[EN+i*28+7]) for i in range(32)
                             if pb.memory[EN+i*28] == 4 and pb.memory[EN+i*28+1]&1
                             and pb.memory[EN+i*28+12] == 127]
                    record['trace'].append([frame,clock,pb.memory[PL+2],pb.memory[PL+9],pb.memory[PL+11],marks])
                    if clock < 96:
                        before_resolution = pb.memory[PL+2]
                    if 66 <= clock < 96 and len(set(marks)) == 8 and not captured:
                        assert set(marks) == {(68+x,80+y) for x,y in
                            ((0,-24),(17,-17),(24,0),(17,17),(0,24),(-17,17),(-24,0),(-17,-17))}
                        pb.screen.image.save(str(out/f'{name}-warning.png'))
                        captured = True
                    if clock >= 66 and not moved:
                        if name == 'escape':
                            pb.button_press('right')
                        else:
                            put16(pb,PL+9,64+dx)
                            put16(pb,PL+11,72+dy)
                        moved = True
                    if clock >= 108:
                        break
                else:
                    raise AssertionError('ring cycle stalled')
                record['hp_before'] = hp
                record['hp_after'] = pb.memory[PL+2]
                record['escaped_distance'] = pb.memory[PL+9]-64
                pb.screen.image.save(str(out/f'{name}-after.png'))
                assert captured == (name != 'crowded'), ('wrong ring warning availability',name)
                assert before_resolution == hp, ('warning caused damage',name)
                assert (pb.memory[PL+2] < hp) == damaged, ('wrong ring damage',name,hp,pb.memory[PL+2])
                if name == 'escape':
                    assert record['escaped_distance'] >= 40, record
                print('[mire-ring]',name,'PASS',flush=True)
            finally:
                pb.stop(save=False)
    finally:
        (out/'capture.json').write_text(json.dumps(report))


if __name__ == '__main__':
    main()
