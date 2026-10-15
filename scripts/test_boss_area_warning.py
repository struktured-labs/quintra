#!/usr/bin/env python3
"""Shared boss blasts must have a complete warning or fizzle under crowding."""
import hashlib
import json
from pathlib import Path
from test_boss_identity import ROM, PL, EN, addr, enter_boss, put16


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    script = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = Path('builds')/f'boss-area-warning-{sha[:8]}-{script[:8]}'
    out.mkdir(parents=True,exist_ok=True)
    report = dict(rom_sha256=sha,script_sha256=script,records=[],
        fixture='Fresh entry; half HP, clock 63, fixed positions. Unrelated volleys/signatures suppressed. Escape uses held Right. Crowded case fills other slots with long-lived FX.')
    try:
        for stage in (0,2,3,6,7,8):
            for mode in ('hold','escape','crowded','late-crowded'):
                pb,boss=enter_boss(stage,keep_open=True)
                record=dict(stage=stage,mode=mode,trace=[])
                report['records'].append(record)
                try:
                    pb.memory[boss+5]=240
                    pb.tick(4)
                    for i in range(32):
                        e=EN+i*28
                        if e==boss: continue
                        for j in range(28): pb.memory[e+j]=0
                        if mode=='crowded':
                            pb.memory[e]=4
                            pb.memory[e+1]=7
                            pb.memory[e+12]=29
                            pb.memory[e+16]=200
                    put16(pb,PL+9,64); put16(pb,PL+11,72)
                    put16(pb,boss+3,160); put16(pb,boss+7,24)
                    pb.memory[boss+14]=pb.memory[boss+23]//2
                    pb.memory[boss+2]=2
                    pb.memory[boss+5]=0
                    pb.memory[boss+6]=63
                    pb.memory[PL+2]=pb.memory[PL+1]
                    pb.memory[PL+15]=pb.memory[PL+20]=0
                    hp=pb.memory[PL+2]
                    moved=False
                    warned=False
                    crowded=False
                    pre_damage=hp
                    for frame in range(140):
                        pb.memory[boss+18]=250
                        pb.memory[boss+20]=1
                        pb.tick()
                        clock=pb.memory[addr('_boss_phase_clock')]
                        marks=[(pb.memory[EN+i*28+3],pb.memory[EN+i*28+7]) for i in range(32)
                            if pb.memory[EN+i*28]==4 and pb.memory[EN+i*28+1]&1
                            and pb.memory[EN+i*28+12]==127]
                        record['trace'].append([frame,clock,pb.memory[PL+2],pb.memory[PL+9],pb.memory[PL+11],marks])
                        if clock<96: pre_damage=pb.memory[PL+2]
                        if 66<=clock<96 and len(set(marks))==4:
                            assert set(marks)=={(52,80),(84,80),(68,64),(68,96)}
                            if not warned: pb.screen.image.save(str(out/f'{stage}-{mode}-warning.png'))
                            warned=True
                        if clock>=66 and mode=='escape' and not moved:
                            pb.button_press('right'); moved=True
                        if clock>=74 and mode=='late-crowded' and not crowded:
                            for i in range(32):
                                e=EN+i*28
                                if pb.memory[e+1]&1: continue
                                for j in range(28): pb.memory[e+j]=0
                                pb.memory[e]=4
                                pb.memory[e+1]=7
                                pb.memory[e+12]=29
                                pb.memory[e+16]=200
                            crowded=True
                            record['crowding_frame']=frame
                        if clock>=100: break
                    else: raise AssertionError('area clock stalled')
                    pb.screen.image.save(str(out/f'{stage}-{mode}-resolved.png'))
                    assert pre_damage==hp, 'damage before warning completed'
                    if mode!='crowded': assert warned, 'missing four-marker warning'
                    assert pb.memory[PL+2]==(hp-2 if mode=='hold' else hp), (stage,mode,'unexpected area damage',hp,pb.memory[PL+2])
                    if mode=='escape': assert pb.memory[PL+9]>=96, 'held-input escape did not move clear'
                    record['passed']=True
                    print(f'[boss-area-warning] stage={stage} {mode} PASS',flush=True)
                finally: pb.stop(save=False)
        report['passed']=True
    finally: (out/'capture.json').write_text(json.dumps(report))


if __name__=='__main__': main()
