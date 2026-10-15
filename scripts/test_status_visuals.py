#!/usr/bin/env python3
"""Distinct native status glyphs, bounded effects and clean expiry."""
import hashlib
import json
from pathlib import Path
from test_will_max import ROM, PLAYER as P, ENTITIES as E, boot, clear_arena, addr

sha=hashlib.sha256(ROM.read_bytes()).hexdigest()
out=Path('builds')/f'status-visuals-{sha[:8]}'
out.mkdir(parents=True,exist_ok=True)
records=[]
pb=boot(0)
try:
    clear_arena(pb)
    glyphs=[bytes(pb.memory[1,0x8E00+i*16:0x8E10+i*16]) for i in range(13)]
    assert all(any(g) for g in glyphs) and len(set(glyphs))==13,'status atlas absent/duplicated'
    for kind in range(1,14):
        clear_arena(pb)
        pb.memory[P+2]=40
        pb.memory[addr('_player_status_kind')]=kind
        pb.memory[addr('_player_status_ticks')]=12
        visible=False; peak=0
        for frame in range(140):
            pb.tick()
            fx=[E+i*28 for i in range(32) if pb.memory[E+i*28]==4
                and pb.memory[E+i*28+1]&1 and pb.memory[E+i*28+13]&8]
            peak=max(peak,len(fx))
            oam=[0xFE00+i*4 for i in range(40)]
            shown=any(pb.memory[o] and pb.memory[o+2]==223+kind and pb.memory[o+3]&8 for o in oam)
            if shown and not visible:
                pb.tick(2)
                pb.screen.image.save(str(out/f'{kind:02}.png')); visible=True
        assert visible and peak<=3,(kind,visible,peak)
        assert pb.memory[addr('_player_status_kind')]==0,(kind,'did not expire')
        records.append(dict(kind=kind,visible=visible,peak=peak))
    print('[status-visuals] PASS 13 distinct rendered statuses, bounded FX, expiry')
finally:
    pb.stop(save=False)
    (out/'capture.json').write_text(json.dumps(dict(rom_sha256=sha,records=records),indent=2))
