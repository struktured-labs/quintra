#!/usr/bin/env python3
"""Check loaded native body tiles, retaining pixels and screenshots per ROM."""
import hashlib
import json
import os
from pathlib import Path
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology)

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get('QUINTRA_TEST_ROM', ROOT / 'rom/working/quintra.gbc'))


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    out = ROOT / 'builds' / f'boss-body-art-{sha[:8]}'
    out.mkdir(parents=True, exist_ok=True)
    select_rom_topology(ROM)
    a = symbol_addresses(ROM)
    records = []
    try:
        for stage in range(9):
            if stage in (0, 1, 3, 4, 5, 6, 7, 8):
                continue  # Moving bodies have dedicated native checks.
            pb, _, _ = boot_to_stage(ROM, a, stage, 'normal', 0)
            try:
                advance_to_sanctuary(pb, a, stage)
                advance_to_boss(pb, a, stage)
                pb.tick(8)
                raw = list(pb.memory[0x9380:0x9390])  # Signed BG tile 56.
                pixels = [[((raw[y*2] >> (7-x)) & 1)
                           + 2*((raw[y*2+1] >> (7-x)) & 1)
                           for x in range(8)] for y in range(8)]
                edges = sum(pixels[y][x] != pixels[y][x-1]
                            for y in range(8) for x in range(1, 8))
                edges += sum(pixels[y][x] != pixels[y-1][x]
                             for y in range(1, 8) for x in range(8))
                records.append(dict(stage=stage, raw=raw, pixels=pixels, edges=edges))
                pb.screen.image.save(str(out / f'boss-{stage+1}.png'))
                assert edges <= 8, (stage, 'repeating high-frequency body texture', edges)
                assert any(value for row in pixels for value in row), 'body erased'
                print(f'[boss-body-art] {stage+1}/9 quiet, nonempty native surface PASS', flush=True)
            finally:
                pb.stop(save=False)
    finally:
        (out / 'capture.json').write_text(json.dumps(dict(rom_sha256=sha,
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            fixture='Fresh boot; native boss entry; eight additional frames; no art injection.',
            records=records), indent=2))


if __name__ == '__main__':
    main()
