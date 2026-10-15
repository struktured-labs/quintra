#!/usr/bin/env python3
"""Native stationary-shot fixtures at the enlarged body edge and just outside it."""
import hashlib
import json
from pathlib import Path
from test_boss_identity import ROM, ROOT, EN, PL, enter_boss, put16


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    records = []
    out = ROOT / 'builds' / f'large-boss-collision-{sha[:8]}'
    out.mkdir(parents=True, exist_ok=True)
    try:
        for stage in (3, 4, 7):
            for hit in (True, False):
                pb, boss = enter_boss(stage, keep_open=True)
                try:
                    pb.memory[boss+5] = 240
                    pb.tick(4)
                    for i in range(32):
                        e = EN+i*28
                        if e != boss:
                            for j in range(28):
                                pb.memory[e+j] = 0
                    put16(pb, boss+3, 72)
                    put16(pb, boss+7, 48)
                    pb.memory[boss+1] |= 4
                    pb.memory[boss+14] = 100
                    pb.memory[boss+24] = 0
                    put16(pb, PL+9, 32)
                    put16(pb, PL+11, 112)
                    shot = EN if EN != boss else EN+28
                    pb.memory[shot] = 1
                    pb.memory[shot+1] = 0x17
                    edge = -3 if hit else -6
                    put16(pb, shot+3, 84 if stage == 4 else 72+edge)
                    put16(pb, shot+7, 48+edge if stage == 4 else 60)
                    pb.memory[shot+14] = 1
                    pb.memory[shot+16] = 120
                    pb.memory[shot+25] = 0x11
                    pb.memory[shot+26] = 10
                    trace = []
                    for frame in range(12):
                        pb.tick()
                        trace.append([frame, pb.memory[boss+14], pb.memory[shot]])
                    records.append(dict(stage=stage, expected_hit=hit, trace=trace))
                    assert (pb.memory[boss+14] < 100) == hit, records[-1]
                finally:
                    pb.stop(save=False)
        print('[large-boss-collision] PASS 3 enlarged edges and 3 outside misses')
    finally:
        (out/'capture.json').write_text(json.dumps(dict(rom_sha256=sha,
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            records=records), indent=2))


if __name__ == '__main__':
    main()
