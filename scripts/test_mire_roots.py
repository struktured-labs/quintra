#!/usr/bin/env python3
"""Mire Heart hybrid roots: ghost preview, sub-tile hit, gap, ring gap, shots."""
from test_boss_identity import EN, PL, TM, addr, enter_boss, put16

ACTIVE = addr('_mire_root_active')
WIND = addr('_mire_root_windup')
U = addr('_mire_root_u')
CLOCK = addr('_boss_phase_clock')
ROOT = 55


def pos(pb):
    return (pb.memory[PL + 9] | (pb.memory[PL + 10] << 8),
            pb.memory[PL + 11] | (pb.memory[PL + 12] << 8))


def bg(pb, tx, ty):
    base = 0x9C00 if pb.memory[0xFF40] & 0x08 else 0x9800
    return pb.memory[base + (ty & 31) * 32 + (tx & 31)]


def root_cells(pb):
    found = []
    for ty in range(1, 16):
        for tx in range(1, 28):
            tile = bg(pb, tx, ty)
            if ROOT <= tile <= ROOT + 8:
                found.append((tx, ty, tile))
    return found


def gap_tile(cells):
    roots = {(tx, ty) for tx, ty, _ in cells}
    for ty in range(2, 14):
        for tx in range(2, 18):
            if (tx, ty) in roots:
                continue
            if all(max(abs(tx - rx), abs(ty - ry)) >= 2 for rx, ry in roots):
                return tx, ty
    raise AssertionError('no 16px pocket between roots')


def center_of(boss_xy):
    return ((boss_xy[0] + 16) >> 3, (boss_xy[1] + 16) >> 3)


def place_on_tile(pb, tx, ty):
    # Hurtbox center (x+8, y+12) sits on the vein center of this tile.
    put16(pb, PL + 9, tx * 8 + 4 - 8)
    put16(pb, PL + 11, ty * 8 + 4 - 12)


def quiet_boss(pb, boss):
    pb.memory[boss + 20] = 1
    pb.memory[boss + 5] = 0
    pb.memory[boss + 2] = 1
    if pb.memory[boss + 23]:
        pb.memory[boss + 14] = pb.memory[boss + 23]


def arm(pb, boss):
    quiet_boss(pb, boss)
    pb.memory[PL + 15] = 255
    for _ in range(900):
        pb.tick()
        if pb.memory[ACTIVE] == 0:
            break
    else:
        raise AssertionError('previous cast did not end')
    quiet_boss(pb, boss)
    pb.memory[boss + 6] = 0
    pb.memory[boss + 21] = 0
    pb.memory[PL + 15] = 0
    pb.memory[PL + 22] = 0
    for _ in range(40):
        pb.tick()
        if pb.memory[ACTIVE] and pb.memory[U] <= 2:
            return True
    return False


