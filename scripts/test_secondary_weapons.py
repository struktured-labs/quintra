#!/usr/bin/env python3
"""Live B-input tests; inventory/arena are staged, weapon logic is native."""
import hashlib
import json
from pathlib import Path
from test_will_max import ROM, PLAYER as P, ENTITIES as E, TILEMAP as T, boot, clear_arena, put16, press, addr

sha=hashlib.sha256(ROM.read_bytes()).hexdigest()
script_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
out=Path('builds')/f'secondaries-{sha[:8]}-{script_sha[:8]}'
out.mkdir(parents=True,exist_ok=True)
records=[]

def scene(item):
    pb=boot(0)
    clear_arena(pb)
    pb.memory[addr('_entity_enemy_count')]=0
    pb.memory[addr('_room_world_width')]=160
    pb.memory[addr('_room_world_height')]=136
    pb.memory[P+24]=item
    pb.memory[P+18]=item
    pb.memory[P+19]=0
    pb.memory[P+13]=1
    put16(pb,P+9,24); put16(pb,P+11,64)
    pb.tick(8)
    return pb

def shots(pb,marker):
    return [E+i*28 for i in range(32) if pb.memory[E+i*28]==1
            and pb.memory[E+i*28+1]&1 and pb.memory[E+i*28+23]==marker]

def fire(pb):
    pb.button_press('b'); pb.tick(3); pb.button_release('b')

def boomerang():
    pb=scene(45)
    try:
        fire(pb)
        points=[]
        for f in range(130):
            live=shots(pb,0xF4)
            if not live: break
            assert len(live)==1
            e=live[0]
            points.append([f,pb.memory[e+3],pb.memory[e+15]])
            pb.tick()
        assert points and max(x for _,x,_ in points)>=105,points
        assert not shots(pb,0xF4),'return missed the player'
        assert any(state for _,_,state in points),'never returned'
        records.append(dict(case='boomerang',trace=points))
    finally: pb.stop(save=False)

def hook():
    pb=scene(46)
    try:
        for y in range(1,16): pb.memory[T+y*20+14]=21
        fire(pb)
        positions=[]; latched=False
        for f in range(140):
            live=shots(pb,0xF5)
            positions.append(pb.memory[P+9])
            if live and pb.memory[live[0]+15]==1:
                latched=True
                pb.screen.image.save(str(out/'hook-wall.png'))
            assert pb.memory[P+9]+13<112,'hook pulled body inside pillar'
            pb.tick()
        assert latched and max(positions)>64,positions
        assert not shots(pb,0xF5),'hook never returned'
        records.append(dict(case='hook-wall',positions=positions))
    finally: pb.stop(save=False)

def heavy(item,marker):
    pb=scene(item)
    try:
        put16(pb,P+9,72)
        pb.memory[P+4]=5
        fire(pb)
        points=[]; splash=False
        for f in range(120):
            live=shots(pb,marker)
            if live:
                e=live[0]; points.append([pb.memory[e+3],pb.memory[e+7]])
                if f==14: pb.screen.image.save(str(out/f'{item}.png'))
            splash |= bool(shots(pb,0xF2))
            pb.tick()
        if item==47:
            assert max(x for x,y in points)-min(x for x,y in points)>=44,points
            assert max(y for x,y in points)-min(y for x,y in points)>=44,points
            assert pb.memory[P+4]==5
        else:
            assert splash,'bomb never exploded'
            assert pb.memory[P+4]==4,'bomb must cost exactly one MP'
            assert len(set(map(tuple,points)))==1,'neutral bomb was not dropped'
        assert not shots(pb,marker)
        records.append(dict(case=str(item),points=points,splash=splash))
    finally: pb.stop(save=False)

