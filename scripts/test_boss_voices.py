#!/usr/bin/env python3
"""Capture native boss-door PCM and verify identity, attenuation and sparse calls."""
import hashlib
import json
import os
import re
import wave
from pathlib import Path
import numpy as np
from make_stage_states import (boot_to_stage, advance_to_sanctuary,
    symbol_addresses, select_rom_topology, put16, graph_direction, dungeon_size)

ROM=Path(__file__).resolve().parent.parent/'rom/working/quintra.gbc'
NOISE=(0x64,0x27,0x53,0x19,0x75,0x4B,0x36,0x45,0x6D)


def main():
    select_rom_topology(ROM)
    a=symbol_addresses(ROM)
    noi=ROM.with_suffix('.noi').read_text()
    voice=int(re.search(r'DEF _boss_voice 0x([0-9A-Fa-f]+)',noi)[1],16)
    sha=hashlib.sha256(ROM.read_bytes()).hexdigest()
    no_hook=os.environ.get('QUINTRA_VOICE_NO_HOOK')=='1'
    out=Path('builds')/(f'boss-voices-{sha[:8]}' + ('-unobserved' if no_hook else ''))
    out.mkdir(parents=True,exist_ok=True)
    records=[]
    for stage in range(9):
        pb,_,_=boot_to_stage(ROM,a,stage,'normal',0)
        try:
            advance_to_sanctuary(pb,a,stage)
            trace=[]; chunks=[]; calls=[]
            if not no_hook:
                pb.hook_register(voice>>16,voice&0xFFFF,lambda ctx: ctx[0].append(len(ctx[1])),(calls,trace))
            direction=graph_direction(dungeon_size(stage)-2,dungeon_size(stage)-1)
            x,y={'up':(72,8),'right':(136,60),'down':(72,112),'left':(8,60)}[direction]
            put16(pb,a['_player']+9,x); put16(pb,a['_player']+11,y)
            for frame in range(180):
                pb.tick()
                trace.append([frame,pb.memory[0xFF12],pb.memory[0xFF21],pb.memory[0xFF22]])
                chunks.append(pb.sound.ndarray.copy())
            pcm=np.concatenate(chunks,axis=0)
            record=dict(stage=stage+1,direction=direction,trace=trace,calls=calls,
                        minimum=int(pcm.min()),maximum=int(pcm.max()),samples=len(pcm))
            records.append(record)
            with wave.open(str(out/f'door-{stage+1:02}.wav'),'wb') as audio:
                audio.setnchannels(2);audio.setsampwidth(2);audio.setframerate(48000)
                audio.writeframes((pcm.astype(np.int16)*256).tobytes())
            assert any(t[2]==0x33 and t[3]==NOISE[stage] for t in trace), ('missing quiet boss call',stage)
            assert pcm.max()>pcm.min(),('silent native PCM',stage)
            if not no_hook:
                assert 1<=len(calls)<=2, ('door call cadence',stage,calls)
            else:
                observed=Path('builds')/f'boss-voices-{sha[:8]}'/f'door-{stage+1:02}.wav'
                assert observed.read_bytes()==(out/f'door-{stage+1:02}.wav').read_bytes(), 'observer changed native PCM'
            print('[boss-voice]',stage+1,'quiet call + native PCM',flush=True)
        finally:
            pb.stop(save=False)
            (out/'capture.json').write_text(json.dumps(dict(rom_sha256=sha,records=records),indent=2))
    print('[boss-voices] PASS all nine door identities and native PCM; listening review still required')


if __name__=='__main__':main()
