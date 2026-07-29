#pragma bank 7

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/class_palettes.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

u8 room_appearance_tier;
static u8 room_appearance_weapon = 0xFF;

static u8 progression_tier(void) {
    u8 i;
    u8 relics = 0;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] != 0xFF) relics++;
    if (run_state.bosses_beaten >= 6 || relics >= 6) return 3;
    if (run_state.bosses_beaten >= 3 || relics >= 3) return 2;
    if (run_state.bosses_beaten >= 1 || relics >= 1) return 1;
    return 0;
}

static u8 weapon_palette_kind(void) {
    u16 id = player.starter_weapon < N_ITEMS
        ? items[player.starter_weapon].id : 0;
    if (id == 30u) return 2; // Rift Flail
    if (id == 31u) return 3; // Astral Spear
    if (id == 0u || id == 1u || id == 4u) return 1;
    return 0;
}

void room_refresh_player_appearance(u8 celebrate) BANKED {
    u8 tier = progression_tier();
    u8 weapon_changed = room_appearance_weapon != player.starter_weapon;
    u8 tier_changed = room_appearance_tier != tier;
    u8 class_id = player.class_id < 5 ? player.class_id : 0;
    room_appearance_tier = tier;
    room_appearance_weapon = player.starter_weapon;
    palette_obj_load(1, tier
        ? class_obj_upgrade_palettes[class_id][tier - 1]
        : class_obj_palettes[class_id]);
    palette_obj_load(2, weapon_obj_palettes[weapon_palette_kind()]);
    tiles_load_weapon_sprite(player.starter_weapon);
    tiles_load_shield_sprite(class_id);
    if (celebrate && (tier_changed || weapon_changed)) {
        fx_spawn(SPR_FX_IMPACT, 0x06,
            (i16)player.x - 3, (i16)player.y - 3, 14);
        fx_spawn(SPR_FX_IMPACT, 0x06,
            (i16)player.x + 11, (i16)player.y + 9, 18);
        sfx_play_equip();
    }
}

void room_spawn_shield_aura(void) BANKED {
    u8 radius = (u8)((player.class_id == 3 ? 14 : 10)
        + (room_appearance_tier << 1));
    fx_spawn(SPR_SHIELD_AURA, 1,
        (i16)player.x + 4
            + ((player.shield_timer & 8) ? radius : -(i16)radius),
        (i16)player.y + 4
            + ((player.shield_timer & 16) ? radius : -(i16)radius),
        8);
}
