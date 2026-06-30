#ifndef QUINTRA_GAME_PROJECTILE_H
#define QUINTRA_GAME_PROJECTILE_H

#include "core/types.h"
#include "game/entity.h"

// Spawn a player projectile at player.x/y in (dx,dy) direction (8-dir deltas).
// Returns entity index or 0xFF if no slot. Damage taken from player's
// starter_weapon spec (currently hardcoded 2 for Phase 5).
u8   projectile_spawn_player(i8 dx, i8 dy);

// Per-frame update (called by entity_update_all dispatch)
void projectile_update(entity_t *e, u8 idx);

#endif
