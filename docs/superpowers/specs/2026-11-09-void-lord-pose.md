# Void Lord blink pose

The arrival flash stays 4 ticks, and Event Horizon stays the chebyshev
square of 96. This pass only changes the picture.

The idle grid stays the checked-in Void Lord. The blink pose pulls both
wings in, joins the crown into a flare, and widens the horizon slit.
Sixteen tiles upload to VRAM bank 1 at 128..143 when the stage is 8.
That leaves Hexa's background tiles 40..55 and limb tiles 88..127, the
large-boss poses at 64..87, and the vertical shots at 208..213 alone.

`colossus_oam_draw` points the sprites at 128 and sets the bank bit
while `state_timer` is in the last 12 ticks of the 36-tick hold, and
while the existing flash counter is running. Nothing writes a new flash
length.
