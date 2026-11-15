#!/usr/bin/env python3
"""Hold Aim keeps the last 8-way heading after the D-pad is released."""
import hashlib
import json
from pathlib import Path
from test_will_max import (
    ROM, PLAYER as PL, addr, boot, clear_arena, player_shots, press,
)

sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
out = Path('builds') / f'persistent-aim-{sha[:8]}'
out.mkdir(parents=True, exist_ok=True)
AIM = addr('_player_aim_dir')
MODE = addr('_player_penta_aim')
SCREEN = addr('_loop_current_screen')

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

DIAGONALS = (
    (('up', 'right'), 1, 1, -1),
    (('down', 'right'), 3, 1, 1),
    (('down', 'left'), 5, -1, 1),
    (('up', 'left'), 7, -1, -1),
)

# Boomerang, hookshot, morningstar, bombs.
SECONDARIES = (45, 46, 47, 48)
AUX_MARK = {45: 0xF4, 46: 0xF5, 47: 0xF6, 48: 0xF7}


def signed(value):
    return value - 256 if value > 127 else value


def pos(pb):
    return (pb.memory[PL + 9] | (pb.memory[PL + 10] << 8),
            pb.memory[PL + 11] | (pb.memory[PL + 12] << 8))


def release_all(pb):
    for key in ('a', 'b', 'up', 'down', 'left', 'right', 'start', 'select'):
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


def shot_velocity(pb, button='a'):
    for entity in player_shots(pb):
        pb.memory[entity] = pb.memory[entity + 1] = 0
    pb.memory[PL + 22] = 0
    pb.button_press(button)
    for _ in range(24):
        pb.tick()
        shots = player_shots(pb)
        if shots:
            entity = shots[0]
            vx, vy = signed(pb.memory[entity + 10]), signed(pb.memory[entity + 11])
            pb.button_release(button)
            return entity, vx, vy
    pb.button_release(button)
    raise AssertionError('no stationary projectile for %s' % button)


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


def stagger_release(pb, keys, first, settle=3):
    """Release one diagonal key one frame before the other."""
    other = keys[0] if first == keys[1] else keys[1]
    hold(pb, keys)
    assert first in keys and other in keys
    pb.button_release(first)
    pb.tick(1)
    pb.button_release(other)
    pb.tick(settle)


def tap(pb, key):
    # Same cadence as test_aim_toggle: short presses miss the Aim page.
    pb.button_press(key)
    pb.tick(8)
    pb.button_release(key)
    pb.tick(12)


def toggle_aim_twice(pb):
    """Flip Classic then back to Hold Aim through the real Aim page."""
    release_all(pb)
    pb.tick(8)
    start_mode = pb.memory[MODE]
    tap(pb, 'start')
    assert pb.memory[SCREEN] == 9
    tap(pb, 'select')
    tap(pb, 'a')
    assert pb.memory[MODE] == (0 if start_mode else 1)
    tap(pb, 'a')
    assert pb.memory[MODE] == start_mode
    tap(pb, 'b')
    assert pb.memory[SCREEN] == 5
    assert pb.memory[MODE] == start_mode


def existing_simultaneous_cases(pb, records):
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
        _, vx, vy = shot_velocity(pb)
        velocity = (vx, vy)
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
            _, vx2, vy2 = shot_velocity(pb)
            again = (vx2, vy2)
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
            _, svx, svy = shot_velocity(pb)
            south = (svx, svy)
            assert matches(south, 0, 1), ('replaced aim', south)
        records.append(dict(keys=list(keys), direction=direction, velocity=list(velocity)))


def staggered_diagonal_cases(pb, records, label='corvin'):
    for keys, direction, sx, sy in DIAGONALS:
        for first in keys:
            reset(pb)
            stagger_release(pb, keys, first)
            assert pb.memory[MODE] == 1, (label, keys, first, 'mode')
            assert pb.memory[AIM] == direction, (
                label, keys, first, 'stagger collapsed aim', pb.memory[AIM])
            _, vx, vy = shot_velocity(pb)
            velocity = (vx, vy)
            assert matches(velocity, sx, sy), (
                label, keys, first, 'staggered shot', velocity)
            assert pb.memory[AIM] == direction
            records.append(dict(
                case='stagger', label=label, keys=list(keys),
                first=first, direction=direction, velocity=list(velocity)))


