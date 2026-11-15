# GPT Image 2.6 monster pass — region 2 (stages 3-5)

Date: 2026-11-15. Follows the region-1 monster pass (#81).

## Scope

Rank-and-file enemies that spawn in stages 3-5, redrawn with GPT Image 2.6
Sunburst (`gpt-image-2.6-sunburst`) candidates as reference and hand-quantized
to the 3-colour OBJ palette each sprite already used. Every candidate came from
the earlier generation batch, so this pass made no new API calls.

| Enemy | Size | Frame B |
|---|---|---|
| Skeleton | 8x8 | jaw drops, arms swing |
| Wisp | 8x8 | flame flickers taller |
| Sentry | 8x8 | eye shutter narrows |
| Mirror Moth | 8x8 | wings fold |
| Mire Spore | 8x8 | cap puffs, spores lift |
| Shade | 8x8 | hem ripples |
| Rune Lantern | 8x8 | glyph flare |
| Prism Skitter | 8x8 | legs shuffle |
| Bog Toad | 8x8 | throat sac swells |
| Bramble | 8x8 | thorns sway |
| Frost Lancer | 8x8 | same silhouette as before, plus a lance; legs step |
| Rift Cantor | 8x8 | mouth opens (chant) |

## Animation

Each enemy uses the region-1 `ENEMY_ANIM` table and gets an authored B frame
(`Some(&NAME_B)`) in place of the old mirrored copy of A. The atlas already
stored a mirrored B for every enemy, so authored frames cost nothing extra.
The change is visual only: hitboxes, timing, AI and WRAM are untouched.

## Budget

`[layout] OK`: unchanged from main (home ends 0x3F82, bank 6 free 446 B, all
other banks identical).

## Verification

- `cargo test` (31) passes. That includes the generated-atlas golden check.
- PyBoy results are listed in the PR body.
- Before/after GIFs come from headless PyBoy captures of the same seeds and
  rooms (`docs/previews/monsters-region2/`). For skeleton, bog toad and
  bramble the player was moved next to the enemy. For frost lancer the enemy
  was moved on-screen.
