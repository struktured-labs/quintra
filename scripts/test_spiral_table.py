#!/usr/bin/env python3
"""Exhaustive signed-rounding check for the compiled spiral lookup table."""
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    source = (ROOT / 'src/game/boss_projectile.c').read_text()
    sine = [int(n) for n in re.findall(r'-?\d+', re.search(
        r'sine\[32\] = \{(.*?)\};', source, re.S)[1])]
    table = [int(n) for n in re.findall(r'-?\d+', re.search(
        r'spiral_offset\[25\]\[32\] = \{(.*?)\};', source, re.S)[1])]
    expected = [v * radius // 16 for radius in range(25) for v in sine]
    assert len(sine) == 32 and len(table) == 800
    assert table == expected, 'signed rounding or radius changed'
    rom = (ROOT / 'rom/working/quintra.gbc').read_bytes()
    encoded = bytes(v & 255 for v in expected)
    bank = rom[15 * 0x4000:16 * 0x4000]
    assert bank.count(encoded) == 1, 'exact lookup missing from compiled bank 15'
    offset = bank.index(encoded)
    mutated = bytearray(bank)
    mutated[offset + 799] ^= 1
    assert encoded not in mutated, 'corrupted-table negative control passed'
    sha = hashlib.sha256(rom).hexdigest()
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = dict(rom_sha256=sha, script_sha256=script_sha,
                  entries=800, bank=15, offset=offset,
                  signed_rounding_exact=True, mutation_rejected=True,
                  scope='exhaustive compiled table; native trajectories tested separately')
    out = ROOT / 'tmp' / f'spiral-table-{sha[:8]}-{script_sha[:8]}.json'
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n')
    print('[spiral-table] PASS all 800 compiled offsets, including negative rounding')


if __name__ == '__main__':
    main()
