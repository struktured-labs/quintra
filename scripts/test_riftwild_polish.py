#!/usr/bin/env python3
"""Real dialogue inputs and field entry, with staged progression/approaches."""
import hashlib
import json
import os
import re
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_riftwild,
                               symbol_addresses, select_rom_topology, put16)

rom = Path(os.environ.get('QUINTRA_TEST_ROM', 'rom/working/quintra.gbc')).resolve()
sha = hashlib.sha256(rom.read_bytes()).hexdigest()
out = Path('builds') / f'riftwild-polish-{sha[:8]}'
out.mkdir(parents=True, exist_ok=True)
a = symbol_addresses(rom)
topic = int(re.search(r'DEF _dialog_topic 0x([0-9A-Fa-f]+)',
                     rom.with_suffix('.noi').read_text()).group(1), 16)
select_rom_topology(rom)
pb, _, _ = boot_to_stage(rom, a, 1, 'normal', 0)
pl, rs, es = a['_player'], a['_run_state'], a['_entities']
report = dict(rom_sha256=sha, fixture='Real field seam and A/B inputs; staged source screen, position, flags',
              script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

def step(n):
    for _ in range(n):
        pb.memory[pl+2] = pb.memory[pl+1]
        pb.memory[pl+15] = 120
        pb.tick()

def tap(key):
    pb.button_press(key); step(8); pb.button_release(key); step(12)

def pickups():
    return [es+i*28 for i in range(32)
            if pb.memory[es+i*28] == 3 and pb.memory[es+i*28+1] & 1]

def enter_from_west(source, target):
    pb.memory[rs+18] = source
    put16(pb, pl+9, 232); put16(pb, pl+11, 64)
    pb.button_press('right'); step(100); pb.button_release('right'); step(120)
    assert pb.memory[rs+18] == target, (target, pb.memory[rs+18])

def talk(expected, label):
    speaker = next(e for e in pickups() if pb.memory[e+17] == 21)
    put16(pb, pl+9, pb.memory[speaker+3] | pb.memory[speaker+4] << 8)
    put16(pb, pl+11, pb.memory[speaker+7] | pb.memory[speaker+8] << 8)
    tap('a')
    assert pb.memory[a['_loop_current_screen']] == 10
    assert pb.memory[topic] == expected, (expected, pb.memory[topic])
    pb.screen.image.save(str(out / f'{label}-lore.png'))
    lore = hashlib.sha256(pb.screen.image.tobytes()).hexdigest()
    tap('a')
    pb.screen.image.save(str(out / f'{label}-advice.png'))
    advice = hashlib.sha256(pb.screen.image.tobytes()).hexdigest()
    tap('b')
    return lore, advice

try:
    advance_to_riftwild(pb, a, 1)
    if not os.environ.get('QUINTRA_VAULT_ONLY'):
        first = talk(14, 'singer-first')
        pb.memory[pl+44] |= 2
        raft = talk(14, 'singer-raft')
        assert first[1] != raft[1], 'Raft owner still told to find a raft'
        pb.memory[rs+47] |= 0x20
        returned = talk(14, 'singer-return')
        assert first[0] != returned[0], 'Singer forgot the shrine discovery'
        report['singer_pages'] = dict(first=first, raft=raft, returned=returned)
        pb.memory[pl+44] &= ~2
    pb.memory[rs+47] = 0x80
    enter_from_west(7, 8)
    if not os.environ.get('QUINTRA_VAULT_ONLY'):
        talk(13, 'sealed-arch')
    # Vault field 30 is entered through its real east-facing neighbor seam.
    pb.memory[rs+18] = 31
    put16(pb, pl+9, 0); put16(pb, pl+11, 64)
    pb.button_press('left'); step(100); pb.button_release('left'); step(120)
    assert pb.memory[rs+18] == 30
    loot = [e for e in pickups() if pb.memory[e+17] != 21]
    assert len(loot) == 4, len(loot)
    pb.screen.image.save(str(out / 'vault-arrival.png'))
    step(1000)
    assert all(pb.memory[e+1] & 1 for e in loot), 'Vault gifts expired while exploring'
    pb.screen.image.save(str(out / 'vault-wait.png'))
    talk(12, 'vault')
    normal = next(e for e in loot if pb.memory[e+17] == 2)
    pb.memory[normal+22] = 0
    pb.memory[normal+16] = 10
    step(60)
    assert not pb.memory[normal+1] & 1, 'Ordinary loot timeout was disabled'
    # Walking over a surviving coin still works and does not duplicate it.
    coin = next(e for e in loot if pb.memory[e+17] == 2 and pb.memory[e+1] & 1)
    before = pb.memory[pl+16] | pb.memory[pl+17] << 8
    put16(pb, pl+9, pb.memory[coin+3] | pb.memory[coin+4] << 8)
    put16(pb, pl+11, pb.memory[coin+7] | pb.memory[coin+8] << 8)
    step(15)
    after = pb.memory[pl+16] | pb.memory[pl+17] << 8
    assert after == before + 5, (before, after)
    assert not pb.memory[coin+1] & 1
    enter_from_west(30, 31)
    put16(pb, pl+9, 0); put16(pb, pl+11, 64)
    pb.button_press('left'); step(100); pb.button_release('left'); step(120)
    assert pb.memory[rs+18] == 30
    assert all(pb.memory[e+17] == 21 for e in pickups()), 'Vault became farmable'
    report['status'] = 'PASS'
    print('[riftwild-polish] PASS sealed-arch identity, vault wait, dialogue, coin collection')
finally:
    pb.stop(save=False)
    (out / 'capture.json').write_text(json.dumps(report, indent=2))
