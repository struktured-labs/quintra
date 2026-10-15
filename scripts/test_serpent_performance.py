#!/usr/bin/env python3
"""Compare full-growth encounters, including all displayed-frame stalls."""
import hashlib
import json
import re
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology, put16)

ROOT = Path(__file__).resolve().parent.parent


def run(rom, length):
    a = symbol_addresses(rom)
    noi = rom.with_suffix('.noi').read_text()
    for name in ('_serpent_tail_visible', '_serpent_tail_x', '_serpent_tail_y',
                 '_entity_anim_counter', '_serpent_body_dirty'):
        match = re.search(rf'DEF {name} 0x([0-9A-Fa-f]+)', noi)
        if match:
            a[name] = int(match[1], 16)
    select_rom_topology(rom)
    pb, _, _ = boot_to_stage(rom, a, 1, 'normal', 0)
    trace = []
    try:
        advance_to_sanctuary(pb, a, 1)
        advance_to_boss(pb, a, 1)
        en, pl = a['_entities'], a['_player']
        boss = next(en+i*28 for i in range(32) if pb.memory[en+i*28] == 2
                    and pb.memory[en+i*28+1]&1 and pb.memory[en+i*28+20]&1)
        for slot in range(32):
            e = en+slot*28
            if e != boss:
                pb.memory[e] = pb.memory[e+1] = 0
        put16(pb, pl+9, 72)
        put16(pb, pl+11, 112)
        put16(pb, boss+3, 168)
        put16(pb, boss+7, 16)
        pb.memory[boss+15] = 2
        pb.memory[boss+11] = 0
        pb.memory[boss+18] = 0
        pb.memory[boss+21] = 4
        pb.memory[a['_serpent_tail_visible']] = length
        for i in range(length+1):
            pb.memory[a['_serpent_tail_x']+i] = max(16, 180-i*8)
            pb.memory[a['_serpent_tail_y']+i] = 28
        if '_serpent_body_dirty' in a:
            pb.memory[a['_serpent_body_dirty']] = 1
        previous = pb.memory[a['_entity_anim_counter']]
        updates = 0
        for frame in range(1200):
            pb.memory[pl+2] = pb.memory[pl+1]
            pb.tick()
            current = pb.memory[a['_entity_anim_counter']]
            updates += (current-previous) & 255
            previous = current
            trace.append([frame, current, pb.memory[boss+15], pb.memory[boss+3], pb.memory[boss+7]])
        return dict(rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),
                    length=length, updates=updates, frames=1200, trace=trace)
    finally:
        pb.stop(save=False)


def main():
    parent = run(ROOT / 'builds/serpent-sprite-parent-89a32fb9/quintra.gbc', 20)
    candidate = run(ROOT / 'rom/working/quintra.gbc', 48)
    out = ROOT / 'tmp' / f'serpent-performance-{candidate["rom_sha256"]}.json'
    out.write_text(json.dumps(dict(parent=parent, candidate=candidate)))
    ratio = candidate['updates']/parent['updates']
    print(f'[serpent-performance] parent={parent["updates"]}/1200, '
          f'candidate={candidate["updates"]}/1200, ratio={ratio:.3f}')
    assert ratio >= .95, 'larger tail costs more than the 5% regression budget'


if __name__ == '__main__':
    main()
