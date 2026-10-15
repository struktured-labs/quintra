#!/usr/bin/env python3
"""Moving boss OBJ focus, including three phases and menu resume."""
import argparse
import hashlib
import json
from pathlib import Path
from test_boss_identity import ROM, ROOT, EN, PL, addr, enter_boss


def mural_cells(pb):
    bank = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 0
    cells = [(x,y) for y in range(17) for x in range(28)
             if 55 <= pb.memory[0x9800+y*32+x] <= 63]
    pb.memory[0xFF4F] = bank
    return cells


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', type=int, choices=(0,3,4,6,7,8), default=0)
    stage = parser.parse_args().stage
    large = stage in (3,4,7)
    tile_count = 24 if large else 16
    atlas_size = (48 if stage == 4 else tile_count) * 16
    name = {0:'crystal',3:'spider',4:'mire',6:'golem',7:'hydra',8:'void'}[stage]
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = ROOT / 'builds' / f'{name}-focus-{sha[:8]}-{script_sha[:8]}'
    out.mkdir(parents=True, exist_ok=True)
    record = dict(rom_sha256=sha, script_sha256=script_sha, trace=[])
    pb, boss = enter_boss(stage, keep_open=True)
    try:
        bank = pb.memory[0xFF4F]
        pb.memory[0xFF4F] = int(large)
        atlas = bytes(pb.memory[0x8280:0x8280+atlas_size])
        pb.memory[0xFF4F] = bank
        pixels = [(atlas[i] >> bit & 1) | ((atlas[i+1] >> bit & 1)<<1)
                  for i in range(0,atlas_size,2) for bit in range(8)]
        record['colors'] = [pixels.count(c) for c in range(4)]
        if stage == 8:
            def pixel(x, y):
                offset = ((y//8)*4+x//8)*16+(y%8)*2
                bit = 7-x%8
                return (atlas[offset] >> bit & 1) | ((atlas[offset+1] >> bit & 1)<<1)
            record['mantle_gap'] = [pixel(x,26) for x in range(12,20)]
            assert record['mantle_gap'] == [0]*8, 'Void still uses the solid Crystal torso'
            assert all(pixel(x,15) == 3 for x in range(8,24)), 'Void horizon mask missing'
        if stage == 3:
            assert pixels.count(3) >= 64 and pixels.count(2) >= 150, ('missing ice-leg planes',record['colors'])
        else:
            assert pixels.count(3) >= 100, ('missing broad body highlights', record['colors'])
        assert not mural_cells(pb), 'detached boss silhouette remains in arena'
        maximum = pb.memory[boss+23]
        poses = set()
        for phase in range(3):
            pb.memory[boss+14] = maximum >> phase
            visible, positions = 0, set()
            poster = False
            visible_streak = 0
            for frame in range(480):
                pb.memory[PL+2] = pb.memory[PL+1]
                pb.tick()
                oam = [list(pb.memory[0xFE00+i*4:0xFE04+i*4]) for i in range(40)]
                tiles = [r for r in oam if 40 <= r[2] < (88 if stage == 4 else 40+tile_count) and r[0]
                         and bool(r[3]&8) == large]
                visible += len(tiles) == tile_count
                if large and len(tiles) == tile_count:
                    base = min(r[2] for r in tiles)
                    assert base in ((40,64) if stage == 4 else (40,))
                    poses.add(base)
                    assert sorted(r[2] for r in tiles) == list(range(base,base+24)), 'large atlas repeated or missing tiles'
                    anchor = next(r for r in tiles if r[2] == base)
                    width = 4 if stage == 4 else 6
                    for row in tiles:
                        offset = row[2]-base
                        assert (row[1]-anchor[1])%256 == offset%width*8, (phase,frame,anchor,row,tiles)
                        assert (row[0]-anchor[0])%256 == offset//width*8, (phase,frame,anchor,row,tiles)
                positions.add((pb.memory[boss+3],pb.memory[boss+7]))
                assert not mural_cells(pb), (phase,frame,'projection returned')
                record['trace'].append([phase,frame,pb.memory[boss+3],pb.memory[boss+7],len(tiles)])
                on_camera = sum(8 <= r[0] < 152 and 1 <= r[1] < 168 for r in tiles)
                visible_streak = visible_streak+1 if len(tiles) == tile_count and on_camera >= (18 if large else 12) else 0
                if frame >= 120 and not poster and visible_streak >= 3:
                    pb.screen.image.save(str(out / f'phase-{phase}.png'))
                    record.setdefault('poster_frames', {})[phase] = frame
                    poster = True
            assert poster, (phase,'no clear on-camera body frame')
            assert visible >= 360, (phase,'moving boss vanished excessively',visible)
            if phase == 0 and stage == 0:
                assert len(positions) >= 3 and max(x for x,y in positions)-min(x for x,y in positions) >= 72
            elif phase == 0 and stage == 3:
                assert len(positions) >= 2 and max(abs(x-a)+abs(y-b)
                    for x,y in positions for a,b in positions) >= 32, 'Spider did not blink to a distinct flank'
            elif phase == 0 and stage == 8:
                assert {(40,32),(104,32),(160,64),(104,40)} <= positions, 'Void did not visit its four warp anchors'
            else:
                assert len(positions) >= 8, (phase,'moving body stalled',len(positions))
        if stage == 4:
            assert poses == {40,64}, 'Mire heart never contracts'
        pb.button_press('start')
        record['menu_entry'] = []
        for frame in range(60):
            pb.tick()
            screen = pb.memory[addr('_loop_current_screen')]
            record['menu_entry'].append([frame,screen,pb.memory[PL+2]])
            if screen == 9:
                pb.button_release('start')
                break
        else:
            raise AssertionError(('menu did not open',record['menu_entry']))
        pb.tick(8)
        pb.button_press('b')
        for _ in range(60):
            pb.tick()
            if pb.memory[addr('_loop_current_screen')] == 5:
                pb.button_release('b')
                break
        else:
            raise AssertionError('menu did not close')
        pb.tick(60)
        assert pb.memory[addr('_loop_current_screen')] == 5
        assert not mural_cells(pb), 'menu restored detached boss silhouette'
        pb.memory[0xFF4F] = int(large)
        assert bytes(pb.memory[0x8280:0x8280+atlas_size]) == atlas, 'menu lost boss art'
        pb.memory[0xFF4F] = 0
        pb.screen.image.save(str(out / 'menu-resume.png'))
        record['passed'] = True
        print(f'[{name}-focus] PASS broad native facets, moving body in three phases, no murals, menu restoration')
    finally:
        pb.stop(save=False)
        (out / 'capture.json').write_text(json.dumps(record))


if __name__ == '__main__':
    main()
