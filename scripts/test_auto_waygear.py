#!/usr/bin/env python3
"""Fresh-boot collision replay; accepts a pinned baseline ROM and symbols."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from pyboy import PyBoy

p = argparse.ArgumentParser()
p.add_argument('--rom', type=Path, default=Path('rom/working/quintra.gbc'))
p.add_argument('--report', type=Path, default=Path('/tmp/quintra-auto-waygear.json'))
a = p.parse_args()
noi = a.rom.with_suffix('.noi').read_text()
def addr(name):
    return int(re.search(rf'DEF _{name} 0x([0-9a-fA-F]+)', noi)[1], 16)
pl, tm, en = map(addr, ('player', 'room_tilemap', 'entities'))
records = []
for tile, owned, hero, allowed in (
    (97, 0, 0, False), (97, 2, 0, True), (101, 2, 0, True),
    (100, 1, 0, True), (100, 2, 0, False),
    (108, 4, 0, True), (102, 4, 0, True), (108, 0, 0, False),
    (97, 0, 3, True), (108, 0, 2, True),
    (2, 15, 0, False), (21, 15, 0, False), (109, 15, 0, False),
):
    pb = PyBoy(str(a.rom), window='null', cgb=True)
    def press(key):
        pb.button_press(key); pb.tick(4)
        pb.button_release(key); pb.tick(4)
    pb.tick(240); press('start'); pb.tick(30); press('a'); pb.tick(90)
    assert pb.memory[addr('loop_current_screen')] == 5
    for i in range(32 * 28): pb.memory[en + i] = 0
    for y in range(17):
        for x in range(20): pb.memory[tm + y * 20 + x] = tile if 10 <= x <= 12 else 1
    pb.memory[pl] = hero
    pb.memory[pl + 44] = owned
    pb.memory[pl + 45] = 255
    pb.memory[pl + 7] = 5
    for off, value in ((9, 64), (11, 64)):
        pb.memory[pl + off] = value; pb.memory[pl + off + 1] = 0
    trace = []
    pb.button_press('right')
    for frame in range(55):
        pb.memory[pl + 15] = 120
        pb.tick()
        trace.append([frame, pb.memory[pl + 9] | pb.memory[pl + 10] << 8,
                      pb.memory[pl + 11] | pb.memory[pl + 12] << 8])
    actual = trace[-1][1] >= 104
    records.append(dict(tile=tile, owned=owned, hero=hero, allowed=allowed,
                        crossed=actual, passed=actual == allowed, trace=trace))
    pb.stop(save=False)
a.report.write_text(json.dumps(dict(rom_sha256=hashlib.sha256(a.rom.read_bytes()).hexdigest(),
    fixture='fresh boot; injected terrain strip; held-right movement; legacy slot unset',
    cases=records), indent=2))
failures = [r for r in records if not r['passed']]
assert not failures, [(r['tile'], r['owned'], r['hero'], r['trace'][-1]) for r in failures]
print('[auto-waygear] PASS owned and innate traversal; walls, pillars, mountains stay solid')
