#!/usr/bin/env python3
"""Native-update trajectories, warning windows and bounded projectile ancestry."""
import hashlib
import json
from pathlib import Path
from test_will_max import boot, clear_arena, put16, PLAYER, ENTITIES, TILEMAP, ROM, addr


def capture(pattern, generation, speed=0, edge=False, obstacle=False):
    pb = boot(0)
    try:
        clear_arena(pb)
        if edge or obstacle:
            pb.memory[addr('_room_world_width')] = 160
            pb.memory[addr('_room_world_height')] = 136
        e = ENTITIES
        pb.memory[e] = 1
        pb.memory[e+1] = 0x87
        put16(pb, e+3, 139 if edge else 56 if obstacle else 60)
        put16(pb, e+7, 64 if obstacle else 75)
        if obstacle:
            pb.memory[TILEMAP+9*20+8] = 21
        pb.memory[e+5] = 60
        pb.memory[e+9] = 75
        pb.memory[e+12] = 29
        pb.memory[e+13] = 6
        pb.memory[e+14] = 1
        pb.memory[e+16] = 150
        pb.memory[e+17] = 4
        pb.memory[e+18] = pattern
        pb.memory[e+19] = generation
        pb.memory[e+21] = (0,1,2,1,4,3,1)[pattern]
        pb.memory[e+15] = speed
        pb.memory[e+23] = 0xD0
        pb.memory[e+25] = (0x44,0x77,0xEE,0x77,0xEE,0xE6,0x77)[pattern]
        trace = []
        for frame in range(240):
            pb.memory[PLAYER+15] = 120
            pb.tick()
            shots = []
            for slot in range(32):
                b = ENTITIES + slot*28
                if pb.memory[b] != 1 or not pb.memory[b+1] & 1: continue
                shots.append(dict(slot=slot, x=pb.memory[b+3], y=pb.memory[b+7],
                                  pattern=pb.memory[b+18], generation=pb.memory[b+19],
                                  age=pb.memory[b+20], tile=pb.memory[b+12],
                                  palette=pb.memory[b+13], angle=pb.memory[b+17],
                                  shape=pb.memory[b+21]))
            trace.append(dict(frame=frame, shots=shots))
        return trace
    finally:
        pb.stop(save=False)


def main():
    traces = [capture(0,0), capture(1,0), capture(2,2), capture(3,0),
              capture(4,0), capture(5,0,1), capture(5,0,3), capture(3,2),
              capture(0,0,edge=True),capture(2,0,edge=True),
              capture(0,0,obstacle=True),capture(2,0,obstacle=True),capture(5,2,1)]
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = Path('tmp/boss-projectile-traces-' + hashlib.sha256(ROM.read_bytes()).hexdigest()[:8] + '-' + script_sha[:8] + '.json')
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(dict(rom_sha256=hashlib.sha256(ROM.read_bytes()).hexdigest(),
                                  script_sha256=script_sha,
                                  fixture='fresh boot; isolated projectile; native update', traces=traces),indent=2))
    for trace in traces[:2]:
        points = [(s['x'],s['y']) for f in trace for s in f['shots'] if s['slot']==0]
        assert len(set(points)) > 20
        a = points[0]
        assert max(abs(p[0]+p[1]-a[0]-a[1]) for p in points)>6, 'no curvature beyond pixel rounding'
    tree = traces[2]
    warning = [s for f in tree for s in f['shots'] if s['generation']==2 and 40<=s['age']<56]
    assert len(warning)>=12 and len({(s['x'],s['y']) for s in warning})==1, 'split has no stationary warning'
    assert len({s['tile'] for s in warning})==2, 'split warning never flashes'
    assert any(s['generation']==1 and s['pattern']==1 for f in tree for s in f['shots']), 'missing wave children'
    assert any(s['generation']==0 and s['pattern']==0 for f in tree for s in f['shots']), 'missing arc grandchildren'
    assert max(len(f['shots']) for f in tree)<=4, 'ancestry escaped two generations'
    spiral = [s for f in traces[3] for s in f['shots'] if s['slot']==0]
    assert min(s['x'] for s in spiral)<45 and max(s['x'] for s in spiral)>63, 'spiral never circles origin horizontally'
    assert min(s['y'] for s in spiral)<54 and max(s['y'] for s in spiral)>85, 'spiral never circles origin vertically'
    crescent = [s for f in traces[4] for s in f['shots'] if s['slot']==0]
    distances = [abs(s['x']-60)+abs(s['y']-75) for s in crescent]
    assert max(distances)>40 and distances[-1]<5, ('crescent does not return', distances[-1])
    turn = [s for s in crescent if 32<=s['age']<40]
    assert len(turn)>=8 and len({(s['x'],s['y']) for s in turn})==1, 'no return warning'
    travel=[]
    for trace in traces[5:7]:
        point=next(s for f in trace for s in f['shots'] if s['age']==24)
        travel.append(abs(point['x']-60)+abs(point['y']-75))
    assert travel[1]>2.5*travel[0], ('speed bands collapsed',travel)
    recursive = traces[7]
    assert any(s['pattern']==4 and s['generation']==1 for f in recursive for s in f['shots']), 'spiral did not produce crescents'
    assert any(s['pattern']==5 and s['generation']==0 for f in recursive for s in f['shots']), 'crescents did not produce bolts'
    assert max(len(f['shots']) for f in recursive)<=4, 'alternate ancestry escaped budget'
    assert traces[8][3]['shots'], 'small shot was incorrectly rejected at edge'
    assert not any(f['shots'] for f in traces[9][3:]), 'large shot clips the arena boundary'
    assert traces[10][3]['shots'], 'small shot was rejected by a non-overlapping pillar'
    assert not any(f['shots'] for f in traces[11][3:]), 'large shot clips a pillar corner'
    fork = traces[12]
    for generation,pattern in ((2,5),(1,0),(0,1)):
        assert any(s['generation']==generation and s['pattern']==pattern
                   for f in fork for s in f['shots']), ('missing fork generation',generation,pattern)
        if generation:
            warning = [s for f in fork for s in f['shots']
                       if s['generation']==generation and 40<=s['age']<56]
            assert len({s['palette'] for s in warning}) == 2, ('invisible fork warning',generation)
    children = {s['angle'] for f in fork for s in f['shots'] if s['generation']==1 and s['age']==1}
    assert children == {12,28}, ('first fork not perpendicular',children)
    assert {s['palette'] for f in fork for s in f['shots']
            if s['generation']==1 and s['age']<40} == {3}, 'fork sparks lost their violet identity'
    for f in fork:
        assert len(f['shots']) <= 4
        assert sum((1,1,4,2,4)[s['shape']] for s in f['shots']) <= 12
    print('[boss-projectiles] PASS nonlinear motion, speed bands and three warned, bounded recursive families')


if __name__ == '__main__':
    main()
