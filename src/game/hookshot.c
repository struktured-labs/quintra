#pragma bank 16
#include <gb/gb.h>
#include "audio/sfx.h"
#include "game/player.h"
#include "game/pickup.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/status.h"
#include "game/will.h"
#include "render/tiles.h"

static u8 owns(u8 id) {
    u8 i;
    for (i=0; i<INVENTORY_SLOTS; ++i)
        if (player.inventory[i]==id) return 1;
    return 0;
}

void secondary_fire(u8 dir,u8 moving,u8 damage) BANKED {
    u8 used=0;
    if (player.active_item==ITEM_ID_HOOKSHOT) used=projectile_throw_hookshot(dir);
    else if (player.active_item==ITEM_ID_BOOMERANG) used=projectile_throw_boomerang(dir);
    else if (player.active_item==ITEM_ID_MORNINGSTAR || player.active_item==ITEM_ID_BOMBS)
        used=secondary_heavy_fire(dir,moving);
    else {
        if (!STATUS_PLAYER_MUTED() && !player.active_charge && will_fire_signature(dir,damage)) {
            will_begin_signature(); used=1;
        }
        if (!used) used=projectile_throw_boomerang(dir);
    }
    if (!used && (STATUS_PLAYER_MUTED() || !player.active_charge)) sfx_play(SFX_HURT);
}

void secondary_cooldown_tick(void) BANKED {
    if (--player.active_charge==0)
        fx_spawn(SPR_FX_IMPACT,6,player.x+4,player.y+2,6);
}

void secondary_cycle(void) BANKED {
    u8 id=player.active_item<ITEM_ID_BOOMERANG ? ITEM_ID_BOOMERANG : player.active_item+1;
    for (;id<=ITEM_ID_BOMBS;++id)
        if (owns(id)) { player.active_item=id; return; }
    player.active_item=10+player.class_id;
}

u8 projectile_throw_hookshot(u8 dir) BANKED {
    u8 i;
    entity_t *e;
    if (!owns(ITEM_ID_HOOKSHOT)) return 0;
    for (i=0; i<MAX_ENTITIES; ++i)
        if (entities[i].type==ENT_PROJECTILE && (entities[i].flags&EF_ACTIVE)
            && entities[i].ai_data[6]==PROJ_AUX_HOOKSHOT) {
            entity_kill(i);
            return 1;
        }
    i=entity_spawn(ENT_PROJECTILE);
    if (i==0xFF) return 0;
    e=&entities[i];
    e->flags |= EF_PLAYER_PROJ;
    e->x=player.x+4; e->y=player.y+4;
    e->vx=dir8_dx[dir&7]; e->vy=dir8_dy[dir&7];
    e->sprite_tile=SPR_WAYGEAR_HOOK;
    e->palette=6; e->hitbox=0x66; e->hp=255;
    e->state_timer=24; e->ai_data[6]=PROJ_AUX_HOOKSHOT;
    sfx_play_boomerang(0);
    return 1;
}

static i16 magnitude(i16 n) { return n<0 ? -n : n; }

void projectile_update_hookshot(entity_t *e, u8 idx) BANKED {
    u8 i, step, tile;
    i16 dx,dy,nx,ny;
    if (!e->state_timer--) { entity_kill(idx); return; }
    if (!e->state) {
        for (step=0; step<4; ++step) {
            e->x+=e->vx; e->y+=e->vy;
            if (e->x<0 || e->y<0 || e->x+7>=room_world_width
                || e->y+7>=room_world_height) { e->state=2; break; }
            tile=room_tile_at_px(e->x+3,e->y+3);
            if (tile==BGT_WALL || tile==BGT_PILLAR || tile==BGT_TREE
                || tile==BGT_CRYSTAL || tile==BGT_WALL_CRACK) {
                e->state=1; break;
            }
            for (i=0; i<MAX_ENTITIES; ++i)
                if (entities[i].type==ENT_ENEMY && (entities[i].flags&EF_ACTIVE)
                    && aabb_overlap_ee(e,&entities[i])) {
                    e->state=1; e->ai_data[5]=i+1;
                    status_enemy_apply(i,QSTATUS_STOP,4);
                    break;
                }
            if (e->state) break;
        }
        if (!e->state && e->state_timer) return;
        if (!e->state) e->state=2;
        e->state_timer=48;
        if (e->state==1) sfx_play(SFX_HIT);
    }
    if (e->state==1) {
        if (e->ai_data[5]) {
            entity_t *target=&entities[e->ai_data[5]-1];
            if (target->type!=ENT_ENEMY || !(target->flags&EF_ACTIVE)) e->state=2;
            else { e->x=target->x+4; e->y=target->y+4; }
        }
        for (step=0; step<3 && e->state==1; ++step) {
            dx=e->x-player.x-4; dy=e->y-player.y-4;
            if (magnitude(dx)<18 && magnitude(dy)<18) { e->state=2; break; }
            nx=player.x+(dx>0 ? 1 : dx<0 ? -1 : 0);
            ny=player.y+(dy>0 ? 1 : dy<0 ? -1 : 0);
            if (!room_player_position_clear(nx,ny)) { e->state=2; break; }
            player.x=nx; player.y=ny;
        }
    }
    if (e->state==2) {
        dx=player.x+4-e->x; dy=player.y+4-e->y;
        if (magnitude(dx)<=6 && magnitude(dy)<=6) {
            entity_kill(idx); sfx_play_boomerang(1); return;
        }
        e->x+=dx>6 ? 6 : dx<-6 ? -6 : dx;
        e->y+=dy>6 ? 6 : dy<-6 ? -6 : dy;
    }
}

u8 hookshot_draw(entity_t *e,u8 oam,u8 x,u8 y) BANKED {
    u8 n;
    i16 dx=(player.x+4-e->x)/4, dy=(player.y+4-e->y)/4;
    i16 sx,sy;
    x; y;
    for (n=0; n<4 && oam<40; ++n) {
        sx=e->x-room_camera_x+8+dx*n;
        sy=e->y-room_camera_y+16+dy*n;
        set_sprite_tile(oam,n ? SPR_BULLET : e->sprite_tile);
        set_sprite_prop(oam,n ? 6 : e->palette);
        if (sx>0 && sx<168 && sy>0 && sy<152) move_sprite(oam,(u8)sx,(u8)sy);
        else move_sprite(oam,0,0);
        oam++;
    }
    return oam;
}
