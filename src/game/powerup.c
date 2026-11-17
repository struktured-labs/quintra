#pragma bank 20

// Pinned to bank 20: banks 1..19 sit at their 256-byte floors and autobank
// would otherwise land this file in bank 2.
// Temporary power-ups, Phase 1: framework + AEGIS, LIMITLESS, MEND.
// See docs/superpowers/specs/2026-11-16-temporary-powerups.md.
// All hot-path hooks test one WRAM byte before far-calling into this bank.

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/powerup.h"
#include "game/procgen.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "game/will.h"
#include "game/oath_arts.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

void status_effect(u8 kind, u8 palette, i16 x, i16 y) BANKED;

u8 powerup_id;
u8 powerup_ticks;
u8 powerup_aegis_hits;
static u8 powerup_clock;
static u8 powerup_aux;
static u8 powerup_flags;
static u8 powerup_last_mp;
#define PF_BOSS_CLIPPED 0x01

// Normal durations in beats (8 frames): 12 s, 15 s, 12 s.
static const u8 pu_duration[POWERUP_COUNT] = { 0, 90, 112, 90 };
// Colossus / mini-boss rooms clip (never extend) on entry.
static const u8 pu_boss_duration[POWERUP_COUNT] = { 0, 60, 75, 90 };
static const u8 pu_tile[POWERUP_COUNT] = {
    0, SPR_ITEM_WARD_CHARM, SPR_ITEM_MANA_GEM, SPR_HEART
};
// OBJ palettes: 1 ward/aura, 6 rift violet (MP), 7 green (regen).
static const u8 pu_pal[POWERUP_COUNT] = { 0, 0x01, 0x06, 0x07 };
static const u8 pu_name[POWERUP_COUNT] = { 0, NW_AEGIS, NW_LIMIT, NW_MEND };
static const u8 pu_effect[POWERUP_COUNT] = { 0, NW_BLOCK3, NW_FREEMP, NW_REGEN };
static const u8 pu_hud_icon[POWERUP_COUNT] = {
    0, HUD_OFFER_VITAL, HUD_OFFER_RUNE, HUD_OFFER_HEAL
};

void powerup_reset(void) BANKED {
    powerup_id = POWERUP_NONE;
    powerup_ticks = 0;
    powerup_aegis_hits = 0;
    powerup_clock = 0;
    powerup_aux = 0;
    powerup_flags = 0;
}

u8 powerup_spawn(u8 id, fix8_t x, fix8_t y) BANKED {
    u8 idx;
    if (id == POWERUP_NONE || id >= POWERUP_COUNT) return 0xFF;
    idx = pickup_spawn(PICKUP_POWERUP, x, y);
    if (idx != 0xFF) {
        entity_t *e = &entities[idx];
        e->ai_data[1] = id;
        e->sprite_tile = pu_tile[id];
        e->palette = pu_pal[id];
        e->hitbox = 0x88;
        e->state_timer = 255;   // lingers like a relic (~4 s)
    }
    return idx;
}

static void powerup_roll_capsule(fix8_t x, fix8_t y) {
    u8 i;
    if (procgen_current_room_is_boss) return;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_PICKUP
            && entities[i].ai_data[0] == PICKUP_POWERUP) return;
    powerup_spawn((u8)(1 + rng_range(POWERUP_COUNT - 1)), x, y);
}

// RNG-driven enemy-death drop (moved here from pickup_wildcard.c, whose
// bank 13 sits at its emergency floor). Bands are unchanged except that a
// Capsule takes 3% (Easy ~4%) from the former "nothing" share.
void pickup_roll_drop(fix8_t x, fix8_t y) BANKED {
    u8 r = rng_next_u8();
    if (RUN_IS_EASY()) {
        if (r < 72) pickup_spawn(PICKUP_HEART_HALF, x, y);
        else if (r < 179) pickup_spawn(PICKUP_COIN_1, x, y);
        else if (r < 187) pickup_spawn_item((u8)(10 + rng_range(10)), x, y);
        else if (r < 207) pickup_spawn_surge(x, y);
        else if (r < 212) pickup_spawn_wildcard(x, y);
        else if (r < 222) powerup_roll_capsule(x, y);
    } else {
        if (r < 31) pickup_spawn(PICKUP_HEART_HALF, x, y);
        else if (r < 146) pickup_spawn(PICKUP_COIN_1, x, y);
        else if (r < 151) pickup_spawn_item((u8)(10 + rng_range(10)), x, y);
        else if (r < 166) pickup_spawn_surge(x, y);
        else if (r < 176) pickup_spawn_wildcard(x, y);
        else if (r < 184) powerup_roll_capsule(x, y);
    }
}

