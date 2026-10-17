"""Native held-A workload with a fixed six-crawler arena and replenished HP."""
import hashlib
import json
from pathlib import Path
from test_will_max import boot, clear_arena, put16, addr, ROM, PLAYER as P, ENTITIES as E

pb=boot(0)
try:
    clear_arena(pb)
    pb.memory[addr('_room_world_width')]=160
    pb.memory[addr('_room_world_height')]=136
    pb.memory[addr('_entity_enemy_count')]=6
    put16(pb,P+9,72); put16(pb,P+11,96)
    for slot,(x,y) in enumerate(((24,24),(72,24),(120,24),(24,64),(72,64),(120,64))):
        e=E+slot*28
        for offset in range(28): pb.memory[e+offset]=0
        pb.memory[e]=2; pb.memory[e+1]=7
        put16(pb,e+3,x); put16(pb,e+7,y)
        pb.memory[e+12]=20; pb.memory[e+14]=200
        pb.memory[e+25]=0x77; pb.memory[e+26]=1
    clock=addr('_entity_anim_counter')
    previous=pb.memory[clock]
    updates=0
    trace=[]
    pb.button_press('a')
    for frame in range(720):
        pb.memory[P+2]=pb.memory[P+1]
        for slot in range(6): pb.memory[E+slot*28+14]=200
        pb.tick()
        current=pb.memory[clock]
        advanced=(current-previous)&255
        updates+=advanced; previous=current
        shots=sum(pb.memory[E+i*28]==1 and pb.memory[E+i*28+1]&1
                  for i in range(32))
        trace.append([frame,advanced,shots])
    assert max(t[2] for t in trace)>=4, 'firing fixture never became crowded'
    sha=hashlib.sha256(ROM.read_bytes()).hexdigest()
    script_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out=Path('builds')/f'firing-performance-{sha[:8]}-{script_sha[:8]}'
    out.mkdir(parents=True,exist_ok=True)
    pb.screen.image.save(str(out/'held-a.png'))
    (out/'capture.json').write_text(json.dumps(dict(rom_sha256=sha,
        script_sha256=script_sha,updates=updates,frames=720,trace=trace)))
    print(f'[firing-performance] {sha[:8]} updates={updates}/720')
finally:
    pb.stop(save=False)
