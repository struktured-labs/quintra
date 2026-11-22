# Tone-path block puzzle

Date: 2026-11-21
Status: **spec for review, then implement in one room**
Source: Carmelo play reports (t577u–t581u). He likes the musical tones
that already play when a Push Seal crate lands on a new tile, and wants
that sound to *be* the puzzle: shove the block along a hidden path to a
target square that is visible from the start. Tones hint each correct
direction. A wrong shove plays a sour musical double-note (Jeopardy
time-out feel, not a harsh noise buzz) and the crate resets. The notes
of the correct path must form a real melodic phrase that resolves on
the target. A short teaser lets the player learn the phrase by ear.

Facts below were checked against `origin/main` at `b8125c30`. Existing
Push Seal already places a 2x2 gold socket (`BGT_FLOOR3`,
`room_socket_x/y`) and voices `sfx_play_rune((nx + ny) & 3)` on every
off-socket shove; seating the crate on the socket solves, on any route.
This proposal keeps that fixture language and turns one existing
puzzle-eligible slot into a hidden-path melody.

## Goal

1. Enrich one mandatory block-push room so the gold socket stays
   visible, the legal route is hidden, and audio (plus a delayed visual
   fallback) teaches the route.
2. Tie each push **direction** to a **fixed** scale degree so the
   correct path *is* the melody. Author only paths whose direction
   sequence sounds natural and cadences on the target.
3. Stay self-contained in a single room (the standing
   puzzles-are-per-floor rule). No new dungeon-phase bits, no
   cross-room state.
4. Reuse the crate shove in `room.c`, the gold socket, and the rune
   pitch table. Add one new musical error sting. No new tile art, no
   extra sprites, no lasting frame-time cost (slowdown is top priority).
5. First ship: **Stage 1 Waystone, only when the early pool would have
   assigned `PUZZLE_PUSH_SEAL`**. Stage 1 Trial under seed
   `0x51A6D00D` stays an ordinary Push Seal, so
   `scripts/test_puzzles.py::push_seal_contract` does not change.

## 1. Why this slot

`puzzle_slot_kind()` already gives Stages 1–2 a three-kind early pool
(Push Seal, Rune Sequence, Prism Toggle) with Trial and Waystone never
repeating a kind in the same dungeon. The live puzzle-test seed
`0x51A6D00D` makes Stage 1 Trial a Push Seal and Stage 1 Waystone a
Rune Sequence, so replacing *all* Stage 1 Trial push rooms would break
the existing contract.

Rule for v1: if `bosses_beaten == 0` and the Waystone slot would be
`PUZZLE_PUSH_SEAL`, assign the new kind `PUZZLE_TONE_PATH` instead.
The Python mirror `puzzle_slot_kind()` in
`scripts/quintra_topology.py` must match. Later stages keep ordinary
Push Seal until a follow-up expands the pool. The length table in
§4 is written now so that expansion stays consistent.

## 2. Direction-to-note map (fixed, global)

Four cardinal shoves map onto four stable degrees of the existing
major-pentatonic rune scale (`sfx_play_rune` steps 0..3: C5, D5, E5,
G5). The map does not change between rooms or stages, so players can
learn a musical compass.

| Direction | `DIR_*` | Degree | Pitch | `sfx_play_rune` step |
|-----------|---------|--------|-------|----------------------|
| West      | `DIR_W` | tonic (do) | C5 | 0 |
| South     | `DIR_S` | re | D5 | 1 |
| North     | `DIR_N` | mi | E5 | 2 |
| East      | `DIR_E` | sol | G5 | 3 |

West is tonic so a phrase can cadence by shoving left onto the socket.
That makes the *last* step mildly predictable once the player notices
("home is a left shove"). That is accepted for v1: the first N−1 steps
are still hidden, and the teaser still has to be heard. Carbon should
flag this if a rotating tonic (room-local remapping) is worth the lost
global compass.

The existing fifth degree (B5, step 4) is reserved and unused here, so
we do not invent a diagonal shove and we do not collide with five-note
rune phrases.

A correct shove voices that direction's pitch immediately, same
envelope as a mid-phrase rune (`0xF3`, 40-frame CH1 claim). The shove
already plays `SFX_DOOR` in `room.c` before `puzzle_on_block_moved`;
the pitched note must replace or immediately follow that wood-thud so
the melody is the thing you hear, not a door whoosh buried under it.
Preferred: skip `SFX_DOOR` when `room_puzzle_kind == PUZZLE_TONE_PATH`
and let the pitch be the only CH1 voice for that shove.

## 3. How the path is the melody (and why it is not trivial)

The legal route is a seed-stable sequence of cardinal shoves of length
L (§4). There is no painted trail, no unique floor tile, no arrow.
Ordinary apron floor surrounds the crate, so a wrong shove is
physically possible and is rejected by the puzzle, not by collision.

