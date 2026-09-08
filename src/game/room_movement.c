#pragma bank 8

#include "game/player.h"
#include "game/room.h"

void room_player_corner_slide(i8 dx, i8 dy) BANKED {
    u8 distance, side, open = 3;
    i8 sx = dy ? 1 : 0;
    i8 sy = dx ? 1 : 0;
    for (distance = 1; distance <= 3; ++distance) {
        for (side = 0; side < 2; ++side) {
            i8 sign = side ? 1 : -1;
            i16 x = player.x + sign * sx * distance;
            i16 y = player.y + sign * sy * distance;
            if (!(open & (1 << side))) continue;
            // Every intermediate sideways position must fit too.
            if (!room_player_position_clear(x, y)) {
                open &= (u8)~(1 << side);
                continue;
            }
            if (room_player_position_clear(x + dx, y + dy)) {
                player.x += sign * sx;
                player.y += sign * sy;
                return;
            }
        }
    }
}
