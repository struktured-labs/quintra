#pragma bank 15
#include "game/boss_projectile.h"
#include "game/projectile.h"
#include "game/procgen.h"
#include "game/room.h"
#include "render/tiles.h"
#include "render/large_boss.h"
#include "audio/sfx.h"

static const i8 sine[32] = {
    0,3,6,9,11,13,15,16,16,16,15,13,11,9,6,3,
    0,-3,-6,-9,-11,-13,-15,-16,-16,-16,-15,-13,-11,-9,-6,-3
};
/* floor(sine[angle] * radius / 16), preserving signed shift rounding. */
static const i8 spiral_offset[25][32] = {
    {0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0},
    {0,0,0,0,0,0,0,1,1,1,0,0,0,0,0,0,0,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1},
    {0,0,0,1,1,1,1,2,2,2,1,1,1,1,0,0,0,-1,-1,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-2,-1,-1},
    {0,0,1,1,2,2,2,3,3,3,2,2,2,1,1,0,0,-1,-2,-2,-3,-3,-3,-3,-3,-3,-3,-3,-3,-2,-2,-1},
    {0,0,1,2,2,3,3,4,4,4,3,3,2,2,1,0,0,-1,-2,-3,-3,-4,-4,-4,-4,-4,-4,-4,-3,-3,-2,-1},
    {0,0,1,2,3,4,4,5,5,5,4,4,3,2,1,0,0,-1,-2,-3,-4,-5,-5,-5,-5,-5,-5,-5,-4,-3,-2,-1},
    {0,1,2,3,4,4,5,6,6,6,5,4,4,3,2,1,0,-2,-3,-4,-5,-5,-6,-6,-6,-6,-6,-5,-5,-4,-3,-2},
    {0,1,2,3,4,5,6,7,7,7,6,5,4,3,2,1,0,-2,-3,-4,-5,-6,-7,-7,-7,-7,-7,-6,-5,-4,-3,-2},
    {0,1,3,4,5,6,7,8,8,8,7,6,5,4,3,1,0,-2,-3,-5,-6,-7,-8,-8,-8,-8,-8,-7,-6,-5,-3,-2},
    {0,1,3,5,6,7,8,9,9,9,8,7,6,5,3,1,0,-2,-4,-6,-7,-8,-9,-9,-9,-9,-9,-8,-7,-6,-4,-2},
    {0,1,3,5,6,8,9,10,10,10,9,8,6,5,3,1,0,-2,-4,-6,-7,-9,-10,-10,-10,-10,-10,-9,-7,-6,-4,-2},
    {0,2,4,6,7,8,10,11,11,11,10,8,7,6,4,2,0,-3,-5,-7,-8,-9,-11,-11,-11,-11,-11,-9,-8,-7,-5,-3},
    {0,2,4,6,8,9,11,12,12,12,11,9,8,6,4,2,0,-3,-5,-7,-9,-10,-12,-12,-12,-12,-12,-10,-9,-7,-5,-3},
    {0,2,4,7,8,10,12,13,13,13,12,10,8,7,4,2,0,-3,-5,-8,-9,-11,-13,-13,-13,-13,-13,-11,-9,-8,-5,-3},
    {0,2,5,7,9,11,13,14,14,14,13,11,9,7,5,2,0,-3,-6,-8,-10,-12,-14,-14,-14,-14,-14,-12,-10,-8,-6,-3},
    {0,2,5,8,10,12,14,15,15,15,14,12,10,8,5,2,0,-3,-6,-9,-11,-13,-15,-15,-15,-15,-15,-13,-11,-9,-6,-3},
    {0,3,6,9,11,13,15,16,16,16,15,13,11,9,6,3,0,-3,-6,-9,-11,-13,-15,-16,-16,-16,-15,-13,-11,-9,-6,-3},
    {0,3,6,9,11,13,15,17,17,17,15,13,11,9,6,3,0,-4,-7,-10,-12,-14,-16,-17,-17,-17,-16,-14,-12,-10,-7,-4},
    {0,3,6,10,12,14,16,18,18,18,16,14,12,10,6,3,0,-4,-7,-11,-13,-15,-17,-18,-18,-18,-17,-15,-13,-11,-7,-4},
    {0,3,7,10,13,15,17,19,19,19,17,15,13,10,7,3,0,-4,-8,-11,-14,-16,-18,-19,-19,-19,-18,-16,-14,-11,-8,-4},
    {0,3,7,11,13,16,18,20,20,20,18,16,13,11,7,3,0,-4,-8,-12,-14,-17,-19,-20,-20,-20,-19,-17,-14,-12,-8,-4},
    {0,3,7,11,14,17,19,21,21,21,19,17,14,11,7,3,0,-4,-8,-12,-15,-18,-20,-21,-21,-21,-20,-18,-15,-12,-8,-4},
    {0,4,8,12,15,17,20,22,22,22,20,17,15,12,8,4,0,-5,-9,-13,-16,-18,-21,-22,-22,-22,-21,-18,-16,-13,-9,-5},
    {0,4,8,12,15,18,21,23,23,23,21,18,15,12,8,4,0,-5,-9,-13,-16,-19,-22,-23,-23,-23,-22,-19,-16,-13,-9,-5},
    {0,4,9,13,16,19,22,24,24,24,22,19,16,13,9,4,0,-5,-9,-14,-17,-20,-23,-24,-24,-24,-23,-20,-17,-14,-9,-5},
};
static const u8 shapes[7] = { 0,1,2,1,4,3,1 };
static const u8 sprite_cost[5] = { 1,1,4,2,4 };
static const u8 shape_tile[5] = { 208,209,210,214,216 };
static const u8 shape_hitbox[5] = { 0x44,0x77,0xEE,0xE6,0xEE };
static const u8 pattern_palette[7] = { 4,5,3,3,5,4,4 };

