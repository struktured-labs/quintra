#!/usr/bin/env python3
"""Native health-phase previews, transition cards and selected-fight audio."""
import hashlib
import html
import json
import re
import subprocess
import wave
from pathlib import Path
from importlib.metadata import version
import numpy as np
from capture_boss_gallery import NAMES
from make_stage_states import (boot_to_stage, advance_to_sanctuary, advance_to_boss,
                               symbol_addresses, select_rom_topology, put16)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / 'rom/working/quintra.gbc'
FPS = 4194304 / 70224
STRIDE = 2


def capture(pb, a, boss, frames, out, key, stop=None):
    video = out / (key+'-silent.mp4')
    encoder = subprocess.Popen(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', '160x144',
        '-framerate', str(FPS/STRIDE), '-i', '-', '-an', '-c:v', 'libx264',
        '-crf', '12', '-preset', 'fast', '-pix_fmt', 'yuv420p', str(video)], stdin=subprocess.PIPE)
    trace, chunks, mechanics = [], [], []
    stopped = False
    try:
        for frame in range(frames):
            pl = a['_player']
            pb.memory[pl+2] = pb.memory[pl+1]
            pb.tick()
            assert pb.memory[a['_loop_current_screen']] == 5, (key, frame, 'left gameplay')
            assert pb.memory[boss] == 2, (key, frame, 'boss retired')
            chunks.append(pb.sound.ndarray.copy())
            trace.append([frame, pb.memory[boss+14], pb.memory[boss+2],
                          pb.memory[boss+5], pb.memory[boss+6],
                          pb.memory[boss+3], pb.memory[boss+7], pb.memory[boss+15]])
            mechanics.append([frame, *[pb.memory[a[name]] for name in
                ('_cinder_phase', '_cinder_pattern', '_boss_phase_clock', '_boss_link_active')]])
            if frame % STRIDE == 0:
                picture = pb.screen.image.convert('RGB')
                encoder.stdin.write(picture.tobytes())
                if frame == 0 or frame == frames//2:
                    picture.save(str(out / (key+'.png')))
            if stop is not None and stop():
                stopped = True
                break
    finally:
        encoder.stdin.close()
        assert encoder.wait() == 0, key
    pcm = np.concatenate(chunks, axis=0)
    wav = out / (key+'.wav')
    with wave.open(str(wav), 'wb') as audio:
        audio.setnchannels(2)
        audio.setsampwidth(2)
        audio.setframerate(48000)
        audio.writeframes((pcm.astype(np.int16)*256).tobytes())
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-i', str(video), '-i', str(wav), '-c:v', 'copy', '-c:a', 'aac',
        '-b:a', '192k', '-movflags', '+faststart', str(out / (key+'.mp4'))], check=True)
    return dict(key=key, trace=trace, mechanics=mechanics,
                mechanic_columns=['frame', 'cinder_phase', 'cinder_pattern',
                                  'boss_phase_clock', 'boss_link_active'],
                frames=len(trace), requested_frames=frames,
                event_completed=stopped, samples=len(pcm),
                pcm_min=int(pcm.min()), pcm_max=int(pcm.max()))


def special_cards(stage, a, out):
    pb, _, _ = boot_to_stage(ROM, a, stage, 'normal', 0)
    records = []
    try:
        advance_to_sanctuary(pb, a, stage)
        advance_to_boss(pb, a, stage)
        en, pl = a['_entities'], a['_player']
        boss = next(en+i*28 for i in range(32) if pb.memory[en+i*28]==2
                    and pb.memory[en+i*28+1]&1 and pb.memory[en+i*28+20]&1)
        maximum = pb.memory[boss+23] or pb.memory[boss+14]
        put16(pb, pl+9, 104)
        put16(pb, pl+11, 112)

        def clip(key, label, limit, stop):
            record = capture(pb, a, boss, limit, out, key, stop)
            record.update(stage=stage, label=label, event_card=True)
            records.append(record)
            assert record['event_completed'], (key, 'event did not complete', record['frames'])

        if stage == 1:
            for state, label, limit in ((0,'Growth and first coil',2400),
                    (1,'Charged pursuit',500),(2,'Full-length unwind',1800)):
                assert pb.memory[boss+15] == state
                clip(f'serpent-state-{state}',label,limit,lambda: pb.memory[boss+15]!=state)
        elif stage == 2:
            cp, pattern = a['_cinder_phase'], a['_cinder_pattern']
            for i,label in enumerate(('Crucible Wheel','Kiln Press','Brandwalk','Broken Cadence')):
                assert pb.memory[cp]==0 and pb.memory[pattern]==i
                clip(f'cinder-pack-{i}','Kilnbacks · '+label,1000,lambda: pb.memory[pattern]!=i)
            pb.memory[boss+14] = maximum//2
            clip('cinder-transform','Metamorphosis',800,lambda: pb.memory[cp]==2)
            for i,label in enumerate(('Furnace Breath','Slag Spit','Kiln Stomp','Rex Charge')):
                assert pb.memory[cp]==2 and pb.memory[pattern]==i
                clip(f'cinder-rex-{i}','Cinder Rex · '+label,1000,lambda: pb.memory[pattern]!=i)
            pb.memory[boss+14] = 40
            seen=set()
            def recombined():
                phase=pb.memory[cp]
                seen.add(phase)
                return 3 in seen and phase==2
            clip('cinder-fire-reprise','Fire-pack reprise and recombination',800,recombined)
        elif stage == 5:
            pb.memory[boss+14] = maximum//2
            clock=a['_boss_phase_clock']
            for _ in range(700):
                pb.memory[pl+2]=pb.memory[pl+1]
                pb.tick()
                if 96<=pb.memory[clock]<128:
                    break
            else:
                raise AssertionError('Reaper warning did not begin')
            clip('reaper-link-warning','Damage link · warning',300,lambda: pb.memory[a['_boss_link_active']]!=0)
            clip('reaper-linked','Damage link · linked',500,lambda: pb.memory[a['_boss_link_active']]==0)
            clip('reaper-exposed','Damage link · exposed',600,lambda: 96<=pb.memory[clock]<128)
        return records
    finally:
        pb.stop(save=False)


