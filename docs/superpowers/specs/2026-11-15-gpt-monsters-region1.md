# GPT Image 2.6 monster pass — region 1 (stages 0-2)

Date: 2026-11-15. Follows the mini-boss animation pass (#80).

## Scope

Rank-and-file enemies that spawn in stages 0-2, redrawn with GPT Image 2.6
Sunburst (`gpt-image-2.6-sunburst`) candidates as reference and hand-quantized
to the GBC 3-colour OBJ palettes each sprite already used:

| Enemy | Size | Palette | Frame B |
|---|---|---|---|
| B.Crawler | 8x8 | 3 blue | legs alternate |
| Hornet | 8x8 | 5 gold | wings swept down (beat) |
| Rope | 8x8 | 7 green | tongue flick, S-curve shifts |
| Fold Star | 8x8 | 5 gold | rays fold into a bright diamond |
| Flutterbat | 8x8 | 0 bone | wings folded |
| Gloam Leech | 8x8 | 4 red | crescent clenches shut |
| Rift Ooze | 8x8 | 7 green | squash |
| Cinder Kite | 8x8 | 4 red | wings raised |
| Vine Coil | 8x8 | 7 green | leaf crown sways |
| Shard Crab | 8x8 | 6 crystal | claws up, legs shuffle |
| Orc bruiser | 16x16 native (was 2x 8x8) | 7 green | club-carrying grunt, step |
| Bomber bruiser | 16x16 native (was 2x 8x8) | 4 red | walking bomb, fuse sparks |
| Cinder Maw (medium) | 16x16 | stage | maw pulses, flames lick |

Bruisers are drawn a size class below their mini-boss cousins so the two never
read alike.

## Animation

`enemy_anim_tick()` (generated `src/render/enemy_anim_gen.c`, autobanked) runs
from the shared entity renderer every 16th frame. For each enemy type present
it streams frame A or B into the enemy's canonical OBJ slot once
(`set_sprite_data`, same mechanism as the boss pose loaders). Bodies whose
`sprite_tile` was re-pointed away from the canonical slot are left alone.

Every 8x8 enemy is in the table. Enemies without an authored B frame stream a
mirrored copy of A, which reproduces the old whole-sprite X flip exactly, so the
`S_FLIPX` toggle in `entity_draw_core.h` was removed. Bosses, the Sentinel,
Facet Ram and the Reaper keep their own pose drivers.

Visual only: no new WRAM, no hitbox, timing, or AI changes.

## Budget

`[layout] OK`: home ends 0x3F76 (was 0x3F7C, 6 B freed by dropping the flip),
bank 6 free 661 → 458 B (atlas + tick), bank 2 unchanged at 535 B.

## Verification

- `cargo test` (31): new `enemy_animation_table_is_consistent_and_matches_source`
  golden-checks the generated atlas.
- PyBoy: champion_animation, cinder_kite, colossal_cinder, enemy_patterns,
  hornet_swarm, leech_detach, ooze_cycle, shard_crab, title_sprite_leak,
  resume_sprite_palette, boss_identity, suspend, reaper_pose pass.
  bramble_sprite, medium_cinder, farfold_cache and enemy_identity fail
  identically on unmodified main.
- Before/after GIFs: headless PyBoy captures of the same seeds/rooms
  (`docs/previews/monsters-region1/`).