u8 boss_projectile_has_room(u8 cost) BANKED {
    u8 i, free = 0, hostile = 0, sprites = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) free++;
        else if (entities[i].type == ENT_PROJECTILE
            && !(entities[i].flags & EF_PLAYER_PROJ)) {
            hostile++;
            sprites += (entities[i].flags & EF_BOSS_PROJECTILE)
                ? sprite_cost[entities[i].ai_data[4]] : 1;
        }
    }
    return free > 6 && hostile < 12
        && sprites + cost <= (large_boss_index < MAX_ENTITIES ? 10 : 12);
}

u8 boss_projectile_spawn(i16 x, i16 y, u8 angle, u8 pattern,
                        u8 generation, u8 damage) BANKED {
    u8 i, shape;
    entity_t *e;
    if (pattern > BOSS_SHOT_LANE) return 0xFF;
    shape = shapes[pattern];
    if (!procgen_current_room_is_boss) shape = BOSS_SHAPE_PELLET;
    if (!boss_projectile_has_room(sprite_cost[shape])) return 0xFF;
    i = entity_spawn(ENT_PROJECTILE);
    if (i == 0xFF) return i;
    e = &entities[i];
    e->flags |= EF_BOSS_PROJECTILE;
    e->hitbox = shape_hitbox[shape];
    e->x = x - ((e->hitbox >> 4) >> 1);
    e->y = y - ((e->hitbox & 15) >> 1);
    e->x_pad = (u8)e->x; e->y_pad = (u8)e->y;
    e->hp = 1; e->damage = damage;
    e->state_timer = 150;
    e->sprite_tile = procgen_current_room_is_boss ? shape_tile[shape] : SPR_BULLET_B;
    e->palette = pattern_palette[pattern];
    if (pattern == BOSS_SHOT_ARC && generation == 1) e->palette = 3;
    e->ai_data[0] = angle & 31;
    e->ai_data[1] = pattern;
    e->ai_data[2] = generation > 2 ? 2 : generation;
    e->ai_data[3] = 0;
    e->ai_data[4] = shape;
    e->ai_data[6] = BOSS_SHOT_MARKER;
    e->ai_data[7] = entity_anim_counter;
    return i;
}

u8 boss_projectile_vector(i16 x, i16 y, i8 vx, i8 vy, u8 damage,
                          u8 pattern, u8 generation) BANKED {
    u8 ax=vx<0 ? -vx : vx, ay=vy<0 ? -vy : vy;
    u8 angle, slot, speed=ax>ay ? ax : ay;
    if (!speed) return 0xFF;
    if (!ax) angle=0;
    else if (!ay) angle=8;
    else if (ax>ay) angle=6;
    else if (ay>ax) angle=2;
    else angle=4;
    if (vy>0) angle=16-angle;
    if (vx<0) angle=(32-angle)&31;
    slot=boss_projectile_spawn(x,y,angle,pattern,generation,damage);
    if (slot!=0xFF) entities[slot].state=speed>3 ? 3 : speed;
    return slot;
}

static const u8 solid_tiles[128] = {
    0,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,1,1,0,1,0,0,0,0,0,0,0,
    1,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,
};

static u8 blocked(entity_t *e) {
    u8 left=e->x>>3, top=e->y>>3;
    u8 right=(e->x+(e->hitbox>>4)-1)>>3;
    u8 bottom=(e->y+(e->hitbox&15)-1)>>3;
    u8 x,y,tile;
    for (y=top;y<=bottom;++y) {
        if (y<ROOM_H && right<ROOM_W) {
            const u8 *cell=&room_tilemap[y][left];
            for (x=left;x<=right;++x)
                if (solid_tiles[(*cell++)&0x7F]) return 1;
        } else {
            for (x=left;x<=right;++x) {
                tile=room_tile_at_px((i16)x<<3,(i16)y<<3);
                if (solid_tiles[tile]) return 1;
            }
        }
    }
    return 0;
}

