# Bigger Cinder Rex — larger bodies, larger things to avoid

Date: 2026-11-15 · Stage 3 (Ember Kiln) champion · owner ask: "the stage 3 boss … should be bigger in general, larger things to avoid"

## Goal
Make the Ember champion read as a colossus instead of a 32x16 lizard, and make
the hazards big, telegraphed squares the player dodges by position — without
new flicker, slowdown, or OAM budget breaks (40 OAM, 10 sprites per line).

## Design
- **Kilnbacks 16x8 → 16x16.** Each crucible is a 2x2 quad (walk A / walk B /
  blown vent / husk quadrants of one 32x32 sheet in bank-0 OBJ 40..55). Armor
  stays on the lower half, the vent is the weak point. Contact box 14x14, shot
  box 16x16. Kiln Press staggers odd members one body height (16px) behind the
  line, so a formed press puts 3 bodies (6 sprites) on a line, at most 4
  bodies while regrouping (old phalanx: 5 bodies, 10 sprites).
- **Cinder Rex 32x16 → 48x32.** A 6x4, 24-sprite furnace hound drawn from
  bank-1 OBJ 64..87 (idle) and 88..111 (roar head band / stride leg band),
  loaded only in the Ember arena. Generated with gpt-image (edit of the
  existing GPT Rex; $0.0959), quantised to the Ember OBJ palette.
  - Drawn at OAM 16..39 (the tail of OAM). The CGB picks the 10 sprites per
    line by lowest OAM index, so bullets/hazards (OAM 4..15) win a crowded line
    and only Rex edge columns drop for a frame — the player never loses sight
    of something that can hurt them. Generic passes honour `entity_oam_cap`
    (16 during the Rex phase, 40 otherwise).
  - Contact box inset 4/6px (40x28); shot armor covers the full body; the jaw
    remains the weak point. The body is clamped inside the arena; turning
    swaps ends around the same body.
- **Fire pools: BG tiles, not sprites.** Stomp/Slam/Brandwalk hazards are
  24x24 (phase 2) or 16x16 squares painted into the background map with
  bank-1 BG tiles 64..71 (BGPAL_CRACK). Each pool shows a dark warning square
  with a dotted ring for its delay, then ignites (SFX_TICK) into a lit flame;
  only the lit square, inset 2px, burns. The floor under each pool is saved
  and restored exactly on expiry; overlapping pools share ownership. Pools
  cost zero OAM, so they can be big without touching the sprite budget.
- **Furnace Breath** wall lanes skip the columns the Rex body occupies.

## Budget / measurements (PyBoy, headless, same scripted fight, before = origin/main 516ca1d7)
| phase | game updates | worst sprites/line | overflow lines | dropped hazard/bullet sprites | dropped boss sprites |
|---|---|---|---|---|---|
| pack, 600 frames, before | 518 | — | 11 | 0 | 0 |
| pack, 600 frames, after | 524 | 9 | 0 | 0 | 0 |
| Rex, 1200 frames, before | 1065 | 18 | 933 | 375 | 0 |
| Rex, 1200 frames, after | 1063 | 14 | 690 | 0 | 313 (edge columns) |

Banks: new code/art in bank 18 (~13 KB free), bank 9 ~1 KB free, home 0x3F7B.

## Tests
- `scripts/test_cinder_big.py` (new): quad layout, press line budget, 48x32
  bank-1 Rex at OAM 16..39 with unique tiles, tail armor, contact inset,
  stomp pools (warning → lit tiles, square-only burn, exact floor restore),
  furnace wall parts around the Rex, no low-OAM sprite dropped.
- `test_colossal_cinder.py` and `test_cinder_rex_pose.py` updated for the new
  geometry (`test_colossal_cinder` was already failing on main; it passes now).

## Argon review (ship-with-changes), applied
- **Pool warning floor:** every pool warns >= 24 frames (16x16) / 28 frames (24x24); the authored burn time is kept
  (ttl grows by the added warning). The slab-tail slam's 20-frame tell is now 28. Last 6 frames flash: flame (3) ->
  ring (3) -> burn. Fixes the unreactable 12-20 frame slam centred on the champion.
- **Corner seal:** while the 48x32 body is within 48px of a wall, pools keep 16px off that wall, so a 16x16 escape
  strip along the wall always stays clear (Stomp, Brandwalk trail, slam band).
- **Contact box 36x24, biased down:** 6px off each side, 6px off the top spikes, 2px off the toes. A Rex edge column
  dropped on a crowded scanline never leaves invisible hitbox outside the art.
- **Furnace Breath:** lanes through the Rex columns are no longer skipped. A lane that reaches the body hops to its far
  edge, so there is no safe pocket on either side and still no lane sprite on the body's scanlines.
- **Kiln Press:** test asserts no pinch: neighbouring crucibles (excluding the vaulting one) leave either no gap or >= 12px.
- Cost: Rex-phase gameplay updates 1062 -> 1004 per 1200 frames (main 1064). About 35 of the drop is the extra
  Furnace Breath lanes, about 14 the flash. Bullet/hazard sprite drops stay at 0 (main 377).
