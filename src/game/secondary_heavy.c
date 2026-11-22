#pragma bank 26
#include <gb/gb.h>
#include "audio/sfx.h"
#include "game/player.h"
#include "game/pickup.h"
#include "game/projectile.h"
#include "game/sun_lattice.h"
#include "game/room.h"
#include "game/riftwild_den.h"
#include "game/puzzle.h"
#include "game/powerup.h"
#include "game/will.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

/* 2 MP: trickle regen (25/min, 37.5 Picsean) plus a mid-run pool
 * used to outpace a 1 MP bomb even at the 72-frame throw cap.
 * Keep the Pack tip in inventory.c / inventory_aim.c in sync. */
#define BOMB_MP_COST 2u

static const i8 mstar_sx[16] = {
    0, 9, 17, 22, 24, 22, 17, 9,
    0, -9, -17, -22, -24, -22, -17, -9
};
// Orbit reach in pixels for will_b_tier 0..3. Was 24, 27, 33, 39
// (+3, +6, +6); evened to 24, 29, 34, 39 (+5) without shrinking the max.
static const u8 mstar_reach[4] = {24, 29, 34, 39};
static const u8 mstar_life[4] = {40, 40, 44, 48};
static const u8 mstar_box[4]  = {0xAA, 0xAA, 0xCC, 0xDD};
static const u8 mstar_bonus[4] = {3, 3, 4, 5};

