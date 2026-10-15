#pragma bank 15
#include "game/boss_phase.h"
#include "game/boss_projectile.h"
#include "game/enemy_ai.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "audio/boss_voice.h"
#include "audio/sfx.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

u8 boss_phase, boss_phase_clock, boss_link_active;
u8 boss_link_pending;
static u8 area_x, area_y;
static u8 summon_sites;
static u8 area_armed;
void reaper_pose_load(u8 pose) BANKED;

static i16 magnitude(i16 n) { return n < 0 ? -n : n; }

static void hurt(u8 damage) {
    if (player.iframes || player.shield_timer) return;
    if (RUN_IS_EASY()) damage = 1;
    player.hp = player.hp > damage ? player.hp - damage : 0;
    player.iframes = 45;
    hud_redraw_hp();
    sfx_play(SFX_HURT);
}

static u8 summon_clear(u8 x, u8 y) {
    u8 i;
    if (magnitude((i16)x-player.x)<32 && magnitude((i16)y-player.y)<32) return 0;
    if (!room_tile_walkable(room_tile_at_px(x,y))
        || !room_tile_walkable(room_tile_at_px(x+15,y))
        || !room_tile_walkable(room_tile_at_px(x,y+15))
        || !room_tile_walkable(room_tile_at_px(x+15,y+15))) return 0;
    for (i=0;i<MAX_ENTITIES;++i)
        if (entities[i].type == ENT_ENEMY && (entities[i].flags & EF_ACTIVE)
            && magnitude(entities[i].x-x)<24 && magnitude(entities[i].y-y)<24) return 0;
    return 1;
}

static void summon(entity_t *boss) {
    u8 i, count = 0, made = 0;
    if (boss_phase_clock == 160) summon_sites = 0;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if (entities[i].type == ENT_ENEMY && (entities[i].flags & EF_ACTIVE)
            && &entities[i] != boss) count++;
    for (i = 0; i < 4 && count < 2 && made < 2; ++i) {
        u8 x = (i & 1) ? room_world_width - 40 : 24;
        u8 y = (i & 2) ? room_world_height - 40 : 24;
        u8 idx;
        if (!summon_clear(x,y)) continue;
        if (boss_phase_clock == 160) {
            if (x < room_camera_x+8 || (i16)x+16 > (i16)room_camera_x+160
                || y < room_camera_y+8 || (i16)y+16 > (i16)room_camera_y+136) continue;
            if (fx_spawn(SPR_SHIELD_AURA,5,x,y,34) != 0xFF) {
                summon_sites |= 1 << i;
                made++;
            }
            continue;
        }
        if (!(summon_sites & (1 << i))) continue;
        idx = enemy_spawn(boss->ai_data[2] == 3 ? ENEMY_HORNET : ENEMY_BLUE_CRAWLER,x>>3,y>>3);
        if (idx == 0xFF) return;
        entities[idx].hp = 6 + boss_phase * 2;
        entities[idx].damage = 1;
        if (boss->ai_data[2] != 3) {
            entities[idx].ai_data[4] = boss->ai_data[2] == 4 ? 2 : 3;
            entities[idx].ai_data[3] = 0;
        }
        fx_spawn(SPR_SHIELD_AURA,5,x,y,24);
        count++; made++;
    }
    if (boss_phase_clock == 160 && made) boss_voice(boss->ai_data[2],BOSS_VOICE_ATTACK);
    if (boss_phase_clock == 192) summon_sites = 0;
}

static void mire_ring_tick(void) {
    static const i8 dx[8] = { 0,17,24,17,0,-17,-24,-17 };
    static const i8 dy[8] = { -24,-17,0,17,24,17,0,-17 };
    u8 i;
    i16 x, y, distance;
    if (boss_phase_clock == 64) {
        area_x = player.x + 8;
        area_y = player.y + 12;
        area_armed = 1;
        boss_voice(4,BOSS_VOICE_ATTACK);
    }
    if (area_armed && boss_phase_clock >= 64 && boss_phase_clock < 96 && !(boss_phase_clock & 7))
        for (i=0;i<8;++i)
            if (fx_spawn(SPR_SHIELD_AURA,3,(i16)area_x+dx[i]-4,(i16)area_y+dy[i]-4,7) == 0xFF)
                area_armed = 0;
    if (boss_phase_clock != 96 || !area_armed) return;
    area_armed = 0;
    for (i=0;i<8;++i)
        fx_spawn(SPR_FX_IMPACT,3,(i16)area_x+dx[i]-4,(i16)area_y+dy[i]-4,16);
    x = magnitude(player.x + 8 - area_x);
    y = magnitude(player.y + 12 - area_y);
    if (x < 30 && y < 30) {
        distance = x*x + y*y;
        if (distance >= 16*16 && distance < 30*30) hurt(2);
    }
    for (i=0;i<8;i+=2)
        boss_projectile_spawn((i16)area_x+dx[i],(i16)area_y+dy[i],i*4,BOSS_SHOT_WAVE,0,1);
}

