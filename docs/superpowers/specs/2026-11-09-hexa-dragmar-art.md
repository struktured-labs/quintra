# Hexa Dragmar body art

The first sanctum filled its 16×13 footprint by cycling the nine walkable
colossus tiles. That reads as a quilt, and the bright tiles sit in the same
luminance band as the limb heads and the shots.

## VRAM

`BGT_COLOSSUS_VOID` is 55, not 148. Tiles 55..63 are the shared colossus
atlas and the Mire root shapes. GBDK writes background patterns at `0x9000`,
so a background index of 128 or more spills into the tilemap. Indices
148..163 also alias OBJ slots used by items, the beam, and the walk cycle.

The 16 body patterns use background indices 40..55. 40..54 are the shop-offer
and compass glyphs, which are never placed in a room tilemap, and 55 is
already walkable. The bytes live in ROM bank 15 and in VRAM bank 1 at `0x9000` (attribute bit 3).
That does not touch bank-1 OBJ tiles 64..87, 88..127, or 208..213, and it
leaves bank 0 tiles 55..63 for Mire roots and the other colossi. `NH` and
`RV` had no pixel grid in the art note; they follow the same low-noise
index-1 body as the tiles that did.

## Color

Background palette 5 stays at or under the dark clamp (color 3 no brighter
than RGB 15,11,20). Limb OBJ palette 5 and projectile OBJ palettes 3 and 4
are loaded for the sanctum only, above that floor. While a spotlight is on,
the core uses background palette 6, so it takes the spotlighted class's hue.
With no spotlight the sealed core stays on palette 5 and the open core uses
the default palette 6.

## Collision and time

Every new body index is walkable. Limb heads and the core keep their existing
hitboxes. Phase changes rewrite four core tiles. The spotlight still
recolors only the socket that changed, plus the four core attributes.
