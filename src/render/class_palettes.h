// Per-class OBJ palettes — shared by class_select preview + in-run player.
#ifndef QUINTRA_RENDER_CLASS_PALETTES_H
#define QUINTRA_RENDER_CLASS_PALETTES_H

#include <gb/gb.h>
#include "core/types.h"

// [class_id][color 0-3]; color 0 = transparent.
extern const u16 class_obj_palettes[5][4];
// Three visible run-progression tiers. The champion silhouette remains
// class-authored while relics/stage clears earn blue, red, then pearl-gold
// equipment colors.
extern const u16 class_obj_upgrade_palettes[5][3][4];
// Primary-attack palettes: spirit/ranged, steel, Rift Flail, Astral Spear.
extern const u16 weapon_obj_palettes[4][4];
void class_palette_load_obj(u8 slot, u8 class_id) BANKED;

#endif