static void area_tick(entity_t *e) {
    static const i8 dx[4] = { -16,16,0,0 };
    static const i8 dy[4] = { 0,0,-16,16 };
    u8 i, stage = e->ai_data[2];
    i16 x, y;
    if (stage == 4) { mire_ring_tick(); return; }
    if (boss_phase_clock == 64) {
        area_x = player.x + 8;
        area_y = player.y + 12;
        area_armed = 1;
        boss_voice(stage,BOSS_VOICE_ATTACK);
    }
    if (area_armed && boss_phase_clock >= 64 && boss_phase_clock < 96 && !(boss_phase_clock & 7)) {
        for (i=0;i<4;++i)
            if (fx_spawn(SPR_SHIELD_AURA,5,(i16)area_x+dx[i]-4,(i16)area_y+dy[i]-4,9) == 0xFF)
                area_armed = 0;
    }
    if (boss_phase_clock != 96 || !area_armed) return;
    area_armed = 0;
    x = magnitude(player.x + 8 - area_x);
    y = magnitude(player.y + 12 - area_y);
    for (i=0;i<4;++i)
        fx_spawn(SPR_FX_IMPACT,4,(i16)area_x+dx[i]-4,(i16)area_y+dy[i]-4,16);
    if (x < 18 && y < 18 && x*x+y*y < 18*18) hurt(2);
    for (i=0;i<4;++i)
        boss_projectile_spawn(area_x,area_y,i*8,BOSS_SHOT_ARC,0,1);
}

u8 boss_phase_tick(entity_t *e) BANKED {
    u8 phase = 0, i, linked;
    if (!(e->ai_data[3] & 1)) return 0;
    if (e->hp <= (e->ai_data[6] >> 1)) phase = 1;
    if (e->hp <= (e->ai_data[6] >> 2)) phase = 2;
    if (!e->x_frac) {
        e->x_frac = 1;
        e->y_frac = e->x_pad = 0;
        boss_link_active = 0;
        boss_link_pending = 0;
        summon_sites = 0;
        area_armed = 0;
    }
    if (phase + 1 > e->x_frac) {
        e->x_frac = phase + 1;
        e->x_pad = 40;
        e->y_frac = 0;
        e->ai_data[7] = 16;
        boss_link_active = 0;
        summon_sites = 0;
        area_armed = 0;
        for (i=0;i<MAX_ENTITIES;++i)
            if (entities[i].type == ENT_PROJECTILE && !(entities[i].flags & EF_PLAYER_PROJ)) entity_kill(i);
        boss_voice(e->ai_data[2],BOSS_VOICE_PHASE);
        if (e->ai_data[2] == 5) { hud_show_boss_link(2); reaper_pose_load(0); }
    }
    boss_phase = e->x_frac - 1;
    boss_phase_clock = e->y_frac;
    if (e->x_pad) { e->x_pad--; return 1; }
    boss_phase_clock = ++e->y_frac;
    if (e->ai_data[2] == 5 && boss_phase) {
        linked = boss_phase_clock >= 128 && boss_phase_clock < 224;
        if (linked && !boss_link_active) {
            for (i=0;i<MAX_ENTITIES;++i)
                if (entities[i].type == ENT_PROJECTILE && (entities[i].flags & EF_PLAYER_PROJ))
                    entities[i].ai_data[4] |= PROJ_PRELINK;
            boss_voice(5,BOSS_VOICE_PHASE);
        }
        boss_link_active = linked;
        reaper_pose_load(linked ? 2 : boss_phase_clock >= 96 && boss_phase_clock < 128 ? 1 : 0);
        if (linked) hud_show_boss_link(1);
        else if (boss_phase_clock >= 96 && boss_phase_clock < 128) hud_show_boss_link(0);
        else hud_show_boss_link(2);
        e->palette = linked ? 3 : 6;
        if (boss_phase_clock >= 96 && boss_phase_clock < 224 && !(boss_phase_clock & 7)) {
            i16 dx = (player.x-e->x)/4, dy = (player.y-e->y)/4;
            for (i=1;i<4;++i)
                fx_spawn(SPR_SHIELD_AURA, linked ? 3 : 5,e->x+8+dx*i,e->y+8+dy*i,9);
        }
        return 0;
    }
    boss_link_active = 0;
    if (boss_phase && e->ai_data[2] != 1) area_tick(e);
    if (boss_phase && (boss_phase_clock == 160 || boss_phase_clock == 192)
        && (e->ai_data[2] == 3 || e->ai_data[2] == 4 || e->ai_data[2] == 8)) summon(e);
    return 0;
}

