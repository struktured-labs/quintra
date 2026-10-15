#ifndef QUINTRA_BOSS_PROJECTILE_H
#define QUINTRA_BOSS_PROJECTILE_H
#include <gb/gb.h>
#include "game/entity.h"
#define BOSS_SHOT_MARKER 0xD0
#define EF_BOSS_PROJECTILE 0x80
#define BOSS_SHAPE_PELLET 0
#define BOSS_SHAPE_ORB 1
#define BOSS_SHAPE_SEED 2
#define BOSS_SHAPE_BOLT 3
#define BOSS_SHAPE_CRESCENT 4
#define BOSS_SHOT_ARC 0
#define BOSS_SHOT_WAVE 1
#define BOSS_SHOT_SEED 2
#define BOSS_SHOT_SPIRAL 3
#define BOSS_SHOT_RETURN 4
#define BOSS_SHOT_BOLT 5
#define BOSS_SHOT_LANE 6
u8 boss_projectile_has_room(u8 cost) BANKED;
u8 boss_projectile_vector(i16 x, i16 y, i8 vx, i8 vy, u8 damage,
    u8 pattern, u8 generation) BANKED;
u8 boss_projectile_spawn(i16 x, i16 y, u8 angle, u8 pattern,
    u8 generation, u8 damage) BANKED;
void boss_projectile_update(entity_t *e, u8 idx) BANKED;
void boss_projectile_load_art(void) BANKED;
u8 boss_projectile_draw(entity_t *e, u8 oam, u8 x, u8 y) BANKED;
#endif
