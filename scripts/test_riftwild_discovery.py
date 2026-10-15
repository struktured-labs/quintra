#!/usr/bin/env python3
"""Native Bellwater fixture: real Riftwild entry, staged shore approach."""
import hashlib
import io
import json
import os
import re
from pathlib import Path
from pyboy import PyBoy
from make_stage_states import (boot_to_stage, advance_to_riftwild,
                               symbol_addresses, select_rom_topology, put16)

rom = Path(os.environ.get('QUINTRA_TEST_ROM', 'rom/working/quintra.gbc')).resolve()
sha = hashlib.sha256(rom.read_bytes()).hexdigest()
out = Path('builds') / f'bellwater-{sha[:8]}'
out.mkdir(parents=True, exist_ok=True)
a = symbol_addresses(rom)
a['_room_major_reward_pending'] = int(re.search(
    r'DEF _room_major_reward_pending 0x([0-9A-Fa-f]+)',
    rom.with_suffix('.noi').read_text()).group(1), 16)
a['_dialog_topic'] = int(re.search(r'DEF _dialog_topic 0x([0-9A-Fa-f]+)',
    rom.with_suffix('.noi').read_text()).group(1), 16)
select_rom_topology(rom)
pb, _, _ = boot_to_stage(rom, a, 1, 'normal', 0)
report = dict(rom_sha256=sha, fixture='Progression fixture, real boss exit; staged shore position and raft grant',
              script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
pl, rs, es = a['_player'], a['_run_state'], a['_entities']

def slots():
    return [es + i * 28 for i in range(32) if pb.memory[es + i * 28 + 1] & 1]

def step(n):
    for _ in range(n):
        pb.memory[pl + 2] = pb.memory[pl + 1]
        pb.memory[pl + 15] = 90
        pb.tick()

try:
    advance_to_riftwild(pb, a, 1)
    step(30)
    pb.screen.image.save(str(out / 'arrival.png'))
    residents = [pb.memory[e + 18] for e in slots() if pb.memory[e] == 3]
    report['pickup_topics'] = residents
    assert 14 in residents and 15 in residents, residents
    reward = next(e for e in slots() if pb.memory[e + 22] == 0xB1)
    put16(pb, pl + 9, 32); put16(pb, pl + 11, 40)
    pb.button_press('a'); step(12); pb.button_release('a'); step(30)
    assert pb.memory[a['_loop_current_screen']] == 10, 'Reed Singer cannot be approached'
    assert pb.memory[a['_dialog_topic']] == 14, 'Reed Singer became a generic vault conversation'
    pb.screen.image.save(str(out / 'singer.png'))
    pb.button_press('b'); step(12); pb.button_release('b'); step(30)
    step(700)
    assert pb.memory[reward + 1] & 1, 'Shrine reward timed out'
    # Approach from two water rows south, without a traversal ability.
    put16(pb, pl + 9, 120)
    put16(pb, pl + 11, 64)
    pb.button_press('up'); step(80); pb.button_release('up')
    report['shore_y'] = pb.memory[pl + 11] | (pb.memory[pl + 12] << 8)
    assert not pb.memory[rs + 47] & 0x20, 'Reward reachable from shore without swimming'
    assert pb.memory[reward + 1] & 1
    pb.screen.image.save(str(out / 'shore.png'))
    before = pb.memory[pl + 3]
    pb.memory[pl + 44] |= 2  # Owned raft; no explicit equipment toggle.
    pb.button_press('up')
    for _ in range(180):
        step(1)
        if pb.memory[rs + 47] & 0x20:
            break
    pb.button_release('up')
    assert pb.memory[rs + 47] & 0x20, 'Raft could not reach the shrine reward'
    assert pb.memory[pl + 3] == before + 2
    assert pb.memory[a['_room_major_reward_pending']] > 0
    pb.screen.image.save(str(out / 'claim.png'))
    step(180)
    pb.screen.image.save(str(out / 'reward-card.png'))
    assert pb.memory[a['_loop_current_screen']] == 10
    pb.button_press('b'); step(12); pb.button_release('b'); step(30)
    # Cross a real field edge, return, then cold-boot its room-entry SRAM.
    put16(pb, pl + 9, 232); put16(pb, pl + 11, 64)
    pb.button_press('right'); step(100); pb.button_release('right'); step(120)
    assert pb.memory[rs + 18] == 1, 'East route blocked'
    put16(pb, pl + 9, 0); put16(pb, pl + 11, 64)
    pb.button_press('left'); step(100); pb.button_release('left'); step(120)
    assert pb.memory[rs + 18] == 0, 'Return route blocked'
    assert not any(pb.memory[e + 22] == 0xB1 for e in slots()), 'Reward duplicated on revisit'
    battery = io.BytesIO()
    pb.stop(save=True, ram_file=battery)
    battery.seek(0)
    pb = PyBoy(str(rom), window='null', cgb=True, ram_file=battery)
    pb.tick(240)
    pb.button_press('a'); pb.tick(8); pb.button_release('a'); pb.tick(240)
    assert pb.memory[rs + 47] & 0x20, 'Claim lost on cold resume'
    assert not any(pb.memory[e + 22] == 0xB1 for e in slots()), 'Reward duplicated on cold resume'
    report['revisit_and_cold_resume'] = 'PASS'
    pb.stop(save=False)
    pb, _, _ = boot_to_stage(rom, a, 1, 'normal', 3)
    advance_to_riftwild(pb, a, 1)
    assert pb.memory[pl] == 3 and not pb.memory[pl + 44] & 2
    put16(pb, pl + 9, 120); put16(pb, pl + 11, 64)
    pb.button_press('up'); step(120); pb.button_release('up')
    assert pb.memory[rs + 47] & 0x20, 'Innate swimmer cannot reach island'
    report['innate_swimmer'] = 'PASS'
    report['status'] = 'PASS'
    print('[bellwater] PASS: encounter, timeout, water gate, raft, ceremony, revisit, cold resume')
finally:
    pb.stop(save=False)
    (out / 'capture.json').write_text(json.dumps(report, indent=2))
