#!/usr/bin/env python3
"""Native moving BG tail, projectile OAM separation and menu/defeat cleanup."""
import hashlib
import json
import os
import re
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology, put16)

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get('QUINTRA_TEST_ROM', ROOT / 'rom/working/quintra.gbc'))


def attrs(pb):
    pb.memory[0xFF4F] = 1
    result = list(pb.memory[0x9800:0x9A20])
    pb.memory[0xFF4F] = 0
    return result


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    a = symbol_addresses(ROM)
    noi = ROM.with_suffix('.noi').read_text()
    for name in ('_serpent_tail_visible', '_serpent_tail_x', '_serpent_tail_y',
                 '_entity_anim_counter', '_serpent_body_dirty', '_serpent_tail_active'):
        match = re.search(rf'DEF {name} 0x([0-9A-Fa-f]+)', noi)
        if match:
            a[name] = int(match[1], 16)
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = ROOT / 'builds' / f'serpent-body-{sha[:8]}-{script_sha[:8]}'
    out.mkdir(parents=True, exist_ok=True)
    report = dict(rom_sha256=sha, script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), trace=[])
    select_rom_topology(ROM)
    pb, _, _ = boot_to_stage(ROM, a, 1, 'normal', 0)
    try:
        advance_to_sanctuary(pb, a, 1)
        advance_to_boss(pb, a, 1)
        en, pl = a['_entities'], a['_player']
        boss = next(en+i*28 for i in range(32) if pb.memory[en+i*28] == 2
                    and pb.memory[en+i*28+1]&1 and pb.memory[en+i*28+20]&1)
        put16(pb, pl+9, 72)
        put16(pb, pl+11, 112)
        for frame in range(2200):
            pb.memory[pl+2] = pb.memory[pl+1]
            pb.tick()
            length = pb.memory[a['_serpent_tail_visible']]
            report['trace'].append([frame, length, pb.memory[boss+15],
                                    pb.memory[a['_entity_anim_counter']]])
            if length >= 48:
                break
        assert length == 48, ('body did not reach 48 segments', length)
        points = [(pb.memory[a['_serpent_tail_x']+i], pb.memory[a['_serpent_tail_y']+i])
                  for i in range(49)]
        gaps = [abs(x-u)+abs(y-v) for (x,y),(u,v) in zip(points, points[1:])]
        report['full_body_points'] = points
        assert all(8 <= gap <= 10 for gap in gaps), ('disconnected sampled body', gaps)
        assert sum(gaps) >= 384, ('shortened route', sum(gaps))
        cells = {i for i, v in enumerate(attrs(pb)) if v == 6}
        report['full_body_cells'] = sorted(cells)
        assert len(cells) >= 38, ('full-grown body folded into an overlapping mass', len(cells))
        pb.screen.image.save(str(out / 'full-body.png'))
        tile_art = bytes(pb.memory[0x9370:0x9400])
        palette_index = pb.memory[0xFF68]
        palette_bytes = []
        for index in range(48, 56):
            pb.memory[0xFF68] = index
            palette_bytes.append(pb.memory[0xFF69])
        pb.memory[0xFF68] = palette_index
        palette = [palette_bytes[i] | palette_bytes[i+1] << 8 for i in range(0, 8, 2)]
        report['body_palette'] = palette
        assert palette == [6 | 7<<5 | 10<<10, 9 | 1<<5 | 4<<10,
                           23 | 3<<5 | 6<<10, 31 | 13<<5 | 10<<10], 'body lost blood-red palette'
        colors = [(tile_art[row] >> bit & 1) | ((tile_art[row+1] >> bit & 1) << 1)
                  for row in range(0, 144, 2) for bit in range(8)]
        report['body_pixel_counts'] = [colors.count(color) for color in range(4)]
        assert colors[:64].count(3) == 4 and colors[:64].count(1) == 4, 'missing lit and shaded dorsal scales'
        assert colors[:320].count(0) == 0, 'holes inside body or straight edges'
        assert [colors[i*64:(i+1)*64].count(0) for i in range(5,9)] == [3]*4, 'missing rounded outer corners'
        assert colors.count(2) >= 350, 'body texture overwhelms the broad base shade'
        for button in ('start', 'b'):
            pb.button(button)
            pb.tick(90)
        assert pb.memory[a['_loop_current_screen']] == 5
        report['menu_before_settle'] = dict(
            dirty=pb.memory[a['_serpent_body_dirty']],
            cells=[i for i,v in enumerate(attrs(pb)) if v==6])
        # LCD ticks can stop between trail simulation and its VRAM upload.
        pb.memory[boss+5] = 240
        pb.tick(6)
        assert bytes(pb.memory[0x9370:0x9400]) == tile_art, 'menu lost body atlas'
        expected = set()
        for i in range(1, 49):
            tx = pb.memory[a['_serpent_tail_x']+i] >> 3
            ty = pb.memory[a['_serpent_tail_y']+i] >> 3
            expected.update(y*32+x for y in (ty,) for x in (tx,)
                            if 0 < x < 27 and 0 < y < 16)
        restored = {i for i, v in enumerate(attrs(pb)) if v == 6}
        report['menu_body_cells'] = sorted(restored)
        assert restored == expected, ('menu lost moving body', sorted(expected-restored), sorted(restored-expected))

        pb.memory[boss+5] = 240
        pb.tick(6)
        settled = {i for i,v in enumerate(attrs(pb)) if v == 6}
        report['contour_tiles'] = []
        for cell in sorted(settled):
            top, bottom = cell-32 not in settled, cell+32 not in settled
            left, right = cell-1 not in settled, cell+1 not in settled
            variant = (5 if left else 6 if right else 1) if top else (
                (7 if left else 8 if right else 2) if bottom else (3 if left else 4 if right else 0))
            actual = pb.memory[0x9800+cell]
            report['contour_tiles'].append([cell,actual,55+variant])
            assert actual == 55+variant, ('stale or wrong contour',cell,actual,55+variant)
        pb.screen.image.save(str(out / 'contour-settled.png'))

        # Isolate twelve native boss shots from encounter FX and old volleys.
        report['player_before_projectile_fixture'] = list(pb.memory[pl:pl+24])
        put16(pb, pl+9, 192)
        put16(pb, pl+11, 112)
        pb.memory[boss+5] = 240
        put16(pb, boss+3, 32)
        put16(pb, boss+7, 32)
        for slot in range(32):
            e = en+slot*28
            if e != boss:
                for byte in range(28):
                    pb.memory[e+byte] = 0
        slots = [en+i*28 for i in range(32) if en+i*28 != boss][:12]
        for i, e in enumerate(slots):
            pb.memory[e] = 1
            pb.memory[e+1] = 0x87
            put16(pb, e+3, 40+(i%4)*24)
            put16(pb, e+7, 40+(i//4)*24)
            pb.memory[e+12] = 208
            pb.memory[e+13] = 4
            pb.memory[e+14] = 1
            pb.memory[e+16] = 150
            pb.memory[e+17] = 0
            pb.memory[e+18] = 2
            pb.memory[e+23] = 0xD0
            pb.memory[e+25] = 0x44
        pb.tick(4)
        oam = [list(pb.memory[0xFE00+i*4:0xFE04+i*4]) for i in range(40)]
        report['oam'] = oam
        assert all(40 <= oam[i][2] <= 51 for i in range(4, 16)), 'head OAM overwritten'
        assert sum(208 <= row[2] <= 223 and row[0] != 0 for row in oam[16:]) == 12, 'shots lost to body'
        assert not any(52 <= row[2] <= 53 and row[0] for row in oam), 'tail still consumes OAM'
        pb.screen.image.save(str(out / 'body-and-twelve-shots.png'))

        report['collision_probes'] = []
        for offset in (7, 8):
            for e in slots:
                pb.memory[e] = pb.memory[e+1] = 0
            put16(pb, boss+3, 128)
            put16(pb, boss+7, 24)
            pb.memory[boss+5] = 0
            pb.memory[boss+15] = 1
            pb.memory[boss+10] = 96
            pb.memory[boss+18] = 200
            pb.memory[a['_serpent_tail_x']] = 140
            pb.memory[a['_serpent_tail_y']] = 36
            for i in range(1, 49):
                pb.memory[a['_serpent_tail_x']+i] = 80
                pb.memory[a['_serpent_tail_y']+i] = 64
            pb.memory[a['_serpent_body_dirty']] = 1
            put16(pb, pl+9, 84+offset-8)
            put16(pb, pl+11, 68-12)
            pb.memory[pl+2] = 10
            pb.memory[pl+15] = pb.memory[pl+20] = 0
            pb.tick(3)
            hp = pb.memory[pl+2]
            report['collision_probes'].append([offset, hp])
            assert hp == (9 if offset == 7 else 10), ('body-edge collision', offset, hp)

        # Resolve a real lethal collision, including reward-slot reuse.
        pb.memory[boss+14] = 1
        pb.memory[boss+5] = 40
        shot = slots[0]
        for byte in range(28):
            pb.memory[shot+byte] = 0
        pb.memory[shot] = 1
        pb.memory[shot+1] = 0x17
        put16(pb, shot+3, pb.memory[boss+3])
        put16(pb, shot+7, pb.memory[boss+7])
        pb.memory[shot+14] = 1
        pb.memory[shot+16] = 40
        pb.memory[shot+25] = 0xDD
        pb.memory[shot+26] = 10
        report['defeat_frames'] = []
        for frame in range(32):
            pb.tick()
            active = pb.memory[a['_serpent_tail_active']]
            report['defeat_frames'].append([frame, pb.memory[boss], active])
            if not active:
                break
        assert pb.memory[boss] != 2, 'lethal collision did not retire boss'
        assert pb.memory[a['_serpent_tail_active']] == 0, 'Serpent renderer retained reward slot'
        assert not any(v == 6 for v in attrs(pb)), 'body remained after defeat'
        report['passed'] = True
        print('[serpent-body] PASS 48 segments, broad BG body, menu restore, 12 shots + head, defeat cleanup')
    finally:
        pb.stop(save=False)
        (out / 'capture.json').write_text(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
