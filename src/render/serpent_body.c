#pragma bank 15
#include <gb/gb.h>
#include <gb/cgb.h>
#include "game/enemy_ai.h"
#include "game/room.h"
#include "render/palette.h"
#include "render/tiles.h"

u8 serpent_body_dirty;
static u8 body_previous[68], body_next[68], body_changed[68], body_load;
static const u8 body_art[144] = {
    0x00,0xff,0x18,0xff,0x24,0xff,0x00,0xff,0x00,0xff,0x24,0xdb,0x18,0xe7,0x00,0xff,
    0xff,0x00,0xff,0xff,0x00,0xff,0x00,0xff,0x00,0xff,0x00,0xff,0x00,0xff,0x00,0xff,
    0x00,0xff,0x00,0xff,0x00,0xff,0x00,0xff,0x00,0xff,0x00,0xff,0x00,0xff,0xff,0x00,
    0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,
    0x01,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,
    0x3f,0x00,0x7f,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,
    0xfc,0x00,0xfe,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,
    0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0xc0,0x7f,0x40,0x7f,0x3f,0x00,
    0x01,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,0x01,0xfe,0x00,0xfe,0xfc,0x00,
};
static const u16 body_palette[4] = {
    BGR555(6,7,10), BGR555(9,1,4), BGR555(23,3,6), BGR555(31,13,10)
};

void serpent_body_reset(void) BANKED {
    u8 i;
    for (i=0;i<68;++i) body_previous[i]=0;
    serpent_body_dirty=body_load=1;
}

static void mark(u8 x, u8 y) {
    if (!x || x>=27 || !y || y>=16) return;
    body_next[(y<<2)+(x>>3)] |= (u8)(1 << (x&7));
}

static u8 body_tile(u8 index, u8 mask) {
    u8 top=!(body_next[index-4]&mask), bottom=!(body_next[index+4]&mask);
    u8 left=!(mask==1 ? body_next[index-1]&128 : body_next[index]&(mask>>1));
    u8 right=!(mask==128 ? body_next[index+1]&1 : body_next[index]&(mask<<1));
    if (top) return BGT_COLOSSUS_VOID+(left ? 5 : right ? 6 : 1);
    if (bottom) return BGT_COLOSSUS_VOID+(left ? 7 : right ? 8 : 2);
    return BGT_COLOSSUS_VOID+(left ? 3 : right ? 4 : 0);
}

void serpent_body_draw(void) BANKED {
    u8 i, x, y, bit, changed, mask, tile, attr, alive;
    if (serpent_head_index>=MAX_ENTITIES) return;
    alive=entities[serpent_head_index].type==ENT_ENEMY
        && entities[serpent_head_index].ai_data[0]==ENEMY_STONE_SENTINEL
        && entities[serpent_head_index].ai_data[2]==1
        && (entities[serpent_head_index].flags & EF_ACTIVE);
    if (!alive && serpent_tail_visible) {
        serpent_tail_visible=0;
        serpent_body_dirty=1;
    }
    if (body_load) {
        VBK_REG=0;
        set_bkg_data(BGT_COLOSSUS_VOID,9,body_art);
        palette_bg_load(6,body_palette);
        body_load=0;
    }
    if (!serpent_body_dirty) {
        if (!alive) serpent_tail_active=0;
        return;
    }
    serpent_body_dirty=0;
    for (i=0;i<68;++i) body_next[i]=body_changed[i]=0;
    if (alive) {
        for (i=1;i<=serpent_tail_visible && i<serpent_tail_count;++i) {
            x=serpent_tail_x[i]>>3;
            y=serpent_tail_y[i]>>3;
            mark(x,y);
        }
    }
    for (i=4;i<64;++i) {
        changed=body_previous[i]^body_next[i];
        if (!changed) continue;
        body_changed[i] |= changed|(changed<<1)|(changed>>1);
        body_changed[i-4] |= changed;
        body_changed[i+4] |= changed;
        if (i&3) body_changed[i-1] |= changed<<7;
        if ((i&3)!=3) body_changed[i+1] |= changed>>7;
    }
    for (i=4;i<64;++i) {
        changed=body_changed[i]&(body_previous[i]|body_next[i]);
        if (!changed) continue;
        y=i>>2;
        x=(i&3)<<3;
        mask=1;
        for (bit=0;bit<8;++bit,++x,mask<<=1) {
            if (!(changed&mask)) continue;
            if (body_next[i]&mask) {
                tile=body_tile(i,mask);
                attr=6;
            } else {
                tile=room_tile_at_px((i16)x<<3,(i16)y<<3);
                attr=tile==BGT_WALL ? BGPAL_WALL
                    : tile==BGT_DOOR ? BGPAL_DOOR : BGPAL_FLOOR;
            }
            VBK_REG=0; set_bkg_tiles(x,y,1,1,&tile);
            VBK_REG=1; set_bkg_tiles(x,y,1,1,&attr);
        }
        body_previous[i]=body_next[i];
    }
    VBK_REG=0;
    if (!alive) serpent_tail_active=0;
}
