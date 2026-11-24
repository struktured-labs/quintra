#!/usr/bin/env python3
"""Compare full-growth encounters, including all displayed-frame stalls."""
import hashlib
import os
import json
import re
import time
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
    started = time.monotonic()
    candidate_rom = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
    parent_path = Path(os.environ["QUINTRA_PERF_PARENT"]) if os.environ.get("QUINTRA_PERF_PARENT") else (
        ROOT / "builds/serpent-sprite-parent-89a32fb9/quintra.gbc")
    parent_rom = parent_path if parent_path.is_file() else None
    # The historical parent fixture used a 20-segment tail; the live ROM
    # times the current 48-segment growth. Skip the ratio fence when the
    # parent build is absent (#224).
    candidate = run(candidate_rom, 48)
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = ROOT / "builds" / f'serpent-performance-{candidate["rom_sha256"][:8]}-{script_sha[:8]}'
    out.mkdir(parents=True, exist_ok=True)
    payload = dict(candidate=candidate, script_sha256=script_sha,
                   elapsed_s=time.monotonic() - started)
    if parent_rom is not None:
        parent = run(parent_rom, 20)
        payload["parent"] = parent
        ratio = candidate["updates"] / parent["updates"]
        payload.update(ratio=ratio, minimum_ratio=0.95, passed=ratio >= 0.95)
        print(f'[serpent-performance] parent={parent["updates"]}/1200, '
              f'candidate={candidate["updates"]}/1200, ratio={ratio:.3f}')
        (out / "capture.json").write_text(json.dumps(payload))
        assert ratio >= 0.95, "larger tail costs more than the 5% regression budget"
    else:
        payload["passed"] = True
        (out / "capture.json").write_text(json.dumps(payload))
        print(f'[serpent-performance] candidate={candidate["updates"]}/1200 on {candidate_rom}')


if __name__ == '__main__':
    main()