def main():
    pb, boss = enter_boss(4, keep_open=True)
    try:
        body = [(i % 20, i // 20) for i in range(20 * 17)
                if ROOT <= pb.memory[TM + i] <= ROOT + 8]
        assert not body, f'colossus slots are already on the Mire map: {body[:8]}'
        put16(pb, PL + 9, 96)
        put16(pb, PL + 11, 64)
        assert arm(pb, boss), 'cast fizzled in open floor'
        assert pb.memory[WIND] == 1 and pb.memory[U] == 0
        locked = (pb.memory[boss + 3] | (pb.memory[boss + 4] << 8),
                  pb.memory[boss + 7] | (pb.memory[boss + 8] << 8))
        saw_contract = saw_rest = False
        preview_hp = pb.memory[PL + 2]
        pb.memory[PL + 7] = 5
        while pb.memory[U] < 20:
            pb.tick()
        cells = root_cells(pb)
        assert len(cells) >= 8, cells
        hazard = (cells[0][0], cells[0][1])
        assert cells[0][2] == ROOT, 'preview is not the bud tile'
        assert pb.memory[TM + hazard[1] * 20 + hazard[0]] in (1, 19, 20)
        place_on_tile(pb, *hazard)
        vein_y = pos(pb)[1]
        # Step toward the open side of the arena so the wall does not end the
        # measurement early.
        flee = 'down' if hazard[1] < 8 else 'up'
        pb.button_press(flee)
        while pb.memory[U] < 48:
            pb.tick()
            tile = pb.memory[0xFE00 + 4 * 4 + 2]
            if tile >= 64:
                saw_contract = True
            elif 40 <= tile < 64:
                saw_rest = True
            assert pb.memory[boss + 3] | (pb.memory[boss + 4] << 8) == locked[0]
            assert pb.memory[boss + 7] | (pb.memory[boss + 8] << 8) == locked[1]
            assert pb.memory[PL + 2] == preview_hp, 'ghost path dealt damage'
        pb.button_release(flee)
        escaped_px = abs(pos(pb)[1] - vein_y)
        assert saw_contract and saw_rest, 'lobes did not contract during windup'
        assert escaped_px >= 8, f'only traveled {escaped_px}px before growth'

        while pb.memory[U] < 72:
            pb.tick()
        gap = gap_tile(root_cells(pb))
        place_on_tile(pb, *gap)
        hold_hp = pb.memory[PL + 2]
        while pb.memory[U] < 88:
            pb.tick()
            assert pb.memory[PL + 2] == hold_hp, 'gap tile dealt damage'
        assert pb.memory[TM + gap[1] * 20 + gap[0]] in (1, 19, 20)

        # A second cast: stand on the vein and take the one hit, then no more.
        put16(pb, PL + 9, 96)
        put16(pb, PL + 11, 64)
        assert arm(pb, boss), 'second cast fizzled'
        while pb.memory[U] < 72:
            pb.tick()
        hazard = next((tx, ty) for tx, ty, tile in root_cells(pb) if tile != ROOT)
        before = pb.memory[PL + 2]
        hit = None
        for _ in range(12):
            place_on_tile(pb, *hazard)
            pb.memory[PL + 15] = 0
            pb.tick()
            if pb.memory[PL + 2] < before:
                hit = pb.memory[PL + 2]
                break
        assert hit == before - 2, (before, hit, bg(pb, *hazard), 'vein damage')
        assert pb.memory[PL + 15] == 45
        after = pb.memory[PL + 2]
        while pb.memory[ACTIVE] and pb.memory[U] < 88:
            pb.tick()
            assert pb.memory[PL + 2] == after, 'roots hit twice in one cast'
        assert bg(pb, *hazard) != pb.memory[TM + hazard[1] * 20 + hazard[0]]
        assert pb.memory[TM + hazard[1] * 20 + hazard[0]] in (1, 19, 20), \
            'root wrote the logical tilemap'

        # Shot crosses the overlay because the logical tile is still floor.
        pb.memory[PL + 22] = 0
        pb.button_press('right')
        pb.button_press('a')
        pb.tick(6)
        pb.button_release('a')
        pb.button_release('right')
        shots = [EN + i * 28 for i in range(32)
                 if pb.memory[EN + i * 28] == 1 and pb.memory[EN + i * 28 + 1] & 0x10]
        assert shots, 'no player shot during the rooted cast'

        while pb.memory[ACTIVE]:
            pb.tick()
        assert pb.memory[CLOCK] > 96 or pb.memory[CLOCK] < 2
        # Ring window must not revive the roots.
        while pb.memory[CLOCK] < 112:
            pb.tick()
            assert pb.memory[ACTIVE] == 0, 'roots overlapped the ring windup'
        assert pb.memory[ACTIVE] == 0

        # Corner: a cast next to the wall must not be an unavoidable hit.
        put16(pb, PL + 9, 8)
        put16(pb, PL + 11, 8)
        put16(pb, boss + 3, 32)
        put16(pb, boss + 7, 32)
        pb.memory[PL + 15] = 0
        corner_hp = pb.memory[PL + 2]
        assert arm(pb, boss) or pb.memory[ACTIVE] == 0
        for _ in range(100):
            if pb.memory[ACTIVE] == 0 and pb.memory[CLOCK] > 96:
                break
            pb.tick()
        assert pb.memory[PL + 2] == corner_hp, 'corner cast had no safe pocket'
        print('[mire-roots] PASS preview', escaped_px, 'px off the vein before growth;',
              'damage 2; gap clean; shots pass; ring starts with roots clear;',
              'corner hp held')
    finally:
        pb.stop(save=False)


if __name__ == '__main__':
    main()
