#pragma bank 10

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/waygear.h"
#include "render/tiles.h"

static void open_current_grove(void) {
    u8 grass = BGT_GRASS;
    u8 floor_attr = BGPAL_FLOOR;
    u8 left;
    u8 right;
    if (!run_state.world_mode) return;
    left = room_tilemap[7][14];
    right = room_tilemap[7][15];
    // Only the two traversal-reward groves auto-swap the active implement.
    // Check the authored pair as well as the screen so a malformed field can
    // never turn an unrelated pair of terrain cells into grass.
    if (!((run_state.world_screen == 17 && left == BGT_GATE_BOULDER
                && right == BGT_GATE_BOULDER)
            || (run_state.world_screen == 29 && left == BGT_GATE_WATER
                && right == BGT_GATE_WATER))) return;
    room_tilemap[7][14] = room_tilemap[7][15] = BGT_GRASS;
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(14), ROOM_BG_MAP_Y(7), 1, 1, &grass);
    set_bkg_tiles(ROOM_BG_MAP_X(15), ROOM_BG_MAP_Y(7), 1, 1, &grass);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(14), ROOM_BG_MAP_Y(7), 1, 1, &floor_attr);
    set_bkg_tiles(ROOM_BG_MAP_X(15), ROOM_BG_MAP_Y(7), 1, 1, &floor_attr);
    VBK_REG = 0;
    sfx_play(SFX_DOOR);
}

u8 waygear_grant(u8 gear) BANKED {
    u8 bit;
    if (gear >= WAYGEAR_COUNT) return 0;
    bit = WAYGEAR_BIT(gear);
    if (player.waygear_owned & bit) return 0;
    // The Raft and Hook sit behind a gate crossed with the previous tool.
    // Open that mouth before auto-equipping the discovery; otherwise the new
    // tool immediately revokes the old traversal permission and soft-locks
    // the hero inside the two-cell grove.
    open_current_grove();
    player.waygear_owned |= bit;
    // A newly discovered traversal implement resonates immediately. The
    // Pack can later swap the single active slot at any time outside action.
    player.waygear_equipped = gear;
    sfx_play_reward(SFX_REWARD_SIGIL);
    room_refresh_player_appearance(1);
    return 1;
}

static void stamp_pocket(u8 gate) {
    u8 x, y;
    // A sealed northern grove touches the central clearing but never blocks
    // a cardinal graph trail. Its two-cell mouth admits the 12px champion
    // exactly when hero nature or the equipped implement authorizes it.
    for (x = 12; x <= 18; ++x) {
        room_tilemap[2][x] = BGT_TREE;
        room_tilemap[7][x] = BGT_TREE;
    }
    for (y = 2; y <= 7; ++y) {
        room_tilemap[y][12] = BGT_TREE;
        room_tilemap[y][18] = BGT_TREE;
    }
    for (y = 3; y < 7; ++y)
        for (x = 13; x < 18; ++x)
            room_tilemap[y][x] = BGT_GRASS;
    // Keep rows 8/9 untouched: they are the field's complete east/west trail.
    room_tilemap[7][14] = gate;
    room_tilemap[7][15] = gate;
}

static void open_pedestal(void) {
    u8 x, y;
    for (y = 3; y <= 7; ++y)
        for (x = 13; x <= 17; ++x)
            room_tilemap[y][x] = BGT_GRASS;
    room_tilemap[5][15] = BGT_WILD_FLOWER;
}

void waygear_prepare_world_field(void) BANKED {
    u8 screen;
    if (!run_state.world_mode) return;
    screen = run_state.world_screen;

    // First implement is freely discoverable; the next two form a capability
    // chain. Sauran and Picsean can skip the corresponding prior tool, making
    // champion identity a route advantage rather than a cosmetic stat line.
    if (screen == 3 && !(player.waygear_owned & WAYGEAR_BIT(WAYGEAR_GLOVE))) {
        open_pedestal();
        pickup_spawn_waygear(WAYGEAR_GLOVE, FIX8(120), FIX8(40));
    } else if (screen == 17
            && !(player.waygear_owned & WAYGEAR_BIT(WAYGEAR_RAFT))) {
        stamp_pocket(BGT_GATE_BOULDER);
        pickup_spawn_waygear(WAYGEAR_RAFT, FIX8(120), FIX8(40));
    } else if (screen == 29
            && !(player.waygear_owned & WAYGEAR_BIT(WAYGEAR_HOOK))) {
        stamp_pocket(BGT_GATE_WATER);
        pickup_spawn_waygear(WAYGEAR_HOOK, FIX8(120), FIX8(40));
    } else if (screen == 16) {
        stamp_pocket(BGT_GATE_THORNS);
        pickup_spawn_wayfarer(0, FIX8(120), FIX8(40));
    } else if (screen == 23) {
        stamp_pocket(BGT_GATE_VENT);
        pickup_spawn_wayfarer(4, FIX8(120), FIX8(40));
    } else if (screen == 32) {
        stamp_pocket(BGT_GATE_CHASM);
        pickup_spawn_wayfarer(2, FIX8(120), FIX8(40));
    }
}
