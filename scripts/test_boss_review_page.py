#!/usr/bin/env python3
"""Browser acceptance for the served native boss-mechanic review."""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parent.parent


async def check(args):
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=args.chromium,
                                           args=['--no-sandbox'])
        page = await browser.new_page(viewport={'width': 1280, 'height': 960})
        await page.goto(args.url)
        response = await page.request.get(args.url.rstrip('/') + '/capture.json')
        manifest = await response.json()
        sha = hashlib.sha256((ROOT / 'rom/working/quintra.gbc').read_bytes()).hexdigest()
        assert manifest['complete'] and manifest['rom_sha256'] == sha
        assert len(manifest['records']) == 61
        assert await page.locator('article').count() == 61
        for record in manifest['records']:
            if record.get('event_card'):
                assert record['event_completed']
                assert len(record['mechanics']) == record['frames']
        card = page.locator('article').filter(
            has=page.locator('h3', has_text='Full-length unwind'))
        await card.scroll_into_view_if_needed()
        await page.wait_for_function("Array.from(document.querySelectorAll('article video'))"
                                     ".some(v=>!v.paused && v.currentTime>0)")
        await card.locator('.flag').click()
        assert await card.locator('.flag').get_attribute('aria-pressed') == 'true'
        await card.locator('.focus').click()
        await page.wait_for_function("document.querySelector('dialog video')"
                                     ".webkitAudioDecodedByteCount>0")
        assert await page.locator('article video').evaluate_all(
            '(vs)=>vs.every(v=>v.paused && v.muted)')
        box = await page.locator('dialog video').bounding_box()
        assert box['width'] >= 480, box
        assert abs(box['width'] / box['height'] - 160 / 144) < .01, box
        args.out.mkdir(parents=True, exist_ok=True)
        await page.screenshot(path=str(args.out / 'browser-selected.png'))
        await page.locator('#close').click()
        await page.wait_for_function("!document.querySelector('dialog video').hasAttribute('src')"
                                     " && document.querySelector('dialog video').paused")
        await page.screenshot(path=str(args.out / 'browser-grid.png'))
        (args.out / 'browser-check.json').write_text(json.dumps(dict(
            rom_sha256=sha, cards=61, selected_video_bounds=box,
            browser=browser.version, audio='decoded, not listening-qualified',
            script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())))
        await page.goto(args.url.rstrip('/') + '/artwork/artwork.html')
        assert await page.locator('section').count() == 4
        assert await page.locator('img').count() == 8
        await page.wait_for_function("Array.from(document.images).every(i=>i.complete && i.naturalWidth===160 && i.naturalHeight===144)")
        assert sha[:8] in await page.locator('body').inner_text()
        await page.screenshot(path=str(args.out / 'browser-artwork.png'), full_page=True)
        await browser.close()
        print('[boss-review-page] PASS 61 cards, event traces, enlarged aspect ratio, '
              'isolated audio decoding, shortlist and close cleanup')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='http://127.0.0.1:8919/')
    parser.add_argument('--chromium', required=True)
    parser.add_argument('--out', type=Path, required=True)
    asyncio.run(check(parser.parse_args()))
