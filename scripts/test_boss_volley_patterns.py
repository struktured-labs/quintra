#!/usr/bin/env python3
"""Observe authored volley identities in real boss updates across HP phases."""
import hashlib
import json
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / 'rom/working/quintra.gbc'
PATTERNS = ((0,5,3),(1,4,1),(5,0,3),(3,1,3),(1,2,3),(4,4,3),(5,5,4),(1,3,1),(3,4,3))


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    a = symbol_addresses(ROM)
    select_rom_topology(ROM)
    records=[]
    script_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out=ROOT/'builds'/f'boss-volley-patterns-{sha[:8]}-{script_sha[:8]}'
    out.mkdir(parents=True,exist_ok=True)
    try:
        for stage in range(9):
            if stage == 2:
                continue  # Cinder's bespoke attack driver is qualified separately.
            pb, _, _ = boot_to_stage(ROM, a, stage, 'normal', 0)
            try:
                advance_to_sanctuary(pb, a, stage)
                advance_to_boss(pb, a, stage)
                en, pl = a['_entities'], a['_player']
                boss = next(en+i*28 for i in range(32) if pb.memory[en+i*28] == 2
                            and pb.memory[en+i*28+1]&1 and pb.memory[en+i*28+20]&1)
                maximum = pb.memory[boss+23] or pb.memory[boss+14]
                for phase in range(3):
                    record=dict(stage=stage, phase=phase, trace=[])
                    records.append(record)
                    pb.memory[boss+14] = max(1, maximum >> phase)
                    patterns=set()
                    families=set()
                    visible_beats={}
                    pictured=set()
                    for frame in range(1200 if stage == 8 else 720):
                        pb.memory[pl+2]=pb.memory[pl+1]
                        pb.tick()
                        shots=[]
                        for slot in range(32):
                            e=en+slot*28
                            if pb.memory[e]==1 and pb.memory[e+1]&0x81==0x81:
                                row=[slot,pb.memory[e+18],pb.memory[e+19],pb.memory[e+21],
                                     pb.memory[e+25],pb.memory[e+15],pb.memory[e+3],pb.memory[e+7]]
                                patterns.add(row[1]);shots.append(row)
                                families.add((row[1],row[2]))
                        record['trace'].append([frame,shots])
                        if stage == 6:
                            live={(shot[1],shot[2]) for shot in shots}
                            for pair in ((5,2),(0,1),(1,0)):
                                visible_beats[pair]=visible_beats.get(pair,0)+1 if pair in live else 0
                                if visible_beats[pair]>=3 and pair not in pictured:
                                    pb.screen.image.save(str(out/f'golem-phase-{phase}-family-{pair[0]}-{pair[1]}.png'))
                                    pictured.add(pair)
                    assert PATTERNS[stage][phase] in patterns, (stage,phase,patterns)
                    if stage == 6:
                        assert (5,2) in families, ('Golem branching root starved',phase,families)
                        assert (0,1) in families and (1,0) in families, ('Golem fork incomplete',phase,families)
                print(f'[boss-volley-patterns] stage {stage+1} phase identities PASS',flush=True)
            finally:
                pb.stop(save=False)
    finally:
        (out/'capture.json').write_text(json.dumps(dict(
            rom_sha256=sha,script_sha256=script_sha,records=records)))


if __name__=='__main__':
    main()
