# Crystal Colossus second pose

The 32×32 colossus drawer called `set_sprite_tile`, `set_sprite_prop`, and
`move_sprite` once per tile, 48 calls for a 16-sprite body. That was the
frame cost on Void Lord and the other square colossi. `colossus_oam_draw`
(bank 12) writes `shadow_OAM` directly, the same way the 16×16 path already
does. Home only pays for one banked call, so the square-boss drawer can
grow without crossing `0x4000`, and the recovered time pays for the pose bit.

Crystal's second pose is 16 OBJ tiles in VRAM bank 1 at 128..143. That
leaves Hexa's background tiles 40..55 and limb tiles 88..127, the
large-boss poses at 64..87, and the vertical shots at 208..213 alone.
Status marks start at 224. The upload runs from
`room_load_stage_obj_identity` (bank 13) when the stage is 0. Bank 2 has no
room for another call. Every stage-identity load wipes bank-1 OBJ
128..143 first when that stage is entered, so a later Rex room cannot
keep Crystal's tiles. The draw points the 16 sprites at 128 and sets the
bank bit.

The idle frame stays the checked-in Crystal grid. The second frame lifts the
fists, pulls the legs up, and swaps the torso highlights. It is selected
while a signature is armed, during the phase freeze, during the last 18
ticks before a well warp, and on every other 16-tick beat.
