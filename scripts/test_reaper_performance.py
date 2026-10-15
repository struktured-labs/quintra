#!/usr/bin/env python3
"""Compare complete LCD timelines before/after Reaper's three-pose renderer."""
import hashlib
import json
import re
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology)

ROOT = Path(__file__).resolve().parent.parent


def run(rom):
    select_rom_topology(rom)
    a = symbol_addresses(rom)
    counter = int(re.search(r'DEF _entity_anim_counter 0x([0-9A-Fa-f]+)',
                           rom.with_suffix('.noi').read_text())[1], 16)
    pb, _, _ = boot_to_stage(rom, a, 5, 'normal', 0)
    trace = []
    try:
        advance_to_sanctuary(pb, a, 5)
        advance_to_boss(pb, a, 5)
        en, pl = a['_entities'], a['_player']
        boss = next(en+i*28 for i in range(32) if pb.memory[en+i*28] == 2
                    and pb.memory[en+i*28+1]&1 and pb.memory[en+i*28+20]&1)
        pb.memory[boss+14] = pb.memory[boss+23]//2
        previous, updates = pb.memory[counter], 0
        for frame in range(1200):
            pb.memory[pl+2] = pb.memory[pl+1]
            pb.tick()
            current = pb.memory[counter]
            updates += (current-previous)&255
            previous = current
            trace.append([frame, current, pb.memory[boss+6], pb.memory[boss+3],
                          pb.memory[boss+7], pb.memory[boss+13]])
        return dict(rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),
                    frames=1200, updates=updates, trace=trace)
    finally:
        pb.stop(save=False)


def main():
    parent = run(ROOT/'builds/reaper-pose-parent-0e54e32f/quintra.gbc')
    candidate = run(ROOT/'rom/working/quintra.gbc')
    out = ROOT/'builds'/f'reaper-performance-{candidate["rom_sha256"][:8]}.json'
    out.write_text(json.dumps(dict(parent=parent, candidate=candidate,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        fixture='fresh boss entry, half-health Reaper, stationary replenished-health player')))
    ratio = candidate['updates']/parent['updates']
    print(f'[reaper-performance] {parent["updates"]} -> {candidate["updates"]}/1200, ratio={ratio:.3f}')
    assert ratio >= .95, 'pose rendering costs more than 5% of game updates'


if __name__ == '__main__':
    main()
