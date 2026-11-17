#ifndef QUINTRA_GAME_RIFTWILD_DENSITY_H
#define QUINTRA_GAME_RIFTWILD_DENSITY_H
#include "core/types.h"

// Seed-stable per-field Riftwild encounter budget (audit L5). Returns the
// lower of the rolled dungeon-style count and this field's band.
u8 riftwild_field_enemy_count(u8 rolled) BANKED;
// 1 when this field is one of the seeded quiet fields (no ambient hostiles).
u8 riftwild_field_is_quiet(void) BANKED;

#endif
