# Web player audio pops (Tesla browser)

Status: implemented. Fix in the WasmBoy fork (struktured-labs/wasmboy#23), vendored here.

## Problem
Carmelo hears popping in the itch web build on the Tesla in-car browser
(Chromium on a weak CPU).

## Findings
- Audio path: emulator worker -> MessagePort -> AudioWorklet ring (42 ms
  target, 512-frame blocks, ack flow control). No SharedArrayBuffer, so
  COOP/COEP and cross-origin isolation do not matter.
- The AudioContext asks for 44.1 kHz. A device that refuses gets its native
  rate, and the worklet resamples linearly. Both rates are tested.
- Root cause: on an underrun the worklet output a hard 0 and jumped back when
  blocks resumed. Game Boy output sits on a DC level, so each edge clicked. A
  slow CPU misses the 42 ms target often, so the clicks turn into popping.
  Frames dropped on overflow also stepped.
- Firefox pops the same way when starved (headless measurement below), so this
  is not Tesla-specific.

## Fix (in the fork)
1. Declick: each discontinuity (start, restart, overflow drop) begins at the
   previous output, and the offset decays (3 ms). An underrun glides to
   silence instead of cutting.
2. Adaptive depth: each underrun episode raises the queue target 1.5x, up to
   100 ms. The producer paces to the raised target. A device that keeps up
   stays at 42 ms.
3. Upstreamed the two patches that only existed in the vendored bundle:
   catch-up scheduling, and no main-thread latency readings with direct
   output.

## Verification
- Fork regression test `test/browser/audio-pops-browser.js` (CI job "Browser
  Audio"): a seeded starved schedule, 44.1k and 48k, no SAB. Old worklet: 28
  clicks at each rate. New: 0.
- Live: `tools/measure_web_audio_pops.mjs <itch-web dir>` runs the real game
  in headless Chromium or Firefox, optionally throttled, at either rate.

## Not done (follow-ups)
- Native-rate AudioContext, which drops Chromium's second resampler on 48k
  devices, and a ~20 Hz DC blocker to match the GB's AC coupling. Both change
  the sound on desktop, so each needs its own A/B.
