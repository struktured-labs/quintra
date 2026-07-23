#include <string.h>

#include "core/types.h"
#include "game/player.h"
#include "game/room.h"
#include "content.h"

player_state_t player;

void player_clear(void) {
    u8 i;
    // Passive clocks are gameplay progress within one run, never hidden
    // carryover from the previous champion/death screen.
    room_reset_passive_timers();
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
    for (i = 0; i < INVENTORY_SLOTS; ++i) player.inventory[i] = 0xFF;
    player.score_lo = player.score_hi = 0;
}

void player_init_from_class(u8 class_id) {
    player_clear();
    if (class_id >= N_CLASSES) return;

    {
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
        // HP-sight, Picsean's fast MP, Vespine's poison synergy) are
        // keyed off passive_perk/class at their point of effect.
        switch (c->passive_perk) {
            case 1:   // Wolfkin: +20% move speed
                if (player.spd < 9) player.spd++;
                break;
            // case 2 (Sauran HP+2/slow regen): the +2 is pre-baked into
            // his 16-half-heart base; the regen half ticks in room.c.
        }
    }
}

// Starter cadence is authored as the no-upgrade baseline. SPD earned during
// the run removes two frames per point, with a six-frame floor so turbo fire
// stays controllable and attack-speed relics have an obvious payoff.
u8 player_fire_delay(u8 base) BANKED {
    u8 start_spd;
    u8 haste;
    if (player.class_id >= N_CLASSES) return base;
    start_spd = classes[player.class_id].base_stats.spd;
    haste = (player.spd > start_spd) ? (u8)(player.spd - start_spd) : 0;
    haste = (u8)(haste << 1);
    return (base > (u8)(haste + 6)) ? (u8)(base - haste) : 6;
}
