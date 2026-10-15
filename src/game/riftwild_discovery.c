#pragma bank 11
#include <gb/gb.h>
#include "game/entity.h"
#include "game/pickup.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

void riftwild_discovery_prepare(void) BANKED {
    u8 x,y,i;
    if (run_state.riftwild_region || run_state.world_screen
        || RUN_RIFTWILD_IS_HOLLOW()) return;

    for (y=2;y<=7;++y) for (x=12;x<=18;++x)
        room_tilemap[y][x]=BGT_WILD_WATER;
    for (y=4;y<=5;++y) for (x=14;x<=16;++x)
        room_tilemap[y][x]=BGT_GRASS;
    room_tilemap[3][14]=room_tilemap[3][16]=BGT_PILLAR;
    room_tilemap[3][15]=BGT_CRYSTAL;
    room_tilemap[4][15]=BGT_WILD_FLOWER;

    for (y=4;y<=7;++y) for (x=3;x<=8;++x)
        room_tilemap[y][x]=BGT_GRASS;
    for (x=3;x<=7;++x) room_tilemap[3][x]=BGT_TREE;
    room_tilemap[4][8]=room_tilemap[5][7]=BGT_WILD_FLOWER;
    room_tilemap[6][6]=room_tilemap[7][5]=BGT_WILD_FLOWER;
    room_tilemap[5][3]=BGT_WILD_REEDS;
    room_tilemap[6][3]=BGT_WILD_REEDS;
    pickup_spawn_wayfarer(14,FIX8(32),FIX8(40));
    if (!RUN_RIFTWELL_USED()) pickup_spawn_riftwell(FIX8(40),FIX8(48));
    pickup_spawn_wayfarer(15,FIX8(128),FIX8(32));
    if (!(run_state.riftwild_flags & 0x20)) {
        i=pickup_spawn_item(15,FIX8(120),FIX8(40));
        if (i!=0xFF) {
            // This authored island is intentionally gated, not a stranded drop.
            entities[i].x=FIX8(120);
            entities[i].y=FIX8(40);
            entities[i].ai_data[5]=0xB1;
        }
    }
}
