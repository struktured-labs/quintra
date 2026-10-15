#!/usr/bin/env python3
"""Continuous controller probe of the Reaper's exposed/link alternation."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / 'rom/working/quintra.gbc'


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--ignore-link', action='store_true')
    parser.add_argument('--signature', action='store_true')
    args = parser.parse_args()
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = ROOT / 'builds' / f'reaper-controller-{sha[:8]}-{script_sha[:8]}' / (
        ('ignore' if args.ignore_link else 'respect') + ('-signature' if args.signature else ''))
    out.mkdir(parents=True, exist_ok=True)
    a = symbol_addresses(ROM)
    noi = ROM.with_suffix('.noi').read_text()
    for name in ('_boss_phase', '_boss_phase_clock', '_boss_link_active', '_entity_anim_counter'):
        a[name] = int(re.search(rf'DEF {name} 0x([0-9A-Fa-f]+)', noi)[1], 16)
    select_rom_topology(ROM)
    pb, _, _ = boot_to_stage(ROM, a, 5, 'normal', 3)
    report = dict(rom_sha256=sha, script_sha256=script_sha, ignore_link=args.ignore_link,
        signature=args.signature,
        fixture='Developer stage 6 Picsean entry, sanctuary heal, boss HP set to half once. '
                'No RAM writes thereafter. Controller reads world positions including off-camera '
                'threats and link state every 12 LCD frames; not human difficulty proof.', trace=[])
    try:
        advance_to_sanctuary(pb, a, 5)
        advance_to_boss(pb, a, 5)
        en, pl = a['_entities'], a['_player']
        boss = next(en+i*28 for i in range(32) if pb.memory[en+i*28] == 2
                    and pb.memory[en+i*28+1]&1 and pb.memory[en+i*28+20]&1)
        pb.memory[boss+14] = pb.memory[boss+23] // 2
        report['initial_player'] = list(pb.memory[pl:pl+24])
        report['initial_boss_hp'] = pb.memory[boss+14]
        held, steering = set(), set()
        previous_link, cycles, waypoint = False, 0, 0
        route = ((16,112),(192,112),(192,8),(16,8))
        attack_allowed = False
        for frame in range(5000):
            x, y = pb.memory[pl+9], pb.memory[pl+11]
            if frame % 12 == 0:
                tx, ty = route[waypoint]
                if abs(x-tx)<12 and abs(y-ty)<12:
                    waypoint = (waypoint+1) % 4
                    tx, ty = route[waypoint]
                threats = [(pb.memory[boss+3]+16,pb.memory[boss+7]+16,24)]
                for i in range(32):
                    e = en+i*28
                    if pb.memory[e] == 1 and pb.memory[e+1]&1 and not pb.memory[e+1]&16:
                        threats.append((pb.memory[e+3]+4,pb.memory[e+7]+4,12))
                choices = []
                for dx,dy in ((0,0),(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
                    nx,ny = x+dx*12,y+dy*12
                    if not (8<=nx<=200 and 8<=ny<=112): continue
                    cost = .02*(abs(nx-tx)+abs(ny-ty))
                    for hx,hy,radius in threats:
                        distance = max(abs(nx+8-hx),abs(ny+12-hy))/radius
                        if distance<3: cost += 1/max(.1,distance-.7)**2
                    choices.append((cost,dx,dy))
                if choices:
                    _,dx,dy = min(choices)
                    steering = set()
                    if dx: steering.add('right' if dx>0 else 'left')
                    if dy: steering.add('down' if dy>0 else 'up')
                clock = pb.memory[a['_boss_phase_clock']]
                attack_allowed = args.ignore_link or not (96<=clock<224)
            wanted = steering.copy()
            if frame%96 in (*range(4),*range(8,12)): wanted.clear()
            if args.signature and frame%48 in range(24,28): wanted.add('b')
            if attack_allowed and frame%48<6:
                dx,dy = pb.memory[boss+3]+8-x,pb.memory[boss+7]-y
                wanted = {'a'}
                if abs(dx)>abs(dy)//2 and dx: wanted.add('right' if dx>0 else 'left')
                if abs(dy)>abs(dx)//2 and dy: wanted.add('down' if dy>0 else 'up')
            for button in held-wanted: pb.button_release(button)
            for button in wanted-held: pb.button_press(button)
            held = wanted
            pb.tick()
            hp, link = pb.memory[pl+2], bool(pb.memory[a['_boss_link_active']])
            screen = pb.memory[a['_loop_current_screen']]
            defeated = pb.memory[a['_run_state']+11]>=6
            report['trace'].append(dict(frame=frame,hp=hp,boss_hp=pb.memory[boss+14],
                x=pb.memory[pl+9],y=pb.memory[pl+11],buttons=sorted(held),linked=link,
                phase=pb.memory[a['_boss_phase']],clock=pb.memory[a['_boss_phase_clock']],
                update=pb.memory[a['_entity_anim_counter']],screen=screen))
            if previous_link and not link: cycles += 1
            if link != previous_link or frame%600==0:
                pb.screen.image.save(str(out/f'frame-{frame:04d}.png'))
            previous_link = link
            if not hp or screen!=5 or defeated or cycles>=3: break
        report.update(cycles=cycles,final_hp=hp,defeated=defeated,frames=frame+1)
        assert hp>0 and (cycles>=3 or defeated), 'controller did not survive link cycles'
        assert any(row['linked'] for row in report['trace']), 'never exercised damage link'
        assert min(row['boss_hp'] for row in report['trace']) < report['initial_boss_hp'], 'never damaged boss'
        print(f'[reaper-controller] PASS cycles={cycles} hp={hp} defeated={defeated} frames={frame+1}')
    finally:
        pb.stop(save=False)
        (out/'capture.json').write_text(json.dumps(report))


if __name__ == '__main__':
    main()
