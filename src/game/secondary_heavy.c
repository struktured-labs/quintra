#pragma bank 16
#include <gb/gb.h>
#include "audio/sfx.h"
#include "game/player.h"
#include "game/pickup.h"
#include "game/projectile.h"
#include "game/room.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

u8 secondary_heavy_fire(u8 dir,u8 moving) BANKED {
    u8 i,bomb=player.active_item==ITEM_ID_BOMBS;
    entity_t *e;
    if (player.active_charge || (bomb && !player.mp)) return 0;
    for (i=0;i<INVENTORY_SLOTS;++i)
        if (player.inventory[i]==player.active_item) break;
    if (i==INVENTORY_SLOTS) return 0;
    for (i=0;i<MAX_ENTITIES;++i)
        if (entities[i].type==ENT_PROJECTILE && (entities[i].flags&EF_ACTIVE)
            && (entities[i].ai_data[6]==PROJ_AUX_MORNINGSTAR
                || entities[i].ai_data[6]==PROJ_AUX_FUSE_BOMB)) return 0;
    i=entity_spawn(ENT_PROJECTILE);
    if (i==0xFF) return 0;
    e=&entities[i];
    e->flags |= EF_PLAYER_PROJ;
    e->x=player.x+4; e->y=player.y+4;
    e->sprite_tile=bomb ? SPR_ITEM_RIFT_BOMB : 237;
    e->palette=bomb ? 4 : 13;
    e->hitbox=0xAA; e->hp=8;
    e->damage=player.atk+(bomb ? 8 : 3);
    e->state_timer=bomb ? 48 : 40;
    e->ai_data[0]=dir*2;
    e->ai_data[2]=1;
    e->ai_data[6]=bomb ? PROJ_AUX_FUSE_BOMB : PROJ_AUX_MORNINGSTAR;
    if (bomb) {
        if (moving) { e->vx=dir8_dx[dir&7]*2; e->vy=dir8_dy[dir&7]*2; }
        player.mp--; hud_redraw_mp();
    }
    player.active_charge=bomb ? 72 : 56;
    sfx_play_weapon(PROJ_FLAIL);
    return 1;
}

void secondary_heavy_update(entity_t *e,u8 idx) BANKED {
    static const i8 sx[16]={0,9,17,22,24,22,17,9,0,-9,-17,-22,-24,-22,-17,-9};
    u8 a,t;
    if (!e->state_timer--) { entity_kill(idx); return; }
    if (e->ai_data[6]==PROJ_AUX_MORNINGSTAR) {
        a=(++e->ai_data[0]>>1)&15;
        e->x=player.x+4+sx[a]; e->y=player.y+4-sx[(a+4)&15];
        if (!room_tile_walkable(room_tile_at_px(e->x+4,e->y+4))) entity_kill(idx);
        return;
    }
    if (e->state_timer>32) {
        t=room_tile_at_px(e->x+e->vx+4,e->y+e->vy+4);
        if (!room_tile_walkable(t)) e->vx=e->vy=0;
        e->x+=e->vx; e->y+=e->vy;
    }
    if (e->state_timer<16) {
        e->palette=(e->state_timer&2) ? 4 : 5;
        if (!(e->state_timer&7)) sfx_play(SFX_TICK);
    }
    if (!e->state_timer) {
        i16 x=e->x+4,y=e->y+4;
        u8 damage=e->damage;
        i8 dx,dy;
        entity_kill(idx);
        for (dy=-1;dy<=1;++dy)
            for (dx=-1;dx<=1;++dx)
                if (room_tile_at_px(x+dx*8,y+dy*8)==BGT_WALL_CRACK)
                    room_open_secret((u8)((x+dx*8)>>3),(u8)((y+dy*8)>>3));
        projectile_spawn_splash(x,y,damage,0xFF);
        fx_spawn(SPR_FX_IMPACT,4,x-14,y-14,16);
        fx_spawn(SPR_FX_IMPACT,4,x+10,y-14,16);
        fx_spawn(SPR_FX_IMPACT,4,x-14,y+10,16);
        fx_spawn(SPR_FX_IMPACT,4,x+10,y+10,16);
        room_shake(2,10); sfx_play(SFX_ROAR);
    }
}
