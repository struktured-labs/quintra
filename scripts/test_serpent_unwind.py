#!/usr/bin/env python3
"""Fresh encounter: retain earned body length across real attack cycles."""
import hashlib
import json
import os
import re
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology, put16)

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get('QUINTRA_TEST_ROM', ROOT / 'rom/working/quintra.gbc'))


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    a = symbol_addresses(ROM)
    noi = ROM.with_suffix('.noi').read_text()
    for name in ('_serpent_tail_visible', '_serpent_tail_x', '_serpent_tail_y'):
        a[name] = int(re.search(rf'DEF {name} 0x([0-9A-Fa-f]+)', noi)[1], 16)
    select_rom_topology(ROM)
    pb, _, _ = boot_to_stage(ROM, a, 1, 'normal', 0)
    trace = []
    out = ROOT / 'builds' / f'serpent-unwind-{sha[:8]}'
    out.mkdir(parents=True, exist_ok=True)
    try:
        advance_to_sanctuary(pb, a, 1)
        advance_to_boss(pb, a, 1)
        en, pl = a['_entities'], a['_player']
        boss = next(en+i*28 for i in range(32) if pb.memory[en+i*28] == 2
                    and pb.memory[en+i*28+1]&1 and pb.memory[en+i*28+20]&1)
        put16(pb, pl+9, 196)
        put16(pb, pl+11, 104)
        longest = 0
        cycles = 0
        previous_state = 0
        unwinding_positions = set()
        for frame in range(4200):
            pb.memory[pl+2] = pb.memory[pl+1]
            pb.tick()
            length = pb.memory[a['_serpent_tail_visible']]
            state = pb.memory[boss+15]
            x, y = pb.memory[boss+3], pb.memory[boss+7]
            trace.append([frame, state, length, x, y, pb.memory[boss+21], pb.memory[boss+11]])
            assert length >= longest, (frame, 'earned tail shrank', longest, length)
            longest = max(longest, length)
            if previous_state == 2 and state == 1:
                cycles += 1
                pb.screen.image.save(str(out / f'cycle-{cycles}.png'))
            if state == 2:
                unwinding_positions.add((x, y))
            previous_state = state
            assert pb.memory[a['_loop_current_screen']] == 5
            if cycles >= 2:
                break
        assert longest == 48, ('never grew full body', longest)
        assert cycles >= 2, ('did not complete two unwind cycles', cycles)
        assert len(unwinding_positions) >= 250, ('stationary recovery', len(unwinding_positions))
        print(f'[serpent-unwind] PASS length={longest}, cycles={cycles}, '
              f'unwind_positions={len(unwinding_positions)}, frames={len(trace)}')
    finally:
        pb.stop(save=False)
        (out / 'capture.json').write_text(json.dumps(dict(rom_sha256=sha,
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            fixture='Fresh boss entry; stationary player with HP replenished; no boss state injection.',
            trace=trace)))


if __name__ == '__main__':
    main()