The phrase *is* the direction sequence under the map in §2. A teaser
(§6) plays that phrase from the socket, so the skill is: hear a tune,
translate it into shoves with the fixed compass. Once the compass is
learned this is fair rather than cryptic, but it is never a free
visible path, and every room still has its own tune.

To stay musical rather than a random walk that happens to use four
pitches, v1 does **not** procedurally invent arbitrary L-step routes
and hope they cadence. It picks from a small ROM bank of authored
phrases. Each entry stores:

- the L direction bytes
- the crate's start origin relative to the socket (the vector sum of
  the steps, inverted)
- a short comment naming the tune (for the spec and tests)

Every banked phrase ends on tonic (West / C5), uses only legal 2x2
crate shoves, stays inside the carved apron, does not visit the same
origin twice, and has a non-zero net displacement so the socket is not
the start cell.

### 3.1 Stage 1 bank (L = 4)

Four shoves, last is always West (tonic C5). Net is measured from the
crate's start origin to the socket origin (N = (0,−1), E = (+1,0),
S = (0,+1), W = (−1,0)). Loops (net 0) and monotone triples (EEE, NNN,
SSS) are omitted. Because the cadence shove is West, the socket is
always one tile west of the crate's penultimate cell; it may still sit
east, north, or south of the *start*. A socket due-west of the start
is not in this bank (that would need an eastward overshoot and a
second West, which collapses to a loop at L = 4).

| Id | Melody | Shoves | Net | Why it sings |
|----|--------|--------|-----|--------------|
| 0 | G5 G5 D5 C5 | E, E, S, W | (+1, +1) | sol-sol-re-do: a little amen cadence |
| 1 | G5 D5 G5 C5 | E, S, E, W | (+1, +1) | sol-re-sol-do: question, then home |
| 2 | D5 G5 G5 C5 | S, E, E, W | (+1, +1) | re-sol-sol-do |
| 3 | E5 G5 E5 C5 | N, E, N, W | (+1, −2) | mi-sol-mi-do |
| 4 | G5 E5 G5 C5 | E, N, E, W | (+1, −1) | sol-mi-sol-do |
| 5 | E5 E5 G5 C5 | N, N, E, W | (+1, −2) | mi-mi-sol-do |
| 6 | G5 G5 E5 C5 | E, E, N, W | (+1, −1) | sol-sol-mi-do |
| 7 | D5 D5 G5 C5 | S, S, E, W | (+1, +1) | re-re-sol-do |
| 8 | E5 E5 D5 C5 | N, N, S, W | (0, −1) | mi-mi-re-do |
| 9 | D5 D5 E5 C5 | S, S, N, W | (0, +1) | re-re-mi-do |
| 10 | G5 E5 E5 C5 | E, N, N, W | (0, −2) | sol-mi-mi-do |
| 11 | G5 D5 D5 C5 | E, S, S, W | (0, +2) | sol-re-re-do |
| 12 | D5 G5 D5 C5 | S, E, S, W | (+1, +2) | re-sol-re-do |
| 13 | E5 G5 G5 C5 | N, E, E, W | (+1, −1) | mi-sol-sol-do |

A room seed picks `id = (seed >> 5) % BANK_LEN` and places the socket
with the same 8/10 × 6/8 candidates Push Seal already uses, then
places the crate at `socket - net`. If that crate origin would sit on
a wall, in the doorway slit, or outside the 1..16 / 1..13 origin
range, try the next bank entry (at most a full cycle). Then carve the
axis-aligned bounding apron plus a one-tile margin, the same way
`prepare_push` does, so both start and socket are on open floor and a
wrong shove has space to exist (and be rejected).

The Rust Push Seal mirror is **not** required for v1; the C bank is
the source of truth, and the headless test enumerates the same table.
A follow-up may add a tiny Rust mirror if we widen the bank.

## 4. Path length per stage

| Stage | `bosses_beaten` | Length L | Shape rule |
|-------|-----------------|----------|------------|
| 1 (first ship) | 0 | 4 | Bank in §3.1. One bend or overshoot. |
| 2 | 1 | 5 | Same compass; add a 5-note bank that still cadences on C5. At least one bend. |
| 3+ | ≥ 2 | 6 | Longer bank, at least one jog (a direction and its opposite both appear). |

v1 implements only the Stage 1 row. The table is binding for later
PRs. Five- and six-note phrases may repeat a direction (the compass
has only four pitches) but must still end on C5 and must not be a
straight line.

## 5. Reset and the error sting

A shove that is not the next step of the phrase is a miss, even if it
moves toward the socket or lands on it early.

On a miss, in `puzzle_on_block_moved` (which already runs after
`room.c` has written the new 2x2):

