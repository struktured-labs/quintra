#pragma bank 17
// Water traversal is a real ability (Tide Raft waygear or Picsean's innate
// swim, see WAYGEAR_TILE_PASSABLE), but it used to draw the champion simply
// walking across the water. While the champion's feet are over water this
// draws either a bobbing log raft with a foam wake under them or, for the
// Picsean, a swim pose: the torso sinks into a ripple ring that replaces the
// legs. Visual only; collision, speed and save state are unchanged.

#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/room.h"
#include "game/water_ride.h"
#include "game/waygear.h"
#include "render/tiles.h"

#define PICSEAN_CLASS 3
#define RAFT_PALETTE  5     // coin gold/brown/cream
#define OBJ_VRAM_BANK1 0x08

u8 water_ride_mode;

static u8 feet_on_water(void) {
    u8 t = room_tile_at_px((i16)player.x + 8, (i16)player.y + 12);
    return t == BGT_WILD_WATER || t == BGT_GATE_WATER;
}

void water_ride_hide(void) BANKED {
    if (water_ride_mode == WATER_RIDE_RAFT) {
        move_sprite(WATER_RIDE_OAM, 0, 0);
        move_sprite(WATER_RIDE_OAM + 1, 0, 0);
        move_sprite(WATER_RIDE_OAM + 2, 0, 0);
    }
    water_ride_mode = WATER_RIDE_NONE;
}

// Runs after the champion's OAM 0..3 were written for this frame. Idempotent:
// the compact-room draw calls it again after the entity pass so the raft keeps
// its slots in crowded rooms (entities rotate through the rest).
void water_ride_place(void) BANKED {
    u8 mode = WATER_RIDE_NONE;
    u8 sx, sy, beat, bob;
    OAM_item_t *it;
    // Hot path: this runs every frame. Only a Picsean or a Tide Raft owner
    // can ever stand on water, so everyone else skips the tile probe.
    if (player.class_id != PICSEAN_CLASS
        && !(player.waygear_owned & WAYGEAR_BIT(WAYGEAR_RAFT))) {
        if (water_ride_mode) water_ride_hide();
        return;
    }
    if (player.hp && feet_on_water())
        mode = player.class_id == PICSEAN_CLASS
            ? WATER_RIDE_SWIM : WATER_RIDE_RAFT;
    if (mode != water_ride_mode) {
        water_ride_hide();
        if (mode == WATER_RIDE_NONE) return;
        // Re-upload on every entry: 160 bytes, once per stretch of water,
        // and immune to any screen that reused bank-1 OBJ VRAM meanwhile.
        water_ride_load_tiles();
        water_ride_mode = mode;
    }
    if (mode == WATER_RIDE_NONE) return;
    sx = (u8)((i16)player.x - room_camera_x + 8);
    sy = (u8)((i16)player.y - room_camera_y + 16);
    beat = (u8)((entity_anim_counter >> 3) & 1);
    bob = (u8)((entity_anim_counter >> 4) & 1);
    if (mode == WATER_RIDE_SWIM) {
        u8 prop;
        // Damage flicker hides OAM 0 by parking it; keep the swimmer hidden.
        if (shadow_OAM[0].y == 0) return;
        prop = (u8)((shadow_OAM[0].prop & 0x07) | OBJ_VRAM_BANK1);
        it = &shadow_OAM[0];
        it[0].y = it[1].y = (u8)(sy + 3 + bob);
        it[2].y = it[3].y = (u8)(sy + 9);
        it[2].x = sx; it[3].x = (u8)(sx + 8);
        it[2].tile = (u8)(beat ? WATER_RIDE_SWIM_B : WATER_RIDE_SWIM_A);
        it[3].tile = (u8)(it[2].tile + 1);
        it[2].prop = it[3].prop = prop;
        return;
    }
    // Raft: OAM 36..38 have a higher index than the champion, so the hero
    // stands on top of it; the raft rides 1px up and down on the swell.
    {
        u8 tile = (u8)(beat ? WATER_RIDE_RAFT_B : WATER_RIDE_RAFT_A);
        u8 y = (u8)(sy + 11 + bob);
        it = &shadow_OAM[WATER_RIDE_OAM];
        it[0].y = it[1].y = it[2].y = y;
        it[0].x = (u8)(sx - 4);
        it[1].x = (u8)(sx + 4);
        it[2].x = (u8)(sx + 12);
        it[0].tile = tile;
        it[1].tile = (u8)(tile + 1);
        it[2].tile = (u8)(tile + 2);
        it[0].prop = it[1].prop = it[2].prop =
            (u8)(RAFT_PALETTE | OBJ_VRAM_BANK1);
    }
}
