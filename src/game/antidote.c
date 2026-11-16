#pragma bank 17

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/antidote.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/run_state.h"
#include "game/status.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

u8 antidote_count(void) BANKED {
    u8 i, n = 0;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == ITEM_ID_ANTIDOTE) n++;
    return n;
}

static u8 free_slot(void) {
    u8 i;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == 0xFF) return i;
    return 0xFF;
}

u8 antidote_can_carry(void) BANKED {
    return antidote_count() < ANTIDOTE_CARRY_MAX && free_slot() != 0xFF;
}

u8 antidote_grant(void) BANKED {
    u8 slot;
    if (antidote_count() >= ANTIDOTE_CARRY_MAX) return 0;
    slot = free_slot();
    if (slot == 0xFF) return 0;
    player.inventory[slot] = ITEM_ID_ANTIDOTE;
    return 1;
}

void antidote_cure(void) BANKED {
    status_player_cure();
    hud_show_cured();
    sfx_play_reward(SFX_REWARD_MAGIC);
}

u8 antidote_try_rescue(void) BANKED {
    u8 i;
    if (!STATUS_PLAYER_DOT()) return 0;
    for (i = 0; i < INVENTORY_SLOTS; ++i) {
        if (player.inventory[i] == ITEM_ID_ANTIDOTE) {
            player.inventory[i] = 0xFF;
            antidote_cure();
            return 1;
        }
    }
    return 0;
}

u8 antidote_collect(u8 bought) BANKED {
    if (!antidote_grant()) return 0;
    hud_show_word(NW_CURE1);
    if (!bought) sfx_play_reward(SFX_REWARD_RELIC);
    else if (STATUS_PLAYER_DOT()) antidote_try_rescue();
    return 1;
}

u8 antidote_spawn(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_ANTIDOTE, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_ITEM_ANTIDOTE;
        entities[idx].palette = ANTIDOTE_ICON_PROP; // green vial, bank 1
        // 0xB1 is pickup_update's "never expires" reward mark: a cure
        // must not vanish before the poisoned champion reaches it.
        entities[idx].ai_data[5] = 0xB1;
    }
    return idx;
}

u8 antidote_try_drop(u8 eid, fix8_t x, fix8_t y) BANKED {
    u8 roll;
    u8 source = (eid == ENEMY_MIRE_SPORE || eid == ENEMY_BRAMBLE_SPRITE);
    u8 rescue = (STATUS_PLAYER_DOT() && !antidote_count());
    if ((!source && !rescue) || !antidote_can_carry()) return 0;
    roll = (u8)((u8)run_state_enemies_killed_total() + (u8)run_state.run_seed);
    // One in four poison-source kills; one in eight other kills while
    // poisoned, burning or bleeding with an empty pouch.
    if (roll & (source ? 3 : 7)) return 0;
    return antidote_spawn(x, y) != 0xFF;
}
