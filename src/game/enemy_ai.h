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
// Bank-9 tightening-spiral movement for Verdant's Snake-like Colossus cycle.
void serpent_feed_tick(entity_t *e) BANKED;
void serpent_motion_tick(entity_t *e) BANKED;

// Every giant owns one warned, screen-shaping half-health signature. Returns
// nonzero while the signature freezes the ordinary movement/volley driver.
u8 colossus_signature_tick(entity_t *e) BANKED;

// Verdant's body is a real route history rendered behind its mobile head.
// Fourteen overlapping 8x8 segments leave ten OAM entries for bullets after
// the broad 4x3 head and player, preserving the encounter's bullet-hell half.
#define SERPENT_TAIL_POINTS 15
extern u8 serpent_tail_x[SERPENT_TAIL_POINTS];
extern u8 serpent_tail_y[SERPENT_TAIL_POINTS];
extern u8 serpent_tail_count;
extern u8 serpent_tail_visible;
extern u8 serpent_tail_active;
extern u8 serpent_head_index;
void serpent_tail_reset(u8 head_x, u8 head_y) BANKED;
void serpent_tail_update(entity_t *e) BANKED;
void serpent_tail_contact(void) BANKED;
void serpent_draw(void) BANKED;

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

// Bank-6 one-wave reinforcement caller. Its long tell remains interruptible:
// killing the caller before resolution prevents every escort spawn.
void rift_cantor_update(entity_t *e, const enemy_def_t *def) BANKED;
// Bank-2 reachable-space movement for the spent caller. Keeping this beside
// enemy_try_step avoids spending scarce summoner-bank bytes on four trampolines.
void enemy_cantor_evade(entity_t *e) BANKED;

#endif
