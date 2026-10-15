#!/usr/bin/env python3
"""Native Reaper sweep sharing and automatic pre-link projectile grace."""
import hashlib
import json
import os
import re
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology, put16)

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get('QUINTRA_TEST_ROM', ROOT / 'rom/working/quintra.gbc'))


def enter():
    select_rom_topology(ROM)
    a = symbol_addresses(ROM)
    noi = ROM.with_suffix('.noi').read_text()
    for name in ('_boss_link_active', '_boss_phase_clock', '_music_track_id',
                 '_room_tilemap'):
        a[name] = int(re.search(rf'DEF {name} 0x([0-9A-Fa-f]+)', noi)[1], 16)
    pb, _, _ = boot_to_stage(ROM, a, 5, 'normal', 0)
    advance_to_sanctuary(pb, a, 5)
    advance_to_boss(pb, a, 5)
    en = a['_entities']
    boss = next(en+i*28 for i in range(32) if pb.memory[en+i*28] == 2
                and pb.memory[en+i*28+1]&1 and pb.memory[en+i*28+20]&1)
    pb.memory[boss+14] = pb.memory[boss+23]//2
    return pb, a, boss


def clear(pb, en, boss):
    for i in range(32):
        e = en+i*28
        if e != boss:
            for j in range(28):
                pb.memory[e+j] = 0


def sweep(record, mode):
    pb, a, boss = enter()
    try:
        pl, en = a['_player'], a['_entities']
        put16(pb, pl+9, 32)
        put16(pb, pl+11, 96)
        for _ in range(200):
            pb.memory[pl+2] = pb.memory[pl+1]
            pb.tick()
            if pb.memory[boss+20]&0x40:
                break
        else:
            raise AssertionError('sweep never armed')
        # Align the already-armed sweep with the middle of a linked window.
        pb.memory[boss+6] = 0 if mode == 'exposed' else 160
        victories = pb.memory[a['_run_state']+11]
        if mode == 'lethal':
            pb.memory[boss+14] = 1
            pb.memory[boss+2] = 3
        pb.memory[pl+15] = pb.memory[pl+20] = 0
        hp, boss_hp = pb.memory[pl+2], pb.memory[boss+14]
        trace = record['sweep_'+mode] = []
        for frame in range(120):
            if pb.memory[boss+20]&0x40:
                clear(pb, en, boss)
            if mode == 'shielded':
                pb.memory[pl+20] = 255
            if mode == 'iframes':
                pb.memory[pl+15] = 255
            pb.tick()
            trace.append([frame, pb.memory[boss+18],
                pb.memory[a['_boss_link_active']], pb.memory[pl+2], pb.memory[boss+14]])
            if mode == 'lethal':
                if pb.memory[a['_run_state']+11] == victories+1:
                    break
                continue
            if not pb.memory[boss+20]&0x40 and pb.memory[boss+18] >= 30:
                break
        else:
            raise AssertionError('sweep did not fire')
        taken = hp-pb.memory[pl+2]
        if mode == 'lethal':
            pb.tick(60)
            assert pb.memory[a['_run_state']+11] == victories+1
            assert list(pb.memory[a['_room_tilemap']+9:a['_room_tilemap']+11]) == [3,3]
            assert pb.memory[a['_music_track_id']] == 19
            kinds = [pb.memory[en+i*28+17] for i in range(32)
                     if pb.memory[en+i*28] == 3 and pb.memory[en+i*28+1]&1]
            assert kinds.count(0) >= 2 and kinds.count(2) >= 2 and 3 in kinds, kinds
            record['sweep_lethal_rewards'] = kinds
            return
        if mode in ('shielded', 'iframes'):
            assert taken == 0 and pb.memory[boss+14] == boss_hp, trace[-1]
            return
        assert taken > 0, trace[-1]
        if mode == 'exposed':
            assert not pb.memory[a['_boss_link_active']] and pb.memory[boss+14] == boss_hp
            return
        assert pb.memory[a['_boss_link_active']], trace[-1]
        assert boss_hp-pb.memory[boss+14] == taken, ('sweep bypassed damage link', taken,
                                                    boss_hp, pb.memory[boss+14])
    finally:
        pb.stop(save=False)


def airborne(record):
    pb, a, boss = enter()
    try:
        pl, en = a['_player'], a['_entities']
        for _ in range(400):
            pb.memory[pl+2] = pb.memory[pl+1]
            pb.tick()
            if 120 <= pb.memory[a['_boss_phase_clock']] < 128:
                break
        else:
            raise AssertionError('warning window not reached')
        clear(pb, en, boss)
        shot = en if en != boss else en+28
        pb.memory[shot] = 1
        pb.memory[shot+1] = 0x17
        put16(pb, shot+3, 32)
        put16(pb, shot+7, 104)
        pb.memory[shot+14] = 1
        pb.memory[shot+16] = 100
        pb.memory[shot+25] = 0x77
        pb.memory[shot+26] = 2
        record['airborne'] = []
        for frame in range(40):
            pb.memory[pl+2] = pb.memory[pl+1]
            pb.tick()
            record['airborne'].append([frame, pb.memory[a['_boss_phase_clock']],
                pb.memory[a['_boss_link_active']], pb.memory[shot+21]])
            if pb.memory[a['_boss_link_active']]:
                break
        assert pb.memory[shot] == 1 and pb.memory[shot+21]&0x40, record['airborne']
        pb.memory[boss+5] = 40
        put16(pb, pl+9, 32)
        put16(pb, pl+11, 96)
        put16(pb, shot+3, pb.memory[boss+3])
        put16(pb, shot+7, pb.memory[boss+7])
        pb.memory[pl+15] = 0
        hp, boss_hp = pb.memory[pl+2], pb.memory[boss+14]
        pb.tick(3)
        assert pb.memory[pl+2] == hp and pb.memory[boss+14] < boss_hp
        record['grace_collision'] = [hp, boss_hp, pb.memory[pl+2], pb.memory[boss+14]]
    finally:
        pb.stop(save=False)


