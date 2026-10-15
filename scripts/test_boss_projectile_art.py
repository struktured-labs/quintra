#!/usr/bin/env python3
"""Native boss-room atlas, metasprite sizes and menu restoration."""
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology, put16)

ROM = Path(__file__).resolve().parent.parent / 'rom/working/quintra.gbc'


def main():
    select_rom_topology(ROM)
    a = symbol_addresses(ROM)
    pb, _, _ = boot_to_stage(ROM, a, 6, 'normal', 0)
    try:
        advance_to_sanctuary(pb, a, 6)
        advance_to_boss(pb, a, 6)
        atlas = bytes(pb.memory[0x8D00:0x8E00])
        assert len(set(atlas))>10, 'boss atlas not loaded'
        en, pl = a['_entities'], a['_player']
        for i in range(32*28): pb.memory[en+i]=0
        put16(pb, pl+9, 64)
        put16(pb, pl+11, 100)
        for slot, (x, y, shape, tile, hitbox, pal) in enumerate(((32,48,0,208,0x44,4),
                (64,48,1,209,0x77,5),(96,48,2,210,0xEE,3),
                (56,80,3,214,0xE6,4),(104,80,4,216,0xEE,5))):
            e=en+slot*28
            pb.memory[e]=1; pb.memory[e+1]=0x87
            put16(pb,e+3,x); put16(pb,e+7,y)
            pb.memory[e+5]=x; pb.memory[e+9]=y
            pb.memory[e+12]=tile; pb.memory[e+13]=pal
            pb.memory[e+14]=1; pb.memory[e+16]=150
            pb.memory[e+17]=8; pb.memory[e+18]=(0,1,2,5,4)[shape]
            pb.memory[e+19]=0; pb.memory[e+20]=0
            pb.memory[e+21]=shape; pb.memory[e+23]=0xD0
            pb.memory[e+25]=hitbox
        visible = set()
        for _ in range(8):
            pb.tick()
            visible |= {pb.memory[0xFE00+i*4+2] for i in range(40) if pb.memory[0xFE00+i*4]}
        assert set(range(208,220))<=visible, visible
        pb.screen.image.save('/tmp/quintra-boss-projectile-sizes.png')
        for button in ('start','b'):
            pb.button(button)
            pb.tick(90)
        assert pb.memory[a['_loop_current_screen']]==5
        assert bytes(pb.memory[0x8D00:0x8E00])==atlas, 'menu corrupted boss shot art'
        print('[boss-projectile-art] PASS five native silhouettes, multi-tile OAM and menu restoration')
    finally:
        pb.stop(save=False)


if __name__=='__main__': main()
