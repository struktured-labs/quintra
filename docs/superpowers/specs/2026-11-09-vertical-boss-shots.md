# Vertical boss shots

#27 mirrored the bank-0 bolt and crescent. Those glyphs are horizontal.
OAM can flip a sprite. It cannot turn it 90 degrees, so a north or south
lane still showed the sideways picture.

Bank 0 tiles 208..223 are full. VRAM bank 1 tiles 208..213 are free in a
boss room: status marks start at 224, and the large-boss poses use 40..87.
The north bolt (2 tiles) and the north crescent (4 tiles) load there once,
with the rest of the boss-shot atlas. The loader sets `VBK_REG` back to 0.

A lane within four angle steps of north or south selects that art with the
OAM bank bit. South also sets `S_FLIPY` and swaps the tile rows, so the
point or the solid back leads. East and west keep the #27 mirror. Hitboxes
stay on the entity, not the glyph. OAM count is unchanged.
