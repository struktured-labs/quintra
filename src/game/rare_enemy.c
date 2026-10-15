#pragma bank 16
#include "game/rare_enemy.h"
#include "game/boss_projectile.h"
#include "game/player.h"
#include "game/run_state.h"
#include "game/room.h"
#include "game/status.h"
#include "audio/sfx.h"
#include "render/tiles.h"
#include "content.h"

void rare_enemy_prepare(void) BANKED {
    u8 i;
    u32 roll=run_state.run_seed ^ ((u32)run_state.room_counter*2654435761UL);
    roll ^= roll >> 16;
    if (RUN_IS_EASY() || run_state.world_mode || run_state_dungeon_local()<5
        || (roll&63)) return;
    for (i=0; i<MAX_ENTITIES; ++i) {
        entity_t *e=&entities[i];
        u8 id=e->ai_data[0];
        u16 hp;
        if (e->type!=ENT_ENEMY || !(e->flags&EF_ACTIVE)
            || (e->flags&(EF_ALPHA|EF_ELITE))) continue;
        if (id!=ENEMY_BLUE_CRAWLER && id!=ENEMY_HORNET
            && id!=ENEMY_ORC && id!=ENEMY_SKELETON) continue;
        e->flags |= EF_RARE;
        hp=(u16)e->hp*4+24;
        e->hp=hp>160 ? 160 : (u8)hp;
        e->damage=6+(run_state.bosses_beaten>>1);
        e->x_pad=0;
        e->palette=4;
        break;
    }
}

u8 rare_enemy_tick(entity_t *e) BANKED {
    u8 clock=++e->x_pad, i, shot;
    u8 pattern=(e->ai_data[0]&1) ? BOSS_SHOT_SPIRAL : BOSS_SHOT_BOLT;
    u8 payload=(e->ai_data[0]&1) ? QSTATUS_SLOW : QSTATUS_POISON;
    e->palette=(clock&16) ? 4 : 6;
    if (clock==128) {
        e->y_pad=(u8)((e->x ^ e->y ^ entity_anim_counter)&31);
        sfx_play(SFX_ROAR);
    }
    if (clock>=128 && clock<160) {
        if (!(clock&7)) fx_spawn(SPR_SHIELD_AURA,4,e->x,e->y-8,8);
        return 1;
    }
    if (clock==160) {
        for (i=0;i<4;++i) {
            shot=boss_projectile_spawn(e->x+4,e->y+4,
                e->y_pad+i*8,pattern,2,e->damage);
            if (shot!=0xFF) entities[shot].ai_data[5]=0x80|payload;
        }
        sfx_play(SFX_FIRE);
    }
    return 0;
}
