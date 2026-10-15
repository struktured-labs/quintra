#!/usr/bin/env python3
"""Live-ROM contract for the nine telegraphed Colossus signatures."""
import hashlib
import json
from pathlib import Path
from test_boss_identity import EN, PL, ROM, addr, enter_boss


ENTITY_SIZE = 28
EXPECTED = (3, 8, 7, 8, 8, 5, 8, 5, 8)
NAMES = (
    "Prism Lance", "Coil Tempest", "Furnace Breath",
    "Web Crucifix", "Miasma Bloom", "Death Sweep",
    "Sunfall", "Threefold Deluge", "Event Horizon",
)


def clear_disposable(pb):
    for slot in range(32):
        entity = EN + slot * ENTITY_SIZE
        if pb.memory[entity] in (1, 4):
            pb.memory[entity] = pb.memory[entity + 1] = 0


def hostile_projectiles(pb):
    result = []
    for slot in range(32):
        entity = EN + slot * ENTITY_SIZE
        if (pb.memory[entity] == 1
                and pb.memory[entity + 1] & 1
                and not pb.memory[entity + 1] & 0x10):
            assert pb.memory[entity+1]&0x80, 'signature bypassed shared boss projectile rules'
            result.append((pb.memory[entity+17], pb.memory[entity+18]))
    return result


def main():
    report = []
    captures = []
    for stage, (name, expected) in enumerate(zip(NAMES, EXPECTED)):
        pb, boss = enter_boss(stage, keep_open=True)
        record = dict(stage=stage, name=name, trace=[])
        captures.append(record)
        try:
            clear_disposable(pb)
            maximum = pb.memory[boss + 23]
            assert maximum > 1, f"stage {stage + 1} never captured max HP"
            if stage == 2:
                # Ember no longer enters the shared one-shot signature
                # dispatcher: its entire fight is a pack/Rex curriculum. Force
                # the first Rex attack and prove Furnace Breath creates seven
                # parallel lanes around one gap after a long warning beat.
                phase = addr("_cinder_phase")
                pattern = addr("_cinder_pattern")
                timer = addr("_cinder_timer")
                pb.memory[phase] = 2
                pb.memory[pattern] = 0
                pb.memory[timer] = 0
                pb.memory[boss + 14] = maximum // 2
                pb.memory[PL + 15] = 255
                for _ in range(240):
                    pb.memory[PL + 15] = 255
                    if pb.memory[timer] < 36:
                        clear_disposable(pb)
                    pb.tick()
                    record['trace'].append([pb.memory[timer], hostile_projectiles(pb)])
                    if len(hostile_projectiles(pb)) >= expected:
                        break
                shots = hostile_projectiles(pb)
                assert len(shots) == expected, (
                    f"Furnace Breath emitted {len(shots)}, expected {expected}")
                assert len(set(shots)) == 1 and shots[0][0] in (0,16) and shots[0][1] == 6, (
                    f"Furnace Breath lost its unified vertical wall: {shots}")
                report.append(f"3:Kilnback/Cinder Rex Furnace Breath={len(shots)}")
                continue
            pb.memory[boss + 14] = maximum // 2

            saw_warning = False
            initial_timer = 0
            shots = []
            for _ in range(320):
                pb.memory[PL + 15] = 255
                pb.memory[PL + 2] = 16
                pb.tick()
                flags = pb.memory[boss + 20]
                if flags & 0x40:
                    saw_warning = True
                    initial_timer = max(initial_timer, pb.memory[boss + 18])
                current = hostile_projectiles(pb)
                record['trace'].append([flags,pb.memory[boss+18],current])
                if (saw_warning and not (flags & 0x40)
                        and pb.memory[boss + 18] >= 30
                        and len(current) >= expected):
                    shots = current
                    break

            assert saw_warning and initial_timer >= 40, (
                f"stage {stage + 1} {name} lost its long warning: {initial_timer}")
            assert pb.memory[boss + 20] & 0x80, (
                f"stage {stage + 1} {name} did not latch as spent")
            assert pb.memory[boss + 18] >= 30, (
                f"stage {stage + 1} {name} lost its recovery window")
            assert len(shots) == expected, (
                f"stage {stage + 1} {name} emitted {len(shots)}, expected {expected}")

            if stage in (0, 2, 7):
                assert len(set(shots)) == 1, f"{name} lost its unified fat lane"
            elif stage == 5:
                assert all(angle in (8,24) and pattern == 5 for angle, pattern in shots), (
                    "Death Sweep no longer crosses one horizontal row")
            elif stage in (1, 4, 6, 8):
                assert len(set(shots)) == 8, f"{name} lost its complete radial bloom"
            else:
                assert len(set(shots)) == 4, (
                    "Web Crucifix lost one of its cardinal directions")
            report.append(f"{stage + 1}:{name}={len(shots)}")
        finally:
            pb.stop(save=False)
            sha=hashlib.sha256(ROM.read_bytes()).hexdigest()
            out=Path('tmp')/f'boss-signatures-{sha}.json'
            out.parent.mkdir(exist_ok=True)
            out.write_text(json.dumps(dict(rom_sha256=sha,records=captures)))

    print("[colossus-signatures] PASS " + "; ".join(report))


if __name__ == "__main__":
    main()
