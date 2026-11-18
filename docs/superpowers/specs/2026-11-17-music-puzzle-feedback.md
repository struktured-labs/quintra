# Music puzzle feedback, complexity, and door-switch art

Date: 2026-11-17
Status: implementation
Source: Carmelo play reports (final note lost under the reveal jingle;
Aether Lattice "I can never tell how I solved it"; both music styles
should be slightly more complex; door-switch floor button should look
like a real unpressed/pressed plate).

## 1. Final note vs secret-revealed jingle

`sfx_play_puzzle_after_note()` already delays `SFX_PUZZLE` by 20 frames
so the last rune can speak, but 20 frames is only half of the plate’s
40-frame CH1 claim, and the fanfare then takes CH1 at full volume. On
the Aether Lattice the last press currently skips `voice_plate` and
fires `sfx_play(SFX_PUZZLE)` immediately, so the resolving note is
never heard at all.

Rule:

- Mid-phrase plates keep the current envelope (`0xF3`, 40-frame CH1
  claim) so walking to the next plate retriggers cleanly.
- The accepted **final** note is `sfx_play_rune_final(step)` in the
  resident dispatcher: envelope `0xF7` (volume 15, period-7 decay),
  a 56-frame CH1 claim, and in the same call it arms
  `PEND_PUZZLE_DELAY` (40 frames of the last pitch, then CH4
  stone-breath, then 8 frames later the fanfare’s CH1 D4 figure).
  Melody lock covers the hold plus the fanfare
  (`melody_lock(MELODY_PRIORITY_SECRET, 40+8+45)`).
- Hidden landscape secrets that are not a pitched plate keep the
  immediate `sfx_play(SFX_PUZZLE)`. `sfx_play_puzzle_after_note()`
  remains only as the delay arm used by the atomic final-note call.

Verify with headless APU capture in `scripts/test_puzzles.py`: on the
solve frame, CH1 is still the last plate’s frequency (no sweep), the
pitch is still held at mid-delay (>= 24 extra frames), and
`SFX_PUZZLE`’s CH1 figure must not start before frame 40.

## 2. Aether Lattice audit (row of tiles, `PUZZLE_PHASE_SWITCH`)

Current rule: a four-plate Lights-Out row at y=8, x={4,8,12,16}. Each
press XORs a neighbor mask `{0x03,0x07,0x0E,0x0C}`. The matrix is full
rank over GF(2), so every published state has a unique 3- or 4-press
solution, generated backwards from all-lit (`0x0F`). That part is
deterministic and never soft-locks.

What is off, and why Carmelo cannot tell how he solved it:

- The plates use the same note-tile art and pitches 0..3 as a rune
  phrase, so the row *reads* as a melody puzzle, but the rule is
  "toggle yourself and your neighbors." There is no target melody and
  no correct/wrong step.
- A press voices only the touched plate. Neighbors flip silently, so
  audio and visuals disagree.
- The solving press skips the note and plays the reveal jingle, so the
  last action does not teach anything.
- There is no echo, no reset cue, and no wrong-step buzz. Walking the
  row (or mashing with the contact latch) can stumble into the unique
  solution; the jingle then fires and the player cannot reconstruct
  why.
- Lightning `puzzle_phase_switch_zap()` still toggles
  `RUN_DEEP_PHASE_OPEN_BIT` and forces all plates lit when opening.
  That tool path is fine; the walk-on-plates path is the problem.

### New rule: call-and-response row melody

Keep the same four physical plates, the same note colours / flash, the
same remote gate bit, and the same lightning zap (XOR the bit; if now
open, mark the phrase complete and light every plate; if now closed,
clear progress and idle the row). Replace Lights-Out with a
seed-deterministic melody the player must walk.

- Plate layout is a zigzag along the east-west aisle, not a straight
  line on y=8: plates sit at `(4,7), (8,9), (12,7), (16,9)` so the
  player can walk the centre lane without being forced across a
  neighbour. Cardinal body-width lanes stay carved as they are now.
- On room entry, after a 20-frame rest, the row **echoes the target
  phrase** once: each step flashes and voices its pitch with a short
  echo envelope (`0xF2`) at **24 frames** per note. Movement and
  combat stay free; only plate input is ignored. `melody_lock` covers
  the echo so BGM cannot eat a cue note. After a wrong reset, the
  phrase echoes again following a **40-frame** rest. A lightning zap
  cancels any active echo immediately.
- Length by dungeon depth (`run_state.bosses_beaten`): 3 notes in
  stage 1, 4 in stage 2, 5 in stage 3+ (a 5-note phrase reuses exactly
  one plate, so "step on each once" cannot solve it).
- Phrase construction is seed-stable and must not use only low entropy
  bits of the seed. Consecutive steps may not be the same plate.
  Stage 3+ includes exactly one revisited plate. Pitches stay bound
  to physical plates 0..3. Published phrases must not be the
  monotonic left-to-right or right-to-left sweeps
  (`0,1,2[,3]` / `3,2,1[,0]` or a 3-note prefix of either).
- Mid-phrase presses **pulse-flash** and voice the pitch; they do not
  latch `room_rune_lit_mask`. Only the solve (or a successful zap)
  lights every plate. That way a revisited note in a 5-note phrase
  is not already sunken when it is needed again, and walking the
  aisle never looks like partial progress.
- The accepted final note is one atomic resident call,
  `sfx_play_rune_final(pitch)`: envelope `0xF7`, 56-frame CH1 claim,
  and it arms the 40+8-frame ducked fanfare itself. Do not call
  `sfx_play_rune` and `sfx_play_puzzle_after_note` as two steps;
  the first would clear `pend_kind`. Then set the phase bit and
  latch all four plates lit.
