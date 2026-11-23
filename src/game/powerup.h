#ifndef QUINTRA_GAME_POWERUP_H
#define QUINTRA_GAME_POWERUP_H

// Temporary power-ups (docs/superpowers/specs/2026-11-16-temporary-powerups.md).
// One timed slot, independent of the status slot and of Surge Spark.
// Timers are eight-frame beats, like status conditions.
// Phase 1: Aegis, Limitless, Mend. Phase 2-4: Roulette, Confusion retune,
// Formation, Halo, Long Reach, Blast Assist, Wingmates, shrines.

#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"

#define POWERUP_NONE      0
#define POWERUP_AEGIS     1  // 3-hit shield bubble, orbiting ward shards
#define POWERUP_LIMITLESS 2  // Oath Arts / Bombs cost no MP; Will auto-banks
#define POWERUP_MEND      3  // +1 half-heart every 12 beats
#define POWERUP_FORMATION 4  // two parallel A copies
#define POWERUP_HALO      5  // every 3rd A fires an 8-way ring
#define POWERUP_LONGREACH 6  // 4x hit area (2x per axis), +50% travel
#define POWERUP_BLAST     7  // each A impact blooms a small bomb
#define POWERUP_WINGMATES 8  // two Life Force-style flank buddies
#define POWERUP_COUNT     9

#define POWERUP_AEGIS_HITS      3
#define POWERUP_AEGIS_BOSS_HITS 2

// Roulette / shrine spawn flags for powerup_spawn_roulette().
#define ROULETTE_SHRINE    0x01
#define ROULETTE_UNCOMMON  0x04  // dungeon shrine: uncommon or better faces

// Shrine claim bits in run_state.powerup_shrines.
#define PU_SHRINE_DUNGEON  0x01
#define PU_SHRINE_RIFT_0   0x02
#define PU_SHRINE_RIFT_1   0x04
#define PU_SHRINE_RIFT_2   0x08

extern u8 powerup_id;          // POWERUP_NONE in ordinary play
extern u8 powerup_ticks;       // beats remaining
extern u8 powerup_aegis_hits;  // shield charges left (Aegis only)
extern u8 powerup_drop_cool;   // 20 s capsule-drop cooldown, in beats
extern u8 powerup_world_live;  // 1 while a roulette/shrine pickup is in the room
extern u8 powerup_test_cmd;    // PyBoy test hook (see powerup_extra.c)

#define POWERUP_FREE_MP() (powerup_id == POWERUP_LIMITLESS)

void powerup_reset(void) BANKED;
u8   powerup_spawn(u8 id, fix8_t x, fix8_t y) BANKED;
u8   powerup_spawn_roulette(fix8_t x, fix8_t y, u8 flags) BANKED;
void powerup_collect(u8 id) BANKED;
// Once per room frame while powerup_id != 0.
void powerup_tick(void) BANKED;
// Contextual HUD lane widget (icon, seconds, Aegis charges).
void powerup_hud(void) BANKED;
// Pack Status line: writes the active name + seconds and returns 1,
// or returns 0 if no power-up is running.
u8   powerup_pack_line(void) BANKED;
// Hostile contact/projectile about to hurt: spend an Aegis charge instead.
u8   powerup_aegis_absorb(u8 hostile_idx) BANKED;

// Cooldown, roulette animation, test hook. Called from status_tick.
void powerup_tick_cooldown(void) BANKED;
void powerup_note_drop(void) BANKED;
// Place a seed-stable shrine if this room owns one and it is unclaimed.
void powerup_place_room_shrine(void) BANKED;
// Elite/alpha/rare bonus: double capsule chance, after the guaranteed drop.
void pickup_roll_elite_bonus(fix8_t x, fix8_t y) BANKED;
void powerup_try_spawn_capsule(u8 id, fix8_t x, fix8_t y) BANKED;

// Fire-copy hooks (banked). Relic/combat leaves test a WRAM byte first.
void powerup_on_primary_fire(u8 primary, u8 dir, u8 damage) BANKED;
void powerup_echo_primary(u8 primary, u8 dir, u8 damage) BANKED;
u8 powerup_try_collect(u8 slot) BANKED;
void powerup_on_proj_impact(u8 idx, i16 x, i16 y) BANKED;
// Copy-vs-boss volley cap: 0 if this copy should deal no boss damage.
u8   powerup_copy_hit_ok(void) BANKED;
// Roulette lock: 1 once the face is awarded (caller may despawn), 0 if
// the capsule is still spinning or frozen on the winning face.
u8   powerup_roulette_try_lock(u8 idx) BANKED;
void powerup_confusion_stars(void) BANKED;
// Visual-only: bounce is added to the icon's OAM Y; decorate writes
// the 16x16 bezel, smear overlay, and lock sparkles (bank 1 tiles).
extern i8 powerup_roulette_bob;
u8   powerup_roulette_decorate(u8 oam, u8 sx, u8 sy) BANKED;
extern u8 powerup_roulette_fxflags;
extern u8 powerup_roulette_spark_t;
#define RF_FRAME 0x01
#define RF_SMEAR 0x02
#define RF_SPARK 0x04
// Visited, unclaimed dungeon shrine cell? 1 = draw the gold "!" mark.
u8   powerup_shrine_map_mark(u8 cell) BANKED;

void powerup_helpers_on_collect(u8 id) BANKED;
void powerup_helpers_on_end(void) BANKED;
void powerup_helpers_tick(void) BANKED;

#endif
