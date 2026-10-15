#pragma bank 13
#include <gb/gb.h>
#include "render/large_boss.h"
#include "game/enemy_ai.h"
#include "game/room.h"
#include "game/player.h"

u8 large_boss_index = 255;

u8 large_boss_shot_overlap(const entity_t *shot, const entity_t *boss) BANKED {
    i16 x=boss->x, y=boss->y;
    u8 w=40,h=24;
    if(boss->ai_data[2]==4) {x+=4;y-=4;w=24;h=40;}
    else {x-=4;y+=4;}
    return shot->x+(shot->hitbox>>4)>x && shot->x<x+w
        && shot->y+(shot->hitbox&15)>y && shot->y<y+h;
}

u8 large_boss_contact(const entity_t *boss) BANKED {
    i16 x=boss->x+4,y=boss->y+4;
    u8 w=24,h=24;
    if(boss->ai_data[2]==4) {y-=6;h=36;}
    else {x-=6;w=36;}
    return player.x+11>x && player.x+5<x+w
        && player.y+15>y && player.y+9<y+h;
}

void large_boss_reset(void) BANKED { large_boss_index=254; }

u8 large_boss_draw(u8 oam) BANKED {
    entity_t *e;
    u8 i, r, c, width, height, tile=40, pal;
    i16 x,y;
    if (large_boss_index==254) {
        large_boss_index=255;
        for(i=0;i<MAX_ENTITIES;++i) {
            e=&entities[i];
            if (e->type==ENT_ENEMY && (e->flags&EF_ACTIVE)
                && e->ai_data[0]==ENEMY_STONE_SENTINEL && (e->ai_data[3]&1)
                && (e->ai_data[2]==3 || e->ai_data[2]==4 || e->ai_data[2]==7)) {
                large_boss_index=i; break;
            }
        }
    }
    if (large_boss_index>=MAX_ENTITIES) return oam;
    e=&entities[large_boss_index];
    if(e->type!=ENT_ENEMY || !(e->flags&EF_ACTIVE) || !(e->ai_data[3]&1)) {
        large_boss_index=255; return oam;
    }
    if (!(e->flags&EF_ON_SCREEN)) return oam;
    width=e->ai_data[2]==4 ? 4:6;
    height=e->ai_data[2]==4 ? 6:4;
    if (height==6) {
        u8 beat=entity_anim_counter&63;
        if (beat<6 || (beat>=12 && beat<18)) tile=64;
    }
    x=e->x-room_camera_x+8-(width==6 ? 8:0);
    y=e->y-room_camera_y+16-(height==6 ? 8:0);
    pal=e->palette|8;
    if(e->ai_data[7]) {--e->ai_data[7]; if(e->ai_data[7]&1) pal=8;}
    __critical {
        for(r=0;r<height;++r) for(c=0;c<width;++c) {
            set_sprite_tile(oam,tile++);
            set_sprite_prop(oam,pal);
            move_sprite(oam++,(u8)(x+c*8),(u8)(y+r*8));
        }
    }
    return oam;
}
