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

// ai_data[4] is visual-only for player projectiles. Physical sword/spear
// tiles are authored pointing north-east; the renderer mirrors them around
// the actual aim so a thrust reads in the direction the player chose.
#define PROJ_VIS_FLIP_X 0x01
#define PROJ_VIS_FLIP_Y 0x02

// Spawn a player projectile at player.x/y in (dx,dy) direction (8-dir deltas)
// with explicit damage + ProjectileKind (PROJ_* from generated enums.h) —
// kind shapes speed/range/pierce so each class weapon feels distinct.
u8   projectile_spawn_player(i8 dx, i8 dy, u8 damage, u8 kind) BANKED;

// Enemy-owned projectile from (px,py) toward direction (dx,dy), 2 px/tick.
u8   projectile_spawn_enemy(i16 px, i16 py, i8 dx, i8 dy, u8 damage) BANKED;

// Enemy projectile with an explicit px/tick velocity (vx,vy). Used by bosses
// to vary bullet speed within a single attack pattern.
u8   projectile_spawn_enemy_v(i16 px, i16 py, i8 vx, i8 vy, u8 damage) BANKED;

// Per-frame update (called by entity_update_all dispatch)
void projectile_update(entity_t *e, u8 idx) BANKED;

#endif
