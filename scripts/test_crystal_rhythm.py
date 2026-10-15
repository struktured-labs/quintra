#!/usr/bin/env python3
"""Measure Crystal's actual volley cycle, with staged positions/cooldown."""
import hashlib
import json
from pathlib import Path
from test_boss_identity import ROM, EN, PL, RS, enter_boss, put16

sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
out = Path('builds') / f'crystal-rhythm-{sha[:8]}'
out.mkdir(parents=True, exist_ok=True)
records = []
try:
    for easy in (0, 1):
        for volley, expected in ((0, 9 if easy else 3), (1, 9 if easy else 8)):
            pb, boss = enter_boss(0, keep_open=True)
            try:
                for i in range(32):
                    e = EN+i*28
                    if e != boss: pb.memory[e] = pb.memory[e+1] = 0
                pb.memory[RS+26] = easy
                pb.memory[boss+14] = pb.memory[boss+23] = 100
                pb.memory[boss+18] = 12
                pb.memory[boss+22] = volley
                pb.memory[boss+10] = 80
                put16(pb, boss+3, 80); put16(pb, boss+7, 48)
                put16(pb, PL+9, 128); put16(pb, PL+11, 96)
                warned = False
                for frame in range(100):
                    pb.memory[PL+2] = pb.memory[PL+1]
                    pb.memory[PL+15] = 60
                    pb.tick()
                    warned |= pb.memory[boss+24] > 0
                    if pb.memory[boss+22] != volley: break
                shots = [EN+i*28 for i in range(32)
                         if pb.memory[EN+i*28] == 1 and pb.memory[EN+i*28+1] & 0x80]
                record = dict(easy=easy, volley=volley, shots=len(shots), warned=warned,
                              cooldown=pb.memory[boss+18], angles=[pb.memory[e+17] for e in shots])
                records.append(record)
                assert len(shots) == expected, record
                assert record['cooldown'] == (46 if easy else 58 if volley else 30), record
                assert warned, record
                if not easy and not volley: assert sorted(record['angles']) == [8,12,16], record
                pb.tick(8)
                pb.screen.image.save(str(out/f'easy-{easy}-volley-{volley}.png'))
            finally: pb.stop(save=False)
    print('[crystal-rhythm] PASS warned aimed fan/ring alternation; Easy unchanged')
finally:
    (out/'capture.json').write_text(json.dumps(dict(rom_sha256=sha, records=records), indent=2))
