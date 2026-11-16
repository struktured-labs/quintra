// Visible water traversal: Tide Raft under the champion, or Picsean's swim.
#ifndef QUINTRA_GAME_WATER_RIDE_H
#define QUINTRA_GAME_WATER_RIDE_H

#include <gb/gb.h>
#include "core/types.h"

// CGB VRAM bank 1 OBJ tiles 0..9 (OAM attribute bit 3).
#define WATER_RIDE_TILE        0
#define WATER_RIDE_TILE_COUNT  10
#define WATER_RIDE_RAFT_A      0   // 24x8: 0..2
#define WATER_RIDE_RAFT_B      3   // 24x8: 3..5
#define WATER_RIDE_SWIM_A      6   // 16x8: 6..7
#define WATER_RIDE_SWIM_B      8   // 16x8: 8..9

// The raft borrows the top three entity OAM entries while it is shown. OAM
// 39 stays free for the major-reward icon.
#define WATER_RIDE_OAM         36
#define WATER_RIDE_OAM_COUNT   3

enum {
    WATER_RIDE_NONE = 0,
    WATER_RIDE_RAFT,
    WATER_RIDE_SWIM,
};

extern u8 water_ride_mode;

void water_ride_load_tiles(void) BANKED;
void water_ride_place(void) BANKED;
void water_ride_hide(void) BANKED;

#endif
