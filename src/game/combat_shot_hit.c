#pragma bank 16
// Cold player-shot damage. The miss scan stays in bank 3 and must not carry
// this frame: SDCC spills every local of the function that contains both.
#include "audio/sfx.h"
#include "game/hexa_boss.h"
#include "audio/boss_voice.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/boss_phase.h"
#include "game/combat.h"
#include "game/dungeon_director.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/rare_enemy.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "game/will.h"
#include "render/tiles.h"
#include "content.h"

u8 combat_defeat_enemy(u8 j, u8 i, u8 weak) BANKED;
u8 status_enemy_effective_poise(u8 idx, u8 poise) BANKED;
u8 status_enemy_hit_damage(u8 idx, u8 damage) BANKED;

static void knockback_enemy(entity_t *e, i8 bvx, i8 bvy, u8 poise) {
    u8 n;
    if (poise >= 3) return;
    {
        i8 kx = (bvx > 0) ? 1 : (bvx < 0) ? -1 : 0;
        i8 ky = (bvy > 0) ? 1 : (bvy < 0) ? -1 : 0;
        for (n = 0; n < 3; ++n) enemy_try_step(e, kx, ky);
    }
}

u8 combat_apply_player_shot_hit(entity_t *shot, u8 i, entity_t *ej,
                                       u8 j, u8 *giant_hits) BANKED {
    u8 eid, weakness, poise, dmg;
    u8 shot_spent_for_split = 0;
    u8 weak;

    eid = ej->ai_data[0];
    if (shot->ai_data[6] == PROJ_AUX_HOOKSHOT
        || shot->ai_data[6] == PROJ_AUX_FUSE_BOMB) return 0;
    if (shot->ai_data[6] == PROJ_AUX_BOOMERANG) {
        if (!(ej->flags & (EF_ELITE | EF_ALPHA | EF_RARE))
            && eid != ENEMY_STONE_SENTINEL
            && eid != ENEMY_STAGE_REAPER
            && ej->ai_data[2] != ENEMY_AUX_BELLWARDEN
            && enemy_status_kind[j] != QSTATUS_STOP) {
            status_enemy_apply(j, QSTATUS_STOP, 14);
        }
        return 0;
    }
    // Keep specialist rejection out of the miss scan's stack frame. The
    // helper is entered only for authored armor, shell, or projection
    // bodies—not every ordinary contact.
    if (eid == ENEMY_FACET_RAM || eid == ENEMY_FOLD_STAR
            || (eid < N_ENEMIES
                && enemies[eid].ai_kind == AI_COUNTER_GUARD)) {
        enemy_special_reject_hit(i, j);
        // Projectile retirement is the authoritative rejection result.
        if (!(shot->flags & EF_ACTIVE)) return 1;
    }
    // Fang Forms is a two-body cleave, not two consecutive damage ticks
    // against one overlapping body. Preserve the projectile so it can
    // strike a different enemy farther down the same lane.
    if (shot->ai_data[6] == PROJ_AUX_WOLFKIN_FANG
        && shot->ai_data[5] == j) return 0;
    if (eid == ENEMY_STONE_SENTINEL && ej->ai_data[3]
        && (shot->ai_data[3] & PROJ_FLAG_CONVERGENCE)) {
        if ((*giant_hits) >= 4) {
            entity_kill(i);
            return 1;
        }
        (*giant_hits)++;
    }
    if (eid == ENEMY_STONE_SENTINEL && ej->ai_data[3]
        && (shot->ai_data[3] & PROJ_FLAG_HOWL)) {
        if (will_howl_giant_hits >= WILL_HOWL_GIANT_HIT_CAP) {
            entity_kill(i);
            return 1;
        }
        will_howl_giant_hits++;
        // Each Howl lane may touch this giant only once. It retains its
        // normal pierce value against separate crowd bodies.
        shot->hp = 1;
    }
    weakness = (eid < N_ENEMIES) ? enemies[eid].stats.weakness : 0;
    // Large bosses reuse the Stone Sentinel definition but must not inherit
    // its lightning-only weakness, and they have no elemental weakness.
    if (eid == ENEMY_STONE_SENTINEL && ej->ai_data[3]) weakness = 0;
    poise = (eid < N_ENEMIES) ? enemies[eid].stats.poise : 0;
    poise = status_enemy_effective_poise(j, poise);

    dmg = shot->damage;
    weak = (shot->ai_data[1] & weakness) ? 1 : 0;
    if (weak) {
        dmg = (u8)(dmg + ((dmg + 1) >> 1));
        if (player.class_id == 4) dmg++;
    }
    if (rng_range(100)
        < (u8)(status_player_effective_stat(QSTATUS_STAT_LCK) * 5))
        dmg = (u8)(dmg << 1);
    if (player.class_id == 2 && will_corvin_mark_ticks
        && j == will_corvin_mark_slot) {
        dmg = (u8)(dmg + WILL_CORVIN_MARK_BONUS);
    }
    if (player.hp <= 2 && player.hp > 0) dmg++;
    if (dmg == 0) dmg = 1;
    dmg = status_enemy_hit_damage(j, dmg);
    if (j == room_encounter_target && room_return_echo_kind >= 4) {
        dmg = dungeon_return_hit_damage(dmg);
        if (!dmg) {
            entity_kill(i);
            return 1;
        }
    }
    if (shot->ai_data[6] == PROJ_AUX_WOLFKIN_FANG)
        shot->ai_data[5] = j;

    if (ej->ai_data[0] == ENEMY_STONE_SENTINEL
        && ej->ai_data[3]
        && ej->ai_data[2] >= 2
        && ej->ai_data[2] <= 8) {
        u8 cap = RUN_IS_EASY() ? 5 : 3;
        if (dmg > cap) dmg = cap;
    }
    if (ej->ai_data[0] == ENEMY_STONE_SENTINEL
        && (ej->ai_data[3] & 1)
        && ej->ai_data[2] == HEXA_STAGE) {
        dmg = hexa_filter_damage(dmg);
        if (!dmg) {
            entity_kill(i);
            return 1;
        }
    }

    if (boss_link_active && boss_link_reflect(ej, shot, dmg)) {
        entity_kill(i);
        return 1;
    }
    if (shot->ai_data[3] & PROJ_FLAG_SPLASH) {
        shot->ai_data[3] &= (u8)~PROJ_FLAG_SPLASH;
        projectile_spawn_splash(
            FIX8_TO_INT(shot->x) + 3,
            FIX8_TO_INT(shot->y) + 3,
            dmg > 1 ? (u8)((dmg + 1) >> 1) : 1, j);
    }

    if (ej->hp > dmg) {
        ej->hp = (u8)(ej->hp - dmg);
        status_try_player_shot(j, i);
        ej->ai_data[7] = weak ? 7 : 4;
        knockback_enemy(ej, shot->vx, shot->vy, poise);
        if (g_hitstop < (weak ? 2 : 1)) g_hitstop = weak ? 2 : 1;
        if (weak) {
            i16 hx = FIX8_TO_INT(ej->x) + 4;
            i16 hy = FIX8_TO_INT(ej->y) + 4;
            fx_spawn(SPR_FX_IMPACT, 3, hx, hy, 10);
            sfx_play(SFX_WEAK);
        } else {
            sfx_play(SFX_HIT);
            if (ej->ai_data[0] == ENEMY_STONE_SENTINEL
                && (ej->ai_data[3] & 1))
                boss_voice(ej->ai_data[2], BOSS_VOICE_PAIN);
        }
    } else {
        shot_spent_for_split = combat_defeat_enemy(j, i, weak);
    }
    if (shot_spent_for_split) return 1;
    fx_spawn(SPR_FX_IMPACT, 2,
        (i16)FIX8_TO_INT(shot->x),
        (i16)FIX8_TO_INT(shot->y), 4);
    if (shot->hp <= 1) {
        entity_kill(i);
        return 1;
    }
    shot->hp--;
    return 0;
}