def grace_and_override(pb, records):
    # A collapsed component cardinal must not overwrite during the window.
    reset(pb)
    hold(pb, ('up', 'right'))
    pb.button_release('up')
    pb.tick(4)
    assert pb.memory[AIM] == 1, ('grace mid-window', pb.memory[AIM])
    # Holding that same cardinal past the window replaces the diagonal.
    pb.tick(4)
    assert pb.memory[AIM] == 2, ('grace expired', pb.memory[AIM])
    pb.button_release('right')
    pb.tick(4)
    _, vx, vy = shot_velocity(pb)
    assert matches((vx, vy), 1, 0), ('post-grace east', (vx, vy))
    records.append(dict(case='grace-expire', aim=pb.memory[AIM], velocity=[vx, vy]))

    # A cardinal that is not a component of the stored diagonal replaces it
    # immediately, even inside the grace window.
    reset(pb)
    hold(pb, ('up', 'right'))
    pb.button_release('up')
    pb.button_release('right')
    pb.button_press('left')
    pb.tick(1)
    assert pb.memory[AIM] == 6, ('deliberate left', pb.memory[AIM])
    pb.button_release('left')
    pb.tick(3)
    _, vx, vy = shot_velocity(pb)
    assert matches((vx, vy), -1, 0), ('deliberate left shot', (vx, vy))
    records.append(dict(case='deliberate-cardinal', aim=pb.memory[AIM], velocity=[vx, vy]))


def secondaries_after_stagger(pb, records):
    for item in SECONDARIES:
        reset(pb)
        pb.memory[PL + 24] = item
        pb.memory[PL + 18] = item
        pb.memory[PL + 4] = max(pb.memory[PL + 4], 5)
        pb.memory[PL + 19] = 0
        stagger_release(pb, ('up', 'right'), 'up')
        assert pb.memory[AIM] == 1, (item, 'aim before B', pb.memory[AIM])
        entity, vx, vy = shot_velocity(pb, button='b')
        marker = pb.memory[entity + 23]
        assert marker == AUX_MARK[item], (item, marker)
        if item == 48:
            # Bombs only receive throw velocity while the pad is held, but
            # the shared heading still has to be northeast.
            assert pb.memory[entity + 17] == 2, (item, 'bomb dir', pb.memory[entity + 17])
        elif item == 47:
            # Morningstar starts its orbit from dir*2; NE is 2.
            assert pb.memory[entity + 17] in (2, 3), (item, 'star angle', pb.memory[entity + 17])
        else:
            assert matches((vx, vy), 1, -1), (item, 'secondary shot', (vx, vy))
        records.append(dict(
            case='secondary', item=item, velocity=[vx, vy],
            aux=marker, aim=pb.memory[AIM]))
        release_all(pb)


def will_max_after_stagger(pb, records):
    reset(pb)
    pb.memory[PL + 42] = 90
    pb.memory[PL + 48] = 1
    stagger_release(pb, ('up', 'right'), 'right')
    assert pb.memory[AIM] == 1
    pb.memory[PL + 22] = 0
    pb.button_press('a')
    for _ in range(40):
        pb.tick()
        if pb.memory[PL + 48] == 0:
            break
    pb.button_release('a')
    pb.tick(4)
    shots = player_shots(pb)
    assert shots, 'Will MAX produced no shots'
    assert pb.memory[AIM] == 1, ('will max aim', pb.memory[AIM])
    # At least one lane must travel northeast, proving the shared heading.
    velocities = [(signed(pb.memory[s + 10]), signed(pb.memory[s + 11])) for s in shots]
    assert any(matches(v, 1, -1) for v in velocities), ('will max lanes', velocities)
    records.append(dict(case='will-max', velocities=[list(v) for v in velocities]))


def all_class_staggers(records):
    for class_id in range(5):
        pb = boot(class_id)
        try:
            assert pb.memory[MODE] == 1, class_id
            staggered_diagonal_cases(pb, records, label='class-%d' % class_id)
        finally:
            pb.stop(save=False)


def main():
    records = []
    pb = boot(2)
    try:
        existing_simultaneous_cases(pb, records)
        staggered_diagonal_cases(pb, records)
        grace_and_override(pb, records)
        toggle_aim_twice(pb)
        # Toggling twice must not drop Hold Aim or forget a fresh diagonal.
        reset(pb)
        stagger_release(pb, ('up', 'right'), 'up')
        assert pb.memory[MODE] == 1
        assert pb.memory[AIM] == 1, ('toggle-twice aim', pb.memory[AIM])
        _, vx, vy = shot_velocity(pb)
        assert matches((vx, vy), 1, -1), ('toggle-twice shot', (vx, vy))
        records.append(dict(case='toggle-twice', velocity=[vx, vy]))
        image = getattr(pb.screen, 'image', None)
        if image is not None:
            image.save(str(out / 'stagger-ur-release-up-first.png'))
        secondaries_after_stagger(pb, records)
        will_max_after_stagger(pb, records)
        print('[persistent-aim] PASS 8 directions, stagger release, grace, toggle, secondaries, Will')
    finally:
        pb.stop(save=False)

    all_class_staggers(records)
    print('[persistent-aim] PASS five-class staggered diagonals')
    (out / 'capture.json').write_text(json.dumps(
        dict(rom_sha256=sha, records=records), indent=2))


if __name__ == '__main__':
    main()
