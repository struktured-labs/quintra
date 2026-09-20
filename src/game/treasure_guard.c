#pragma bank 13

#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/pickup.h"
#include "game/room.h"
#include "content.h"
#include "core/rng.h"

u8 pickup_boss_relic_for_class(void) BANKED {
    return pickup_farfold_relic_for_class(rng_range(3));
}

u8 pickup_farfold_relic_for_class(u8 roll) BANKED {
    static const u8 relics[5][3] = {
        {12,17,19}, {10,16,19}, {11,12,17}, {12,15,16}, {12,17,19}
    };
    while (roll >= 3) roll -= 3;
    return relics[player.class_id < 5 ? player.class_id : 0][roll];
}

u8 treasure_cache_guarded(void) BANKED {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY)
            return 1;
    return 0;
}

void treasure_cache_prepare(void) BANKED {
    u8 i, count = 0;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY) count++;
    for (i = 0; i < 4 && count < 4; ++i) {
        u8 x = (i & 1) ? 27 : 25;
        u8 y = (u8)(19 + i * 2);
        u8 idx;
        if (!room_tile_walkable(room_tile_at_px(x * 8, y * 8))
            || !room_tile_walkable(room_tile_at_px(x * 8 + 15, y * 8 + 15))) continue;
        idx = enemy_spawn(i & 1 ? ENEMY_ORC : ENEMY_BLUE_CRAWLER, x, y);
        if (idx == 0xFF) break;
        entities[idx].ai_data[1] = 60;
        count++;
    }
}
