# Cinder Rex native furnace art

Verified against `main` after #27 and #29. Those commits did not touch
`boss_maw()` or `cinder_draw()`. The stretched column is still live.

## What the source actually does

`boss_maw()` stamps a 32×16 `REX` into the lower half of the 16-tile stage
atlas. `cinder_draw()` then paints it as five columns with
`stretched_col = {0,1,2,2,3}`, so column 2 appears twice. A headless capture
of phase 2 shows OAM tiles `48,49,50,50,51` on one row.

`cinder_rex_facing` is 0 when `dir8_dx` is positive (east) and 1 when it is
negative (west). The atlas jaw sits in column 0. An east step therefore has
to mirror, or the jaw trails the body. The contact box stays
`x .. x+40` by `y .. y+16` in both `cinder_body_contact` and
`cinder_shot_touches_body`. HP, formations, vent targeting, and the four Rex
attacks are unchanged.

Ember's OBJ palette is `(0,0,0), (22,9,4), (6,2,1), (31,27,10)`. Index 1 is
the rust brick, index 2 is the near-black iron, index 3 is the heat. Pixel
strings use those indices. A literal "1 = darkest" grid would paint the
brick volume black.

## Picture

Kilnbacks stay 16×8, prow on the right, two tiles, no flip. Closed walks are
a flat boiler with two chimney rims and piston stompers, and no magma
speckles except the 2×1 eye. Vent opens a white-hot trough. Husk drops the
roof and sits on the floor.

Rex is one 32×16 hound: jaw and 2×2 eye in column 0, twin stacks in column 1,
three-bar molten ribs in column 2, slag-hammer tail in column 3, two pillar
legs. No post-stamp pixels. The draw loop is `2×4`. East (`facing == 0`)
uses `S_FLIPX` and reversed columns. The sprite origin is `sx + 4`, so the
32px picture sits in the middle of the 40px box.

OAM for the body falls from 10 to 8. Hazards still stop at slot 21. Five
Kilnbacks on one row are still the ten-sprite scanline case.

## Tests

`cinder_rex_is_a_native_four_column_furnace_hound` pins the eye, the open
vent, the collapsed husk, and four distinct Rex columns. The live Ember
contract expects eight unique tiles `48..55` and still runs Furnace Breath,
Slag Spit, Kiln Stomp, Charge, and the five-husk reprise. The golden sprite
blob is regenerated from `boss_maw()`.
