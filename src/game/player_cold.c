#pragma bank 13

#include "core/types.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/will.h"
#include "content.h"

// Field-only leaves called by the always-mapped construction wrappers. They
// deliberately call no other routines: nested far calls during boot/reset can
// otherwise leave the cartridge's mapped bank different from the caller's.
void player_clear_fields(void) BANKED {
    u8 i;
    player.class_id = 0xFF;
    player.hp_max = player.hp = 0;
    player.mp_max = player.mp = 0;
    player.atk = player.def = player.spd = player.lck = 0;
    player.x = player.y = 0;
    player.facing = FACE_S;
    player.anim_frame = 0;
    player.iframes = 0;
    player.coins = 0;
    player.active_item    = 0xFF;
    player.active_charge  = 0;
    player.shield_timer   = 0;
    player.starter_weapon = 0xFF;
    player.fire_cooldown  = 0;
    player.move_acc       = 0;
    room_transform_ticks  = 0;
    room_weapon_surge_ticks = 0;
    g_player_ricochet = 0;
    g_player_attack_traits = 0;
    for (i = 0; i < INVENTORY_SLOTS; ++i) player.inventory[i] = 0xFF;
    player.score_lo = player.score_hi = 0;
    player.will_charge = 0;
    will_corvin_mark_slot = 0xFF;
    will_corvin_mark_ticks = 0;
    will_howl_giant_hits = 0;
    will_vespine_swarm_ticks = 0;
    player.active_oath = 0;
    player.waygear_owned = 0;
    player.waygear_equipped = 0xFF;
    player.curse_flags = 0;
    player.curse_rooms = 0;
}

void player_apply_class(u8 class_id) BANKED {
    const class_def_t *c = &classes[class_id];
    player.class_id = c->id;
    player.hp_max   = c->base_stats.hp_max;
    player.hp       = c->base_stats.hp_max;
    player.mp_max   = c->base_stats.mp_max;
    player.mp       = c->base_stats.mp_max;
    player.atk      = c->base_stats.atk;
    player.def      = c->base_stats.def;
    player.spd      = c->base_stats.spd;
    player.lck      = 0;
    player.starter_weapon = (u8)c->starter_weapon;
    player.active_item    = (u8)c->signature_active;

    // Stat-shaped passives apply at init; behavioral ones (Corvin's
    // HP-sight, Picsean's fast MP, Vespine's poison synergy) are keyed off
    // passive_perk/class at their point of effect.
    switch (c->passive_perk) {
        case 1:   // Wolfkin: +20% move speed
            if (player.spd < 9) player.spd++;
            break;
        // case 2 (Sauran HP+2/slow regen): the +2 is pre-baked into his
        // 16-half-heart base; the regen half ticks in room.c.
    }
}
