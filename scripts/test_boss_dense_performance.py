#!/usr/bin/env python3
"""Native update cadence during late-phase bosses with summoned escorts."""
import hashlib
import json
import time
from pathlib import Path
from test_boss_identity import ROM, PL, EN, addr, enter_boss, put16


def main():
    sha=hashlib.sha256(ROM.read_bytes()).hexdigest()
    script=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out=Path('builds')/f'boss-dense-performance-{sha[:8]}-{script[:8]}'
    out.mkdir(parents=True,exist_ok=True)
    report=dict(rom_sha256=sha,script_sha256=script,records=[],
        fixture='Fresh entry, fixed player position and half/quarter boss HP. Player health replenished, no attacks. Native summons and projectiles are not injected or suppressed.',
        guard='At least 600 entity updates per 1200 LCD frames, including transition and stall frames. Engineering floor, not hardware qualification.')
    try:
        for stage in (3,4,8):
            for phase in (1,2):
                pb,boss=enter_boss(stage,keep_open=True)
                record=dict(stage=stage,phase=phase,trace=[])
                report['records'].append(record)
                started=time.monotonic()
                try:
                    put16(pb,PL+9,72); put16(pb,PL+11,104)
                    pb.memory[boss+14]=pb.memory[boss+23]>>phase
                    clock=addr('_entity_anim_counter')
                    previous=pb.memory[clock]
                    updates=streak=longest_stall=dense_frames=dense_updates=0
                    max_shots=0
                    picture=False
                    for frame in range(1200):
                        pb.memory[PL+2]=pb.memory[PL+1]
                        pb.tick()
                        current=pb.memory[clock]
                        advanced=(current-previous)&255
                        previous=current
                        updates+=advanced
                        streak=0 if advanced else streak+1
                        longest_stall=max(longest_stall,streak)
                        escorts=shots=effects=sprites=0
                        for slot in range(32):
                            e=EN+slot*28
                            if not pb.memory[e+1]&1: continue
                            kind=pb.memory[e]
                            if kind==2 and e!=boss: escorts+=1
                            if kind==1 and not pb.memory[e+1]&16:
                                shots+=1
                                sprites+=(1,1,4,2,4)[pb.memory[e+21]] if pb.memory[e+1]&128 else 1
                            if kind==4: effects+=1
                        max_shots=max(max_shots,shots)
                        if escorts==2:
                            dense_frames+=1
                            dense_updates+=advanced
                            if shots>=6 and not picture:
                                pb.screen.image.save(str(out/f'{stage}-{phase}-dense.png'))
                                picture=True
                        record['trace'].append([frame,advanced,escorts,shots,effects,
                            pb.memory[addr('_boss_phase_clock')],pb.memory[boss+3],pb.memory[boss+7],sprites])
                        assert sprites<=12, ('summons bypassed hostile sprite budget',stage,phase,frame,shots,sprites)
                        assert pb.memory[addr('_loop_current_screen')]==5
                    record.update(updates=updates,dense_frames=dense_frames,dense_updates=dense_updates,
                        longest_stall=longest_stall,max_shots=max_shots,elapsed_s=time.monotonic()-started)
                    assert dense_frames>=300, 'fixture never sustained two escorts'
                    assert max_shots>=6 and picture, 'fixture did not exercise a busy projectile scene'
                    assert updates>=600, ('boss below half display cadence',stage,phase,updates)
                    record['passed']=True
                    print(f'[boss-dense] stage={stage} phase={phase} updates={updates}/1200 two-escort={dense_updates}/{dense_frames} peak-shots={max_shots} longest-stall={longest_stall}',flush=True)
                finally: pb.stop(save=False)
        report['passed']=True
    finally: (out/'capture.json').write_text(json.dumps(report))


if __name__=='__main__': main()
