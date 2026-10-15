#!/usr/bin/env python3
"""Fresh-ROM, real-time boss review clips and a self-contained comparison page."""
import hashlib
import json
import subprocess
from importlib.metadata import version
from pathlib import Path

from capture_boss_gallery import NAMES
from make_stage_states import (advance_to_boss, advance_to_sanctuary,
                               boot_to_stage, select_rom_topology, symbol_addresses)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / 'rom/working/quintra.gbc'
SHA = hashlib.sha256(ROM.read_bytes()).hexdigest()
OUT = ROOT / 'builds' / f'boss-review-{SHA[:8]}'
FRAMES = 1800
STRIDE = 4
FPS = 4194304 / 70224


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    select_rom_topology(ROM)
    addrs = symbol_addresses(ROM)
    records = []
    for stage, name in enumerate(NAMES):
        pb, _, _ = boot_to_stage(ROM, addrs, stage, 'normal', 0)
        try:
            advance_to_sanctuary(pb, addrs, stage)
            advance_to_boss(pb, addrs, stage)
            en, pl = addrs['_entities'], addrs['_player']
            bosses = [en + i * 28 for i in range(32)
                      if pb.memory[en+i*28] == 2 and pb.memory[en+i*28+1] & 1
                      and pb.memory[en+i*28+20] & 1]
            assert len(bosses) == 1, (stage, bosses)
            boss = bosses[0]
            assert pb.memory[boss + 19] == stage
            initial_hp = pb.memory[boss + 14]
            filename = f'boss-{stage+1:02}.mp4'
            encoder = subprocess.Popen([
                'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                '-f', 'rawvideo', '-pixel_format', 'rgb24', '-video_size', '160x144',
                '-framerate', str(FPS / STRIDE), '-i', '-', '-an',
                '-c:v', 'libx264', '-crf', '12', '-preset', 'fast',
                '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(OUT / filename)
            ], stdin=subprocess.PIPE)
            trace = []
            try:
                for frame in range(FRAMES):
                    pb.memory[pl + 2] = pb.memory[pl + 1]
                    if frame == 900:
                        pb.memory[boss + 14] = max(1, initial_hp // 3)
                    pb.tick()
                    assert pb.memory[addrs['_loop_current_screen']] == 5, (stage, frame)
                    assert pb.memory[boss] == 2, (stage, frame, 'boss disappeared')
                    if frame % STRIDE == 0:
                        picture = pb.screen.image.convert('RGB')
                        encoder.stdin.write(picture.tobytes())
                        trace.append([frame, pb.memory[boss + 14], pb.memory[boss + 15],
                                      pb.memory[boss+3], pb.memory[boss+7]])
                        if frame == 300:
                            picture.save(OUT / f'boss-{stage+1:02}.png')
            finally:
                encoder.stdin.close()
                assert encoder.wait() == 0
            records.append(dict(stage=stage+1, name=name, file=filename,
                                hp_before=initial_hp, trace=trace))
            print(f'[boss-review] {stage+1}/9 {name}', flush=True)
        finally:
            pb.stop(save=False)
    metadata = dict(rom_sha256=SHA, pyboy=version('pyboy'), frames=FRAMES,
                    fps=FPS, sample_stride=STRIDE, audio=False,
                    setup='Fresh boot per boss; progression fixture; stationary Wolfkin; '
                          'HP replenished each frame; boss HP set to one third at frame 900. '
                          'Native AI, terrain and rendering; no time compression.', bosses=records)
    (OUT / 'capture.json').write_text(json.dumps(metadata, indent=2))
    cards = ''.join(f'''<article id="boss-{r['stage']}">
      <header><span>{r['stage']:02}</span><h2>{r['name'].replace('>', '→')}</h2></header>
      <video autoplay muted loop playsinline preload="auto" poster="boss-{r['stage']:02}.png"
        src="{r['file']}" aria-label="{r['name']}"></video>
      <footer><button class="focus">Enlarge</button><button class="flag" aria-pressed="false">☆ Needs work</button></footer>
    </article>''' for r in records)
    (OUT / 'index.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Quintra · Boss review</title>
<style>
:root{color-scheme:dark;font-family:system-ui,sans-serif;background:#10121b;color:#e8e8ef}
body{max-width:1260px;margin:auto;padding:24px}h1{margin:0;color:#f4cf80;font-size:30px}
.intro{color:#aeb5cb;line-height:1.6;max-width:920px}nav{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}
button,a{color:#dfe9ff}button{background:#232a3e;border:1px solid #46516c;border-radius:7px;padding:9px 13px;cursor:pointer}
button:hover{background:#36415c}button:focus-visible{outline:2px solid #f4cf80}
main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
article{background:#191e2d;border:1px solid #343d54;border-radius:10px;overflow:hidden}
article.flagged{border:2px solid #f4cf80}header{display:flex;align-items:center;gap:10px;padding:12px}
header span{color:#f4cf80}h2{font-size:14px;letter-spacing:.04em;margin:0}
video{width:100%;aspect-ratio:160/144;display:block;image-rendering:pixelated;background:#000}
footer{display:flex;justify-content:space-between;padding:10px;gap:8px}
dialog{max-width:min(90vw,800px);padding:20px;border:1px solid #566381;border-radius:12px;background:#10121b}
dialog::backdrop{background:#000d}dialog video{max-height:75vh;width:auto;max-width:100%;margin:auto}
small{display:block;color:#aeb5cb;margin:20px 0}#selection{color:#f4cf80}
@media(max-width:850px){main{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:520px){main{grid-template-columns:1fr}body{padding:12px}}
</style><h1>QUINTRA / Boss review</h1>
<p class="intro">Nine current-ROM battles, side by side. Watch silhouettes, contrast against the floor,
movement and attack tells. Each clip loops for about 30 seconds at real-time speed, without audio.
Click <b>Needs work</b> to keep a shortlist on this browser.</p>
<p class="intro">Capture setup: Normal difficulty, stationary Wolfkin with health replenished.
At 15 seconds, boss health is lowered to one third to expose health-triggered phases.
These are staged visual previews—not full fights or difficulty demonstrations.</p>
<nav><button id="pause">Pause all</button><button id="restart">Restart together</button>
<a href="capture.json">Capture details / raw traces</a></nav><p id="selection">Shortlist: none yet</p><main>'''
        + cards + '''</main><small>ROM ''' + SHA + ''' · Fresh PyBoy captures, 160×144 LCD, sampled every fourth frame.
No MiSTer session was touched.</small>
<dialog><h2 id="focus-title"></h2><video controls muted loop playsinline></video><button id="close">Close / Esc</button></dialog>
<script>
const videos=[...document.querySelectorAll('main video')], modal=document.querySelector('dialog'), big=modal.querySelector('video');
let paused=false; const key='quintra-boss-shortlist'; let chosen=[];
try{chosen=JSON.parse(localStorage.getItem(key)||'[]')}catch{}
function selection(){document.querySelector('#selection').textContent='Shortlist: '+(chosen.join(', ')||'none yet');
document.querySelectorAll('article').forEach(card=>{const active=chosen.includes(card.querySelector('h2').textContent);
card.classList.toggle('flagged',active);card.querySelector('.flag').setAttribute('aria-pressed',String(active))})}
selection();document.querySelector('#pause').onclick=()=>{paused=!paused;videos.forEach(v=>paused?v.pause():v.play().catch(()=>{}));
document.querySelector('#pause').textContent=paused?'Play all':'Pause all'};
document.querySelector('#restart').onclick=()=>videos.forEach(v=>v.currentTime=0);
document.querySelectorAll('article').forEach(card=>{card.querySelector('.flag').onclick=()=>{
const name=card.querySelector('h2').textContent;chosen=chosen.includes(name)?chosen.filter(n=>n!==name):[...chosen,name];
try{localStorage.setItem(key,JSON.stringify(chosen))}catch{}selection()};
card.querySelector('.focus').onclick=()=>{videos.forEach(v=>v.pause());big.src=card.querySelector('video').src;
document.querySelector('#focus-title').textContent=card.querySelector('h2').textContent;modal.showModal();big.play().catch(()=>{})}});
document.querySelector('#close').onclick=()=>modal.close();modal.onclose=()=>{big.pause();if(!paused)videos.forEach(v=>v.play().catch(()=>{}))};
</script></html>''')
    print(OUT / 'index.html')


if __name__ == '__main__':
    main()