def page(out, sha, records):
    sections = []
    for stage, name in enumerate(NAMES):
        cards = []
        for r in records:
            if r['stage'] != stage:
                continue
            label = html.escape(r['label'])
            key = r['key']
            cards.append(f'<article><h3>{label}</h3><video muted loop playsinline preload="metadata" '
                         f'poster="{key}.png" src="{key}.mp4"></video>'
                         f'<button class="focus">Enlarge + audio</button>'
                         f'<button class="flag" aria-pressed="false">☆ Needs work</button></article>')
        sections.append(f'<section><h2>{stage+1:02} · {html.escape(name)}</h2><div class="cards">'
                        + ''.join(cards) + '</div></section>')
    (out / 'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Quintra · Boss phases</title>
<style>
:root{color-scheme:dark;font-family:system-ui;background:#10121b;color:#e5eaf5}
body{max-width:1400px;margin:auto;padding:24px}h1,h2{color:#f5cc80}h3{font-size:15px;margin:12px}
p{max-width:1000px;line-height:1.6;color:#adb8d0}a{color:#9ed7ff}
.cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px}
article{border:1px solid #3e4963;border-radius:10px;overflow:hidden;background:#191e2d}
article.flagged{border-color:#ffb962}video{width:100%;aspect-ratio:160/144;image-rendering:pixelated;display:block}
button{background:#29334c;border:1px solid #556383;color:#eef3ff;border-radius:6px;padding:10px;margin:8px;cursor:pointer}
button:focus-visible{outline:2px solid #ffda86}section{margin:30px 0}
dialog{background:#10121b;color:#eef3ff;border:1px solid #556383;max-width:min(90vw,850px)}
dialog::backdrop{background:#000d}dialog video{width:min(640px,80vw,83.333vh);height:auto;max-width:100%;margin:auto}
@media(max-width:850px){.cards{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:520px){.cards{grid-template-columns:1fr}body{padding:12px}}
</style><h1>QUINTRA / Boss phase workshop</h1>
<p>Work in progress: one card per health phase, both transition windows, and separate
Serpent, Kilnback/Cinder Rex and Reaper mechanic cycles.
Visible cards animate silently; enlarge a fight to hear only that clip.
Mark the weakest visuals with “Needs work.”</p>
<p>Fresh boot per boss. Normal difficulty, stationary Wolfkin with health replenished each frame.
Boss health is explicitly set to half and quarter for previews. These staged captures demonstrate
native rendering and AI, not difficulty or successful dodging. Mechanic cards use fresh encounters,
a stationary central player, native event boundaries and explicit HP cuts for Cinder's transformation
and reprise and Reaper's link. They include the first frame of the next state.
Body art, balance, escape-route playtesting and sound review remain in progress.</p>
<button id="pause">Pause previews</button> <a href="capture.json">ROM binding and full traces</a>
<p id="selection">Shortlist: none</p>''' + ''.join(sections) +
        f'<p>ROM {sha} · Native 160×144, real-time speed, every second LCD frame. '
        'MP4 contains browser-encoded audio; corresponding WAV files preserve native PCM. No hardware reload.</p>' + '''
<dialog><h2 id="title"></h2><video controls loop playsinline></video><button id="close">Close / Esc</button></dialog>
<script>
const cards=[...document.querySelectorAll('article')], modal=document.querySelector('dialog'),big=modal.querySelector('video');
let paused=false;const visible=new Set();let chosen=[];const storage='quintra-phase-shortlist';
try{chosen=JSON.parse(localStorage.getItem(storage)||'[]')}catch{}
function name(c){return c.closest('section').querySelector('h2').textContent+' / '+c.querySelector('h3').textContent}
function refresh(){document.querySelector('#selection').textContent='Shortlist: '+(chosen.join('; ')||'none');
cards.forEach(c=>{const yes=chosen.includes(name(c));c.classList.toggle('flagged',yes);c.querySelector('.flag').setAttribute('aria-pressed',String(yes))})}
function playback(){cards.forEach(c=>{const v=c.querySelector('video');if(!paused&&!modal.open&&visible.has(v))v.play().catch(()=>{});else v.pause()})}
const observer=new IntersectionObserver(entries=>{entries.forEach(e=>e.isIntersecting?visible.add(e.target):visible.delete(e.target));playback()});
cards.forEach(c=>{const v=c.querySelector('video');observer.observe(v);
c.querySelector('.focus').onclick=()=>{big.src=v.src;big.currentTime=v.currentTime;big.muted=false;
document.querySelector('#title').textContent=name(c);modal.showModal();playback();big.play().catch(()=>{})};
c.querySelector('.flag').onclick=()=>{const n=name(c);chosen=chosen.includes(n)?chosen.filter(x=>x!==n):[...chosen,n];
try{localStorage.setItem(storage,JSON.stringify(chosen))}catch{}refresh()}});
document.querySelector('#pause').onclick=()=>{paused=!paused;document.querySelector('#pause').textContent=paused?'Play previews':'Pause previews';playback()};
document.querySelector('#close').onclick=()=>modal.close();modal.onclose=()=>{big.pause();big.removeAttribute('src');big.load();playback()};refresh();
</script></html>''')


def main():
    sha = hashlib.sha256(ROM.read_bytes()).hexdigest()
    script_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    out = ROOT / 'builds' / f'boss-phases-{sha[:8]}-{script_sha[:8]}'
    out.mkdir(parents=True, exist_ok=True)
    select_rom_topology(ROM)
    a = symbol_addresses(ROM)
    noi = ROM.with_suffix('.noi').read_text()
    for name in ('_cinder_phase','_cinder_pattern','_boss_phase_clock','_boss_link_active'):
        a[name]=int(re.search(rf'DEF {name} 0x([0-9A-Fa-f]+)',noi)[1],16)
    records = []
    for stage in range(9):
        pb, _, _ = boot_to_stage(ROM, a, stage, 'normal', 0)
        try:
            advance_to_sanctuary(pb, a, stage)
            advance_to_boss(pb, a, stage)
            en = a['_entities']
            bosses = [en+i*28 for i in range(32) if pb.memory[en+i*28] == 2
                      and pb.memory[en+i*28+1]&1 and pb.memory[en+i*28+20]&1]
            assert len(bosses) == 1, (stage, bosses)
            boss = bosses[0]
            maximum = pb.memory[boss+23] or pb.memory[boss+14]
            for phase in range(3):
                pb.memory[boss+14] = max(1, maximum >> phase)
                if phase:
                    record = capture(pb, a, boss, 120, out, f'boss-{stage+1}-transition-{phase}')
                    record.update(stage=stage, label=f'Transition {phase} → {phase+1}')
                    records.append(record)
                record = capture(pb, a, boss, 600, out, f'boss-{stage+1}-phase-{phase+1}')
                record.update(stage=stage, label=f'Phase {phase+1}')
                assert all(row[2] == phase+1 for row in record['trace']), (stage, phase, 'wrong phase')
                records.append(record)
            print(f'[phase-review] {stage+1}/9 captured', flush=True)
        finally:
            pb.stop(save=False)
            (out / 'capture.json').write_text(json.dumps(dict(rom_sha256=sha,
                symbols_sha256=hashlib.sha256(ROM.with_suffix('.noi').read_bytes()).hexdigest(),
                script_sha256=script_sha, pyboy=version('pyboy'), fps=FPS, stride=STRIDE,
                complete=False, records=records)))
    for stage in (1,2,5):
        records.extend(special_cards(stage,a,out))
        print(f'[phase-review] stage {stage+1} mechanic cycles captured',flush=True)
        (out / 'capture.json').write_text(json.dumps(dict(rom_sha256=sha,
            symbols_sha256=hashlib.sha256(ROM.with_suffix('.noi').read_bytes()).hexdigest(),
            script_sha256=script_sha, pyboy=version('pyboy'), fps=FPS, stride=STRIDE,
            complete=len(records)==61, records=records)))
    assert len(records)==61
    page(out, sha, records)
    print(out / 'index.html', flush=True)


if __name__ == '__main__':
    main()
