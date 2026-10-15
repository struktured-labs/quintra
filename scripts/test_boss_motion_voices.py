#!/usr/bin/env python3
"""Native encounter audio: movement must not fall back to the shared roar."""
import hashlib
import json
import os
import wave
from pathlib import Path

import numpy as np
from test_boss_identity import ROM, PL, addr, enter_boss


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    script = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    observed = os.environ.get('QUINTRA_VOICE_NO_HOOK') != '1'
    base = Path('builds') / f'boss-motion-voices-{sha[:8]}-{script[:8]}'
    out = base if observed else Path(str(base) + '-unobserved')
    out.mkdir(parents=True, exist_ok=True)
    records = []
    try:
        for stage, noise in ((0, 0x64), (3, 0x19), (5, 0x4B), (8, 0x6D)):
            pb, boss = enter_boss(stage, keep_open=True)
            trace, chunks, shared = [], [], []
            record = dict(stage=stage, trace=trace, shared_roars=shared)
            records.append(record)
            try:
                if observed:
                    entry = addr('_sfx_play')

                    def sfx(_):
                        if pb.register_file.A == 6:
                            shared.append(len(trace))

                    pb.hook_register(entry >> 16, entry & 0xFFFF, sfx, None)
                for frame in range(720):
                    pb.memory[PL + 2] = pb.memory[PL + 1]
                    pb.tick()
                    trace.append([frame, pb.memory[boss + 3], pb.memory[boss + 7],
                                  pb.memory[0xFF21], pb.memory[0xFF22]])
                    chunks.append(pb.sound.ndarray.copy())
                pcm = np.concatenate(chunks, axis=0)
                wav = out / f'stage-{stage}.wav'
                with wave.open(str(wav), 'wb') as audio:
                    audio.setnchannels(2)
                    audio.setsampwidth(2)
                    audio.setframerate(48000)
                    audio.writeframes((pcm.astype(np.int16) * 256).tobytes())
                assert not shared, ('shared movement roar', stage, shared)
                assert any(row[3:] == [0xB3, noise] for row in trace), ('missing voice', stage)
                assert len({tuple(row[1:3]) for row in trace}) >= 2, ('no movement', stage)
                assert pcm.max() > pcm.min(), ('silent audio', stage)
                if not observed:
                    assert wav.read_bytes() == (base / wav.name).read_bytes(), 'PCM observer effect'
                    parent = json.loads((base / 'capture.json').read_text())
                    assert trace == next(r['trace'] for r in parent['records'] if r['stage'] == stage)
                print('[motion-voice]', stage, 'PASS', flush=True)
            finally:
                pb.stop(save=False)
    finally:
        (out / 'capture.json').write_text(json.dumps(dict(
            rom_sha256=sha, script_sha256=script, observed=observed,
            fixture='stationary replenished-health player, natural phase-zero encounter',
            records=records), indent=2))


if __name__ == '__main__':
    main()
