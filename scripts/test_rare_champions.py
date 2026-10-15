#!/usr/bin/env python3
"""Rare promotion and native recursive/status attacks with fixed headroom."""
import hashlib
import json
from pathlib import Path
from test_will_max import ROM, PLAYER as P, ENTITIES as E, boot, clear_arena, put16, addr

sha=hashlib.sha256(ROM.read_bytes()).hexdigest()
out=Path('builds')/f'rare-champions-{sha[:8]}'
out.mkdir(parents=True,exist_ok=True)
pb=boot(0)
trace=[]
try:
    clear_arena(pb)
    pb.memory[addr('_run_state')+26]=0
    pb.memory[addr('_entity_enemy_count')]=1
    put16(pb,P+9,120); put16(pb,P+11,96)
    for off,val in {0:2,1:0x87,5:120,12:32,13:4,14:100,17:0,25:0x66,26:6}.items():
        pb.memory[E+off]=val
    put16(pb,E+3,64); put16(pb,E+7,72)
    generations=set(); palettes=set(); peak=0; warning=False
    for frame in range(360):
        pb.memory[P+15]=120; pb.memory[P+2]=40
        pb.tick()
        clock=pb.memory[E+5]
        warning |= 128<=clock<160
        palettes.add(pb.memory[E+13])
        shots=[E+i*28 for i in range(32) if pb.memory[E+i*28]==1 and pb.memory[E+i*28+1]&1]
        peak=max(peak,len(shots))
        for e in shots:
            if pb.memory[e+1]&128:
                generations.add(pb.memory[e+19])
                assert pb.memory[e+22]==0x81,'champion children lost poison payload'
        if frame in (20,80,120): pb.screen.image.save(str(out/f'{frame}.png'))
        trace.append([frame,clock,len(shots)])
    assert warning and {4,6}<=palettes
    assert {0,1,2}<=generations,generations
    assert peak<=12,peak
    print('[rare-champions] PASS warned recursive burst, inherited poison, rare tint, 12-shot ceiling')
finally:
    pb.stop(save=False)
    (out/'capture.json').write_text(json.dumps(dict(rom_sha256=sha,trace=trace),indent=2))

from test_stage_archetypes import generated_room, RS
promotions=[]
def probe(pb,_):
    enemies=[E+i*28 for i in range(32) if pb.memory[E+i*28]==2 and pb.memory[E+i*28+1]&1]
    rare=[e for e in enemies if pb.memory[e+1]&128]
    assert len(rare)<=1
    for e in rare:
        assert not pb.memory[e+1]&0x60,'rare replaced the alpha/elite'
        assert pb.memory[e+14]>=28 and pb.memory[e+26]>=6
        promotions.append(dict(room=pb.memory[RS+1],hp=pb.memory[e+14],damage=pb.memory[e+26]))

for local in (6,7):
    for seed in range(256):
        roll=(seed ^ ((local*2654435761)&0xFFFFFFFF))
        roll ^= roll>>16
        if roll&63: continue
        generated_room(0,seed=seed,local_room=local,probe=probe)
        if promotions: break
    if promotions: break
assert promotions,'no rare champion generated in eligible seeded rooms'
(out/'promotion.json').write_text(json.dumps(promotions,indent=2))
print('[rare-champions] PASS natural seeded promotion separate from pack alpha')