u8 boss_phase_motion(entity_t *e) BANKED {
    u8 stage = e->ai_data[2], d, clock = boss_phase_clock & 127;
    i8 dx, dy;
    if (!boss_phase || stage == 1 || stage == 2 || stage == 5) return 0;
    if (boss_phase_clock >= 64 && boss_phase_clock < 112) return 1;
    if (stage == 0 || stage == 6) {
        if (clock == 1) {
            e->vy = magnitude(player.x-e->x)>magnitude(player.y-e->y)
                ? (player.x>e->x ? 2 : 6) : (player.y>e->y ? 4 : 0);
            e->ai_data[7]=16;
        }
        if (clock>=24 && clock<48) {
            d=(u8)e->vy&7;
            enemy_try_step(e,dir8_dx[d],dir8_dy[d]);
            if (boss_phase==2) enemy_try_step(e,dir8_dx[d],dir8_dy[d]);
        }
        if (stage == 6 && ((clock >= 48 && clock < 64) || clock >= 112)) {
            i16 cx = (room_world_width >> 1) - 16;
            i16 cy = (room_world_height >> 1) - 16;
            dx = e->x < cx ? 1 : e->x > cx ? -1 : 0;
            dy = e->y < cy ? 1 : e->y > cy ? -1 : 0;
            if (dx) enemy_try_step(e,dx,0);
            if (dy) enemy_try_step(e,0,dy);
        }
    } else if (stage == 3 || stage == 7) {
        if (!(clock & 1)) {
            dx = clock<64 ? 1 : -1;
            dy = (clock&32) ? 1 : -1;
            enemy_try_step(e,dx,0);
            if (boss_phase==2) enemy_try_step(e,0,dy);
        }
    } else {
        if (!(clock & 1)) {
            dx = player.y>e->y ? 1 : -1;
            dy = player.x>e->x ? -1 : 1;
            if (boss_phase==2 && (clock&64)) { dx=-dx; dy=-dy; }
            if (!enemy_try_step(e,dx,dy)) enemy_try_step(e,-dx,-dy);
        }
    }
    return 1;
}

u8 boss_link_reflect(entity_t *boss, entity_t *shot, u8 damage) BANKED {
    if (!boss_link_active || boss->ai_data[0] != ENEMY_STONE_SENTINEL
        || !(boss->ai_data[3]&1) || boss->ai_data[2]!=5
        || (shot->ai_data[4]&PROJ_PRELINK)) return 0;
    hurt(damage>2 ? 2 : damage);
    return 1;
}

void boss_link_share(u8 source, u8 damage) BANKED {
    u8 i;
    if (!boss_link_active) return;
    if (!(entities[source].flags&EF_BOSS_PROJECTILE)
        && !(entities[source].type==ENT_ENEMY && entities[source].ai_data[0]==ENEMY_STONE_SENTINEL)) return;
    for (i=0;i<MAX_ENTITIES;++i)
        if (entities[i].type==ENT_ENEMY && entities[i].ai_data[0]==ENEMY_STONE_SENTINEL
            && (entities[i].ai_data[3]&1) && entities[i].ai_data[2]==5) {
            if (entities[i].hp > damage) entities[i].hp -= damage;
            else {
                entities[i].hp = 0;
                boss_link_pending = i + 1;
                boss_link_active = 0;
            }
            entities[i].ai_data[7]=8;
            return;
        }
}
