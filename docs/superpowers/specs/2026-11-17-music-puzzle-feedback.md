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
- The accepted **final** note uses a longer envelope (`0xF7`, volume 15
  with period-7 decay) and a 56-frame CH1 claim.
- The reveal fanfare is delayed **40 frames**, then starts on CH4
  (the existing stone-breath) while CH1 of the fanfare waits 8 more
  frames, so the last pitch is still audible as the jingle begins.
  Melody lock covers the hold plus the fanfare
  (`melody_lock(MELODY_PRIORITY_SECRET, 40+8+45)`).
- Every music-puzzle solve, including the row, calls
  `sfx_play_puzzle_after_note()` after voicing the last plate. Hidden
  landscape secrets that are not a pitched plate keep the immediate
  `sfx_play(SFX_PUZZLE)`.

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

- On room entry, after a short 20-frame rest, the row **echoes the
  target phrase** once: each step flashes and voices its pitch with
  the mid-phrase envelope, ~16 frames apart. Input is ignored during
  the echo. After a wrong reset, the phrase echoes again following a
  20-frame rest so the player can hear what to retry.
- Length by dungeon depth (`run_state.bosses_beaten`): 3 notes in
  stage 1, 4 in stage 2, 5 in stage 3+ (a 5-note phrase reuses one
  plate, so "step on each once" cannot solve it).
- Phrase construction is seed-stable. Consecutive steps may not be
  the same plate (no instant double-tap). Stage 3+ includes exactly
  one revisited plate. Pitches stay bound to physical plates 0..3.
- A correct step latches that plate’s pressed look (a revisit lights
  it again after any interim idle), voices its pitch, and advances.
  The final accepted note uses the long envelope and delayed fanfare
  above, then sets the phase bit and leaves every plate in the
  phrase lit.
- A wrong step plays `SFX_REFUSE` on CH1 after a short wrong-pitch
  voice is skipped (the refuse cue *is* the buzz; do not also play
  the plate’s pitch, or the clue fights the error). Flash the bad
  plate, shake, clear the lit mask, and idle every plate. No HP
  charge: this row is a remote shortcut wall, not a mandatory Trial.
- The contact latch still requires stepping off before the next
  press, so walking a tile cannot double-count.
- Accidental left-to-right mashing must fail the source contract and
  the live test for every published phrase.

## 3. Rune-sequence plates (`PUZZLE_RUNE_SEQUENCE`)

Keep the existing grammar: 3 / 4 / 5 plates by stage, stable
per-plate pitches, rising or falling traversal, wrong note costs one
half-heart, confirmed notes stay safe to revisit and still voice.

Slightly more complex, still fair:

- **Echo on entry** (and after a wrong reset), same call-and-response
  cadence as the row. The echo flashes plates in required order so
  the phrase is learnable with the sound off as well as on. Input
  during the echo is ignored; a player already standing on a plate
  must step off and back on after the echo to count a press.
- Stage 3+ five-note phrases already exist in `prepare_sequence` even
  when later stages currently assign Sun Lattice / Prism Toggle to
  the Trial/Waystone slots. Do not change that assignment. When a
  five-note room does appear, the echo plus the longer final note
  make the larger court readable.
- No HP change, no new plate count, no new banks of tiles.

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

- `puzzle.c` is bank 6 (historically tight). Echo playback and the
  row melody tick live in `rune_notes.c` (bank 21). `sfx.c` changes
  stay in the resident dispatcher and must stay a few bytes.
- `scripts/check_rom_layout.py` must stay green (256-byte emergency
  floor per bank). `scripts/test_new_game_start.py` must keep
  passing.
- Extend `scripts/test_puzzles.py`:
  - Source + live APU contract for the 40-frame final-note hold and
    ducked fanfare, on both a rune phrase and the row.
  - Row: echo plays the published phrase before input is accepted;
    a wrong step buzzes, clears lit plates, and re-echoes; a correct
    walk solves and persists the remote phase bit; a left-to-right
    mash does not solve; lightning zap still opens the gate;
    door-entry still uploads note tiles (poisoned VRAM contract).
  - Rune rooms: echo on entry, existing colour / flash / damage /
    revisit contracts still hold.
  - Door switch: activating a `BGT_SWITCH` leaves `BGT_SWITCH_PRESSED`
    (walkable, door palette), not `BGT_FLOOR`.
- No deploys. PR, then squash-merge when CI is green.

## 6. Non-goals

Sun Lattice, Prism Toggle, Push Seal, and the remote gate chamber
geometry stay as they are. Rune plate colours and packed palettes
stay as specified in `2026-11-16-music-tile-colors.md`. Do not
reassign later-stage Trial/Waystone kinds solely to show five-note
phrases.
