#ifndef QUINTRA_GAME_ENEMY_AI_H
#define QUINTRA_GAME_ENEMY_AI_H


#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"
#include "content.h"

// Spawn an enemy by content enemy_id_t at given tile coords.
u8   enemy_spawn(u8 enemy_content_id, u8 tile_x, u8 tile_y) BANKED;

// Per-frame update (called by entity_update_all dispatch)
void enemy_update(entity_t *e, u8 idx) BANKED;

// Move an enemy 1px by (dx,dy) if the target tile is walkable + in bounds.
// Returns 1 if it moved. Exposed for knockback in combat.
u8 enemy_try_step(entity_t *e, i8 dx, i8 dy) BANKED;

// Bank-5 positional caster used by typed AI_SPINNER content entries.
void spinner_update(entity_t *e, const enemy_def_t *def) BANKED;

#endif
