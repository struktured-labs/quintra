#!/usr/bin/env python3
"""Cold battery-resume must reload the stage's OBJ palette and sprite atlas."""
import hashlib
import io
import json
import os
from pathlib import Path
from pyboy import PyBoy
from make_stage_states import boot_to_stage, advance_to_court, symbol_addresses, select_rom_topology

rom=Path(os.environ.get('QUINTRA_TEST_ROM','rom/working/quintra.gbc')).resolve()
sha=hashlib.sha256(rom.read_bytes()).hexdigest()
out=Path('builds')/f'resume-palette-{sha[:8]}'
out.mkdir(parents=True,exist_ok=True)
a=symbol_addresses(rom)
select_rom_topology(rom)

def palette(pb):
    pb.memory[0xFF40] &= 0x7f
    data=[]
    for i in range(48,56):
        pb.memory[0xFF6A]=i
        data.append(pb.memory[0xFF6B])
    return data

pb,_,_=boot_to_stage(rom,a,0,'normal',0)
advance_to_court(pb,a,0)
pb.tick(90)
expected=palette(pb)
pb.memory[0xFF4F]=0
expected_atlas=bytes(pb.memory[0x8280:0x8380])
battery=io.BytesIO()
pb.stop(save=True,ram_file=battery)
(out/'quintra.sav').write_bytes(battery.getvalue())
battery.seek(0)
pb=PyBoy(str(rom),window='null',cgb=True,ram_file=battery)
try:
    pb.tick(240)
    pb.button_press('a');pb.tick(8);pb.button_release('a');pb.tick(180)
    pb.screen.image.save(str(out/'resumed.png'))
    actual=palette(pb)
    pb.memory[0xFF4F]=0
    actual_atlas=bytes(pb.memory[0x8280:0x8380])
    record=dict(rom_sha256=sha,expected=expected,actual=actual,
                script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                expected_atlas_sha256=hashlib.sha256(expected_atlas).hexdigest(),
                actual_atlas_sha256=hashlib.sha256(actual_atlas).hexdigest(),
                room=pb.memory[a['_run_state']+1],stage=pb.memory[a['_run_state']+11])
    (out/'capture.json').write_text(json.dumps(record,indent=2))
    print(record,flush=True)
    assert record['stage']==0 and record['room']==5
    assert any(expected[2:]) and actual==expected, 'cold resume lost stage OBJ palette'
    assert actual_atlas==expected_atlas, 'cold resume lost stage OBJ artwork'
finally:pb.stop(save=False)
