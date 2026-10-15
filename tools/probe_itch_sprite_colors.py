#!/usr/bin/env python3
"""Input-only browser color probe; retain screenshots and raw OBJ palettes."""
import argparse
import base64
import hashlib
import json
import re
import time
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait

p=argparse.ArgumentParser()
p.add_argument('url')
p.add_argument('--out',type=Path,required=True)
p.add_argument('--save',type=Path)
p.add_argument('--assert-palette',action='store_true')
a=p.parse_args()
noi=Path('rom/working/quintra.noi').read_text()
screen_address=int(re.search(r'DEF _loop_current_screen 0x([0-9A-Fa-f]+)',noi)[1],16)
a.out.mkdir(parents=True,exist_ok=True)
o=Options();o.add_argument('-headless')
d=webdriver.Firefox(options=o)
d.set_script_timeout(120)
records=[]
build={}
try:
    d.get(a.url)
    build=d.execute_async_script('fetch("build.json").then(r=>r.json()).then(arguments[arguments.length-1]);')
    WebDriverWait(d,30).until(lambda b:b.find_element(By.ID,'status').text.startswith('Ready'))
    if a.save:
        d.find_element(By.ID,'save-file').send_keys(str(a.save.resolve()))
        WebDriverWait(d,30).until(lambda b:b.find_element(By.ID,'status').text=='Save imported')
        d.refresh()
        WebDriverWait(d,30).until(lambda b:b.find_element(By.ID,'status').text.startswith('Ready'))
    d.find_element(By.ID,'launch').click()
    d.execute_async_script('window.WasmBoy.WasmBoy.pause().then(arguments[arguments.length-1]);')
    route=[('title',-1,240),('select',7,8),('select-release',-1,30),
                             ('enter',4,8),('room',-1,180),('menu',7,8),
                             ('menu-release',-1,30),('resume',5,8),('resumed',-1,60),
                             ('east',1,180),('east-release',-1,60)]
    for cycle in range(4):
        route += [(f'death-{cycle}',-1,3600),(f'restart-{cycle}',7,8),
                  (f'release-{cycle}',-1,30),(f'choose-{cycle}',4,8),(f'new-run-{cycle}',-1,180)]
    if a.save:
        route=[('saved-title',-1,240),('continue',4,8),('continued',-1,180),
               ('pack',7,8),('pack-release',-1,30),('back',5,8),('continued-after-menu',-1,60)]
    for label,key,frames in route:
        result=d.execute_async_script('''
            const done=arguments[arguments.length-1],key=arguments[0],n=arguments[1];
            (async()=>{
              const api=window.WasmBoy.WasmBoy;
              document.querySelectorAll('[data-touch-input]').forEach(b=>b.dispatchEvent(new PointerEvent('pointerup',{bubbles:true,pointerId:99,pointerType:'touch'})));
              if(key>=0) document.querySelector('[data-touch-input="'+['UP','RIGHT','DOWN','LEFT','A','B','SELECT','START'][key]+'"]')
                .dispatchEvent(new PointerEvent('pointerdown',{bubbles:true,pointerId:99,pointerType:'touch'}));
              await new Promise(r=>setTimeout(r,60));
              let keys=Array(8).fill(0);if(key>=0)keys[key]=1;
              await api._runWasmExport('setJoypadState',keys);
              await api._runNumberOfFrames(n);
              const loc=await api._getWasmConstant('GBC_PALETTE_LOCATION');
              const mem=await api._getWasmConstant('GAMEBOY_INTERNAL_MEMORY_LOCATION');
              const size=await api._getWasmConstant('GAMEBOY_INTERNAL_MEMORY_SIZE');
              const sm=await api._runWasmExport('getWasmBoyOffsetFromGameBoyOffset',[arguments[2]]);
              return {screen:Array.from(await api._getWasmMemorySection(sm,sm+1))[0],palettes:Array.from(await api._getWasmMemorySection(loc,loc+128)),
                memory:Array.from(await api._getWasmMemorySection(mem,mem+size))};
            })().then(done).catch(e=>done({error:String(e)}));
        ''',key,frames,screen_address)
        assert 'error' not in result,result
        time.sleep(.1)
        png=d.execute_script("return document.querySelector('#game').toDataURL().split(',')[1]")
        (a.out/f'{label}.png').write_bytes(base64.b64decode(png))
        records.append(dict(label=label,key=key,frames=frames,**result))
        print(label,'screen',result['screen'],'black palettes',
              [i for i in range(8) if not any(result['palettes'][66+i*8:72+i*8])],flush=True)
    if a.assert_palette:
        for record in records:
            if record['label'] in ('continued','continued-after-menu'):
                assert record['screen']==5
                assert record['palettes'][112:120]==[0,0,67,73,36,127,255,83], record['palettes'][112:120]
finally:
    d.quit()
    (a.out/'capture.json').write_text(json.dumps(dict(url=a.url,build=build,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),records=records)))