1. Play the new sting `sfx_play_tone_miss()` (§5.1). Do **not** play
   `SFX_HIT` (noise crunch), `SFX_HURT`, or `SFX_REFUSE` (the shop /
   magic "nuh-uh" fourth). Those are the wrong dialect.
2. Snap the crate back to its **start** origin (not one step back).
   Restore any gold socket quadrant the miss covered or vacated.
   Update `puzzle_block_x/y`. The phrase progress returns to 0 so the
   tune restarts cleanly.
3. Do **not** charge a half-heart. This is a routing puzzle, not a
   rune trap. No room shake longer than a 4-frame tap, and no extra
   sprites.

Stepping out and back, or leaving the room and returning, also resets
progress (prepare runs again on entry if unsolved), same as other
fixtures. The always-open return door stays, so a player who feels
stuck can leave; they are not wedged.

### 5.1 Sour double-note (Jeopardy time-out, musical)

New resident dispatcher helper `sfx_play_tone_miss()`, declared next
to `sfx_play_rune` in `sfx.h`. It is musical: two square-wave pitches
on CH1, no CH4 noise.

- Note 1: F5 (GB freq word **1868**), 50% duty, envelope `0xA3`
  (medium-loud, period-3 decay).
- After 10 frames, note 2: E5 (existing word **1849**), same duty,
  envelope `0x93` (slightly quieter, a little longer). The interval is
  a descending minor second — sour, but clearly a pair of notes, in
  the same register as the compass phrase.
- Total CH1 claim ~24 frames. No melody lock long enough to swallow
  the next teaser or a quick retry. No sweep.

This is the "double error" Carmelo asked for, and the later
clarification that it must stay *notes*, not a harsh buzz. Tests
assert CH1 is a tonal envelope (not a noise write to `NR41`–`NR44`)
and that the second frequency is 1849 after the 10-frame gap.

## 6. Teaser: learn the phrase by ear

The socket is the speaker. The player can hear the whole correct
phrase without having to guess the first step in silence.

**Approach teaser.** When the puzzle is locked and the champion's
feet first enter a 2-tile Chebyshev neighbourhood of the socket's
2x2 (not while a shove is in progress, and not while the crate
already overlaps the socket), the socket plays the phrase once:
each step uses `sfx_play_rune_echo(step)` at **24 frames** per note,
the same short echo envelope the Aether Lattice lesson uses (`0xF2`).
The last (tonic) note may use a slightly longer echo so the cadence
sits. Movement and combat stay free. A 150-frame cooldown prevents
the lesson from looping if the player camps the plate. Leaving the
neighbourhood and walking back in may retrigger after the cooldown.

**Echo Chime teaser.** If the room kind is `PUZZLE_TONE_PATH` and
the seal is still locked, `puzzle_chime_reveal` (already called from
the dungeon-tool dispatcher) plays the same phrase immediately,
ignoring the approach cooldown, and does **not** spend a hidden-secret
reveal. Echo Chime remains a shortcut, never a requirement: the
approach teaser is available with base movement alone.

On room entry, do **not** auto-play the phrase. A packed guard room
plus a four-note lesson on the first frame would fight the stage
music and the arrival SFX.

## 7. Accessibility (visual fallback after failures)

The puzzle is audio-forward, but it must be solvable with the sound
off after a fair number of honest attempts.

- After **3** misses in this visit, the *next* correct destination
  cell (the origin the crate should occupy after the next legal
  shove) flashes near-white for 20 frames, using the existing flash
  path (`set_tile_live` + a short timer, no new tile). Luminance
  flash, not a hue-only cue, so it survives common colour-blindness
  and a greyscale GB.
- After **6** misses, the remaining path origins shimmer once in
  sequence (12 frames each) and then go back to ordinary floor. This
  is a one-shot lecture, not a permanent painted trail.
- Miss count clears on solve and on leaving the room. It does not
  persist in `run_state`.
- No HUD text is required for v1.

Hearing-impaired play is: fail a few times, watch the flash, finish.
Able-eared play can ignore the flash entirely.

## 8. Solve, fanfare, and existing contracts

When the crate seats on the socket *as the last legal step*, play
`sfx_play_rune_final(0)` (tonic C5, long hold, delayed `SFX_PUZZLE`
fanfare — same rule as the last rune in
`2026-11-09-puzzle-note.md` / `2026-11-17-music-puzzle-feedback.md`)
and call `mark_puzzle_solved`. The trial/waystone bit, the tool-charge
pickup, the door unseal, and the 18-frame shake stay exactly as they
are for other mandatory puzzles.

If a miss somehow landed on the socket, that is still a miss: sting,
reset to start, socket gold restored. Reaching the gold plate on the
wrong tune does not clear the seal.

