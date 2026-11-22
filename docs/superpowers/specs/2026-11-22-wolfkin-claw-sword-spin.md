# Wolfkin Claw Sword: readable blade, 360° spin slash, reserved tiles

Date: 2026-11-22. Follows `2026-11-21-wolfkin-longsword.md` (#187).

struktured playtested the longsword (t628u). The kit is a viable path to
victory, but:

1. The sword looks bad, and the slash animation looks terrible. Top priority
   is readability: it reads as a garbled sprite.
2. Mid-run the sword turned into "four unrelated symbols" (live bug).
3. The slash is not useful enough. Suggestion: a round-trip slash all the
   way around Wolfkin. A ~180-270° arc is also acceptable if it plays and
   reads better.
4. Rebrand it as a **Claw Sword**: a real blade with a wolf/claw look
   (fang-curved tip, claw notches, three-claw guard). Not Wolverine claws.

## 1. Root causes (measured on main `339c1db4`)

**Garbled sword (bug).** The sword's 16 tiles were loaded once into bank-1
OBJ 160..175. That is also `MAGIC_TILE` (160, 16 tiles), the spell-art
window, and `magic_room_enter()` rewrites it on every room entry and Pack
resume. The sword's `tiles_loaded` latch then never reloaded. After the
first door or Pack visit, every slash and stab drew spell glyphs (the
segments show as 3-4 unrelated symbols). Headless repro: swing, open and
close the Pack, swing again. All 16 sword tiles differ.
`evidence`: `repro_garbled.png` in the PR previews.

**Ugly slash (art).** The slash drew the same three hand-made tiles for
every heading, flipped, at three fanned boxes 12 px apart. The fan left
gaps and mismatched pieces, so it never read as one blade.

**Weak slash (design).** Front plus two diagonals, 22 px, 4 live frames.
Anything at the side or behind was safe, and the swing was hard to land
compared to the stab.

## 2. Tile reservation

- The Claw Sword owns **bank-1 OBJ 144..159**, reserved (header comment in
  `wolfkin_sword.h`). A static scan of every bank-1 `set_sprite_data` and
  `set_bkg_data` call found no other writer there. BG data goes to
  0x9000+, so it does not alias 0x8900.
- `wolfkin_sword_load()` also runs on every room entry and Pack resume,
  beside `magic_room_enter()`. A screen outside the room that rewrites
  bank 1 (title, class select, vignettes) can't leave a stale blade.
- Regression test: tiles at 144..159 must equal the ROM art after a
  swing, Pack open/close, a spell, a Will MAX, and a room change. For a
  non-Wolfkin hero the window must stay untouched (proving nothing else
  writes it).

## 3. Art (Claw Sword)

GPT Image 2 (`gpt-image-2.6-sunburst`) made two reference renders: a
horizontal blade and a 45° blade, with a fang tip, back-edge claw
notches, and a three-talon guard. At 8x8 per tile, automatic downscaling
lost the outline and the tip, so the tiles are hand-placed from those
references in `tools/claw_sword_art.py`. That script prints the C
initializer. It uses 4 OBJ colours: transparent, pale edge, steel, and
outline.

| Tiles | Use |
|---|---|
| 0..3 | East blade: fang pommel + wrapped grip, three-claw guard, notched blade, fang tip |
| 4..7 | North blade (rotation of 0..3) |
| 8..10 | NE diagonal: hilt, blade, tip, placed in **6 px steps** so the 8x8 tiles overlap 2 px and the joints never pinch |
| 11, 12 | Spin arc trail for the NNE and ENE half-headings (all 8 by flips) |
| 13, 14 | Blank (smear off) |
| 15 | Full-heart beam: symmetric claw spark, reads in any heading |

All 8 headings come from H/V/diagonal plus X/Y flips. The blade is
parented: its guard sits at the body edge, the hand, every frame.

## 4. Spin vs. wide arc

Options: (a) 360° spin, (b) 270° arc, (c) 180° arc.

**Chosen: 360° spin.** Reasons:
- It matches the "round-trip all the way around" ask, and it's the only
  one of the three with no blind side. Wolfkin is the melee hero who gets
  surrounded. A 270° arc still leaves a 90° gap behind him, which is
  exactly where melee chasers sit.
- It reads clearly: one blade turning a full circle with a trail behind
  it is the most legible motion at 8x8 OBJ scale. A partial arc needs a
  start and stop pose that looks a lot like the stab.
- It doesn't trivialize fights, because the cost is time, not reach. It
  has a 3-frame telegraphed cock-back, and the next swing waits 30
  frames instead of 20. Single-target DPS drops from 15.0/s to 10.0/s (11.5/s at the 26 f SPD floor),
  so the stab (20.8/s) stays the precise boss tool.
- The 270° variant would have cost the same OAM and nearly the same
  code, but it gives up the omnidirectional crowd clear that makes the
  slash worth pressing.

## 5. Numbers

**Spin (neutral A, pad released)**

- Cock-back: 4 frames (spawn + 3 updates). The blade is drawn one
  heading behind the aim, not live.
- Sweep: 8 headings clockwise from the aim, exactly 2 frames each, then 2
  frames back at the front. That's 16 + 2 live frames, and life is 21
  frames. Cardinal blades flip so the pale cutting edge leads the
  clockwise turn. Diagonals can't do that with flips alone: NE/SW lead,
  SE/NW trail.
- Blade: 3 tiles (guard, blade, fang tip). Tile centres are 12/20/28 px
  from Wolfkin's centre on cardinals and 8/14/20 px per axis on
  diagonals (about 28 px Euclidean, clear of the body corner), so the
  tip sits about 32 px out on every heading (about 24 px past the body
  edge).
- Arc trail: 1 tile 15° behind the blade, 25 px from centre, live from
  step 1. It kisses the back of the tip and fills the angular gap
  between headings.
- Hitboxes are 10x10 per tile (Longreach: 12x12), centred on the 8x8
  tile, so reach is the same on every side. Coverage is analytic: any
  8x8 body whose centre is within 32 px of Wolfkin's centre is touched
  at some step, at every angle (100%).
- Damage: 5 (weapon 1 + ATK 2 + 2), same as the old slash.
- Once per enemy per swing: a shared 8-body latch (was 4). Blade, trail
  and beam share it. A full latch stops further damage that swing, and
  never re-hits.
- Pierce: segment hp 8, so the latch, not hp, ends a crowd swing, and no
  tile vanishes mid-turn.
- Cooldown: 30 frames (was 20 via weapon rate). Run-earned SPD may shorten
  it through `player_fire_delay`, but never below 26 frames. That leaves
  a 5-frame open window after every spin, and a spin can't restart its
  latch mid-swing. Stab gets a matching floor of 12 (life + 2).
- Slot pressure: the sword waits (no cooldown spent) until there are free
  entity slots for the whole blade, so it never draws a stub.
- Blade segments never carry Ricochet, because they don't travel.
- OAM: 4 sprites (3 blade + trail), plus 1 for the full-heart beam (fired
  along the aim at the cock-back).

**Stab (A with d-pad held): unchanged in role**

- 9 damage, 26-frame cooldown (SPD floor 12), 32 px past the body edge on cardinals,
  narrow 8x8 boxes, grows out from the hand.
- New art. Diagonal stabs use the 6 px chain (about 20 px per axis).

**Will scaling.** The sword has no per-level Will hook. Max Will stays
Moonfang Cross-Rend, the same as before. No change.

## 5b. Carbon review (2026-11-22)

One Carbon call on this spec, the code, and the captures. Verdict: **ship
with changes**. Applied in this PR:

- Stab cooldown floor (life + 2), alongside spin's, so SPD can't reset
  the shared latch mid-swing.
- Diagonal spin offsets 6 to 8 px (28 px Euclidean, off the body
  corner). Spin boxes are centred on the tile (top-left anchoring had
  favoured S/E by 1-2 px).
- The 1-based age off-by-one: the cock-back now really lasts 3 updates,
  and each step, including the final front step, owns exactly 2.
- Removed Ricochet from parented segments.
- Full-blade slot pre-check (no stub swords, no cooldown spent).
- The spin's cardinal cutting edge leads the clockwise turn.
- The diagonal blade is thicker and single-edged, with spine notches, a
  hooked fang tip and a wider guard.
- The trail sits closer to the tip (15° behind, r 25).
- Balance: Carbon kept 360° over 270°. It flagged SPD builds as a
  possible "walking buzzsaw", so the SPD floor is 26 f, not 23.

Not taken: a separate beam latch (beam TTL vs cooldown is unchanged
from #187), a spin move-slow (left for playtest), and a build-time VRAM
allocator (the runtime regression test guards the window).

## 6. Rename

Item 0 `Longblade` is now **Claw Sword** ("Spin all round, stab deep. Full
hearts: beam."). Internal symbols stay `wolfkin_sword_*`.

## 7. Tests

`scripts/test_wolfkin_longsword.py`:
- Spin hits enemies on all 8 sides exactly once (5 damage each). A body
  48 px out is untouched.
- Spin cooldown is at least 23 frames.
- Stab reach and damage, beam latch, Formation beams, sprite reach, and
  attract reach still hold.
- VRAM: the sword window equals the ROM art after Pack, spell, Will MAX
  and a room change. It's untouched for Vespine.

Plus `check_rom_layout`, `test_new_game_start` (with Continue), and
`test_performance`.

## 8. Out of scope

Max Will redesign, other heroes, publishing, itch, Pocket, MiSTer.
