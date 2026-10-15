#!/usr/bin/env python3
"""Read native HUD tiles/palettes across Reaper link phases and menu resume."""
import hashlib
import json
from pathlib import Path
from test_reaper_link import ROM, ROOT, enter

ROWS = {
    'warning': [8,81,77,91,88,8],
    'linked': [91,89,8,84,79,88],
    'exposed': [84,79,79,84,94,88],
}
COLORS = {
    'warning': [(0,0,0),(12,8,2),(24,15,3),(31,25,8)],
    'linked': [(0,0,0),(9,5,14),(18,8,24),(27,15,31)],
    'exposed': [(0,0,0),(5,11,7),(12,22,10),(18,31,13)],
}


def row(pb):
    bank = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 0
    result = list(pb.memory[0x9C0A:0x9C10])
    pb.memory[0xFF4F] = bank
    return result


def palette(pb):
    old = pb.memory[0xFF68]
    raw = []
    for offset in range(8):
        pb.memory[0xFF68] = 40+offset
        raw.append(pb.memory[0xFF69])
    pb.memory[0xFF68] = old
    return [raw[i] | raw[i+1]<<8 for i in range(0,8,2)]


def pose(pb):
    bank = pb.memory[0xFF4F]
    pb.memory[0xFF4F] = 0
    result = list(pb.memory[0x8280:0x8380])
    pb.memory[0xFF4F] = bank
    return result


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = ROOT / 'builds' / ('reaper-cues-'+sha[:8]+'-'+script_sha[:8])
    out.mkdir(parents=True, exist_ok=True)
    report = dict(rom_sha256=sha, script_sha256=script_sha,
                  trace=[], observed={})
    pb, a, boss = enter()
    try:
        pl = a['_player']
        previous = None
        visible_streak = 0
        for frame in range(650):
            pb.memory[pl+2] = pb.memory[pl+1]
            pb.tick()
            clock = pb.memory[a['_boss_phase_clock']]
            linked = pb.memory[a['_boss_link_active']]
            tiles = row(pb)
            stable = tiles == previous
            previous = tiles
            visible = sum(0 < pb.memory[0xFE00+i*4] < 152
                          and 0 < pb.memory[0xFE01+i*4] < 168
                          and 40 <= pb.memory[0xFE02+i*4] < 56 for i in range(40))
            visible_streak = visible_streak+1 if visible == 16 and stable else 0
            report['trace'].append([frame, clock, linked, tiles, visible])
            for name, expected in ROWS.items():
                if visible_streak < 3 or tiles != expected or name in report['observed']:
                    continue
                colors = palette(pb)
                assert colors == [r+(g<<5)+(b<<10) for r,g,b in COLORS[name]], (name,colors)
                assert pb.memory[0xFF4A] == 136, 'cue displaced bottom HUD'
                old_bank = pb.memory[0xFF4F]
                pb.memory[0xFF4F] = 0
                hearts = list(pb.memory[0x9C00:0x9C08])
                pb.memory[0xFF4F] = old_bank
                assert all(tile in (4,5,6,8) for tile in hearts), ('cue overwrote hearts', hearts)
                if name == 'warning':
                    assert 96 <= clock <= 128 and not linked
                elif name == 'linked':
                    assert linked and 128 <= clock <= 224
                else:
                    assert not linked
                pb.screen.image.save(str(out / (name+'.png')))
                report['observed'][name] = dict(frame=frame, palette=colors, pose=pose(pb))
            if len(report['observed']) == 3 and linked and 144 <= clock < 170:
                break
        assert set(report['observed']) == set(ROWS), report['observed']
        poses = [v['pose'] for v in report['observed'].values()]
        for i in range(3):
            for j in range(i+1,3):
                assert sum(a != b for a,b in zip(poses[i],poses[j])) >= 30, 'boss pose did not change'
        pb.button('start')
        pb.tick(20)
        assert pb.memory[a['_loop_current_screen']] == 9
        pb.button('b')
        for frame in range(30):
            pb.memory[pl+2] = pb.memory[pl+1]
            pb.tick()
            if pb.memory[a['_loop_current_screen']] == 5 and row(pb) == ROWS['linked']:
                break
        else:
            raise AssertionError('menu resume lost the active link instruction')
        for frame in range(24):
            pb.tick()
            extrema = pb.screen.image.convert('RGB').getextrema()
            if frame >= 7 and max(hi-lo for lo,hi in extrema) > 64:
                break
        else:
            raise AssertionError('menu resume never displayed a nonblank game frame')
        assert pb.memory[a['_loop_current_screen']] == 5 and row(pb) == ROWS['linked']
        assert pose(pb) == report['observed']['linked']['pose'], 'menu lost linked boss pose'
        pb.screen.image.save(str(out / 'menu-resume.png'))
        report['menu_resume'] = row(pb)
        report['passed'] = True
        print('[reaper-cues] PASS native warning/link/exposed text, palettes, distinct poses and menu resume')
    finally:
        pb.stop(save=False)
        (out / 'capture.json').write_text(json.dumps(report))


if __name__ == '__main__':
    main()