Ordinary Push Seal rooms are unchanged: any route onto the socket
still solves, and off-socket shoves still play the position-based
rune blip they play today.

## 9. Fit with self-contained-per-floor puzzles

The entire machine lives in one court. Solve state is the existing
`RUN_WAYSTONE_BIT` (or `RUN_TRIAL_BIT` if a later PR reuses this kind
in a Trial slot). No `dungeon_phase` bit, no remote gate, no
requirement that another room be visited first. Guard pack, combat
seal policy, and "leave by the return door" behaviour match Push
Seal. The fixture does not appear in reserved lore cells, shops,
sanctuaries, or boss rooms, because it only occupies a Waystone
(later: Trial) slot.

This is a sibling of Push Seal and Rune Sequence, not a dungeon-wide
Law / deep-switch puzzle, and not a replacement for the note-plate
phrase (those plates stay visible and coloured;
`2026-11-16-music-tile-colors.md` still applies only to rune rooms).

## 10. Performance

No extra sprites, no per-frame path walk except a cheap
already-on-the-player-update distance check for the teaser (a few
u8 compares) and an optional flash timer decrement. Reset and hint
flashes are a handful of `set_tile_live` calls on the miss or hint
frame, the same cost as a rune reset. The sting and teaser are CH1
one-shots already in the resident dispatcher. Do not add a per-tile
shadow map, do not keep a second copy of the room, and do not run
the 2x2 crate search every frame (keep the existing
`puzzle_block_x/y` watch). Crowded-room slowdown work stays the
priority: this room must not introduce a new hitch on shove, reset,
or teaser.

## 11. Art

Reuse the 2x2 cairn (`BGT_BLOCK*`) and the gold socket (`BGT_FLOOR3`,
door palette) already shipped for Push Seal. No GPT Image 2 pass
unless a later review proves the socket cannot read as "the visible
target" in this room. Hidden path cells stay ordinary floor.

## 12. Tests and previews

New headless script `scripts/test_tone_path_block.py`, plus a
one-shot blackmage wrapper that also runs `test_new_game_start.py`
(including Continue) and `check_rom_layout.py` (banks ≥ 256 free).

The contract, on a seed whose Stage 1 Waystone is `PUZZLE_TONE_PATH`:

1. Arrival: kind and lock set, one cairn, a visible 2x2 gold socket,
   crate not already seated, at least the usual live guard pack
   before the test clears it.
2. A wrong first shove plays the miss sting (CH1 tonal, second note
   1849 after 10 frames, no CH4 noise write) and the crate is back
   at its start origin; the socket is still gold; lock remains 1;
   HP unchanged.
3. Walking the exact banked phrase seats the crate, voices each
   mapped pitch in order (C5/D5/E5/G5 words 1798 / 1825 / 1849 /
   1881), and the last step uses the final-note envelope then
   releases the seal. Waystone (or trial) bit persists.
4. A mid-phrase miss after two correct shoves also resets to start,
   not to the last correct cell.
5. Approach teaser: placing the champion in the socket neighbourhood
   starts an echo of the full phrase in order, 24 frames apart.
6. After three scripted misses, the next correct cell is flashed.

Previews (GIF + a short audio description of each beat) land in
`/workspace/quintra-tonepath/`.

## 13. Implementation sketch (v1, one PR)

- `puzzle.h`: add `PUZZLE_TONE_PATH` after the existing kinds.
- `puzzle_slot_kind` + `quintra_topology.puzzle_slot_kind`: Stage 1
  Waystone Push Seal → tone path.
- `prepare_tone_path(seed)` next to `prepare_push`, sharing socket
  and cairn drawing helpers where they already exist.
- Extend `puzzle_on_block_moved` for this kind (progress, miss
  reset, solve).
- `puzzle_update_player`: approach teaser + hint timers.
- `puzzle_chime_reveal`: Echo Chime teaser.
- `sfx.h` / `sfx.c`: `sfx_play_tone_miss()`.
- `room.c`: skip `SFX_DOOR` on a tone-path shove so the pitch speaks.
- Tests and the topology mirror. Draft PR against `main`. No merge,
  no deploy.

## Open questions for Carbon

1. Is the global West-is-tonic last-step tell acceptable, or should
   the socket add a resolving C5 after whatever the last direction
   was, so last shoves can be any compass point?
2. Is the 10-note Stage 1 bank large enough, and are the named
   cadences actually pleasing on a GBC square wave at these
   envelopes?
3. Approach-teaser radius and 150-frame cooldown: too chatty, or too
   shy?
4. Full reset to start vs step-back for a miss — full reset is what
   this spec picks, because the phrase should restart.
5. Any performance or ROM-resident dispatcher size concern with the
   new sting and the teaser state?
