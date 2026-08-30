#pragma bank 13

#include <gb/gb.h>
#include "core/rng.h"
#include "core/types.h"
#include "game/room.h"
#include "render/tiles.h"
#include "content.h"

void procgen_apply_early_archetype(u8 stage, u32 seed) BANKED {
    u8 archetype = stage_room_archetype[stage % N_STAGES];
    u8 i;
    if (archetype == STAGE_ARCH_CAVERN) {
        u8 variant = (u8)((seed >> 5) % 6);
        if (variant == 0) {
            static const u8 x[12] = {3,4,5,14,15,16,3,4,5,14,15,16};
            static const u8 y[12] = {4,4,4,4,4,4,12,12,12,12,12,12};
            for (i = 0; i < 12; ++i) room_tilemap[y[i]][x[i]] = BGT_CRYSTAL;
        } else if (variant == 1) {
            for (i = 3; i <= 6; ++i) {
                room_tilemap[i][5] = BGT_CRYSTAL;
                room_tilemap[(u8)(17-i)][14] = BGT_CRYSTAL;
            }
        } else if (variant == 2) {
            static const u8 x[12] = {4,5,6,13,14,15,4,5,6,13,14,15};
            static const u8 y[12] = {3,4,5,3,4,5,14,13,12,14,13,12};
            for (i = 0; i < 12; ++i) room_tilemap[y[i]][x[i]] = BGT_CRYSTAL;
        } else if (variant == 3) {
            for (i = 3; i <= 7; ++i) {
                room_tilemap[4][i] = BGT_PILLAR;
                room_tilemap[13][(u8)(19-i)] = BGT_PILLAR;
            }
        } else if (variant == 4) {
            static const u8 x[12] = {3,4,7,8,12,13,16,17,4,5,14,15};
            static const u8 y[12] = {5,5,3,3,14,14,11,11,12,12,5,5};
            for (i = 0; i < 12; ++i) room_tilemap[y[i]][x[i]] = BGT_CRYSTAL;
        } else {
            for (i = 4; i <= 6; ++i) {
                room_tilemap[i][4] = BGT_PILLAR;
                room_tilemap[i][15] = BGT_CRYSTAL;
                room_tilemap[(u8)(17-i)][4] = BGT_CRYSTAL;
                room_tilemap[(u8)(17-i)][15] = BGT_PILLAR;
            }
        }
    } else if (archetype == STAGE_ARCH_GROVE) {
        u8 variant = (u8)((seed >> 7) % 6);
        if (variant == 0) {
            static const u8 x[10] = {3,4,5,14,15,16,4,5,13,14};
            static const u8 y[10] = {4,4,5,12,12,11,13,13,3,3};
            for (i = 0; i < 10; ++i) room_tilemap[y[i]][x[i]] = BGT_CRYSTAL;
        } else if (variant == 1) {
            for (i = 3; i <= 6; ++i) {
                room_tilemap[i][(u8)(i+1)] = BGT_CRYSTAL;
                room_tilemap[(u8)(17-i)][(u8)(i+1)] = BGT_CRYSTAL;
            }
        } else if (variant == 2) {
            static const u8 x[12] = {3,4,5,6,13,14,15,16,4,5,14,15};
            static const u8 y[12] = {5,5,5,6,11,12,12,12,13,13,4,4};
            for (i = 0; i < 12; ++i) room_tilemap[y[i]][x[i]] = BGT_CRYSTAL;
        } else if (variant == 3) {
            for (i = 3; i <= 6; ++i) {
                room_tilemap[4][i] = BGT_CRYSTAL; room_tilemap[12][i] = BGT_CRYSTAL;
                room_tilemap[5][(u8)(19-i)] = BGT_CRYSTAL;
                room_tilemap[13][(u8)(19-i)] = BGT_CRYSTAL;
            }
        } else if (variant == 4) {
            static const u8 x[14] = {3,4,5,3,4,14,15,16,15,16,5,6,13,14};
            static const u8 y[14] = {3,3,3,4,4,13,13,13,12,12,11,11,5,5};
            for (i = 0; i < 14; ++i) room_tilemap[y[i]][x[i]] = BGT_CRYSTAL;
        } else {
            for (i = 3; i <= 6; ++i) {
                room_tilemap[i][4] = BGT_CRYSTAL;
                room_tilemap[(u8)(17-i)][5] = BGT_CRYSTAL;
                room_tilemap[i][15] = BGT_CRYSTAL;
                room_tilemap[(u8)(17-i)][14] = BGT_CRYSTAL;
            }
        }
    }
}

