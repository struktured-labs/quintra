#pragma bank 10

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/waygear.h"
#include "game/will.h"
#include "render/tiles.h"

u8 waygear_grant(u8 gear) BANKED {
    u8 bit;
    u8 was_full = player.will_level >= WILL_LEVEL_CAP;
    if (gear >= WAYGEAR_COUNT) return 0;
    bit = WAYGEAR_BIT(gear);
    if (player.waygear_owned & bit) return 0;
    player.waygear_owned |= bit;
    if (gear < WAYGEAR_EQUIP_COUNT && was_full)
        player.will_charge = 0;
    // Retain the legacy slot only as the initial Pack cursor.
    if (gear < WAYGEAR_EQUIP_COUNT) player.waygear_equipped = gear;
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

void waygear_prepare_world_field(void) BANKED {
    u8 screen;
    u8 gear;
    if (!run_state.world_mode) return;
    screen = run_state.world_screen;

    // Each permanent implement now appears only after its far-flung regional
    // Warden is defeated. If the player leaves without touching the drop,
    // regenerate it on the cleared pedestal rather than losing progression.
    gear = run_state_riftwild_guard_gear(screen);
    if (gear < WAYGEAR_EQUIP_COUNT) {
        stamp_pocket((u8)(BGT_GATE_BOULDER + gear));
        if (run_state_riftwild_guard_cleared(screen)
            && !(player.waygear_owned & WAYGEAR_BIT(gear)))
            pickup_spawn_waygear(gear, FIX8(120), FIX8(72));
        pickup_spawn_wayfarer(gear == 0 ? 1 : gear == 1 ? 3 : 2,
            FIX8(120), FIX8(40));
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

    // Worldglass waits beside the first awakened arch the champion reaches.
    // If ignored, every later active arch restores it, so the world-shift
    // verb cannot be permanently lost to a missed field pickup.
    if (!RUN_RIFTWILD_IS_HOLLOW()
        && run_state_riftwild_gate_active(screen)
        && !(player.waygear_owned & WAYGEAR_BIT(WAYGEAR_WORLDGLASS)))
        pickup_spawn_waygear(WAYGEAR_WORLDGLASS, FIX8(120), FIX8(40));
}
