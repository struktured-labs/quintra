#!/usr/bin/env python3
"""Controller-only survival probe after an explicitly staged boss entry."""
import argparse
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / 'rom/working/quintra.gbc'
ROUTE = ((16,112),(192,112),(192,8),(16,8))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--class-id', type=int, choices=range(5), default=0)
    parser.add_argument('--hold', action='store_true')
    parser.add_argument('--dash', action='store_true')
    parser.add_argument('--reactive', action='store_true')
    parser.add_argument('--signature', action='store_true')
    parser.add_argument('--combat', action='store_true')
    parser.add_argument('--video', action='store_true')
    args = parser.parse_args()
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    mode = 'hold' if args.hold else ('reactive-dash' if args.dash else 'reactive') if args.reactive else 'dash' if args.dash else 'orbit'
    if args.signature: mode += '-signature'
    if args.combat: mode += '-combat'
    if args.video: mode += '-video'
    out = ROOT/'builds'/f'serpent-escape-{sha[:8]}-{script_sha[:8]}'/f'{args.class_id}-{mode}'
    out.mkdir(parents=True, exist_ok=True)
    a = symbol_addresses(ROM)
    noi = ROM.with_suffix('.noi').read_text()
    for name in ('_serpent_tail_visible', '_serpent_tail_x', '_serpent_tail_y', '_entity_anim_counter'):
        a[name] = int(re.search(rf'DEF {name} 0x([0-9A-Fa-f]+)', noi)[1],16)
    select_rom_topology(ROM)
    pb, _, _ = boot_to_stage(ROM,a,1,'normal',args.class_id)
    report = dict(rom_sha256=sha,script_sha256=script_sha,class_id=args.class_id,
        fixture='Developer stage/sanctuary entry with prior PowerStone; initial sanctuary heal. No RAM writes after entry.',
        route=ROUTE,hold=args.hold,dash=args.dash,reactive=args.reactive,signature=args.signature,
        reaction_frames=12,combat=args.combat,video=args.video,trace=[],crossings=[])
    started = time.monotonic()
    encoder = None
    try:
        advance_to_sanctuary(pb,a,1)
        advance_to_boss(pb,a,1)
        en, pl = a['_entities'],a['_player']
        boss = next(en+i*28 for i in range(32) if pb.memory[en+i*28]==2
                    and pb.memory[en+i*28+1]&1 and pb.memory[en+i*28+20]&1)
        report['initial_player'] = list(pb.memory[pl:pl+24])
        report['initial_boss_hp'] = pb.memory[boss+14]
        if args.video:
            encoder = subprocess.Popen(['ffmpeg','-hide_banner','-loglevel','error','-y',
                '-f','rawvideo','-pixel_format','rgb24','-video_size','160x144',
                '-framerate','4194304/140448','-i','-','-an','-c:v','libx264',
                '-crf','12','-preset','fast','-pix_fmt','yuv420p','-movflags','+faststart',
                str(out/'replay.mp4')],stdin=subprocess.PIPE)
            report['video_sampling'] = 'Silent native frames 0,2,4,... at half GBC display rate; no speed adjustment.'
        previous, cycles, waypoint = pb.memory[boss+15],0,0
        held, steering = set(),set()
        defeated = False
        for frame in range(10000 if args.combat else 4800):
            x,y = pb.memory[pl+9],pb.memory[pl+11]
            tx,ty = ROUTE[waypoint]
            if abs(x-tx)<=2 and abs(y-ty)<=2:
                report['crossings'].append([frame,waypoint,x,y,pb.memory[pl+2]])
                waypoint = (waypoint+1)%len(ROUTE)
                tx,ty = ROUTE[waypoint]
            wanted = set()
            if not args.hold:
                if abs(y-ty)>2:
                    wanted.add('down' if y<ty else 'up')
                elif abs(x-tx)>2:
                    wanted.add('right' if x<tx else 'left')
            if args.reactive:
                if frame%12==0:
                    threats = [(pb.memory[boss+3]+16,pb.memory[boss+7]+16,24)]
                    for i in range(1,pb.memory[a['_serpent_tail_visible']]+1):
                        threats.append((pb.memory[a['_serpent_tail_x']+i]&248,
                                        pb.memory[a['_serpent_tail_y']+i]&248,16))
                    for i in range(32):
                        e=en+i*28
                        if pb.memory[e]==1 and pb.memory[e+1]&1 and not pb.memory[e+1]&16:
                            threats.append((pb.memory[e+3]+4,pb.memory[e+7]+4,12))
                    choices=[]
                    for dx,dy in ((0,0),(1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
                        nx,ny=x+dx*12,y+dy*12
                        if not (8<=nx<=200 and 8<=ny<=112): continue
                        cost=.02*(abs(nx-tx)+abs(ny-ty))
                        for hx,hy,radius in threats:
                            distance=max(abs(nx+8-hx),abs(ny+12-hy))/radius
                            if distance<3: cost+=1/max(.1,distance-.7)**2
                        choices.append((cost,dx,dy))
                    if choices:
                        _,dx,dy=min(choices)
                        steering=set()
                        if dx: steering.add('right' if dx>0 else 'left')
                        if dy: steering.add('down' if dy>0 else 'up')
                wanted=steering.copy()
            if args.dash and frame%96 in (*range(4),*range(8,12)):
                wanted.clear()
            if args.signature and (frame%48 in range(24,28) if args.combat else frame%48<4):
                wanted.add('b')
            if args.combat and frame%48<6:
                dx,dy=pb.memory[boss+3]+12-x-8,pb.memory[boss+7]+12-y-12
                wanted=set()
                if abs(dx)>abs(dy)//2 and dx: wanted.add('right' if dx>0 else 'left')
                if abs(dy)>abs(dx)//2 and dy: wanted.add('down' if dy>0 else 'up')
                wanted.add('a')
            for button in held-wanted: pb.button_release(button)
            for button in wanted-held: pb.button_press(button)
            held = wanted
            pb.tick()
            if encoder and frame%2==0:
                encoder.stdin.write(pb.screen.image.convert('RGB').tobytes())
            state = pb.memory[boss+15]
            hp = pb.memory[pl+2]
            screen = pb.memory[a['_loop_current_screen']]
            report['trace'].append([frame,hp,pb.memory[pl+9],pb.memory[pl+11],
                state,pb.memory[a['_serpent_tail_visible']],sorted(held),
                pb.memory[a['_entity_anim_counter']],screen,pb.memory[boss+14],
                pb.memory[pl+19],pb.memory[pl+20],pb.memory[pl+4],pb.memory[boss+2]])
            defeated=pb.memory[a['_run_state']+11]>=2
            if previous==2 and state==1: cycles+=1
            if state!=previous or frame%600==0:
                pb.screen.image.save(str(out/f'frame-{frame:04d}.png'))
            previous = state
            if not hp or screen!=5 or defeated or (not args.combat and cycles>=2): break
        report.update(cycles=cycles,final_hp=hp,frames=frame+1,
                      survived=bool(hp and cycles>=2),defeated=defeated,elapsed_s=time.monotonic()-started)
        print(f'[serpent-escape] class={args.class_id} hold={args.hold} cycles={cycles} hp={hp} frames={frame+1} crossings={len(report["crossings"])}')
        if args.combat:
            assert defeated and hp>0, 'controller did not defeat Serpent'
        elif not args.hold:
            assert cycles>=2 and hp>0, 'controller route did not survive two cycles'
            if not args.reactive:
                assert len(report['crossings'])>=8, 'route stalled before two complete circuits'
    finally:
        if encoder:
            encoder.stdin.close()
            assert encoder.wait()==0, 'video encoder failed'
        pb.stop(save=False)
        (out/'capture.json').write_text(json.dumps(report))


if __name__=='__main__':
    main()