- A wrong step voices the touched plate (so the pitch is still a
  learnable clue) and plays `SFX_HIT` on CH4, then flashes, shakes,
  and idles every plate. No HP charge: this row is a remote shortcut
  wall, not a mandatory Trial. Re-echo starts after a 40-frame rest
  so the refuse/hit cue and the first echo note do not overlap.
- The contact latch still requires stepping off before the next
  press. While an echo is playing, and on the frame it ends, if the
  champion is standing on a plate then `puzzle_contact` is set so
  that standing still cannot fire a press on the first open frame.
- Accidental left-to-right or right-to-left mashing must fail the
  source contract and the live test for every published phrase.

## 3. Rune-sequence plates (`PUZZLE_RUNE_SEQUENCE`)

Keep the existing grammar: 3 / 4 / 5 plates by stage, stable
per-plate pitches, rising or falling traversal, wrong note costs one
half-heart, confirmed notes stay safe to revisit and still voice.
The longer final note and ducked fanfare from section 1 apply here.

Carbon review (2026-11-17): do **not** echo or flash the required
order on entry or reset. This is a scale-deduction puzzle; giving
away the walk order would turn it into Simon Says and remove the
pitch/colour routing clue. Length already grows by stage. A more
complex rune rule is deferred until the Lattice overhaul is played.

- No entry echo, no new plate count, no HP change, no assignment
  change for later-stage Trial/Waystone slots.

## 4. Door-switch floor button art (addendum)

`BGT_SWITCH` (slot 33, `BGPAL_DOOR`) is a flat 8x8 gold well. On
activation `activate_switch()` replaces it with plain `BGT_FLOOR`, so
the button vanishes. There is no pressed state.

- Generate unpressed and pressed candidates with GPT Image
  (`gpt-image-2.6-sunburst`), using the current `BGT_SWITCH` grid
  upscaled as an edit reference. Unpressed: raised, beveled pressure
  plate, clearly a floor button. Pressed: same plate sunken
  down-right, darker well, still a button (not a bare floor tile).
- Quantize each to one GBC tile, 4 colours, matching dungeon
  `BGPAL_DOOR` (stage door gold) plus the existing dark outline
  index 0. Keep the glyph map style used by `quintra-assets`.
- Add `BGT_SWITCH_PRESSED` at **slot 122** (in-play only;
  `BGT_MAP_CACHE` already overwrites 122 on SELECT; the room atlas
  restores 122 on resume, same pattern as `BGT_DOOR_LOCKED` / note
  plates). Walkable, `BGPAL_DOOR`, never treated as a fresh switch.
- `activate_switch()` writes `BGT_SWITCH_PRESSED` instead of
  `BGT_FLOOR`. Law-altar / lightning toggles that must raise the
  plate again write `BGT_SWITCH` back.
- Before/after contact sheet (current tile, GPT source, quantized
  unpressed, quantized pressed, on a door-palette dungeon floor) is
  saved under `/workspace/quintra-musicpz/`. Log GPT spend to a
  ledger; stop at the $100 program cap. Prior spend is about $6.60.

## 5. Banks, tests, shipping

- `puzzle.c` is bank 6 (historically tight). Echo state, the row
  phrase, and `rune_row_prepare` / `rune_row_tick` live in
  `rune_notes.c` (bank 21) with WRAM arrays; bank 6 only makes those
  two banked calls. `sfx.c` changes stay in the resident dispatcher
  and must stay a few bytes.
- `scripts/check_rom_layout.py` must stay green (256-byte emergency
  floor per bank). `scripts/test_new_game_start.py` must keep
  passing.
- Extend `scripts/test_puzzles.py`:
  - Source + live APU contract for the 40-frame final-note hold and
    ducked fanfare, on both a rune phrase and the row.
  - Row: echo plays the published phrase before input is accepted;
    a wrong step voices the plate, buzzes on CH4, clears lit plates,
    and re-echoes after 40 frames; a correct walk solves and persists
    the remote phase bit; left-to-right and right-to-left mashes do
    not solve; lightning zap opens the gate, a second zap closes and
    resets progress, and a re-echo plus walk still solves; door-entry
    still uploads note tiles (poisoned VRAM contract).
  - Rune rooms: existing colour / flash / damage / revisit contracts
    still hold, plus the longer final-note APU hold.
  - Door switch: activating a `BGT_SWITCH` leaves `BGT_SWITCH_PRESSED`
    (walkable, door palette), not `BGT_FLOOR`. Opening and closing
    SELECT after a press restores VRAM tile 122 to the pressed
    graphic, not Compass cache pixels.
- No deploys. PR, then squash-merge when CI is green.

## 6. Non-goals

Sun Lattice, Prism Toggle, Push Seal, and the remote gate chamber
geometry stay as they are. Rune plate colours and packed palettes
stay as specified in `2026-11-16-music-tile-colors.md`. Do not
reassign later-stage Trial/Waystone kinds solely to show five-note
phrases.

## 7. Carbon review (2026-11-17)

Verdict: approve with changes. The amendments above were taken:

- No order-revealing echo on rune phrases (keeps scale deduction).
- Zigzag row so the aisle is not a forced crossing; mid-phrase does
  not latch the sunken look (revisit stays readable).
- Wrong row press still teaches the plate’s pitch; 40-frame rest
  before re-echo.
- `sfx_play_rune_final` is one atomic resident call.
- Echo cadence is 24 frames with `melody_lock`; zap cancels echo;
  contact is armed if the champion stands on a plate during/at the
  end of an echo.
- Both monotonic sweeps are banned; SELECT resume and double-zap
  are tested; slot 122 is an explicit walkable tile.

Carbon call $0.0303; running total $6.2279 logged.
