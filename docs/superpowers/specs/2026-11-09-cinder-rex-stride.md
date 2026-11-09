# Cinder Rex roar and stride

The 40px hitbox, the eight-sprite body, and the west-facing atlas stay.
Act 1 still draws the ten Kilnback sprites. This pass adds a second
picture for the Rex only.

VRAM bank 1 tiles 128..135 hold one 32×16 pose. The top row opens the
west jaw onto heat. The bottom row reaches the foreleg and trails the
rear foot. That range leaves Hexa's background tiles 40..55 and limb
tiles 88..127, the large-boss poses at 64..87, and the vertical shots
at 208..213 alone. `cinder_draw` sets the sprite bank bit on the head row while Furnace
Breath, Slag Spit, or the charge telegraph is playing, and on the leg
row during Kiln Stomp, the charge, and every other walk beat. The two
beats can play apart. East travel still mirrors with `S_FLIPX` and
reversed columns.

The upload runs from `room_load_stage_obj_identity` when the stage is 2.
Bank 0 tiles 48..55 remain the idle Rex. Spider and Hydra do not use
this room, so their bank-1 range is untouched.
