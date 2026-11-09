# Boss pose animation

Checked against `main` after #27 and #29. Several items in the animation
plan are already shipped and stay as they are.

## Already on main

- Below half health, Crystal, Spider, Mire, Hydra, and Void Lord keep their
  own movement. Only Sun Golem uses the cardinal rush. Mire holds still for
  its root cast and the hollow ring. Do not put those stages back on the
  shared stepper, and do not retune the blink, warp, or bounce countdowns.
- Void Lord's arrival flash is 4 ticks (2 hidden, 2 shown). Event Horizon
  still covers the chebyshev square of 96, and the warning markers sit on
  that square. Leave both alone.
- Bolt and crescent shots already mirror east and west. Hardware sprites
  cannot rotate them. A later pass may add vertical glyphs if a free tile
  range exists. This pass does not.
- `reaper_pose_load` already skips a repeat upload.
- The screen-scale mural painters are gone. Do not restore them.
- Mire's anchored root cast owns BG tiles 55..63. Sprite-root flexion must
  not write `room_tilemap` or move that cast.

## This pass (Spider, Mire, Hydra)

`large_boss_draw` already swaps Mire between bank-1 tiles 40 and 64. Spider
and Hydra were one pose. Bank 13 has 857 bytes free, under the room needed
for two more 384-byte poses, so the crouch and the strike live in
`large_boss_pose_b.c` (`#pragma bank 255`) and upload to bank-1 tiles 64..87
once, at room load.

Mire keeps the existing lub-dub test, so its root redraw still finishes
inside the frame. The two poses now flex the upper and lower roots, and
the flat left-lobe slab is gone. Spider and Hydra take the other branch
and swap to tile 64 when `entity_anim_counter & 16`. A wider selector
(phase bit, volley window, pose lock) dropped simulation updates on the
dense Spider and Mire fights, so it stayed out. The old test that required
identical roots is replaced.

OAM stays 24. There is no per-frame VRAM copy.
