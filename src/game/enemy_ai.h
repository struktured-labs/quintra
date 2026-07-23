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

// Per-stage giant-boss locomotion lives in a separate ROM bank from the
// shared roster AI, keeping the frequently edited encounter layer within the
// 16 KiB cartridge-bank budget.
void boss_motion_tick(entity_t *e) BANKED;

// Bank-6 split/reform behavior for marked Rift Ooze crawler fragments.
void ooze_fragment_update(entity_t *e, u8 idx) BANKED;

// Bank-6 formation behavior. Returns 1 only if another live Hornet makes
// this a swarm; callers retain the original solo chaser otherwise.
u8 hornet_swarm_tick(entity_t *e, u8 idx) BANKED;

// Bank-6 Keese-like flutter cadence and diagonal corner-safe motion.
void flutterbat_update(entity_t *e) BANKED;

// Bank-6 Folding Star bloom/contract timing and diagonal echo motion.
void fold_star_update(entity_t *e, const enemy_def_t *def) BANKED;

// Bank-5 positional caster used by typed AI_SPINNER content entries.
void spinner_update(entity_t *e, const enemy_def_t *def) BANKED;

#endif