// Shared compact-room silhouettes live outside procgen's crowded fixed bank.
void procgen_apply_shared_layout(u8 shape) BANKED {
    u8 i;
    if (shape == 1) {
        room_tilemap[4][4] = BGT_PILLAR; room_tilemap[4][15] = BGT_PILLAR;
        room_tilemap[13][4] = BGT_PILLAR; room_tilemap[13][15] = BGT_PILLAR;
    } else if (shape == 2) {
        u8 placed = 0, tries = 12;
        while (placed < 4 && tries--) {
            u8 cx = (u8)(2 + rng_range(ROOM_W - 4));
            u8 cy = (u8)(2 + rng_range(ROOM_H - 4));
            if (cx >= 9 && cx <= 11) continue;
            if (cy >= 7 && cy <= 9) continue;
            room_tilemap[cy][cx] = BGT_CRYSTAL; placed++;
        }
    } else if (shape == 3) {
        room_tilemap[4][4] = BGT_PILLAR; room_tilemap[4][5] = BGT_PILLAR;
        room_tilemap[4][14] = BGT_PILLAR; room_tilemap[4][15] = BGT_PILLAR;
        room_tilemap[13][4] = BGT_PILLAR; room_tilemap[13][5] = BGT_PILLAR;
        room_tilemap[13][14] = BGT_PILLAR; room_tilemap[13][15] = BGT_PILLAR;
    } else if (shape == 4) {
        for (i = 4; i <= 15; ++i) if (i < 9 || i > 11) {
            room_tilemap[4][i] = BGT_PILLAR; room_tilemap[12][i] = BGT_PILLAR;
        }
        for (i = 4; i <= 12; ++i) if (i < 7 || i > 9) {
            room_tilemap[i][4] = BGT_PILLAR; room_tilemap[i][15] = BGT_PILLAR;
        }
    } else if (shape == 5) {
        for (i = 2; i <= 14; ++i) if (i < 7 || i > 9) {
            room_tilemap[i][5] = BGT_PILLAR; room_tilemap[i][14] = BGT_PILLAR;
        }
    } else if (shape == 6) {
        static const u8 x[12] = {3,4,5,16,15,14,3,4,5,16,15,14};
        static const u8 y[12] = {3,4,5,3,4,5,13,12,11,13,12,11};
        for (i = 0; i < 12; ++i) room_tilemap[y[i]][x[i]] = BGT_CRYSTAL;
    } else if (shape == 7) {
        static const u8 x[6] = {3,4,7,12,15,16};
        for (i = 0; i < 6; ++i) {
            room_tilemap[5][x[i]] = BGT_PILLAR; room_tilemap[11][x[i]] = BGT_PILLAR;
        }
    } else if (shape == 8) {
        for (i = 2; i <= 12; ++i) if (i < 9 || i > 11) room_tilemap[5][i] = BGT_PILLAR;
        for (i = 7; i <= 17; ++i) if (i < 9 || i > 11) room_tilemap[11][i] = BGT_PILLAR;
    } else if (shape == 9) {
        static const u8 x[4] = {4,8,12,16};
        for (i = 0; i < 4; ++i) {
            room_tilemap[4][x[i]] = BGT_PILLAR; room_tilemap[12][x[i]] = BGT_PILLAR;
        }
    } else if (shape == 10) {
        for (i = 6; i <= 13; ++i) if (i < 9 || i > 11) {
            room_tilemap[6][i] = BGT_PILLAR; room_tilemap[10][i] = BGT_PILLAR;
        }
        for (i = 6; i <= 10; ++i) if (i < 7 || i > 9) {
            room_tilemap[i][6] = BGT_PILLAR; room_tilemap[i][13] = BGT_PILLAR;
        }
    } else if (shape == 11) {
        for (i = 3; i <= 7; ++i) {
            room_tilemap[4][i] = BGT_PILLAR; room_tilemap[13][(u8)(19-i)] = BGT_PILLAR;
        }
    } else if (shape == 12) {
        for (i = 2; i <= 7; ++i) room_tilemap[5][i] = BGT_PILLAR;
        for (i = 12; i <= 17; ++i) room_tilemap[11][i] = BGT_PILLAR;
    } else if (shape == 13) {
        static const u8 x[12] = {7,8,12,13,5,5,14,14,7,8,12,13};
        static const u8 y[12] = {4,4,4,4,6,11,6,11,13,13,13,13};
        for (i = 0; i < 12; ++i) room_tilemap[y[i]][x[i]] = BGT_CRYSTAL;
    } else if (shape == 14) {
        static const u8 x[16] = {3,4,5,3,14,15,16,16,3,3,4,5,14,15,16,16};
        static const u8 y[16] = {4,4,4,5,4,4,4,5,12,13,13,13,13,13,13,12};
        for (i = 0; i < 16; ++i) room_tilemap[y[i]][x[i]] = BGT_PILLAR;
    } else if (shape == 15) {
        for (i = 3; i <= 6; ++i) {
            room_tilemap[i][6] = BGT_PILLAR; room_tilemap[(u8)(17-i)][13] = BGT_PILLAR;
        }
    } else if (shape == 16) {
        static const u8 x[12] = {3,4,5,3,3,5,14,15,16,14,16,16};
        static const u8 y[12] = {5,5,5,6,11,11,12,12,12,6,6,11};
        for (i = 0; i < 12; ++i) room_tilemap[y[i]][x[i]] = BGT_PILLAR;
    } else if (shape == 17) {
        static const u8 x[8] = {3,7,13,16,5,8,12,15};
        for (i = 0; i < 4; ++i) room_tilemap[4][x[i]] = BGT_PILLAR;
        for (i = 4; i < 8; ++i) room_tilemap[12][x[i]] = BGT_PILLAR;
    } else if (shape == 18) {
        for (i = 3; i <= 6; ++i) room_tilemap[4][i] = BGT_PILLAR;
        for (i = 13; i <= 16; ++i) room_tilemap[12][i] = BGT_CRYSTAL;
        room_tilemap[5][3] = BGT_PILLAR; room_tilemap[11][16] = BGT_CRYSTAL;
    }
}
