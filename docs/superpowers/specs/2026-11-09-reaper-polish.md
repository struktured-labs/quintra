# Reaper scythe

The link window, the 32-tick raise, the palette swap, and the sixteen
sprites stay. This pass only changes the picture.

The cloak, the hood, the eye slits, and the tattered hem stay. The old
one-pixel shaft becomes a two-pixel haft with a crescent blade. Pose 0
rests that crescent on the right shoulder. Pose 1 lifts it overhead.
Pose 2 reaches it to the right and puts the other arm out.

`reaper_pose_load` still writes the sixteen tiles at 40 and still skips
a repeat upload. Nothing here changes when those poses are chosen:
pose 1 is still clock 96..128 below half health, and pose 2 is still
the link from 128..224. Damage, HP, and the link timer are unchanged.
