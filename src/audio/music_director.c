#pragma bank 10

#include <gb/gb.h>

#include "audio/music.h"
#include "audio/music_director.h"
#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/run_state.h"
#include "content.h"

u8 music_mix_lead_envelope;
u8 music_mix_harmony_mask;
u8 music_mix_harmony_envelope;
u8 music_mix_wave_level;

static void refresh_targets(void) {
    u8 i, visible = 0, nearby = 0, merchant = 0, miniboss = 0;
    u8 relic = 0;
    u8 stage = run_state.bosses_beaten;
    u8 hero_force, baseline;
    u16 hp4 = (u16)player.hp * 4u;
    u16 max4 = (u16)player.hp_max * 4u;

    if (player.hp == 0 || player.hp_max == 0) music_health_target = 3;
    else if (hp4 <= (u16)player.hp_max) music_health_target = 3;
    else if ((u16)player.hp * 2u <= (u16)player.hp_max)
        music_health_target = 2;
    else if (hp4 <= (u16)(max4 - player.hp_max)) music_health_target = 1;
    else music_health_target = 0;

    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        if (!(e->flags & EF_ACTIVE)) continue;
        if (e->type == ENT_PICKUP && e->ai_data[0] == PICKUP_MERCHANT)
            merchant = 1;
        if (e->type == ENT_PICKUP
            && (e->ai_data[0] == PICKUP_RIFT_SIGIL
                || e->ai_data[0] == PICKUP_FARFOLD_RELIC
                || e->ai_data[0] == PICKUP_BOON_CHOICE
                || e->ai_data[0] == PICKUP_WEAPON)) {
            i16 dx = FIX8_TO_INT(e->x) - (i16)player.x;
            i16 dy = FIX8_TO_INT(e->y) - (i16)player.y;
            if (dx < 0) dx = -dx;
            if (dy < 0) dy = -dy;
            if (dx <= 40 && dy <= 32) relic = 2;
            else if (!relic && dx <= 80 && dy <= 64) relic = 1;
        }
        if (e->type != ENT_ENEMY || !(e->flags & EF_ON_SCREEN)) continue;
        visible++;
        {
            i16 dx = FIX8_TO_INT(e->x) - (i16)player.x;
            i16 dy = FIX8_TO_INT(e->y) - (i16)player.y;
            if (dx < 0) dx = -dx;
            if (dy < 0) dy = -dy;
            if (dx <= 48 && dy <= 40) nearby++;
        }
        if ((e->ai_data[0] == ENEMY_STONE_SENTINEL && !e->ai_data[3])
            || (e->flags & EF_ELITE)) miniboss = 1;
    }

    if (visible == 0) music_threat_target = 0;
    else if (nearby >= 5 || visible >= 10) music_threat_target = 3;
    else if (nearby >= 2 || visible >= 6) music_threat_target = 2;
    else music_threat_target = 1;

    if (miniboss) music_context_target = MUSIC_CONTEXT_MINIBOSS;
    else if (merchant || run_state_is_shop())
        music_context_target = MUSIC_CONTEXT_MERCHANT;
    else if (run_state_is_sanctuary()
        || RUN_ROOM_IS_TOWN(run_state.room_counter))
        music_context_target = MUSIC_CONTEXT_SANCTUARY;
    else music_context_target = MUSIC_CONTEXT_EXPLORE;
    // The relic voice is a discovery layer, not permission to soften a live
    // elite encounter. Miniboss rhythm owns CH1 until the room is safe.
    music_relic_target = miniboss ? 0 : relic;

    if (stage >= MUSIC_STAGE_COUNT) stage = MUSIC_STAGE_COUNT - 1;
    hero_force = (u8)(player.atk * 2u + player.def + player.spd);
    baseline = (u8)(classes[player.class_id < 5 ? player.class_id : 0]
        .base_stats.atk * 2u
        + classes[player.class_id < 5 ? player.class_id : 0].base_stats.def
        + classes[player.class_id < 5 ? player.class_id : 0].base_stats.spd
        + 3u + (stage >> 1));
    music_power_target = hero_force >= baseline ? 1 : 0;
}

void music_director_refresh(void) BANKED {
    refresh_targets();
}

void music_adaptive_prepare_section(u8 base, u8 base_wave,
    u8 form, u8 boss) BANKED {
    u8 volume = base & 0xF0;
    refresh_targets();
    music_health_tier = music_health_target;
    music_threat_tier = music_threat_target;
    music_context = music_context_target;
    music_power_tier = music_power_target;
    music_relic_tier = music_relic_target;

    if (form < 2) {
        if (volume >= 0x30) volume -= 0x20;
    } else if (form == 12) {
        if (volume >= 0x40) volume -= 0x30;
    } else if (form < 16) {
        if (volume >= 0x20) volume -= 0x10;
    } else if (form >= 28 && volume < 0xF0) volume += 0x10;
    if (music_context == MUSIC_CONTEXT_SANCTUARY && volume >= 0x20)
        volume -= 0x20;
    else if (music_context == MUSIC_CONTEXT_MERCHANT && volume >= 0x10)
        volume -= 0x10;
    if (music_health_tier >= 2 && volume >= 0x10) volume -= 0x10;
    if (music_threat_tier >= 2 && volume < 0xF0) volume += 0x10;
    if (music_power_tier && volume < 0xF0) volume += 0x10;
    music_mix_lead_envelope = volume | (base & 0x0F);

    if (form == 12) music_mix_wave_level = 0;
    else if (music_context == MUSIC_CONTEXT_SANCTUARY
        || music_context == MUSIC_CONTEXT_MERCHANT) music_mix_wave_level = 0x60;
    else if (music_context == MUSIC_CONTEXT_MINIBOSS
        || music_threat_tier >= 3 || music_power_tier)
        music_mix_wave_level = 0x20;
    else if (form < 2 || form == 13) music_mix_wave_level = 0x60;
    else if (form >= 28) music_mix_wave_level = 0x20;
    else music_mix_wave_level = base_wave;

    if (music_relic_tier >= 2) music_mix_harmony_mask = 0xAA;
    else if (music_relic_tier) music_mix_harmony_mask = 0x44;
    else if (music_context == MUSIC_CONTEXT_SANCTUARY)
        music_mix_harmony_mask = 0x40;
    else if (music_context == MUSIC_CONTEXT_MERCHANT)
        music_mix_harmony_mask = 0x44;
    else if (music_context == MUSIC_CONTEXT_MINIBOSS
        || music_threat_tier >= 3) music_mix_harmony_mask = 0xEE;
    else if (music_threat_tier >= 2) music_mix_harmony_mask = 0xAA;
    else if (form < 2) music_mix_harmony_mask = 0x04;
    else if (boss) music_mix_harmony_mask = 0xAA;
    else music_mix_harmony_mask = 0x44;

    music_mix_harmony_envelope =
        (boss || music_context == MUSIC_CONTEXT_MINIBOSS)
        ? 0x72 : music_context == MUSIC_CONTEXT_SANCTUARY ? 0x32 : 0x42;
    if (music_relic_tier)
        music_mix_harmony_envelope = music_relic_tier >= 2 ? 0x55 : 0x35;
    if (music_power_tier && music_mix_harmony_envelope < 0xE2)
        music_mix_harmony_envelope += 0x20;
    if (form < 2) music_mix_harmony_envelope = 0x32;
    else if (form >= 28) music_mix_harmony_envelope += 0x20;
}
