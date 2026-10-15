#!/usr/bin/env python3
"""Compact nine-boss overview from a completed, ROM-bound phase capture."""
import hashlib
import html
import json
import sys
from pathlib import Path
from capture_boss_gallery import NAMES

out=Path(sys.argv[1])
manifest=json.loads((out/'capture.json').read_text())
sha=hashlib.sha256(Path('rom/working/quintra.gbc').read_bytes()).hexdigest()
assert manifest['complete'] and manifest['rom_sha256']==sha
cards=[]
for stage,name in enumerate(NAMES):
    key=f'boss-{stage+1}-phase-3'
    assert any(r['key']==key for r in manifest['records'])
    assert (out/f'{key}.mp4').is_file()
    cards.append(f'<article><h2>{stage+1:02} · {html.escape(name.title())}</h2>'
        f'<video muted loop playsinline preload="metadata" poster="{key}.png" src="{key}.mp4"></video></article>')
(out/'collage.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Quintra · All nine bosses</title>
<style>:root{color-scheme:dark;font:16px system-ui;background:#10121b;color:#e5eaf5}
body{max-width:1100px;margin:auto;padding:20px}h1,h2{color:#f5cc80}h2{font-size:16px;padding:0 12px}
a{color:#9ed7ff}main{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
article{background:#191e2d;border:1px solid #3e4963;border-radius:8px;overflow:hidden}
video{display:block;width:100%;aspect-ratio:160/144;image-rendering:pixelated}
button{background:#29334c;color:white;border:1px solid #556383;padding:10px;border-radius:6px}
p{line-height:1.5}@media(max-width:650px){main{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(prefers-reduced-motion:reduce){video{scroll-behavior:auto}}</style>
<h1>QUINTRA · All nine bosses</h1>
<p>Animated native-ROM captures · final health phase.
<a href="index.html">Every phase, transition and mechanic + audio</a> ·
<a href="artwork/artwork.html">Artwork comparison</a></p>
<p><button id="pause">Pause animation</button></p><main>'''+''.join(cards)+f'''</main>
<p>ROM {sha[:8]} · beta29. Staged encounters with a protected, stationary player;
these clips show boss behavior, not a player clearing the fights.</p>
<script>
let paused=matchMedia('(prefers-reduced-motion:reduce)').matches;
const visible=new Set(),videos=[...document.querySelectorAll('video')],button=document.querySelector('#pause');
function update(){{button.textContent=paused?'Play animation':'Pause animation';videos.forEach(v=>{{if(!paused&&visible.has(v)&&!document.hidden)v.play().catch(()=>{{}});else v.pause()}})}}
const observer=new IntersectionObserver(entries=>{{entries.forEach(e=>{{if(e.isIntersecting)visible.add(e.target);else visible.delete(e.target)}});update()}});
videos.forEach(v=>observer.observe(v));button.onclick=()=>{{paused=!paused;update()}};
document.addEventListener('visibilitychange',update);update();
</script></html>''')
(out/'collage-build.json').write_text(json.dumps(dict(rom_sha256=sha,
    script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    capture_sha256=hashlib.sha256((out/'capture.json').read_bytes()).hexdigest(),cards=9)))
print(out/'collage.html')
