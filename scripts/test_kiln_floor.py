#!/usr/bin/env python3
"""Check actual far-chamber VRAM, not just the compact logical tilemap."""
import hashlib
import json
from pathlib import Path
from test_boss_identity import ROM, PL, addr, enter_boss

sha=hashlib.sha256(ROM.read_bytes()).hexdigest()
out=Path('builds')/f'kiln-floor-{sha[:8]}'
out.mkdir(parents=True,exist_ok=True)
pb,boss=enter_boss(2,keep_open=True)
trace=[]
try:
    for frame in range(1200):
        pb.memory[PL+2]=pb.memory[PL+1]
        pb.tick()
        bank=pb.memory[0xFF4F]
        pb.memory[0xFF4F]=0
        cells=[pb.memory[0x9800+y*32+x] for y in range(1,16) for x in range(20,27)]
        pb.memory[0xFF4F]=bank
        bad=sum(55<=v<=63 for v in cells)
        trace.append([frame,bad])
        if frame==0:pb.screen.image.save(str(out/'entry.png'))
        assert bad==0, f'legacy furnace mural remains in far-chamber VRAM: {bad} cells'
    pb.button_press('start')
    for _ in range(120):
        pb.tick()
        if pb.memory[addr('_loop_current_screen')]==9:break
    pb.button_release('start');pb.tick(4);pb.button_press('b')
    for _ in range(120):
        pb.tick()
        if pb.memory[addr('_loop_current_screen')]==5:break
    pb.button_release('b');pb.tick(30)
    pb.memory[0xFF4F]=0
    assert not any(55<=pb.memory[0x9800+y*32+x]<=63 for y in range(1,16) for x in range(20,27))
    print('[kiln-floor] PASS far chamber clear through 1200 frames and menu resume')
finally:
    pb.stop(save=False)
    (out/'capture.json').write_text(json.dumps(dict(rom_sha256=sha,trace=trace,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())))
