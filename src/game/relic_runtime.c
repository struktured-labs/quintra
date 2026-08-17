#pragma bank 2

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

// Echo rhythm persists through doors, giving the fourth deliberate primary
// attack a stable run-wide cadence without expanding suspend-save state.
static u8 echo_attack_count;

// Cold inventory reconciliation belongs with the other relic bookkeeping,
// not in projectile bank 3's dense-update budget.
void projectile_sync_player_relics(void) BANKED {
    u8 i;
    g_player_ricochet = 0;
    g_player_attack_traits = 0;
    for (i = 0; i < INVENTORY_SLOTS; ++i) {
        u8 id = player.inventory[i];
        if (id == ITEM_ID_RICOCHET_RUNE) g_player_ricochet = 1;
        else if (id == ITEM_ID_POWER_STONE)
            g_player_attack_traits |= ATTACK_TRAIT_POWER;
        else if (id == ITEM_ID_SWIFT_FANG)
            g_player_attack_traits |= ATTACK_TRAIT_SWIFT;
        else if (id == ITEM_ID_BLOOD_SIGIL)
            g_player_attack_traits |= ATTACK_TRAIT_BLOOD;
    }
}

static u8 has_item(u8 item_id) {
    u8 i;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == item_id) return 1;
    return 0;
}

void pickup_echo_primary(u8 dir, u8 damage, u8 kind) BANKED {
    u8 echo_damage;
    if (!has_item(ITEM_ID_ECHO_PRISM)) return;
    if (++echo_attack_count < 4) return;
    echo_attack_count = 0;
    echo_damage = (u8)((damage + 1) >> 1);
    if (echo_damage == 0) echo_damage = 1;
    projectile_spawn_player(dir8_dx[(u8)((dir + 1) & 7)],
        dir8_dy[(u8)((dir + 1) & 7)], echo_damage, kind);
    projectile_spawn_player(dir8_dx[(u8)((dir + 7) & 7)],
        dir8_dy[(u8)((dir + 7) & 7)], echo_damage, kind);
    room_shake(1, 5);
}