static i16 mstar_offset(i8 base, u8 reach) {
    return (i16)(((i16)base * (i16)reach) / 24);
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


/* Blast presence grows roughly linearly with will_b_tier 0..3:
 * tile radius 1/1/2/3, extra cardinal splashes, a shockwave ring,
 * and (from mid tier) flying fragments. A max-tier throw spends Will. */
static const u8 bomb_bonus[4]    = {8, 10, 12, 14};
static const u8 bomb_tile_r[4]   = {1, 1, 2, 3};
static const u8 bomb_splash_d[4] = {0, 10, 16, 22};
static const u8 bomb_ring_r[4]   = {14, 16, 22, 28};
static const u8 bomb_frags[4]    = {0, 0, 4, 8};
static const u8 bomb_shake[4]    = {2, 2, 3, 3};
static const u8 bomb_shake_t[4]  = {10, 12, 16, 20};

static void bomb_break_tiles(i16 x, i16 y, u8 radius);

static void bomb_spawn_frag(i16 x, i16 y, u8 dir, u8 damage, u8 gold) {
    u8 i;
    entity_t *f;
    i = entity_spawn(ENT_PROJECTILE);
    if (i == 0xFF) return;
    f = &entities[i];
    f->flags |= EF_PLAYER_PROJ;
    f->x = x;
    f->y = y;
    f->vx = (i8)(dir8_dx[dir] * 3);
    f->vy = (i8)(dir8_dy[dir] * 3);
    f->sprite_tile = SPR_BOMB_FRAG;
    f->palette = gold ? SPR_BOMB_FX_GOLD : SPR_BOMB_FX_PROP;
    f->hp = 1;
    f->state_timer = 14;
    f->hitbox = 0x66;
    f->damage = damage ? damage : 1;
    f->ai_data[0] = 0;
    f->ai_data[2] = 1; /* skip bullet shimmer */
    f->ai_data[3] = 0;
    f->ai_data[6] = 0;
}

static void bomb_explode(i16 x, i16 y, u8 damage, u8 tier) {
    u8 dir, step, prop, n;
    i8 rr;
    if (tier > 3) tier = 3;
    /* Visuals first so a crystal-rich room cannot spend every entity slot
     * on wisps before the blast exists. Tile breaks follow; each break
     * waits a vblank, so a packed field may not finish a 7x7 in one fuse. */
    projectile_spawn_splash(x, y, damage, 0xFF);
    n = bomb_splash_d[tier];
    if (n) {
        projectile_spawn_splash(x + (i16)n, y, damage, 0xFF);
        projectile_spawn_splash(x - (i16)n, y, damage, 0xFF);
        projectile_spawn_splash(x, y + (i16)n, damage, 0xFF);
        projectile_spawn_splash(x, y - (i16)n, damage, 0xFF);
    }
    if (tier == 0) {
        fx_spawn(SPR_FX_IMPACT, 4, x - 14, y - 14, 16);
        fx_spawn(SPR_FX_IMPACT, 4, x + 10, y - 14, 16);
        fx_spawn(SPR_FX_IMPACT, 4, x - 14, y + 10, 16);
        fx_spawn(SPR_FX_IMPACT, 4, x + 10, y + 10, 16);
    } else {
        rr = (i8)bomb_ring_r[tier];
        for (dir = 0; dir < 8; dir = (u8)(dir + 1)) {
            prop = (tier >= 3) ? SPR_BOMB_FX_GOLD : SPR_BOMB_FX_PROP;
            if (dir8_dx[dir] < 0) prop |= S_FLIPX;
            if (dir8_dy[dir] > 0) prop |= S_FLIPY;
            fx_spawn(SPR_BOMB_WAVE, prop,
                x + (i16)(dir8_dx[dir] * rr) - 4,
                y + (i16)(dir8_dy[dir] * rr) - 4,
                (u8)(12 + (tier << 1)));
        }
    }
    n = bomb_frags[tier];
    step = (u8)(n <= 4 ? 2 : 1);
    for (dir = 0; dir < 8 && n; dir = (u8)(dir + step)) {
        bomb_spawn_frag(x, y, dir, (u8)((damage + 1) >> 1), (u8)(tier >= 3));
        --n;
    }
    bomb_break_tiles(x, y, bomb_tile_r[tier]);
    room_shake(bomb_shake[tier], bomb_shake_t[tier]);
    sfx_play(SFX_ROAR);
}

/* Unsigned span loop: SDCC has bitten signed i8 for (dy=-r; dy<=r) before,
 * and a large radius must finish even after the FX/fragment spawns. */
static void bomb_break_tiles(i16 x, i16 y, u8 radius) {
    u8 t, ux, uy, span, tx, ty;
    i16 px, py, off;
    if (radius > 3) radius = 3;
    span = (u8)((radius << 1) + 1);
    for (uy = 0; uy < span; ++uy) {
        off = ((i16)uy - (i16)radius) * 8;
        py = y + off;
        for (ux = 0; ux < span; ++ux) {
            off = ((i16)ux - (i16)radius) * 8;
            px = x + off;
            t = room_tile_at_px(px, py);
            if (px < 0 || py < 0) continue;
            tx = (u8)(px >> 3);
            ty = (u8)(py >> 3);
            if (t == BGT_WALL_CRACK)
                room_open_secret(tx, ty);
            else if (t == BGT_PILLAR)
                sun_lattice_strike(tx, ty);
            else if (t == BGT_WILD_STONE)
                riftwild_den_strike(tx, ty);
            else if (t == BGT_WALL)
                puzzle_try_hidden_shot(tx, ty);
            else if (t == BGT_CRYSTAL)
                room_break_crystal(tx, ty);
        }
    }
}

u8 secondary_heavy_fire(u8 dir,u8 moving) BANKED {
    u8 i,bomb=player.active_item==ITEM_ID_BOMBS;
    u8 tier;
    entity_t *e;
    if (player.active_charge || (bomb && !POWERUP_FREE_MP() && player.mp < BOMB_MP_COST)) return 0;
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
        tier=will_b_tier();
        e->ai_data[7]=tier;
        e->hitbox=0xAA;
        e->damage=player.atk+bomb_bonus[tier];
        e->state_timer=48;
        if (moving) { e->vx=dir8_dx[dir&7]*2; e->vy=dir8_dy[dir&7]*2; }
        if (!POWERUP_FREE_MP()) { player.mp = (u8)(player.mp - BOMB_MP_COST); hud_redraw_mp(); }
        if (tier>=3) {
            player.will_charge = 0;
            player.will_level = 0;
        }
    } else {
        tier=will_b_tier();
        e->ai_data[7]=tier;
        e->hitbox=mstar_box[tier];
        e->damage=player.atk+mstar_bonus[tier];
        e->state_timer=mstar_life[tier];
        if (tier>=3) {
            room_shake(1, 8);
            // Max-Will orbits used to leave the gauge armed, so a second
            // swing at full size was free until a base A-attack spent it.
            player.will_charge = 0;
            player.will_level = 0;
        }
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
        e->x=player.x+4+mstar_offset(mstar_sx[a], mstar_reach[tier]);
        e->y=player.y+4-mstar_offset(mstar_sx[(a+4)&15], mstar_reach[tier]);
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
        tier=e->ai_data[7]&3;
        entity_kill(idx);
        bomb_explode(x,y,damage,tier);
    }
}
