# Sun Golem halo pose

Stage 6 already has its own temple body. The second beat lifts both arms,
drops the resting shoulder bar, pulls the left foot up, and adds a bright
arc over the crown plus a wider sun-heart.

Sixteen tiles upload to VRAM bank 1 at 128..143 from
`room_load_stage_obj_identity` when the stage is 6. That range stays clear
of Hexa's background tiles 40..55, Hexa's limbs at 88..127, the large-boss
poses at 64..87, and the vertical shots at 208..213. The draw points the
16 sprites at 128 and sets the bank bit when `entity_anim_counter & 16`.
The cardinal rush is unchanged. OAM stays 16 sprites.
