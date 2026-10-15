#!/usr/bin/env python3
"""Source-bound, current-ROM acceptance run for the boss overhaul."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    rom = ROOT / 'rom/working/quintra.gbc'
    sha = digest(rom)
    suite = [
        ('test_spiral_table.py', []), ('test_boss_projectiles.py', []),
        ('test_boss_projectile_art.py', []), ('test_boss_volley_patterns.py', []),
        ('test_boss_phases.py', []), ('test_boss_area_warning.py', []),
        ('test_mire_ring.py', []), ('test_boss_summons.py', []),
        ('test_colossus_signatures.py', []), ('test_colossal_cinder.py', []),
        ('test_colossal_serpent.py', []), ('test_reaper_link.py', []),
        ('test_reaper_cues.py', []), ('test_reaper_controller.py', []),
        ('test_boss_defeat_art.py', []), ('test_boss_body_art.py', []),
        *[('test_crystal_focus.py', ['--stage', str(stage)]) for stage in (0,3,4,6,7,8)],
        ('test_enemy_patterns.py', []), ('test_boss_dense_performance.py', []),
        ('test_serpent_performance.py', []), ('test_performance.py', []),
        ('test_boss_voices.py', []), ('test_boss_motion_voices.py', []),
    ]
    started = time.monotonic()
    out = ROOT / 'builds' / f'boss-acceptance-{sha[:8]}-{time.time_ns()}'
    out.mkdir(parents=True)
    report = dict(rom_sha256=sha, runner_sha256=digest(Path(__file__)),
                  complete=False, passed=False, checks=[])
    try:
        for index, (script, args) in enumerate(suite + suite[-2:]):
            env = os.environ.copy()
            unobserved = index >= len(suite)
            if unobserved: env['QUINTRA_VOICE_NO_HOOK'] = '1'
            else: env.pop('QUINTRA_VOICE_NO_HOOK', None)
            assert digest(rom) == sha, 'ROM changed during acceptance'
            tick = time.monotonic()
            result = subprocess.run([sys.executable, str(ROOT/'scripts'/script), *args],
                cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            log = f'{index:02}-{Path(script).stem}.log'
            (out/log).write_text(result.stdout)
            report['checks'].append(dict(script=script, args=args, unobserved=unobserved,
                script_sha256=digest(ROOT/'scripts'/script), returncode=result.returncode,
                elapsed_s=time.monotonic()-tick, log=log))
            print(f'[{index+1}/{len(suite)+2}] {script} {args}: {result.returncode}', flush=True)
            if result.returncode: print(result.stdout, flush=True)
        assert digest(rom) == sha, 'ROM changed during acceptance'
        report['complete'] = True
        report['passed'] = all(row['returncode'] == 0 for row in report['checks'])
    finally:
        report['elapsed_s'] = time.monotonic()-started
        (out/'report.json').write_text(json.dumps(report, indent=2))
        print(out, flush=True)
    assert report['passed'], 'acceptance contains failures; inspect retained logs'


if __name__ == '__main__':
    main()