def hook_enemy():
    pb=scene(46)
    try:
        e=E
        for off,val in {0:2,1:7,12:32,14:80,17:0,25:0x66,26:1}.items(): pb.memory[e+off]=val
        put16(pb,e+3,104); put16(pb,e+7,68)
        pb.memory[addr('_entity_enemy_count')]=1
        fire(pb)
        latched=False
        for _ in range(100):
            pb.memory[addr('_enemy_status_kind')]=4
            pb.memory[addr('_enemy_status_ticks')]=20
            pb.memory[addr('_status_enemy_active')]=1
            pb.tick()
            live=shots(pb,0xF5)
            latched |= any(pb.memory[s+22]==1 for s in live)
        assert latched and pb.memory[P+9]>60,'hook did not pull toward monster'
        assert pb.memory[e+14]==80,'hook was an unintended damaging bullet'
    finally: pb.stop(save=False)

def thrown_bomb():
    pb=scene(48)
    try:
        pb.memory[P+4]=5
        pb.button_press('right'); fire(pb); pb.button_release('right')
        xs=[]
        for _ in range(90):
            live=shots(pb,0xF7)
            if live: xs.append(pb.memory[live[0]+3])
            pb.tick()
        assert xs and max(xs)-min(xs)>=24,('throw range',xs)
        assert pb.memory[P+4]==4
        pb.memory[P+4]=0; pb.memory[P+19]=0
        fire(pb)
        assert not shots(pb,0xF7),'empty MP produced a free bomb'
    finally: pb.stop(save=False)

def bomb_damage():
    pb=scene(48)
    try:
        pb.memory[P+4]=5
        e=E
        for off,val in {0:2,1:7,12:32,14:80,17:0,25:0x66,26:1}.items(): pb.memory[e+off]=val
        put16(pb,e+3,40); put16(pb,e+7,68)
        pb.memory[addr('_entity_enemy_count')]=1
        fire(pb)
        exploded=False
        for _ in range(110):
            pb.memory[addr('_enemy_status_kind')]=4
            pb.memory[addr('_enemy_status_ticks')]=20
            pb.memory[addr('_status_enemy_active')]=1
            pb.tick()
            if shots(pb,0xF7):
                assert pb.memory[e+14]==80,'bomb damaged enemy before detonation'
            else:
                exploded=True
        assert exploded and pb.memory[e+14]<80,'blast did not damage nearby monster'
        records.append(dict(case='bomb-damage',remaining_hp=pb.memory[e+14]))
    finally: pb.stop(save=False)

def menu():
    pb=scene(45)
    try:
        for i in range(4): pb.memory[P+24+i]=45+i
        pb.memory[P+18]=10
        press(pb,'start'); pb.tick(12); press(pb,'select'); pb.tick(12)
        for item in (45,46,47,48,10):
            press(pb,'down'); pb.tick(6)
            assert pb.memory[P+18]==item,(item,pb.memory[P+18])
            pb.screen.image.save(str(out/f'kit-{item}.png'))
        press(pb,'b'); pb.tick(30)
        assert pb.memory[addr('_loop_current_screen')]==5
    finally: pb.stop(save=False)

def purchases():
    from test_shop_surge import boot_shop, buy, inventory, shop_wares, PL
    for seed,ware,item,price in ((42,19,46,35),(48,20,47,30),(54,21,48,30)):
        pb=boot_shop(seed)
        try:
            shelf=shop_wares(pb)[ware]
            assert pb.memory[shelf+19]==price
            buy(pb,ware)
            assert item in inventory(pb),(ware,'purchase lost')
            coins=pb.memory[PL+16]|pb.memory[PL+17]<<8
            assert coins==99-price,(ware,coins)
        finally: pb.stop(save=False)

try:
    boomerang(); hook(); hook_enemy(); heavy(47,0xF6); heavy(48,0xF7); thrown_bomb(); bomb_damage(); menu(); purchases()
    print('[secondaries] PASS long return, wall grapple, orbit, timed bomb and menu selection')
finally:
    (out/'capture.json').write_text(json.dumps(dict(rom_sha256=sha,script_sha256=script_sha,records=records),indent=2))