static void split_projectile(entity_t *e,u8 idx) {
    static const u8 child_pattern[3] = { BOSS_SHOT_ARC, BOSS_SHOT_ARC, BOSS_SHOT_WAVE };
    i16 x=e->x+((e->hitbox>>4)>>1), y=e->y+((e->hitbox&15)>>1);
    u8 damage=e->damage, generation=e->ai_data[2]-1;
    u8 payload=e->ai_data[5], child, pattern=e->ai_data[1];
    u8 next=child_pattern[e->ai_data[2]], spread=5, angle=e->ai_data[0];
    if (pattern==BOSS_SHOT_SPIRAL) next=BOSS_SHOT_RETURN;
    else if (pattern==BOSS_SHOT_RETURN) next=BOSS_SHOT_BOLT;
    else if (pattern==BOSS_SHOT_BOLT) { next=BOSS_SHOT_ARC; spread=8; }
    else if (pattern==BOSS_SHOT_ARC) { next=BOSS_SHOT_WAVE; spread=3; }
    entity_kill(idx);
    child=boss_projectile_spawn(x,y,(u8)(angle+spread),next,generation,damage);
    if (child!=0xFF) entities[child].ai_data[5]=payload;
    child=boss_projectile_spawn(x,y,(u8)(angle-spread),next,generation,damage);
    if (child!=0xFF) entities[child].ai_data[5]=payload;
    sfx_play(SFX_TICK);
}

static u8 return_motion(entity_t *e,u8 idx,u8 age,u8 angle) {
    u8 tile;
    i16 forward,side;
    if (age >= 32 && age < 40) {
        e->palette = (age & 2) ? 4 : 5;
        return 0;
    }
    if (age >= 40) age -= 8;
    if (age >= 64) {
        e->x=e->x_pad; e->y=e->y_pad;
        if (age > 64) entity_kill(idx);
        return 0;
    }
    e->palette = 5;
    tile = age >> 1;
    forward = ((16-sine[(tile+8)&31])*3) >> 1;
    side = (sine[tile]*3) >> 2;
    e->x = (i16)e->x_pad + ((sine[angle]*forward + sine[(angle+8)&31]*side) >> 4);
    e->y = (i16)e->y_pad + ((-sine[(angle+8)&31]*forward + sine[angle]*side) >> 4);
    return 1;
}

void boss_projectile_update(entity_t *e, u8 idx) BANKED {
    u8 age, angle, pattern, width, height, split_age;
    i16 delta, forward;
    i8 dx, dy;
    if (!e->state_timer) { entity_kill(idx); return; }
    // A child born later in the table must not receive an extra update.
    if (e->ai_data[7] == entity_anim_counter) return;
    e->ai_data[7] = entity_anim_counter;
    e->state_timer--;
    age = ++e->ai_data[3];
    pattern = e->ai_data[1];
    split_age = pattern == BOSS_SHOT_RETURN ? 72 : 40;
    if (e->ai_data[2] && age >= split_age) {
        if (pattern == BOSS_SHOT_RETURN) { e->x=e->x_pad; e->y=e->y_pad; }
        if (age < split_age + 16) {
            e->palette = (age & 4) ? (pattern_palette[pattern] == 4 ? 3 : 4) : pattern_palette[pattern];
            if (e->ai_data[4] == BOSS_SHAPE_SEED)
                e->sprite_tile = (age & 4) ? 220 : 210;
            else if (e->ai_data[4] == BOSS_SHAPE_ORB)
                e->sprite_tile = (age & 4) ? SPR_FX_IMPACT : 209;
            return;
        } else {
            split_projectile(e,idx);
            return;
        }
    }
    if (pattern == BOSS_SHOT_ARC && age < 72 && !(age & 3))
        e->ai_data[0] = (e->ai_data[0] + 1) & 31;
    angle = e->ai_data[0];
    if (pattern == BOSS_SHOT_WAVE)
        angle = (angle + (sine[(age >> 1) & 31] >> 2)) & 31;
    if (pattern == BOSS_SHOT_SPIRAL) {
        forward = age >> 2;
        if (forward > 24) forward = 24;
        angle = (angle + (age >> 2)) & 31;
        e->x = (i16)e->x_pad + spiral_offset[forward][angle];
        e->y = (i16)e->y_pad - spiral_offset[forward][(angle+8)&31];
    } else if (pattern == BOSS_SHOT_RETURN) {
        if (!return_motion(e,idx,age,angle)) return;
    } else {
        dx = sine[angle]; dy = -sine[(angle+8)&31];
        if (e->state == 1) { dx >>= 1; dy >>= 1; }
        else if (e->state == 3) { dx += dx >> 1; dy += dy >> 1; }
        delta = (i16)e->x_frac + dx;
        e->vx = (i8)(delta >> 4);
        e->x_frac = (u8)delta & 15;
        delta = (i16)e->y_frac + dy;
        e->vy = (i8)(delta >> 4);
        e->y_frac = (u8)delta & 15;
        e->x += e->vx; e->y += e->vy;
    }
    width = e->hitbox >> 4; height = e->hitbox & 15;
    if (e->x < 8 || e->y < 8 || e->x + width > room_world_width - 8
        || e->y + height > room_world_height - 8) { entity_kill(idx); return; }
    if (blocked(e)) entity_kill(idx);
}
