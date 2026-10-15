#!/usr/bin/env python3
"""Native projected-body cleanup after lethal collision and menu redraw."""
import hashlib
import json
from pathlib import Path
from test_boss_identity import ROM, ROOT, EN, PL, RS, TM, addr, enter_boss, put16


def projection_count(pb):
    bank = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 0
    count = sum(55 <= pb.memory[0x9800+y*32+x] <= 63
                for y in range(17) for x in range(28))
    pb.memory[0xFF4F] = bank
    return count


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = ROOT / 'builds' / f'boss-defeat-{sha[:8]}-{script_sha[:8]}'
    out.mkdir(parents=True, exist_ok=True)
    report = dict(rom_sha256=sha, script_sha256=script_sha, records=[])
    screen = addr('_loop_current_screen')
    try:
        for stage in range(9):
            pb, boss = enter_boss(stage, keep_open=True)
            r = dict(stage=stage, trace=[])
            report['records'].append(r)
            try:
                r['initial_projection_cells'] = projection_count(pb)
                if stage in (0, 3, 4, 5, 6, 7, 8):
                    assert r['initial_projection_cells'] == 0, 'Moving boss still has a detached mural'
                    r['entry_oam_trace'] = []
                    stable = 0
                    for frame in range(60):
                        large = stage in (3,4,7)
                        tile_count = 24 if large else 16
                        count = sum(40 <= pb.memory[0xFE02+i*4] < 40+tile_count
                                    and pb.memory[0xFE00+i*4] != 0
                                    and bool(pb.memory[0xFE03+i*4]&8) == large for i in range(40))
                        r['entry_oam_trace'].append([frame,count,pb.memory[boss+24]])
                        stable = stable+1 if count == tile_count else 0
                        if stable >= 3:
                            break
                        pb.memory[PL+2] = pb.memory[PL+1]
                        pb.tick()
                    else:
                        raise AssertionError((stage,'no complete moving body before defeat'))
                elif stage == 2:
                    assert r['initial_projection_cells'] == 0, 'Kilnback still has a detached mural'
                else:
                    assert r['initial_projection_cells'] > 0, (stage, 'missing live body')
                pb.screen.image.save(str(out / f'{stage}-before.png'))
                before = list(pb.memory[TM:TM+340])
                r['initial_targetable'] = bool(pb.memory[boss+1]&4)
                r['lethal_fixture'] = 'one HP, final generic phase, frozen exposed collision anchor'
                pb.memory[boss+14] = 1
                pb.memory[boss+2] = 3
                pb.memory[boss+5] = 240
                pb.tick(4)
                r['settled_anchor'] = list(pb.memory[boss:boss+28])
                pb.memory[boss+1] |= 4
                pb.memory[boss+25] = 0xEE
                for i in range(32):
                    e = EN+i*28
                    if e != boss:
                        for j in range(28):
                            pb.memory[e+j] = 0
                shot = EN if EN != boss else EN+28
                pb.memory[shot] = 1
                pb.memory[shot+1] = 0x17
                put16(pb, shot+3, pb.memory[boss+3])
                put16(pb, shot+7, pb.memory[boss+7])
                pb.memory[shot+14] = 1
                pb.memory[shot+16] = 120
                pb.memory[shot+25] = 0xEE
                pb.memory[shot+26] = 10
                put16(pb, PL+9, 32)
                put16(pb, PL+11, 112)
                for frame in range(120):
                    pb.tick()
                    count = projection_count(pb) if pb.memory[screen] == 5 else -1
                    map_count = sum(55 <= v <= 63 for v in pb.memory[TM:TM+340])
                    r['trace'].append([frame,pb.memory[RS+11],pb.memory[screen],count,map_count])
                    if pb.memory[RS+11] == stage+1 and count == 0 and map_count == 0:
                        break
                else:
                    raise AssertionError((stage, 'body survived defeat', r['trace'][-1]))
                for y in range(1,16):
                    for x in range(1,19):
                        old = before[y*20+x]
                        if not 55 <= old <= 63:
                            assert pb.memory[TM+y*20+x] == old, (stage,x,y,'unrelated terrain changed')
                r['cleanup_frame'] = frame
                if stage < 8:
                    pb.tick(20)
                    if stage in (3,4,7):
                        assert not any(pb.memory[0xFE00+i*4] and pb.memory[0xFE03+i*4]&8
                                       for i in range(40)), 'large boss survived death in OAM'
                    assert projection_count(pb) == 0
                    pb.screen.image.save(str(out / f'{stage}-after.png'))
                    r['menu_trace'] = []
                    pb.button_press('start')
                    for menu_frame in range(120):
                        pb.tick()
                        r['menu_trace'].append([menu_frame,pb.memory[screen]])
                        if pb.memory[screen] == 9:
                            break
                    pb.button_release('start')
                    assert pb.memory[screen] == 9
                    pb.tick(4)
                    pb.button_press('b')
                    for menu_frame in range(120):
                        pb.tick()
                        r['menu_trace'].append([120+menu_frame,pb.memory[screen]])
                        if pb.memory[screen] == 5:
                            break
                    pb.button_release('b')
                    pb.tick(4)
                    assert pb.memory[screen] == 5
                    assert projection_count(pb) == 0, (stage, 'menu restored dead projection')
                    assert list(pb.memory[TM+9:TM+11]) == [3,3]
                    assert pb.memory[addr('_music_track_id')] == 19
                    pb.screen.image.save(str(out / f'{stage}-menu-resume.png'))
                else:
                    pb.screen.image.save(str(out / f'{stage}-cleanup-boundary.png'))
                r['passed'] = True
                print(f'[boss-defeat-art] {stage+1}/9 body clears by frame {frame}',flush=True)
            finally:
                pb.stop(save=False)
        report['passed'] = True
    finally:
        (out / 'capture.json').write_text(json.dumps(report))


if __name__ == '__main__':
    main()
