#!/usr/bin/env python3
"""Controller-driven heading spike in a staged empty floor fixture."""
import hashlib
import json
import os
from pathlib import Path
from test_will_max import ROM, PLAYER as PL, boot, clear_arena, player_shots

sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
out = Path('builds') / f'penta-aim-{sha[:8]}'
out.mkdir(parents=True, exist_ok=True)
report = dict(rom_sha256=sha, records=[], fixture='Blank enemy table and flat floor; real directional/A inputs',
              script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
observe_parent = bool(os.environ.get('QUINTRA_AIM_OBSERVE_PARENT'))
directions = dict(up=(2,0,-1), right=(1,1,0), down=(0,0,1), left=(3,-1,0))

def signed(x):
    return x-256 if x>127 else x

def reset(pb):
    for key in ('a','b','up','down','left','right'):
        pb.button_release(key)
    pb.tick(3)
    clear_arena(pb)
    pb.memory[PL+42] = pb.memory[PL+48] = 0
    pb.memory[PL+15] = 0

def fresh_shot(pb):
    for e in player_shots(pb):
        pb.memory[e] = pb.memory[e+1] = 0
    pb.memory[PL+22] = 0
    for _ in range(20):
        pb.tick()
        shots = player_shots(pb)
        if shots:
            e = shots[0]
            return signed(pb.memory[e+10]), signed(pb.memory[e+11])
    raise AssertionError('No A projectile')

try:
    for hero in range(5):
        pb = boot(hero)
        try:
            for first, second in [('right','up'),('right','down'),('left','up'),('left','down'),
                                  ('up','left'),('up','right'),('down','left'),('down','right')]:
                reset(pb)
                facing, dx, dy = directions[first]
                pb.button_press(first); pb.tick(4)
                assert pb.memory[PL+13] == facing
                pb.button_press('a'); pb.tick(2)
                pb.button_press(second); pb.tick(2)
                velocity = fresh_shot(pb)
                actual_facing = pb.memory[PL+13]
                if not observe_parent:
                    assert actual_facing == facing, (hero,first,second,'diagonal overwrote heading')
                position = [pb.memory[PL+9] | pb.memory[PL+10]<<8,
                            pb.memory[PL+11] | pb.memory[PL+12]<<8]
                _, sx, sy = directions[second]
                assert velocity[0]*(dx+sx)>0 and velocity[1]*(dy+sy)>0, velocity
                if hero == 2 and first == 'right' and second == 'up':
                    pb.screen.image.save(str(out/'diagonal.png'))
                pb.button_release(first); pb.button_release(second); pb.tick(2)
                neutral = fresh_shot(pb)
                if not observe_parent:
                    assert (neutral[0]*dx>0 if dx else neutral[0]==0), neutral
                    assert (neutral[1]*dy>0 if dy else neutral[1]==0), neutral
                if hero == 2 and first == 'right' and second == 'up':
                    pb.screen.image.save(str(out/'neutral.png'))
                # A single held axis intentionally changes the heading.
                pb.button_press(second); pb.tick(4)
                assert pb.memory[PL+13] == directions[second][0]
                report['records'].append(dict(hero=hero, first=first, diagonal=second,
                                               velocity=velocity, neutral=neutral,
                                               facing=actual_facing, position=position))
            # B and A+B retain the old vertical-priority movement heading.
            for buttons in [('b',), ('a','b'), ()]:
                reset(pb)
                pb.button_press('right'); pb.tick(4)
                for button in buttons: pb.button_press(button)
                pb.button_press('up'); pb.tick(8)
                assert pb.memory[PL+13] == 2, (hero, buttons, 'changed non-A heading')
        finally:
            pb.stop(save=False)
    report['status'] = 'PARENT OBSERVATION' if observe_parent else 'PASS'
    print('[penta-aim]', report['status'], '40 cases, cardinal turns, B/chord/plain movement controls')
finally:
    (out/'capture.json').write_text(json.dumps(report, indent=2))
