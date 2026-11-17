# GPT Image pass: secondary B-weapon sprites

Date: 2026-11-16
Status: implementation
Model: gpt-image-2.6-sunburst

## Scope

Redo the four equippable B-button tools so each has a readable 8x8
silhouette at GBC scale. The morningstar is the example that started
this pass; the other three extra weapons are included.

| Item | ID | Current tile | Problem |
|---|---|---|---|
| Boomerang | `ITEM_ID_BOOMERANG` (45) | `SPR_ITEM_BOOMERANG` (128, bank 0) | Thin chevron, easy to miss in flight. Same tile is the shop/inventory icon and the returning projectile (flipped through `PROJ_VIS_FLIP_*`). |
| Hookshot | `ITEM_ID_HOOKSHOT` (46) | `SPR_WAYGEAR_HOOK` (206, bank 0) | Shared with Waygear Rift Hook (chasm walk). Keep one tile; improve the hook+eye+chain silhouette for both. Chain links stay `SPR_BULLET` (untouched). |
| Morningstar | `ITEM_ID_MORNINGSTAR` (47) | hardcoded **237** | No dedicated art. Palette 13 already requests OBJ VRAM **bank 1**, but `status_effects_load` occupies bank-1 tiles 224–237 with status glyphs, so the live icon is glyph 13. Shop/projectile and inventory (prop 11) both already set the bank bit. |
| Bomb Bag | `ITEM_ID_BOMBS` (48) | `SPR_ITEM_RIFT_BOMB` (152, bank 0) | Shares the Rift Bomb *relic* icon. A thrown fuse-bomb should be distinct from that relic. |

Hitboxes, timing, damage, and cooldowns stay as specified in
`docs/superpowers/specs/2026-11-15-will-scaled-b-weapons.md`. This is art
only, plus the dedicated tiles that spec already asked for.

## Tile budget

- Give Morningstar `SPR_ITEM_MORNINGSTAR` = **239**, OBJ VRAM bank 1,
  loaded next to the antidote at 238. Palette prop stays **13**
  (coin gold, bank bit set) in the world/shop/projectile and **11**
  (magic, bank bit set) in the inventory signature slot.
- Give Bomb Bag `SPR_ITEM_BOMB_BAG` = **240**, OBJ VRAM bank 1. World
  and fuse flash use heart palettes 4 and 5 with the bank bit
  (`12` / `13`). The Rift Bomb relic at 152 is unchanged.
- Bank 1 tiles 239–240 sit after the 14 status glyphs (224–237) and
  the antidote (238). Boss bank-1 overlays (Cinder Rex 64–111, serpent
  jaw / crystal 128–143, boss bolts 208–213) do not reach 239–240.
- Boomerang and hook stay in their existing bank-0 slots.
- +0 OAM. +2 OBJ tiles in bank 1. A few dozen bytes in bank 10
  (`tiles_items.c`).

## Art constraints

Each weapon is one 8x8 Game Boy tile, 3 opaque colors plus color 0
transparent, matching the palette it already uses. One frame each
(the boomerang already animates by X/Y flipping that single tile).
Quantize GPT Image 2.6 Sunburst candidates by hand, same pipeline as
Speed Ring / Swift Fang (#61) and the antidote icon.

Skipped: class signature B moves, primary attack FX (sword, flail,
spear, spike, beam, arrow), Waygear glove/raft/worldglass, hook chain
links (shared bullet tile), all relic icons including Rift Bomb.

## Pass 2 (morningstar in motion)

The 8x8 world tip was still lost in flight because `hookshot_draw` spent
4 OAM on a bright `SPR_BULLET` chain plus an 8x8 head. Shop/inventory
keep the 8x8 at 239. The in-world projectile now uses a 16x16 head
(`SPR_ITEM_MORNINGSTAR_BIG` = 241, tiles 241-244, bank 1) drawn with
`morningstar_draw`: 4 OAM, centered on the same point (`x-4, y-4`).
Hitbox stays 0xAA (10x10). Timing, damage, and cooldown unchanged.
Live OAM use stays 4 (budget-neutral vs the previous chain).
Boomerang, hookshot, and bomb bag art are unchanged in this pass.

## Pack-resume test

`scripts/test_secret_door_seal.py` waited a fixed 4 ticks after pack
close. `room_enter` runs with the LCD off, and PyBoy ticks make limited
progress in that state, so the extra bank-1 tile copies raced the
resume blit (inventory frame tile 246 still in VRAM). The test now
waits for `DISPLAY_ON` (capped at 40 ticks).
