#!/usr/bin/env python3
"""Matched native in-game art captures; no resized or generated sprite substitutes."""
import hashlib
import json
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology, put16)

ROOT=Path(__file__).resolve().parent.parent


def main():
    current=ROOT/'rom/working/quintra.gbc'
    previous=ROOT/'builds/mire-parent-855d3d39/quintra.gbc'
    sha=hashlib.sha256(current.read_bytes()).hexdigest()
    script_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out=ROOT/'builds'/f'boss-art-comparison-{sha[:8]}-{script_sha[:8]}'
    out.mkdir(parents=True,exist_ok=True)
    names={0:'Crystal Colossus',3:'Frost Spider',4:'Mire Heart',7:'Blood Hydra'}
    records=[]
    for label,rom in [('before',previous),('after',current)]:
        select_rom_topology(rom)
        a=symbol_addresses(rom)
        for stage in names:
            pb,_,_=boot_to_stage(rom,a,stage,'normal',0)
            try:
                advance_to_sanctuary(pb,a,stage)
                advance_to_boss(pb,a,stage)
                en,pl=a['_entities'],a['_player']
                boss=next(en+i*28 for i in range(32) if pb.memory[en+i*28]==2
                          and pb.memory[en+i*28+1]&1 and pb.memory[en+i*28+20]&1)
                pb.memory[boss+5]=240
                pb.tick(4)
                for i in range(32):
                    if en+i*28!=boss:
                        pb.memory[en+i*28]=pb.memory[en+i*28+1]=0
                put16(pb,boss+3,72);put16(pb,boss+7,48)
                pb.memory[boss+1]|=4
                pb.memory[boss+24]=0
                put16(pb,pl+9,64);put16(pb,pl+11,104)
                pb.memory[pl+15]=240
                pb.tick(40)
                if label == 'after' and stage in (3,4,7):
                    body = [list(pb.memory[0xFE00+i*4:0xFE04+i*4]) for i in range(40)
                            if pb.memory[0xFE00+i*4] and pb.memory[0xFE03+i*4]&8]
                    base=min(row[2] for row in body)
                    assert base in ((40,64) if stage==4 else (40,))
                    assert sorted(row[2] for row in body) == list(range(base,base+24)), (stage, body)
                name=f'{stage}-{label}.png'
                pb.screen.image.save(str(out/name))
                records.append(dict(stage=stage,label=label,image=name,
                    rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),
                    boss=list(pb.memory[boss:boss+28]),player=list(pb.memory[pl:pl+24])))
            finally:pb.stop(save=False)
    cards=''.join(f'<section><h2>{name}</h2><div class="pair">'+''.join(
        f'<figure><img src="{stage}-{label}.png" width="160" height="144"><figcaption>{label.title()}</figcaption></figure>'
        for label in ('before','after'))+'</div></section>' for stage,name in names.items())
    (out/'artwork.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Quintra boss redraws</title>
<style>:root{color-scheme:dark;font:17px system-ui;background:#10121b;color:#e5eaf5}
body{max-width:960px;margin:auto;padding:24px}h1,h2{color:#f5cc80}a{color:#9ed7ff}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0;background:#191e2d;padding:12px}
img{display:block;width:100%;height:auto;image-rendering:pixelated}figcaption{padding:10px}
p{line-height:1.6}section{margin:32px 0}</style><h1>Boss artwork · before / after</h1>
<p>Native ROM captures, matched room/actor positions. Boss AI frozen, other entities removed,
and player protected for comparison. These are actual game sprites, not concept art.
See the <a href="/">animated phase gallery</a> for attacks and movement.</p>'''+cards+
        f'<p>Before: 855d3d39 · After: {sha[:8]}. Mire Heart refinement: clearer lobes, '
        'pointed ventricle, and a two-beat contraction. Other bosses unchanged. '
        'Art-review build; existing performance failures remain open. No hardware reload.</p></html>')
    (out/'capture.json').write_text(json.dumps(dict(rom_sha256=sha,script_sha256=script_sha,records=records),indent=2))
    print(out)


if __name__=='__main__':main()
