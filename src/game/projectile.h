#ifndef QUINTRA_GAME_PROJECTILE_H
#define QUINTRA_GAME_PROJECTILE_H


#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"

// Element bitmask applied to the next player shot(s).
extern u8 g_shot_element;

// ai_data[3] on player projectiles is spare runtime metadata. Spirit
// Convergence tags its eight-way chord so combat can preserve the burst
// against crowds without counting eight overlapping arcs as eight boss hits.
#define PROJ_FLAG_CONVERGENCE 0x01
#define PROJ_FLAG_RICOCHET    0x02
// Wolfkin's Howl uses a cast-wide Colossus hit budget while retaining all
// eight physical lanes against ordinary crowds.
#define PROJ_FLAG_HOWL        0x04
#define PROJ_FLAG_SPLASH      0x08 // Blast Seed: first body impact blooms once
#define PROJ_FLAG_FRACTAL     0x10 // Echo child: forks once after a short flight
#define PROJ_FLAG_BEAM        0x20 // Rift Lens: wide two-sprite heavy projectile

// Cached visible/mechanical mutations granted by ordinary run relics. These
// make a pickup alter the champion's actual attack rather than only changing
// an opaque number on the Pack screen.
#define ATTACK_TRAIT_POWER 0x01
#define ATTACK_TRAIT_SWIFT 0x02
#define ATTACK_TRAIT_BLOOD 0x04
#define ATTACK_TRAIT_SPLASH 0x08
#define ATTACK_TRAIT_BEAM   0x10
#define PROJ_AUX_WOLFKIN_FANG 0xF1
#define PROJ_AUX_SPLASH        0xF2
#define PROJ_AUX_BEAM_TRAIL    0xF3
// The one-per-stage Reaper owns this marker exclusively. On collision its
// clearly telegraphed scythe sets the champion to one heart, never zero.
#define PROJ_AUX_MORTAL_SCYTHE 0xE1

// Cached from the run inventory so ordinary fire never scans all eight slots.
// The cache is refreshed on purchase, new-run reset, and SRAM resume.
extern u8 g_player_ricochet;
extern u8 g_player_attack_traits;
void projectile_sync_player_relics(void) BANKED;

// ai_data[4] is visual-only for player projectiles. Physical sword/spear
// tiles are authored pointing north-east; the renderer mirrors them around
// the actual aim so a thrust reads in the direction the player chose.
#define PROJ_VIS_FLIP_X 0x01
#define PROJ_VIS_FLIP_Y 0x02
// Hostile projectile fired under Confusion. It can bruise other monsters;
// hostile shots retain source enemy ID + 1 in ai_data[5] for status payloads.
#define PROJ_HOSTILE_CONFUSED 0x80

// Spawn a player projectile at player.x/y in (dx,dy) direction (8-dir deltas)
// with explicit damage + ProjectileKind (PROJ_* from generated enums.h) —
// kind shapes speed/range/pierce so each class weapon feels distinct.
u8   projectile_spawn_player(i8 dx, i8 dy, u8 damage, u8 kind) BANKED;

// Enemy-owned projectile from (px,py) toward direction (dx,dy), 2 px/tick.
u8   projectile_spawn_enemy(i16 px, i16 py, i8 dx, i8 dy, u8 damage) BANKED;

// Enemy projectile with an explicit px/tick velocity (vx,vy). Used by bosses
// to vary bullet speed within a single attack pattern.
u8   projectile_spawn_enemy_v(i16 px, i16 py, i8 vx, i8 vy, u8 damage) BANKED;

// Cold relic physics live outside the crowded projectile bank. Echo children
// fork for two bounded generations, Blast Seed creates one stationary area
// hit, and Rift Lens widens the cadence shot into a two-sprite beam.
void projectile_spawn_fractal_pair(i16 px, i16 py, u8 dir,
    u8 damage, u8 can_fork) BANKED;
void projectile_spawn_splash(i16 px, i16 py, u8 damage,
    u8 avoid_slot) BANKED;
void projectile_make_beam(u8 idx) BANKED;
void projectile_update_relic(entity_t *e) BANKED;

#endif
