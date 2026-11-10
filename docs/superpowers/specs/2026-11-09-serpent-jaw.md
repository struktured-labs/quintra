# Serpent jaw and one palette

The meal route, the storm-charge countdown, the twelve-sprite hood,
and the tail frames stay as they are. This pass only changes the
picture.

The closed hood stays the checked-in serpent. The open jaw drops the
lower lip and clears the mouth. Twelve tiles upload to VRAM bank 1 at
128..139 when the stage is 1. That leaves Hexa's background tiles
40..55 and limb tiles 88..127, the large-boss poses at 64..87, and the
vertical shots at 208..213 alone. Tiles 140..143 stay empty. The tail
frames on atlas rows 24..31 are not part of the upload.

`serpent_draw` points the twelve hood sprites at 128 and sets the bank
bit while the serpent is walking toward a meal (`state == 0` and
`vy == 3`) and during the existing storm charge (`state == 1`). The
charge length and the feed flash stay put. Damage still tints the
hood through `ai_data[7]` and does not open the jaw by itself.

The coil's background palette was a private red ramp. It now uses the
same four colors as Verdant Hollow's boss object palette, so the hood
and the coil read as one serpent.
