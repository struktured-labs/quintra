# Playtest feedback (Brandon, 2026-11) — design spec

Small UX fixes from four playtest reports. No new mechanics; every change makes
an existing rule visible.

## R3 — browser audio (top priority, Safari)
- WasmBoy 0.8.14 only resumes an AudioContext whose state is `suspended` and
  never awaits it; Safari also reports `interrupted` (calls, route changes,
  tab switches) and WasmBoy never recovers from it.
- The player shell (`web/itch/player.js`) now resumes every WasmBoy context
  (created via `AudioContext || webkitAudioContext`) whose state is not
  `running`/`closed`, on keydown, pointerdown, touchstart/touchend, mousedown,
  click, gamepad button edges, window focus, visibilitychange (visible) and
  fullscreenchange. `resume()` is called synchronously inside the gesture and a
  one-sample silent buffer primes WebKit. Calls are not de-duplicated so a
  non-gesture attempt cannot swallow a real tap.
- A banner "Press any button or tap to enable sound" shows while started,
  unmuted and any context is not running (statechange-driven).
- Gamepad A/B/Start (standard buttons 0, 1, 9) and Enter/X launch from the
  title card. Note: Chrome does not treat gamepad input as user activation, so a
  gamepad alone may not unlock audio there; the banner then asks for a tap/key.

## R4 — Hunger feedback
- Curse notice: HUNGER then NOHEAL.
- HUD depth slot shows `H<rooms left>` (capped 9) while Hunger is active.
- Heart contact under Hunger re-fires HUNGER/NOHEAL at most every 90 frames
  while standing on it; shop heart refusal shows the same notice.
- Hunger-blocked heart pickups draw in OBJ palette 0 (pale) instead of red.

## R2 — difficulty and Pack clarity
- Class select row 13 explains the SELECT toggle (EASY = more HP, fewer hexes).
- Pack QUEST frame header always shows EASY/NORMAL.
- The left/right-cycled consumable row is labelled `TOOL<NAME>xN` and the
  footer reads `A USE TOOL SEL B KIT`, separating dungeon tools (A, from Pack)
  from the B-button kit (SELECT page) and from the quest goal.

## R1 — "round blue things" / blue flame
- Round blue things = `BGT_PILLAR` (indestructible) sharing black blocks with
  shootable crystals/rubble. Blue flame = MP wisp (PICKUP_MP) ignored at full MP.
- Fix: MPFULL notice (blue) when touching a wisp at full MP, rate-limited.
  Pillar art/hit feedback is proposed follow-up, not in this change.

## Refusal sound — SFX_REFUSE (follow-up request)
Touching something the champion cannot take must *sound* refused, not silent
or like damage/success.
- Voice: CH1 only, no sweep, 25% duty (hollow, unlike SFX_WEAK's bright 50%
  rising ping and the noise-channel hit/death cues). A4 (x=1750) env (9,down,1)
  for 5 frames, then retrigger E4 (x=1650) env (9,down,2): a falling fourth,
  "nuh-uh", ~0.2 s audible. Claims CH1 for 14 frames so the music yields
  CH1 briefly and keeps CH2/CH3/CH4; it never overrides a melody lock.
- Resident (sfx.c) because the second note rides the existing pend scheduler.
- Triggers, each rate-limited per item via `ai_data[4]` = 90 frames (~1.5 s)
  while in contact, reset on stepping away:
  - heart under Hunger (replaces SFX_WEAK), with HUNGER/NOHEAL notice;
  - heart at full HP without a usable Moon Flask (was silent);
  - MP wisp at full MP (replaces SFX_HIT), with MPFULL notice;
  - shop ware refused (Hunger, cap reached, no Pack space) or not enough coins
    (replaces SFX_HURT; the shop latch became the same 90-frame countdown);
  - coin at a full 999 purse (was silent).
- Evidence: `evidence/fixes/refuse-sfx-triggers.json` (sfx_play hook log),
  `evidence/fixes/refuse_sfx.wav` (480 kHz capture, CH1 routed alone, DC
  removed, 5 ms fades).
