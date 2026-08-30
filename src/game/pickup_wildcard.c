#pragma bank 13

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/curse.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/pickup.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

static u8 wildcard_add_capped(u8 value, u8 delta, u8 cap) {
    if (value >= cap || delta >= (u8)(cap - value)) return cap;
    return (u8)(value + delta);
}

void pickup_spawn_wildcard(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_WILDCARD, x, y);
    if (idx != 0xFF) {
        entity_t *e = &entities[idx];
        e->sprite_tile = SPR_SURGE_ORB;
        e->palette = 0x06;
        e->hitbox = 0x88;
        e->state_timer = 255;
        e->state = (u8)(rng_next_u8() & 31);
    }
}

void pickup_roll_drop(fix8_t x, fix8_t y) BANKED {
    u8 r = rng_next_u8();
    if (RUN_IS_EASY()) {
        if (r < 72) pickup_spawn(PICKUP_HEART_HALF, x, y);
        else if (r < 179) pickup_spawn(PICKUP_COIN_1, x, y);
        else if (r < 187) pickup_spawn_item((u8)(10 + rng_range(10)), x, y);
        else if (r < 207) pickup_spawn_surge(x, y);
        else if (r < 212) pickup_spawn_wildcard(x, y);
    } else {
        if (r < 46) pickup_spawn(PICKUP_HEART_HALF, x, y);
        else if (r < 161) pickup_spawn(PICKUP_COIN_1, x, y);
        else if (r < 166) pickup_spawn_item((u8)(10 + rng_range(10)), x, y);
        else if (r < 181) pickup_spawn_surge(x, y);
        else if (r < 191) pickup_spawn_wildcard(x, y);
    }
}

void pickup_resolve_wildcard(void) BANKED {
    u8 fate = (u8)rng_range(8);
    if (fate == 0) {
        u8 before = player.atk;
        player.atk = wildcard_add_capped(player.atk, 1, 15);
        if (player.atk != before) hud_show_stat_gain(STAT_ATK, 1);
        else {
            player.coins = (u16)(player.coins + 15);
            if (player.coins > COIN_CAP) player.coins = COIN_CAP;
            hud_redraw_coins();
        }
        sfx_play_reward(SFX_REWARD_RELIC);
    } else if (fate == 1) {
        curse_cleanse();
        player.hp = player.hp_max;
        player.mp = player.mp_max;
        hud_redraw_all();
        sfx_play_reward(SFX_REWARD_MAGIC);
    } else if (fate == 2) {
        player.coins = (u16)(player.coins + 25);
        if (player.coins > COIN_CAP) player.coins = COIN_CAP;
        hud_redraw_coins();
        sfx_play_reward(SFX_REWARD_PURCHASE);
    } else if (fate == 3) {
        if (player.curse_flags) curse_cleanse();
        else {
            u8 before = player.lck;
            player.lck = wildcard_add_capped(player.lck, 1, 10);
            hud_show_stat_gain(STAT_LCK, (u8)(player.lck - before));
            sfx_play_reward(SFX_REWARD_RELIC);
        }
    } else if (fate == 4) curse_apply(CURSE_FRAIL, 0, 0);
    else if (fate == 5) curse_apply(CURSE_MISFORTUNE, 0, 0);
    else if (fate == 6) curse_apply(CURSE_DULL, 6, 0);
    else curse_apply(CURSE_HUNGER, 6, 0);
}