def lethal(record, mutual=False, grace=False):
    pb, a, boss = enter()
    try:
        pl, en, rs = a['_player'], a['_entities'], a['_run_state']
        for _ in range(400):
            pb.memory[pl+2] = pb.memory[pl+1]
            pb.tick()
            if pb.memory[a['_boss_link_active']]:
                break
        else:
            raise AssertionError('linked window not reached')
        clear(pb, en, boss)
        pb.memory[boss+14] = 1
        pb.memory[boss+2] = 3  # Already in the final HP phase; isolate its fatal hit.
        pb.memory[boss+5] = 240
        put16(pb, boss+3, 128)
        put16(pb, boss+7, 24)
        put16(pb, pl+9, 32)
        put16(pb, pl+11, 96)
        pb.memory[pl+2] = 1 if mutual else 10
        pb.memory[pl+15] = pb.memory[pl+20] = 0
        shot = en if en != boss else en+28
        for i in range(32):
            e = en+i*28
            if e == boss:
                continue
            pb.memory[e] = 1
            pb.memory[e+1] = 0x87
            put16(pb, e+3, 36 if e == shot else 64)
            put16(pb, e+7, 104 if e == shot else 48)
            pb.memory[e+14] = 1
            pb.memory[e+16] = 150
            pb.memory[e+18] = 2
            pb.memory[e+23] = 0xD0
            pb.memory[e+25] = 0x77
            pb.memory[e+26] = 2
        if grace:
            pb.memory[shot+1] = 0x17
            pb.memory[shot+21] = 0x40
            put16(pb, shot+3, 128)
            put16(pb, shot+7, 24)
        victories = pb.memory[rs+11]
        assert list(pb.memory[a['_room_tilemap']+9:a['_room_tilemap']+11]) != [3,3], \
            'north arena exit was already open before fatal hit'
        trace = record['mutual' if mutual else 'grace_lethal' if grace else 'lethal'] = []
        for frame in range(100):
            pb.tick()
            trace.append([frame, pb.memory[pl+2], pb.memory[boss],
                          pb.memory[boss+14], pb.memory[rs+11],
                          pb.memory[rs+12], pb.memory[a['_music_track_id']]])
            if mutual and pb.memory[a['_loop_current_screen']] != 5:
                break
        if mutual:
            assert pb.memory[pl+2] == 0 and pb.memory[rs+11] == victories, trace[-1]
            return
        assert pb.memory[rs+11] == victories+1, ('linked hit failed to defeat boss', trace[-1])
        assert not pb.memory[a['_boss_link_active']]
        assert pb.memory[a['_music_track_id']] == 19, 'missing victory music'
        pb.memory[0xFF4F] = 0
        assert list(pb.memory[0x9C0A:0x9C10]) != [91,89,8,84,79,88], \
            'victory retained the NO ATK warning'
        assert list(pb.memory[a['_room_tilemap']+9:a['_room_tilemap']+11]) == [3,3], \
            'linked victory left north arena exit closed'
        kinds = [pb.memory[en+i*28+17] for i in range(32)
                 if pb.memory[en+i*28] == 3 and pb.memory[en+i*28+1]&1]
        assert kinds.count(0) >= 2 and kinds.count(2) >= 2 and 3 in kinds, kinds
        assert not any(pb.memory[en+i*28] == 1 and pb.memory[en+i*28+1]&1
                       and not pb.memory[en+i*28+1]&0x10 for i in range(32))
        record['lethal_rewards'] = kinds
        pb.screen.image.save(str(ROOT / 'tmp' /
            ('reaper-linked-victory-'+record['rom_sha256'][:8]+'.png')))
    finally:
        pb.stop(save=False)


if __name__ == '__main__':
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    record = dict(rom_sha256=sha, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    try:
        airborne(record)
        for mode in ('linked', 'exposed', 'shielded', 'iframes', 'lethal'):
            sweep(record, mode)
        lethal(record)
        lethal(record, mutual=True)
        lethal(record, grace=True)
        record['passed'] = True
        print('[reaper-link] PASS airborne grace, sweep sharing, lethal rewards/unseal and mutual-death priority')
    finally:
        (ROOT / 'tmp' / f'reaper-link-{sha}.json').write_text(json.dumps(record))
