#!/usr/bin/env python3
"""Fresh-boot phase transitions; HP thresholds are explicit fixture inputs."""
import hashlib
import json
import os
import re
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology, put16)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / 'rom/working/quintra.gbc'


def check_link(pb, a, boss, record):
    en, pl = a['_entities'], a['_player']
    for _ in range(600):
        pb.memory[pl+2] = pb.memory[pl+1]
        pb.tick()
        if pb.memory[a['_boss_link_active']]:
            break
    else:
        raise AssertionError('Reaper never entered linked mode')
    results = []
    record['link_collisions'] = results
    for mode in ('fresh', 'airborne', 'shared'):
        pb.memory[boss+5] = 40
        for slot in range(32):
            e = en + slot*28
            if e != boss:
                for byte in range(28):
                    pb.memory[e+byte] = 0
        pb.tick(4)
        pb.memory[boss+5] = 40  # Hold actual linked mode for isolated collision.
        pb.memory[boss+1] = 7
        pb.memory[boss+14] = 40
        put16(pb, boss+3, 80)
        put16(pb, boss+7, 60)
        put16(pb, pl+9, 32)
        put16(pb, pl+11, 96)
        pb.memory[pl+2] = pb.memory[pl+1]
        pb.memory[pl+15] = 0
        hp = pb.memory[pl+2]
        shot = next(en+i*28 for i in range(32) if en+i*28 != boss
                    and not pb.memory[en+i*28+1]&1)
        for byte in range(28): pb.memory[shot+byte] = 0
        pb.memory[shot] = 1
        pb.memory[shot+1] = 0x87 if mode == 'shared' else 0x17
        put16(pb, shot+3, 36 if mode == 'shared' else 80)
        put16(pb, shot+7, 104 if mode == 'shared' else 60)
        pb.memory[shot+14] = 1
        pb.memory[shot+16] = 40
        pb.memory[shot+21] = 0x40 if mode == 'airborne' else 0
        pb.memory[shot+25] = 0x77
        pb.memory[shot+26] = 2
        if mode == 'shared':
            pb.memory[shot+18] = 2
            pb.memory[shot+23] = 0xD0
        if os.environ.get('QUINTRA_MUTATE_LINK'):
            pb.memory[a['_boss_link_active']] = 0
        collision = dict(mode=mode,before=[hp,40],trace=[])
        results.append(collision)
        for frame in range(3):
            pb.tick()
            collision['trace'].append([frame,pb.memory[pl+2],pb.memory[boss+14],
                pb.memory[boss+3],pb.memory[boss+7],pb.memory[boss+5],
                pb.memory[a['_boss_link_active']],list(pb.memory[shot:shot+28])])
        after = (pb.memory[pl+2], pb.memory[boss+14])
        collision['after'] = after
        if mode == 'fresh':
            assert after[0] < hp and after[1] == 40, results
        elif mode == 'airborne':
            assert after[0] == hp and after[1] < 40, results
        else:
            assert after[0] < hp and after[1] < 40, results
    return results


def main():
    select_rom_topology(ROM)
    a = symbol_addresses(ROM)
    a['_boss_link_active'] = int(re.search(r'DEF _boss_link_active 0x([0-9A-Fa-f]+)',
                                         ROM.with_suffix('.noi').read_text())[1], 16)
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    records = []
    try:
        for stage in range(9):
            pb, _, _ = boot_to_stage(ROM, a, stage, 'normal', 0)
            try:
                advance_to_sanctuary(pb, a, stage)
                advance_to_boss(pb, a, stage)
                en, pl = a['_entities'], a['_player']
                candidates = [en+i*28 for i in range(32)
                              if pb.memory[en+i*28] == 2
                              and pb.memory[en+i*28+1] & 1
                              and pb.memory[en+i*28+20] & 1]
                assert len(candidates) == 1, (stage, candidates)
                boss = candidates[0]
                maximum = pb.memory[boss+23] or pb.memory[boss+14]
                record = dict(stage=stage, maximum=maximum, trace=[])
                records.append(record)
                for phase in range(3):
                    pb.memory[boss+14] = max(1, maximum >> phase)
                    observed = set()
                    frozen = 0
                    for frame in range(360):
                        pb.memory[pl+2] = pb.memory[pl+1]
                        pb.tick()
                        row = [phase, frame, pb.memory[boss+2], pb.memory[boss+5],
                               pb.memory[boss+6], pb.memory[boss+3], pb.memory[boss+7],
                               pb.memory[a['_boss_link_active']], pb.memory[boss+14]]
                        record['trace'].append(row)
                        observed.add(row[2])
                        frozen += bool(row[3])
                        assert pb.memory[a['_loop_current_screen']] == 5, (stage, phase, frame)
                    assert phase+1 in observed, (stage, phase, observed)
                    assert pb.memory[boss+2] == phase+1, (stage, phase, 'phase regressed')
                    if phase:
                        assert frozen >= 30, (stage, phase, 'missing transition warning', frozen)
                    picture = ROOT / 'tmp' / f'boss-phase-{sha[:8]}-{stage}-{phase}.png'
                    picture.parent.mkdir(exist_ok=True)
                    pb.screen.image.save(str(picture))
                if stage == 5:
                    assert {row[7] for row in record['trace']} == {0, 1}, 'link never alternated'
                    check_link(pb, a, boss, record)
                print(f'[boss-phases] {stage+1}/9 thresholds and transition windows PASS', flush=True)
            finally:
                pb.stop(save=False)
    finally:
        suffix = '-no-link' if os.environ.get('QUINTRA_MUTATE_LINK') else ''
        script = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        out = ROOT / 'tmp' / f'boss-phases-{sha}-{script[:8]}{suffix}.json'
        out.parent.mkdir(exist_ok=True)
        out.write_text(json.dumps(dict(rom_sha256=sha,
                                      script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                      mutation=suffix, records=records)))


if __name__ == '__main__':
    main()
