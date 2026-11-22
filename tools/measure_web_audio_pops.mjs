#!/usr/bin/env node
// Measure audio pops in the built itch player under a real, realtime browser.
//
// Usage: node tools/measure_web_audio_pops.mjs <package-dir> [--browser chromium|firefox]
//          [--rate 44100|48000] [--throttle N] [--seconds S]
//
// Serves the package without COOP/COEP (no SharedArrayBuffer, like an in-car
// browser), starts the game with sound, optionally slows the CPU with CDP
// Emulation.setCPUThrottlingRate (Chromium), and taps the worklet output into
// a recorder. --rate 48000 forces the AudioContext to 48 kHz, which is what a
// device gets when it refuses the 44.1 kHz the player asks for.
//
// Reports: underrun episodes (from the worklet's status), "edge clicks" (a
// jump of more than 0.05 into or out of digital silence: the hard cut an
// underrun used to make), and large steps per second (any jump > 0.1).
// Realtime scheduling is not deterministic; compare runs, not single numbers.
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const args = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 ? args[i + 1] : dflt;
};
const dir = path.resolve(args[0] || 'builds/itch-web');
const browserName = opt('browser', 'chromium');
const rate = Number(opt('rate', '44100'));
const throttle = Number(opt('throttle', '1'));
const seconds = Number(opt('seconds', '20'));
const pw = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const types = { '.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css', '.gbc': 'application/octet-stream', '.png': 'image/png', '.json': 'application/json' };
const server = http.createServer((req, res) => {
  const rel = decodeURIComponent(req.url.split('?')[0]);
  const file = path.join(dir, rel === '/' ? 'index.html' : rel);
  if (!file.startsWith(dir) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404);
    res.end();
    return;
  }
  res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const url = `http://127.0.0.1:${server.address().port}/`;

const RECORDER = `
class Rec extends AudioWorkletProcessor {
  constructor() { super(); this.buf = new Float32Array(8192); this.n = 0; }
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) for (let i = 0; i < ch.length; i++) { this.buf[this.n++] = ch[i]; if (this.n === this.buf.length) { this.port.postMessage(this.buf); this.buf = new Float32Array(8192); this.n = 0; } }
    return true;
  }
}
registerProcessor('pop-recorder', Rec);`;

const init = ({ rate, recorder }) => {
  const Native = window.AudioContext || window.webkitAudioContext;
  if (rate !== 44100) {
    const Forced = function(options) {
      return new Native(Object.assign({}, options || {}, { sampleRate: rate }));
    };
    Forced.prototype = Native.prototype;
    window.AudioContext = Forced;
    window.webkitAudioContext = Forced;
  }
  window.__pcm = [];
  window.__tapped = false;
  const connect = AudioNode.prototype.connect;
  AudioNode.prototype.connect = function(dest, ...rest) {
    const result = connect.call(this, dest, ...rest);
    if (!window.__tapped && dest instanceof AudioDestinationNode && typeof AudioWorkletNode === 'function') {
      window.__tapped = true;
      const src = this;
      const ctx = this.context;
      const url = URL.createObjectURL(new Blob([recorder], { type: 'application/javascript' }));
      ctx.audioWorklet.addModule(url).then(() => {
        const rec = new AudioWorkletNode(ctx, 'pop-recorder', { numberOfInputs: 1, numberOfOutputs: 0, channelCount: 1, channelCountMode: 'explicit' });
        rec.port.onmessage = e => window.__pcm.push(e.data);
        connect.call(src, rec);
        window.__recRate = ctx.sampleRate;
      });
    }
    return result;
  };
};

const browserType = pw[browserName];
const launchOpts = browserName === 'chromium'
  ? { headless: true, args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] }
  : { headless: true, firefoxUserPrefs: { 'media.autoplay.default': 0, 'media.autoplay.blocking_policy': 0 } };
const browser = await browserType.launch(launchOpts);
let out;
try {
  const page = await browser.newPage();
  await page.addInitScript(init, { rate, recorder: RECORDER });
  if (browserName === 'chromium' && throttle > 1) {
    const cdp = await page.context().newCDPSession(page);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: throttle });
  }
  await page.goto(url);
  await page.waitForFunction(() => !document.getElementById('launch').disabled, null, { timeout: 60000 });
  await page.click('#launch');
  // Poll worklet status for underrun episodes from the page itself.
  await page.evaluate(() => {
    window.__episodes = 0;
    let last;
    setInterval(() => {
      let stats;
      try { stats = window.WasmBoy.WasmBoy._getAudioChannels().master.audioWorkletStats; } catch (e) { return; }
      if (!stats) return;
      const u = stats.underrunFrames || 0;
      if (last !== undefined && u > last && !window.__inGap) { window.__episodes++; window.__inGap = true; }
      if (last !== undefined && u === last) window.__inGap = false;
      last = u;
      window.__stats = stats;
    }, 15);
  });
  // Walk past the title so gameplay audio runs too.
  for (let t = 0; t < seconds; t += 2) {
    await page.waitForTimeout(2000);
    if (t === 6 || t === 8) await page.keyboard.press('Enter');
  }
  out = await page.evaluate(() => {
    const chunks = window.__pcm;
    const n = chunks.reduce((a, c) => a + c.length, 0);
    const x = new Float32Array(n);
    let o = 0;
    for (const c of chunks) { x.set(c, o); o += c.length; }
    let edge = 0, big = 0, lastEdge = -1e9, sq = 0;
    for (let i = 0; i < n; i++) sq += x[i] * x[i];
    for (let i = 1; i < n; i++) {
      const d = Math.abs(x[i] - x[i - 1]);
      if (d > 0.1) big++;
      if (d > 0.05 && i - lastEdge > 8) {
        // Into or out of a run of at least 64 exact-zero samples (1.4 ms).
        let z = 0;
        if (x[i] === 0) while (z < 64 && i + z < n && x[i + z] === 0) z++;
        else if (x[i - 1] === 0) while (z < 64 && i - 1 - z >= 0 && x[i - 1 - z] === 0) z++;
        if (z >= 64) { edge++; lastEdge = i; }
      }
    }
    const s = window.__stats || {};
    return {
      contextRate: window.__recRate, recordedSeconds: +(n / (window.__recRate || 1)).toFixed(1),
      crossOriginIsolated: self.crossOriginIsolated === true, sab: typeof SharedArrayBuffer !== 'undefined' && self.crossOriginIsolated === true,
      underrunEpisodes: window.__episodes, underrunEvents: s.underrunEvents, underrunFrames: s.underrunFrames,
      rms: +Math.sqrt(sq / Math.max(1, n)).toFixed(4), edgeClicks: edge, bigStepsPerSec: +(big / Math.max(1, n / (window.__recRate || 1))).toFixed(1),
      targetSeconds: s.targetLatencySeconds && +s.targetLatencySeconds.toFixed(3)
    };
  });
} finally {
  await browser.close();
  server.close();
}
console.log(JSON.stringify({ browser: browserName, rate, throttle, ...out }));
