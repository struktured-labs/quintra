#pragma bank 25

// Random 10-orb (items 10..19) selection with diminishing ATK/SPD/LCK
// weights. One rng_next_u8(), same call count as the old 10+rng_range(10).
// See docs/superpowers/specs/2026-11-17-stat-drop-tune.md.

#include <gb/gb.h>

#include "content.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/run_state.h"

#define W_FULL 4
#define W_MID  2
#define W_HIGH 1
#define ATK_MID 2
#define ATK_HIGH 5
#define SPD_EARNED_MID 1
#define SPD_ABS_HIGH 8
#define LCK_HIGH 6

// Iron Heart, Tough Skin, Lucky Coin, Mana Gem, Ward Charm. No stacking
// ATK/SPD, and Hunter's Eye stays off this list so LCK cannot cap mid-run
// from boons alone.
static const u8 boon_pool[5] = { 10, 13, 14, 15, 16 };

static void stat_raised(u8 *atk_r, u8 *spd_r) {
    u8 id = player.class_id < 5 ? player.class_id : 0;
    u8 base_atk = classes[id].base_stats.atk;
    u8 base_spd = classes[id].base_stats.spd;
    // Wolfkin's +1 SPD perk is part of the starting line, not earned.
    if (id == 0 && base_spd < PLAYER_SPD_MAX) base_spd++;
    if (RUN_IS_EASY()) base_atk = (u8)(base_atk + EASY_ATK_BONUS);
    *atk_r = (player.atk > base_atk) ? (u8)(player.atk - base_atk) : 0;
    *spd_r = (player.spd > base_spd) ? (u8)(player.spd - base_spd) : 0;
}

u8 pickup_map_stat_relic(u8 r) BANKED {
    u8 w[10];
    u8 i, atk_r, spd_r, atk_w, spd_w, lck_w;
    u16 total, slot, acc;

    stat_raised(&atk_r, &spd_r);
    atk_w = (atk_r >= ATK_HIGH) ? W_HIGH : (atk_r >= ATK_MID) ? W_MID : W_FULL;
    spd_w = (player.spd >= SPD_ABS_HIGH) ? W_HIGH
        : (spd_r >= SPD_EARNED_MID) ? W_MID : W_FULL;
    lck_w = (player.lck >= LCK_HIGH) ? W_HIGH : W_FULL;

    for (i = 0; i < 10; ++i) w[i] = W_FULL;
    w[1] = spd_w;              /* Speed Ring */
    w[2] = atk_w;              /* Power Stone */
    w[4] = lck_w;              /* Lucky Coin */
    w[8] = lck_w;              /* Hunter's Eye */
    w[9] = atk_w;              /* Blood Sigil */
    /* Swift Fang grants ATK and SPD; drop it entirely once either line is
       in the high taper so residual random ATK/SPD does not stay at 3/N. */
    w[7] = (atk_w <= W_HIGH || spd_w <= W_HIGH) ? 0
        : ((atk_w < spd_w) ? atk_w : spd_w);

    total = 0;
    for (i = 0; i < 10; ++i) total = (u16)(total + w[i]);
    /* Fast path: identical to the historical 10 + (rng_next_u8() % 10). */
    if (total == 40) return (u8)(10 + (r % 10));

    /* Map 0..255 onto 0..total-1 without an 8-bit software modulo. */
    slot = (u16)(((u16)r * total) >> 8);
    acc = 0;
    for (i = 0; i < 10; ++i) {
        acc = (u16)(acc + w[i]);
        if (slot < acc) return (u8)(10 + i);
    }
    return 10;
}

u8 pickup_roll_stat_relic(void) BANKED {
    return pickup_map_stat_relic(rng_next_u8());
}

u8 pickup_boon_relic(u8 roll) BANKED {
    while (roll >= 5) roll = (u8)(roll - 5);
    return boon_pool[roll];
}