static u8 pu_base_duration(u8 id) {
    u8 d = procgen_current_room_is_boss ? pu_boss_duration[id] : pu_duration[id];
    if (RUN_IS_EASY()) d = (u8)(d + (d >> 2));
    return d;
}

static void pu_announce(u8 id) {
    hud_show_word(pu_name[id]);
    hud_show_word(pu_effect[id]);
}

void powerup_collect(u8 id) BANKED {
    u8 base;
    if (id == POWERUP_NONE || id >= POWERUP_COUNT) return;
    base = pu_base_duration(id);
    if (powerup_id == id) {
        // Same power-up again: refresh plus 25%, capped at 1.5x.
        u8 cap = (u8)(base + (base >> 1));
        u16 t = (u16)(powerup_ticks > base ? powerup_ticks : base)
            + (u16)(base >> 2);
        powerup_ticks = (t > cap) ? cap : (u8)t;
    } else {
        powerup_id = id;
        powerup_ticks = base;
        powerup_aux = 0;
        powerup_aegis_hits = 0;
    }
    powerup_flags = procgen_current_room_is_boss ? PF_BOSS_CLIPPED : 0;
    if (id == POWERUP_AEGIS) {
        powerup_aegis_hits = procgen_current_room_is_boss
            ? POWERUP_AEGIS_BOSS_HITS : POWERUP_AEGIS_HITS;
        sfx_play_reward(SFX_REWARD_RELIC);
    } else if (id == POWERUP_LIMITLESS) {
        if (player.mp_max && player.mp == 0) {
            player.mp = 1;
            hud_redraw_mp();
        }
        powerup_last_mp = player.mp;
        if (!player.will_level) {
            player.will_level = 1;
            player.will_charge = 0;
        }
        sfx_play_reward(SFX_REWARD_MAGIC);
    } else {
        sfx_play(SFX_HEART);
    }
    fx_spawn(pu_tile[id], pu_pal[id], (i16)player.x + 4,
        (i16)player.y - 8, 30);
    pu_announce(id);
}

static void pu_end(void) {
    u8 id = powerup_id;
    powerup_id = POWERUP_NONE;
    powerup_ticks = 0;
    powerup_aegis_hits = 0;
    powerup_aux = 0;
    if (id < POWERUP_COUNT && id) {
        hud_show_word(pu_name[id]);
        hud_show_word(NW_ENDED);
    }
    hud_powerup_release();
}

static u8 pu_free_slots(void) {
    u8 i, n = 0;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if (!(entities[i].flags & EF_ACTIVE)) n++;
    return n;
}

