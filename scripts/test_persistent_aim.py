#!/usr/bin/env python3
"""Hold Aim keeps the last 8-way heading after the D-pad is released."""
import hashlib
import json
from pathlib import Path
from test_will_max import ROM, PLAYER as PL, addr, boot, clear_arena, player_shots

sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
out = Path('builds') / f'persistent-aim-{sha[:8]}'
out.mkdir(parents=True, exist_ok=True)
AIM = addr('_player_aim_dir')
MODE = addr('_player_penta_aim')

# dir8: 0 N, 1 NE, 2 E, 3 SE, 4 S, 5 SW, 6 W, 7 NW.
CASES = (
    (('up',), 0, 0, -1),
    (('up', 'right'), 1, 1, -1),
    (('right',), 2, 1, 0),
    (('down', 'right'), 3, 1, 1),
    (('down',), 4, 0, 1),
    (('down', 'left'), 5, -1, 1),
    (('left',), 6, -1, 0),
    (('up', 'left'), 7, -1, -1),
)


def signed(value):
    return value - 256 if value > 127 else value


def pos(pb):
    return (pb.memory[PL + 9] | (pb.memory[PL + 10] << 8),
            pb.memory[PL + 11] | (pb.memory[PL + 12] << 8))


def release_all(pb):
    for key in ('a', 'b', 'up', 'down', 'left', 'right'):
        pb.button_release(key)


def reset(pb):
    release_all(pb)
    pb.tick(16)
    clear_arena(pb)
    pb.memory[PL + 22] = 0
    pb.memory[PL + 42] = pb.memory[PL + 48] = 0


def hold(pb, keys, frames=10):
    for key in keys:
        pb.button_press(key)
    pb.tick(frames)


def shot_velocity(pb):
    for entity in player_shots(pb):
        pb.memory[entity] = pb.memory[entity + 1] = 0
    pb.memory[PL + 22] = 0
    pb.button_press('a')
    for _ in range(24):
        pb.tick()
        shots = player_shots(pb)
        if shots:
            entity = shots[0]
            return signed(pb.memory[entity + 10]), signed(pb.memory[entity + 11])
    raise AssertionError('no stationary projectile')


def matches(velocity, sx, sy):
    vx, vy = velocity
    if sx == 0:
        ok_x = vx == 0
    else:
        ok_x = vx * sx > 0
    if sy == 0:
        ok_y = vy == 0
    else:
        ok_y = vy * sy > 0
    return ok_x and ok_y


def main():
    pb = boot(2)
    records = []
    try:
        assert pb.memory[MODE] == 1, 'Hold Aim is the default'
        assert pb.memory[AIM] == 4, 'a new champion aims south'
        for keys, direction, sx, sy in CASES:
            reset(pb)
            before = pos(pb)
            hold(pb, keys)
            moving = pos(pb)
            assert pb.memory[AIM] == direction, (keys, pb.memory[AIM])
            assert moving != before, (keys, 'did not move')
            if sx:
                assert (moving[0] - before[0]) * sx > 0, (keys, moving, before)
            if sy:
                assert (moving[1] - before[1]) * sy > 0, (keys, moving, before)
            for key in keys:
                pb.button_release(key)
            # One frame can still carry the released pad. After that the
            # hero must stand still; aim is what remains.
            pb.tick(4)
            stopped = pos(pb)
            pb.tick(8)
            assert pos(pb) == stopped, (keys, 'release did not stop', pos(pb), stopped)
            assert pb.memory[AIM] == direction, (keys, 'release cleared aim')
            velocity = shot_velocity(pb)
            assert matches(velocity, sx, sy), (keys, velocity)
            assert pb.memory[AIM] == direction
            assert pos(pb) == stopped, (keys, 'stationary attack moved')
            if keys == ('up', 'right'):
                image = getattr(pb.screen, 'image', None)
                if image is not None:
                    image.save(str(out / 'hold-ur-release-fire.png'))
                # Still northeast with no new direction.
                release_all(pb)
                pb.tick(8)
                assert pos(pb) == stopped, 'idle drift after northeast'
                again = shot_velocity(pb)
                assert matches(again, 1, -1), ('second northeast', again)
                assert pb.memory[AIM] == 1
                # A new direction replaces the retained aim.
                release_all(pb)
                pb.tick(16)
                clear_arena(pb)
                hold(pb, ('down',))
                pb.button_release('down')
                pb.tick(8)
                assert pb.memory[AIM] == 4
                south = shot_velocity(pb)
                assert matches(south, 0, 1), ('replaced aim', south)
            records.append(dict(keys=list(keys), direction=direction, velocity=list(velocity)))
        print('[persistent-aim] PASS 8 directions, hold-UR release fire, replacement')
    finally:
        pb.stop(save=False)
        (out / 'capture.json').write_text(json.dumps(
            dict(rom_sha256=sha, records=records), indent=2))


if __name__ == '__main__':
    main()
