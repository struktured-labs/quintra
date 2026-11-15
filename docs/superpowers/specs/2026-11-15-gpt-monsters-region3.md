# GPT Image 2.6 monster pass — region 3 (stages 6-8) and Warlock bruiser

Date: 2026-11-15. Follows the region-2 monster pass (#83).

## Scope

Rank-and-file enemies that spawn in stages 6-8, plus the last Bruiser variant.
They are redrawn with GPT Image 2.6 Sunburst (`gpt-image-2.6-sunburst`)
candidates as reference and hand-quantized to each sprite's existing 3-colour
OBJ palette. Every candidate came from the earlier generation batch, so this
pass made no new API calls.

| Enemy | Size | Frame B |
|---|---|---|
| Echo Guard | 8x8 | shield and spear shift |
| Dread Bell | 8x8 | bell swings, clapper strikes |
| Rift Warden | 8x8 | crest flares |
| Dusk Midge | 8x8 | wings beat |
| Sunwheel | 8x8 | rays rotate |
| Void Halo | 8x8 | ring pulses |
| Warlock bruiser | 16x16 native (was a 2x-scaled 8x8) | hooded caster, staff sparks |

The Warlock bruiser uses `BRUISER_WARLOCK_A/B` in `BRUISER_SRC` and its own
`ENEMY_ANIM` entry on slot 64. Slot 64 is shared by design with Cinder Maw,
and the two never appear together.

## Budget

`[layout] OK`: home ends 0x3F82 (unchanged). The Warlock B frame adds 128 B to
the autobanked atlas, and the autobanker re-packed it: bank 2 free 535 → 495 B,
bank 5 free 549 → 461 B, bank 6 unchanged at 446 B.

## Verification

- `cargo test` (31) passes.
- PyBoy results are listed in the PR body.
- Before/after GIFs come from headless PyBoy captures of the same seeds and
  rooms (`docs/previews/monsters-region3/`). For Sunwheel the enemy was moved
  on-screen.
