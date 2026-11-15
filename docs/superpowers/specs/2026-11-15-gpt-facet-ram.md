# GPT Image 2.6 pass: Facet Ram

Date: 2026-11-15. Follows the region-1 to region-3 monster passes (#81, #83, #84).

## Scope

Facet Ram (enemy 33) was the last regular enemy without GPT art. The region-1
spec left it out because it has its own facing driver: two authored 16x16 views
(H faces east, V faces south), mirrored for west and north. This pass redraws
both views from one `gpt-image-2.6-sunburst` reference (2 candidates, low
quality, $0.0674). The reference was hand-quantized to OBJ palette 6 and keeps
the original layout:

| View | Base frame | Walk frame (B) |
|---|---|---|
| H (east) | crystal ram, curled ivory horn and snout on the right, ivory rune on the rump (left) | opposite leg stride, rune flicker |
| V (south) | horned face at the bottom, ivory rune at the top | legs tucked, rune flare |

The rune is still the bright, vulnerable rear in both views, so the rear-only
damage read is unchanged.

## Animation

Facet Ram stays out of `ENEMY_ANIM`. Its two views sit back to back at OBJ
242..249, so the new generated `src/render/facet_ram_anim_gen.c` stacks H over
V into one 16x32 unit. `facet_ram_anim_tick()` uploads frame A or B over all 8
tiles once per 16-frame beat, on the shared `entity_anim_counter`. Each live
ram's `facet_ram_update()` calls it, and it returns at once if the beat is
already uploaded.

The file is pinned to bank 17 (about 12 KB free). Autobanking the extra 256 B
pushed bank 2 below the 256-byte floor, and pinning it keeps the other
autobanked atlases where they were. The cost elsewhere is the 8-byte banked
call in bank 11 and one WRAM byte.

Visual only: hitbox, timing, AI and rear-hit rules are unchanged.

## Verification

- `cargo test`: the new `facet_ram_walk_beat_is_distinct_and_matches_source`
  check passes along with the rest of the suite.
- Before/after GIFs come from headless PyBoy fixture captures (east walk, then
  south walk) on the merged-main ROM and this branch.
