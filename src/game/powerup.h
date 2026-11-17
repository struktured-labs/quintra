#ifndef QUINTRA_GAME_POWERUP_H
#define QUINTRA_GAME_POWERUP_H

// Temporary power-ups (docs/superpowers/specs/2026-11-16-temporary-powerups.md).
// One timed slot, independent of the status slot and of Surge Spark.
// Timers are eight-frame beats, like status conditions.

#include <gb/gb.h>
#include "core/types.h"

#define POWERUP_NONE      0
#define POWERUP_AEGIS     1  // 3-hit shield bubble, orbiting ward shards
#define POWERUP_LIMITLESS 2  // Oath Arts / Bombs cost no MP; Will auto-banks
#define POWERUP_MEND      3  // +1 half-heart every 12 beats
#define POWERUP_COUNT     4

#define POWERUP_AEGIS_HITS      3
#define POWERUP_AEGIS_BOSS_HITS 2

extern u8 powerup_id;          // POWERUP_NONE in ordinary play
extern u8 powerup_ticks;       // beats remaining
extern u8 powerup_aegis_hits;  // shield charges left (Aegis only)

#define POWERUP_FREE_MP() (powerup_id == POWERUP_LIMITLESS)

void powerup_reset(void) BANKED;
u8   powerup_spawn(u8 id, fix8_t x, fix8_t y) BANKED;
// Enemy-death Capsule roll band; respects one live Capsule per room and
// never drops in boss rooms.
void powerup_roll_drop(fix8_t x, fix8_t y) BANKED;
void powerup_collect(u8 id) BANKED;
// Once per room frame while powerup_id != 0.
void powerup_tick(void) BANKED;
// Contextual HUD lane widget (icon, seconds, Aegis charges).
void powerup_hud(void) BANKED;
// Hostile contact/projectile about to hurt: spend an Aegis charge instead.
u8   powerup_aegis_absorb(u8 hostile_idx) BANKED;

#endif
