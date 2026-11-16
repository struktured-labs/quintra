# GPT Image 2.6 pass: Road Echo companion

Date: 2026-11-15. Follows the hero/Sentinel and monster passes (#80, #81, #83,
#84, #90).

## Scope

The Road Echo follower (`sprite_companion_walk` in `src/render/tiles_town.c`)
is redrawn from a `gpt-image-2.6-sunburst` edit of its existing upscaled 16x16
two-frame walk, then hand-quantized back onto the same four color roles.

The three kinds still share one body and the palettes they already borrowed:

| Kind | Palette slot | Voice |
|---|---|---|
| Hearth | OBJ 4 | heart-red |
| Way | OBJ 5 | gold landmark |
| Aether | OBJ 6 | stage-magic |

No new palette upload, no new tiles, no new OAM. The companion is front-facing
only (the renderer does not flip it), so this pass keeps the two walk beats it
already had and does not add facings.

## Art

Two candidates were generated at low quality, 1024x1024, from the existing
walk sheet. Glow and antialiasing from the model were discarded. The
hand-cleaned 16x16 keeps the recognizable lantern-hooded traveler and adds:

- a pointed two-pixel lantern cap on a stable head
- a two-pixel smile on the face
- the original robe, eye lights, and out/in foot pattern

Color roles stay 0 transparent, 1 body (face, hands, feet), 2 shadow (brow,
mouth, torso), 3 accent (hood, eyes) so the same pixels stay readable in red,
gold, and violet.

## Budget

Unchanged: 8 OBJ tiles at `SPR_COMPANION_WALK_A` 224..231 (4 tiles per beat),
4 OAM sprites, 128-byte atlas, hitbox 0. Follow, fire, and ask logic are
untouched. `check_rom_layout` must pass.

## Spend

One `images/edits` call (`n=2`, `1024x1024`, `low`): $0.0689. Program total
about $4.00 of the $100 budget.

## Verification

- `python3 scripts/check_rom_layout.py rom/working/quintra`
- `scripts/test_companion.py`
- `scripts/test_companion_greeting.py`