void powerup_tick(void) BANKED {
    u8 id = powerup_id;
    if (id == POWERUP_NONE || id >= POWERUP_COUNT) { powerup_reset(); return; }
    if (procgen_current_room_is_boss) {
        if (!(powerup_flags & PF_BOSS_CLIPPED)) {
            powerup_flags |= PF_BOSS_CLIPPED;
            if (powerup_ticks > pu_boss_duration[id])
                powerup_ticks = pu_boss_duration[id];
            if (powerup_aegis_hits > POWERUP_AEGIS_BOSS_HITS)
                powerup_aegis_hits = POWERUP_AEGIS_BOSS_HITS;
        }
    } else powerup_flags &= (u8)~PF_BOSS_CLIPPED;

    powerup_clock++;
    if (id == POWERUP_LIMITLESS) {
        // Oath Arts cost OATH_MP_COST at their call site in room.c (bank 1
        // has no headroom), so refund that spend here on the next frame.
        // Convergence (full MP -> 0, starts the 135-beat transform) is not
        // refunded: full MP stays reserved for it, as without Limitless.
        if (player.mp < powerup_last_mp
            && (u8)(powerup_last_mp - player.mp) <= OATH_MP_COST
            && room_transform_ticks != 135) {
            player.mp = powerup_last_mp;
            hud_redraw_mp();
        }
        powerup_last_mp = player.mp;
    }
    // Aegis: two ward shards orbit the hero (opposite corners, rotating),
    // faster and flickering on the last charge. Skips in a full field so
    // crowded-room spawn floors stay intact.
    if (id == POWERUP_AEGIS && powerup_aegis_hits
        && (powerup_clock & 3) == 0
        && (powerup_aegis_hits > 1 || (powerup_clock & 8))
        && pu_free_slots() > 6) {
        static const i8 ox[4] = { -12, 12, 12, -12 };
        static const i8 oy[4] = { -12, -12, 12, 12 };
        u8 ph = (u8)((powerup_clock >> 2) & 3);
        fx_spawn(SPR_SHIELD_AURA, 1, (i16)player.x + 4 + ox[ph],
            (i16)player.y + 4 + oy[ph], 8);
        fx_spawn(SPR_SHIELD_AURA, 1, (i16)player.x + 4 + ox[(u8)((ph + 2) & 3)],
            (i16)player.y + 4 + oy[(u8)((ph + 2) & 3)], 8);
    } else if (id == POWERUP_LIMITLESS && (powerup_clock & 31) == 0
        && pu_free_slots() > 6) {
        fx_spawn(SPR_FX_IMPACT, 0x06, (i16)player.x + 4,
            (i16)player.y - 10, 10);
    }
    if (powerup_clock & 7) return;

    // ---- one beat ----
    if (powerup_ticks) powerup_ticks--;
    if (id == POWERUP_MEND) {
        u8 period = procgen_current_room_is_boss ? 18 : 12;
        if (++powerup_aux >= period) {
            powerup_aux = 0;
            if (player.hp < player.hp_max && !STATUS_PLAYER_HEALING_BLOCKED()) {
                player.hp++;
                hud_redraw_hp();
                sfx_play(SFX_HEART);
                status_effect(QSTATUS_REGEN, 7, (i16)player.x + 4,
                    (i16)player.y + 2);
            }
        }
    } else if (id == POWERUP_LIMITLESS) {
        // Oath/Bomb costs are skipped at their call sites. Keep one MP
        // showing so an Oath stays castable after a Convergence drain.
        if (player.mp_max && player.mp == 0) {
            player.mp = 1;
            powerup_last_mp = 1;
            hud_redraw_mp();
        }
        // Will banks one MAX charge every two seconds when empty.
        if (++powerup_aux >= 16) {
            powerup_aux = 0;
            if (!player.will_level && !STATUS_PLAYER_MUTED()) {
                player.will_level = 1;
                player.will_charge = 0;
                sfx_play_will();
            }
        }
    }
    // Last three seconds: one soft tick per second.
    if (powerup_ticks && powerup_ticks <= 22
        && (powerup_ticks % 7) == 0) sfx_play(SFX_TICK);
    if (powerup_ticks == 0) pu_end();
}

void powerup_hud(void) BANKED {
    u8 secs;
    if (!powerup_id || powerup_id >= POWERUP_COUNT) return;
    secs = (u8)(((u16)powerup_ticks * 8u + 59u) / 60u);
    hud_show_powerup(pu_hud_icon[powerup_id], secs,
        powerup_id == POWERUP_AEGIS ? powerup_aegis_hits : 0xFF,
        (powerup_ticks <= 22 && (powerup_clock & 16)) ? 1 : 0);
}

u8 powerup_aegis_absorb(u8 hostile_idx) BANKED {
    entity_t *e;
    if (powerup_id != POWERUP_AEGIS || !powerup_aegis_hits
        || hostile_idx >= MAX_ENTITIES) return 0;
    e = &entities[hostile_idx];
    powerup_aegis_hits--;
    if (player.iframes < 30) player.iframes = 30;
    fx_spawn(SPR_SHIELD_AURA, 1, FIX8_TO_INT(e->x), FIX8_TO_INT(e->y), 12);
    if (e->type == ENT_PROJECTILE) entity_kill(hostile_idx);
    room_shake(1, 4);
    sfx_play(SFX_WEAK);
    if (!powerup_aegis_hits) pu_end();
    return 1;
}
