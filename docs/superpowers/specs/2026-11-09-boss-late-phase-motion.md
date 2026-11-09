# Late-phase boss locomotion and Void telegraph

Below half health, `boss_phase_motion` replaced several bosses' own
movement with one shared stepper. Spider and Hydra took more east steps
than west, because a 48-tick cast pause sat inside the west half of the
128-tick clock, and they walked into the east wall. Replaying that retired clock for
256 ticks nets +24 px east. Crystal lost its
wells, Mire lost its pulse, and Void Lord lost its anchors. Sun Golem
keeps the cardinal charge; that pattern is its own.

Void Lord's warp flash is not a 12-tick blackout. The drawer decrements
`ai_data[7]` and hides on the odd remainder, so a 12-tick flash is 6
hidden frames and 6 shown frames. Across the 36-tick anchor hold that is
6/36 of the cycle, not 12/36. The arrival frames were the hidden ones.
The post-warp flash is 4 ticks (2 hidden, 2 shown). Impact FX still
marks both ends of the jump.

Event Horizon still hurts the chebyshev square `abs(dx) < 96` and
`abs(dy) < 96`. The warning markers for that signature now sit on that
square's perimeter. The blast is not smaller.

While the Reaper link is up, its volley is a three-lane fan instead of
one re-aimed bolt. Shots already in flight keep `PROJ_PRELINK` grace.
Damage, HP, and the link timer are unchanged.

Bolt and crescent shots stay the existing tiles. The bolt points right
and the crescent's solid back is on the left. Hardware sprites can
mirror those glyphs. They cannot rotate them by 90 degrees, so a
north or south lane still shows the horizontal picture and keeps the
authored hitbox. Westbound bolts mirror. Eastbound crescents mirror
so the solid back leads. No new pixels are added.

The screen-scale mural painters and their unused blink frames are
gone. Nothing called them, and a moving boss already enters with no
projection cells. Room entry still uploads the nine shared background
tiles, because the serpent contour reuses those IDs and the Cinder
room test reads tile 56. That upload is not a painted mural.
