#!/usr/bin/env python3
"""A warned Shadow collapse kills Normal; optional hook/nature rescues."""
import hashlib
import json
from pathlib import Path
from test_stage_archetypes import ROM, RS, generated_room
from test_stage_events import PL, PHASE, clear_entities, put16, world_tile

sha=hashlib.sha256(ROM.read_bytes()).hexdigest()
out=Path('builds')/f'lethal-floor-{sha[:8]}'
out.mkdir(parents=True,exist_ok=True)
records=[]

def check(gear=0,hero=0,easy=0):
    def probe(pb,_):
        clear_entities(pb)
        pb.memory[RS+26]=easy
        pb.memory[PL]=hero
        pb.memory[PL+44]=gear
        pb.memory[PL+2]=20
        put16(pb,PL+9,24); put16(pb,PL+11,44)
        warnings=0; damaged=False; fallen=False
        for frame in range(600):
            if not easy:
                pb.memory[PL+15]=120
                pb.memory[PL+20]=120
            pb.tick()
            warnings+=pb.memory[PHASE] in (1,2)
            fallen |= world_tile(pb,4,7)==0
            damaged |= pb.memory[PL+2]<20
            if fallen and (damaged or gear or hero==2):
                pb.tick(6)
                break
        hp=pb.memory[PL+2]
        record=dict(gear=gear,hero=hero,easy=easy,warning_frames=warnings,hp=hp,fallen=fallen)
        records.append(record)
        assert warnings>=60 and fallen,record
        if gear or hero==2:
            assert hp==20,record
            assert world_tile(pb,(pb.memory[PL+9]+8)//8,(pb.memory[PL+11]+12)//8)!=0,record
        elif easy: assert hp==19,record
        else: assert hp==0,record
        pb.screen.image.save(str(out/f'{gear}-{hero}-{easy}.png'))
    generated_room(5,local_room=5,probe=probe)

try:
    check(); check(gear=4); check(hero=2); check(easy=1)
    print('[lethal-floor] PASS warning, lethal despite combat invulnerability, hook/Corvin rescue, Easy damage')
finally:
    (out/'capture.json').write_text(json.dumps(dict(rom_sha256=sha,records=records),indent=2))
