#pragma bank 26
#include <gb/gb.h>
#include "audio/sfx.h"
#include "game/player.h"
#include "game/pickup.h"
#include "game/projectile.h"
#include "game/sun_lattice.h"
#include "game/room.h"
#include "game/bomb_wall.h"
#include "game/riftwild_den.h"
#include "game/puzzle.h"
#include "game/powerup.h"
#include "game/will.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

static const i8 mstar_sx[16] = {
    0, 9, 17, 22, 24, 22, 17, 9,
    0, -9, -17, -22, -24, -22, -17, -9
};
// 8.8 orbit scale for will_b_tier 0..3: 24, 27, 33, 39 px (24 * n/8).
static const u8 mstar_scale[4] = {8, 9, 11, 13};
static const u8 mstar_life[4] = {40, 40, 44, 48};
static const u8 mstar_box[4]  = {0xAA, 0xAA, 0xCC, 0xDD};
static const u8 mstar_bonus[4] = {3, 3, 4, 5};

static i16 mstar_offset(i8 base, u8 scale) {
    return (i16)(((i16)base * (i16)scale) >> 3);
}

static void mstar_clamp(entity_t *e) {
    i16 max_x = (i16)room_world_width - 8;
    i16 max_y = (i16)room_world_height - 8;
    if (max_x < 0) max_x = 0;
    if (max_y < 0) max_y = 0;
    if (e->x < 0) e->x = 0;
    else if (e->x > max_x) e->x = max_x;
    if (e->y < 0) e->y = 0;
    else if (e->y > max_y) e->y = max_y;
}

u8 secondary_heavy_fire(u8 dir,u8 moving) BANKED {
    u8 i,bomb=player.active_item==ITEM_ID_BOMBS;
    u8 tier;
    entity_t *e;
    if (player.active_charge || (bomb && !player.mp && !POWERUP_FREE_MP())) return 0;
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
    e->sprite_tile=bomb ? SPR_ITEM_BOMB_BAG : SPR_ITEM_MORNINGSTAR;
    e->palette=bomb ? SPR_BOMB_BAG_PROP : SPR_MORNINGSTAR_PROP;
    e->hp=8;
    e->ai_data[0]=dir*2;
    e->ai_data[2]=1;
    e->ai_data[6]=bomb ? PROJ_AUX_FUSE_BOMB : PROJ_AUX_MORNINGSTAR;
    if (bomb) {
        e->hitbox=0xAA;
        e->damage=player.atk+8;
        e->state_timer=48;
        if (moving) { e->vx=dir8_dx[dir&7]*2; e->vy=dir8_dy[dir&7]*2; }
        if (!POWERUP_FREE_MP()) { player.mp--; hud_redraw_mp(); }
    } else {
        tier=will_b_tier();
        e->ai_data[7]=tier;
        e->hitbox=mstar_box[tier];
        e->damage=player.atk+mstar_bonus[tier];
        e->state_timer=mstar_life[tier];
        if (tier>=3) room_shake(1, 8);
    }
    player.active_charge=bomb ? 72 : 56;
    sfx_play_weapon(PROJ_FLAIL);
    return 1;
}

void secondary_heavy_update(entity_t *e,u8 idx) BANKED {
    u8 a,t,tier;
    if (!e->state_timer--) { entity_kill(idx); return; }
    if (e->ai_data[6]==PROJ_AUX_MORNINGSTAR) {
        tier=e->ai_data[7]&3;
        a=(++e->ai_data[0]>>1)&15;
        e->x=player.x+4+mstar_offset(mstar_sx[a], mstar_scale[tier]);
        e->y=player.y+4-mstar_offset(mstar_sx[(a+4)&15], mstar_scale[tier]);
        mstar_clamp(e);
        t=room_tile_at_px(e->x+4,e->y+4);
        // One strike per swing: a full orbit would otherwise toggle a vane
        // twice and leave it unchanged (the old swing died on first contact).
        if (t==BGT_PILLAR && !(e->ai_data[5]&1)) {
            if (sun_lattice_strike((u8)((e->x+4)>>3),(u8)((e->y+4)>>3)))
                e->ai_data[5]|=1;
        } else if (t==BGT_WILD_STONE)
            riftwild_den_strike((u8)((e->x+4)>>3),(u8)((e->y+4)>>3));
        if (tier>=3 && !(e->state_timer&3)) {
            fx_spawn(SPR_FX_IMPACT, 6, e->x+4, e->y+4, 6);
            // Keep VRAM bank 1 so the 16x16 head tiles stay in view.
            e->palette=(e->state_timer&4) ? (u8)(8+6) : SPR_MORNINGSTAR_PROP;
        }
        return;
    }
    if (e->state_timer>32) {
        t=room_tile_at_px(e->x+e->vx+4,e->y+e->vy+4);
        if (!room_tile_walkable(t)) e->vx=e->vy=0;
        e->x+=e->vx; e->y+=e->vy;
    }
    if (e->state_timer<16) {
        e->palette=(e->state_timer&2) ? SPR_BOMB_BAG_PROP : SPR_BOMB_BAG_FLASH;
        if (!(e->state_timer&7)) sfx_play(SFX_TICK);
    }
    if (!e->state_timer) {
        i16 x=e->x+4,y=e->y+4;
        u8 damage=e->damage;
        i8 dx,dy;
        entity_kill(idx);
        for (dy=-1;dy<=1;++dy)
            for (dx=-1;dx<=1;++dx)
            {
                t=room_tile_at_px(x+dx*8,y+dy*8);
                if (t==BGT_WALL_CRACK)
                    room_open_secret((u8)((x+dx*8)>>3),(u8)((y+dy*8)>>3));
                else if (t==BGT_WALL_BOMB)
                    bomb_wall_try_open((u8)((x+dx*8)>>3),(u8)((y+dy*8)>>3));
                else if (t==BGT_PILLAR)
                    sun_lattice_strike((u8)((x+dx*8)>>3),(u8)((y+dy*8)>>3));
                else if (t==BGT_WILD_STONE)
                    riftwild_den_strike((u8)((x+dx*8)>>3),(u8)((y+dy*8)>>3));
                else if (t==BGT_WALL)
                    puzzle_try_hidden_shot((u8)((x+dx*8)>>3),(u8)((y+dy*8)>>3));
            }
        projectile_spawn_splash(x,y,damage,0xFF);
        fx_spawn(SPR_FX_IMPACT,4,x-14,y-14,16);
        fx_spawn(SPR_FX_IMPACT,4,x+10,y-14,16);
        fx_spawn(SPR_FX_IMPACT,4,x-14,y+10,16);
        fx_spawn(SPR_FX_IMPACT,4,x+10,y+10,16);
        room_shake(2,10); sfx_play(SFX_ROAR);
    }
}
