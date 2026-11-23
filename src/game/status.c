#pragma bank 13

#include <gb/gb.h>
#include <gbdk/console.h>
#include <string.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/rare_enemy.h"
#include "game/antidote.h"
#include "game/curse.h"
#include "game/enemy_ai.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "game/secret_merchant.h"
#include "game/powerup.h"
#include "render/hud.h"
#include "render/text.h"
#include "render/tiles.h"
#include "content.h"
#include "game/enemy_def.h"

u8 player_status_kind;
u8 status_apply_req;
void status_effect(u8 kind,u8 palette,i16 x,i16 y) BANKED;
u8 player_status_ticks;
u8 enemy_status_kind[MAX_ENTITIES];
u8 enemy_status_ticks[MAX_ENTITIES];
u8 enemy_status_aux[MAX_ENTITIES];
u8 status_enemy_actor = 0xFF;
u8 status_confused_projectiles;
u8 status_enemy_active;

u8 status_enemy_summon_blocked(void) BANKED {
    return status_enemy_actor < MAX_ENTITIES
        && enemy_status_kind[status_enemy_actor] == QSTATUS_MUTE;
}

u8 status_enemy_effective_poise(u8 idx, u8 poise) BANKED {
    if (idx < MAX_ENTITIES
        && enemy_status_kind[idx] == QSTATUS_INVERSION
        && enemy_status_aux[idx] == QSTATUS_INVERT_POISE)
        return 0;
    return poise;
}

u8 status_enemy_hit_damage(u8 idx, u8 damage) BANKED {
    if (idx < MAX_ENTITIES
        && (enemy_status_kind[idx] == QSTATUS_BRITTLE
            || (enemy_status_kind[idx] == QSTATUS_INVERSION
                && enemy_status_aux[idx] == QSTATUS_INVERT_ARMOR)))
        return (u8)(damage + 2);
    return damage;
}

u8 status_hostile_damage_taken(u8 idx) BANKED {
    u8 defense = status_player_effective_stat(QSTATUS_STAT_DEF);
    u8 incoming = entities[idx].damage;
    u8 taken;
    if (entities[idx].type == ENT_ENEMY
        && enemy_status_kind[idx] == QSTATUS_INVERSION
        && enemy_status_aux[idx] == QSTATUS_INVERT_DAMAGE
        && incoming > 1)
        incoming = (u8)((incoming + 1) >> 1);
    taken = (incoming > defense) ? (u8)(incoming - defense) : 1;
    if (player_status_kind == QSTATUS_BRITTLE) taken++;
    taken = (u8)(taken + curse_incoming_bonus());
    return taken;
}

u8 status_clock;
extern u8 hud_notice_ticks;
static u8 player_status_aux;
static u8 confusion_mode;
static u8 confusion_streak;
u16 confusion_immune;
u8 disarm_immune;
static u8 inversion_tie;
static ppos_t bleed_last_x;
static ppos_t bleed_last_y;

u8 status_player_palette_prop(void) BANKED {
    switch (player_status_kind) {
        case QSTATUS_POISON:
        case QSTATUS_REGEN:     return 7;
        case QSTATUS_BURN:
        case QSTATUS_BLEED:
        case QSTATUS_BRITTLE:   return 4;
        case QSTATUS_SLOW:
        case QSTATUS_STOP:      return 3;
        case QSTATUS_CONFUSION:
        case QSTATUS_CURSE:
        case QSTATUS_INVERSION: return 6;
        case QSTATUS_HASTE:     return 5;
        default:                return 0;
    }
}

void room_start_weapon_surge(void) BANKED {
    room_weapon_surge_ticks = 120;
    room_shake(1, 10);
    fx_spawn(SPR_SURGE_ORB, 0x06, (i16)player.x + 4,
        (i16)player.y - 6, 18);
    sfx_play_reward(SFX_REWARD_SURGE);
    status_player_apply(QSTATUS_HASTE, 90);
}

void status_resolve_confused_projectiles(void) BANKED {
    u8 i, j;
    u8 active = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *shot = &entities[i];
        if (!(shot->flags & EF_ACTIVE) || shot->type != ENT_PROJECTILE
            || (shot->flags & EF_PLAYER_PROJ)
            || !(shot->ai_data[4] & PROJ_HOSTILE_CONFUSED)) continue;
        for (j = 0; j < MAX_ENTITIES; ++j) {
            entity_t *target = &entities[j];
            if (!(target->flags & EF_ACTIVE) || target->type != ENT_ENEMY
                || !(target->flags & EF_ON_SCREEN)) continue;
            if (!aabb_overlap_ee(shot, target)) continue;
            if (target->hp > shot->damage)
                target->hp = (u8)(target->hp - shot->damage);
            else target->hp = 1;
            target->ai_data[7] = 8;
            fx_spawn(SPR_FX_IMPACT, 6,
                FIX8_TO_INT(target->x), FIX8_TO_INT(target->y), 8);
            entity_kill(i);
            sfx_play(SFX_HIT);
            break;
        }
        if (shot->flags & EF_ACTIVE) active = 1;
    }
    status_confused_projectiles = active;
}

void status_draw_pack_label(void) BANKED {
    static const char *const names[QSTATUS_COUNT] = {
        "NORMAL ", "POISON ", "BURNING", "SLOWED ", "STOPPED",
        "BLINDED", "CONFUSE", "MUTED  ", "BRITTLE", "BLEED  ",
        "CURSED ", "REGEN  ", "HASTED ", "INVERT "
    };
    u8 kind = player_status_kind < QSTATUS_COUNT
        ? player_status_kind : QSTATUS_NONE;
    gotoxy(12, 1);
    text_write(names[kind]);
}

static u8 status_duration(u8 kind) {
    switch (kind) {
        case QSTATUS_POISON:    return 120; // 16 seconds
        case QSTATUS_BURN:      return 60;  // 8 seconds, faster damage
        case QSTATUS_SLOW:      return 90;
        case QSTATUS_STOP:      return 14;  // brief, fair hard disable
        case QSTATUS_BLIND:     return 75;
        case QSTATUS_CONFUSION: return STATUS_CONFUSION_MEAN_TICKS; // player overwrites with a roll
        case QSTATUS_MUTE:      return 75;
        case QSTATUS_BRITTLE:   return 75;
        case QSTATUS_BLEED:     return 60;  // 8 seconds (was 12)
        case QSTATUS_CURSE:     return 90;
        case QSTATUS_REGEN:     return 90;
        case QSTATUS_HASTE:     return 90;
        case QSTATUS_INVERSION: return 75;
        case QSTATUS_DISARM:    return 30; // ~4 seconds; Easy halves it
        default:               return 0;
    }
}

static u8 status_palette(u8 kind) {
    switch (kind) {
        case QSTATUS_POISON:
        case QSTATUS_REGEN:     return 7; // green
        case QSTATUS_BURN:
        case QSTATUS_BLEED:
        case QSTATUS_BRITTLE:   return 4; // red
        case QSTATUS_SLOW:
        case QSTATUS_STOP:      return 3; // blue
        case QSTATUS_CONFUSION:
        case QSTATUS_CURSE:
        case QSTATUS_INVERSION: return 6; // rift violet
        case QSTATUS_HASTE:     return 5; // gold
        default:               return 0; // Blind/Mute: drained grey
    }
}

u8 status_enemy_palette_prop(u8 idx) BANKED {
    return (idx < MAX_ENTITIES)
        ? status_palette(enemy_status_kind[idx]) : 0;
}

static void status_signal_at(u8 kind, i16 x, i16 y) {
    status_effect(kind,status_palette(kind),x,y);
    sfx_play((kind == QSTATUS_STOP || kind == QSTATUS_MUTE)
        ? SFX_TICK : SFX_WEAK);
}

void status_clear_enemies(void) BANKED {
    memset(enemy_status_kind, 0, sizeof(enemy_status_kind));
    memset(enemy_status_ticks, 0, sizeof(enemy_status_ticks));
    memset(enemy_status_aux, 0, sizeof(enemy_status_aux));
    status_enemy_actor = 0xFF;
    status_confused_projectiles = 0;
    status_enemy_active = 0;
}

void status_reset_all(void) BANKED {
    status_apply_req = 0;
    status_clear_enemies();
    player_status_kind = QSTATUS_NONE;
    player_status_ticks = 0;
    player_status_aux = 0;
    status_clock = 0;
    confusion_mode = 0;
    confusion_streak = 0;
    confusion_immune = 0;
    disarm_immune = 0;
    inversion_tie = 0;
    bleed_last_x = bleed_last_y = 0;
    powerup_reset();
}

void status_player_cure(void) BANKED {
    u8 was_blind = (player_status_kind == QSTATUS_BLIND);
    if (player_status_kind == QSTATUS_CONFUSION) confusion_immune = STATUS_CONFUSION_IMMUNE_FRAMES;
    if (player_status_kind == QSTATUS_DISARM) disarm_immune = 120;
    player_status_kind = QSTATUS_NONE;
    player_status_ticks = 0;
    player_status_aux = 0;
    confusion_streak = 0;
    if (was_blind) room_status_blind_visual(0);
    fx_spawn(SPR_FX_IMPACT, 5, (i16)player.x + 4,
        (i16)player.y + 2, 14);
}

void status_player_refresh_visual(void) BANKED {
    if (player_status_kind == QSTATUS_BLIND)
        room_status_blind_visual(1);
}

static u8 confusion_roll_ticks(void) {
    // Two uniform [0, 75] rolls, signed around the 10 s mean, then
    // clamped to [3 s, 20 s]. That is a cheap integer triangle
    // peaked at 10 s; the 3 s floor only slightly raises the mean
    // (about 10.05 s at 60 Hz). Easy keeps the same shape at 3/5,
    // still never below 3 s (mean then about 6.1 s, cap 12 s).
    u8 r1 = rng_range(STATUS_CONFUSION_MEAN_TICKS + 1);
    u8 r2 = rng_range(STATUS_CONFUSION_MEAN_TICKS + 1);
    u8 ticks;
    if (r2 > (u8)(STATUS_CONFUSION_MEAN_TICKS + r1))
        ticks = 0;
    else
        ticks = (u8)(STATUS_CONFUSION_MEAN_TICKS + r1 - r2);
    if (ticks < STATUS_CONFUSION_MIN_TICKS)
        ticks = STATUS_CONFUSION_MIN_TICKS;
    if (ticks > STATUS_CONFUSION_MAX_TICKS)
        ticks = STATUS_CONFUSION_MAX_TICKS;
    if (RUN_IS_EASY()) {
        ticks = (u8)((u16)(ticks * 3u + 2u) / 5u);
        if (ticks < STATUS_CONFUSION_MIN_TICKS)
            ticks = STATUS_CONFUSION_MIN_TICKS;
    }
    return ticks;
}

void status_player_apply(u8 kind, u8 ticks) BANKED {
    u8 was_blind;
    if (kind == QSTATUS_NONE || kind >= QSTATUS_COUNT) return;
    if (secret_merchant_block_status(kind)) return;
    was_blind = (player_status_kind == QSTATUS_BLIND);
    if (!ticks) ticks = status_duration(kind);
    // Easy is the deep-route tester assist. Keep every condition mechanically
    // present, but halve hostile duration so one unlucky proc cannot erase a
    // long test run after the initiating enemy is already gone.
    if (kind == QSTATUS_CONFUSION && confusion_immune) return;
    if (kind == QSTATUS_DISARM && disarm_immune) return;
    ticks = status_resist_adjust(kind, ticks);
    if (ticks == 0xFF) return;
    if (kind == QSTATUS_CONFUSION) {
        ticks = confusion_roll_ticks();
        // Horizontal mirror or full reverse only; never reshuffle.
        confusion_mode = (rng_next_u8() & 1) ? 1 : 2;
        confusion_streak = 0;
    }
    if (player_status_kind == QSTATUS_CONFUSION && kind != QSTATUS_CONFUSION)
        confusion_immune = STATUS_CONFUSION_IMMUNE_FRAMES;
    player_status_kind = kind;
    player_status_ticks = ticks;
    player_status_aux = 0;
    if (kind == QSTATUS_INVERSION) inversion_tie++;
    if (kind == QSTATUS_BLEED) {
        bleed_last_x = player.x;
        bleed_last_y = player.y;
    }
    if (was_blind && kind != QSTATUS_BLIND) room_status_blind_visual(0);
    if (kind == QSTATUS_BLIND) room_status_blind_visual(1);
    status_signal_at(kind, (i16)player.x + 4, (i16)player.y + 2);
    hud_show_status(kind);
}

static u8 inversion_enemy_aspect(const entity_t *e) {
    u8 eid = e->ai_data[0];
    enemy_def_t def_buf;
    const enemy_def_t *def;
    if (eid >= N_ENEMIES) return QSTATUS_INVERT_SPEED;
    enemy_load_def(eid, &def_buf);
    def = &def_buf;
    if (def->stats.poise >= 3) return QSTATUS_INVERT_POISE;
    if (def->stats.hp >= 20) return QSTATUS_INVERT_ARMOR;
    if (def->stats.damage >= 5) return QSTATUS_INVERT_DAMAGE;
    return QSTATUS_INVERT_SPEED;
}

void status_enemy_apply(u8 idx, u8 kind, u8 ticks) BANKED {
    entity_t *e;
    if (idx >= MAX_ENTITIES || kind == QSTATUS_NONE || kind >= QSTATUS_COUNT)
        return;
    e = &entities[idx];
    if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) return;
    if (!ticks) ticks = status_duration(kind);
    // Elites and Colossi resist duration rather than ignoring the system.
    // Stop becomes a short stagger and Mute cannot erase an entire boss phase.
    if ((e->flags & (EF_ELITE | EF_ALPHA | EF_RARE)) || (e->ai_data[3] & 1)) {
        ticks = (u8)((ticks + 2) / 3);
        if (kind == QSTATUS_STOP && ticks > 6) ticks = 6;
        if (kind == QSTATUS_MUTE && ticks > 12) ticks = 12;
    }
    enemy_status_kind[idx] = kind;
    enemy_status_ticks[idx] = ticks;
    status_enemy_active = 1;
    if (kind == QSTATUS_REGEN) enemy_status_aux[idx] = e->hp;
    else if (kind == QSTATUS_INVERSION)
        enemy_status_aux[idx] = inversion_enemy_aspect(e);
    else enemy_status_aux[idx] = 0;
    e->ai_data[7] = 8;
    status_signal_at(kind, FIX8_TO_INT(e->x), FIX8_TO_INT(e->y));
}

u8 status_hostile_kind_for_enemy(u8 eid) BANKED {
    switch (eid) {
        case ENEMY_SHADE:          return QSTATUS_BLIND;
        case ENEMY_WARLOCK:
        case ENEMY_DREAD_BELL:     return QSTATUS_MUTE;
        case ENEMY_ROPE:
        case ENEMY_FACET_RAM:      return QSTATUS_BLEED;
        case ENEMY_FOLD_STAR:      return QSTATUS_STOP;
        case ENEMY_GLOAM_LEECH:    return QSTATUS_CURSE;
        case ENEMY_CINDER_MAW:
        case ENEMY_CINDER_KITE:    return QSTATUS_BURN;
        case ENEMY_MIRROR_MOTH:    return QSTATUS_INVERSION;
        case ENEMY_MIRE_SPORE:
        case ENEMY_BRAMBLE_SPRITE: return QSTATUS_POISON;
        case ENEMY_RUNE_LANTERN:
        case ENEMY_DUSK_MIDGE:     return QSTATUS_CONFUSION;
        case ENEMY_BOG_TOAD:       return QSTATUS_BRITTLE;
        case ENEMY_FROST_LANCER:   return QSTATUS_SLOW;
        case ENEMY_BUBBLE:         return QSTATUS_DISARM;
        default:                   return QSTATUS_NONE;
    }
}

void status_try_hostile_hit(u8 hostile_idx) BANKED {
    entity_t *e;
    u8 kind;
    u8 chance;
    if (hostile_idx >= MAX_ENTITIES) return;
    e = &entities[hostile_idx];
    if (!(e->flags & EF_ACTIVE)) return;
    if (e->type == ENT_ENEMY && (e->flags & EF_RARE))
        kind = (e->ai_data[0] & 1) ? QSTATUS_SLOW : QSTATUS_POISON;
    else if (e->type == ENT_PROJECTILE && (e->ai_data[5] & 0x80))
        kind = e->ai_data[5] & 0x7F;
    else kind = (e->type == ENT_PROJECTILE)
        ? (e->ai_data[5]
            ? status_hostile_kind_for_enemy((u8)(e->ai_data[5] - 1))
            : QSTATUS_NONE)
        : status_hostile_kind_for_enemy(e->ai_data[0]);
    if (kind == QSTATUS_NONE || kind >= QSTATUS_COUNT) return;
    if (kind == QSTATUS_CONFUSION) {
        if (confusion_immune) return;
        chance = RUN_IS_EASY() ? 10 : 25;
    } else if (kind == QSTATUS_DISARM) {
        if (disarm_immune) return;
        chance = 100;
    } else {
        chance = RUN_IS_EASY() ? 16 : 42;
        if ((e->type == ENT_ENEMY && (e->flags & EF_RARE))
            || (e->type == ENT_PROJECTILE && (e->ai_data[5] & 0x80))) chance = 100;
    }
    if (rng_range(100) >= chance) return;
    if (kind == QSTATUS_CURSE) {
        // Gloam Leeches seed a room-scale hex instead of occupying the short
        // status slot. Most hits create a travel-bounded curse; late-run bad
        // luck can leave a permanent mark until a cleansing Wildcard.
        u8 permanent = (!RUN_IS_EASY() && run_state.bosses_beaten >= 3
            && rng_range(4) == 0);
        u8 curse = permanent
            ? ((rng_next_u8() & 1) ? CURSE_FRAIL : CURSE_MISFORTUNE)
            : ((rng_next_u8() & 1) ? CURSE_DULL : CURSE_HUNGER);
        curse_apply(curse, permanent ? 0 : 6, 1);
    } else status_player_apply(kind, status_duration(kind));
}

void status_try_player_shot(u8 enemy_idx, u8 shot_idx) BANKED {
    entity_t *shot;
    u8 kind = QSTATUS_NONE;
    u8 element;
    u8 chance = 32;
    if (enemy_idx >= MAX_ENTITIES || shot_idx >= MAX_ENTITIES) return;
    shot = &entities[shot_idx];
    if (!(shot->flags & EF_ACTIVE) || shot->type != ENT_PROJECTILE) return;
    element = shot->ai_data[1];

    // Physical reach has its own blood language even when Wolfkin's authored
    // weapon element is fire. Heavy impacts can instead crack armor.
    if (shot->ai_data[2] && rng_range(100) < 28) {
        kind = (shot->damage >= 8) ? QSTATUS_BRITTLE : QSTATUS_BLEED;
        chance = 100;
    } else if (shot->ai_data[3] & PROJ_FLAG_CONVERGENCE) {
        kind = QSTATUS_INVERSION;
        chance = 50;
    } else if (element & 1) kind = QSTATUS_BURN;
    else if (element & 2) kind = QSTATUS_SLOW;
    else if (element & 4) { kind = QSTATUS_STOP; chance = 24; }
    else if (element & 8) {
        // Shadow never settles into one solved debuff: Blind, adaptive
        // Confusion, Mute, and Rift Inversion rotate across successful casts.
        static const u8 shadow[4] = {
            QSTATUS_BLIND, QSTATUS_CONFUSION, QSTATUS_MUTE, QSTATUS_INVERSION
        };
        kind = shadow[(u8)((status_clock + shot_idx) & 3)];
        chance = 38;
    } else if (element & 16) {
        kind = (rng_range(5) == 0) ? QSTATUS_CURSE : QSTATUS_POISON;
        chance = 40;
    }
    if (kind != QSTATUS_NONE && rng_range(100) < chance)
        status_enemy_apply(enemy_idx, kind, status_duration(kind));
}

static u8 remap_dirs(u8 value, u8 mode) {
    u8 out = (u8)(value & (u8)~(J_LEFT | J_RIGHT | J_UP | J_DOWN));
    if (mode == 0) { // quarter-turn clockwise
        if (value & J_UP) out |= J_RIGHT;
        if (value & J_RIGHT) out |= J_DOWN;
        if (value & J_DOWN) out |= J_LEFT;
        if (value & J_LEFT) out |= J_UP;
    } else if (mode == 1) { // horizontal mirror
        if (value & J_UP) out |= J_UP;
        if (value & J_DOWN) out |= J_DOWN;
        if (value & J_LEFT) out |= J_RIGHT;
        if (value & J_RIGHT) out |= J_LEFT;
    } else if (mode == 2) { // half-turn
        if (value & J_UP) out |= J_DOWN;
        if (value & J_DOWN) out |= J_UP;
        if (value & J_LEFT) out |= J_RIGHT;
        if (value & J_RIGHT) out |= J_LEFT;
    } else { // diagonal mirror: axes exchange
        if (value & J_UP) out |= J_LEFT;
        if (value & J_LEFT) out |= J_UP;
        if (value & J_DOWN) out |= J_RIGHT;
        if (value & J_RIGHT) out |= J_DOWN;
    }
    return out;
}

void status_player_filter_input(u8 *keys, u8 *pressed) BANKED {
    u8 dirs = (u8)(*keys & (J_LEFT | J_RIGHT | J_UP | J_DOWN));
    if (player_status_kind == QSTATUS_STOP) {
        *keys &= (u8)~(J_LEFT | J_RIGHT | J_UP | J_DOWN | J_A | J_B);
        *pressed &= (u8)~(J_LEFT | J_RIGHT | J_UP | J_DOWN | J_A | J_B);
        return;
    }
    if (player_status_kind == QSTATUS_DISARM) {
        *keys &= (u8)~J_A;
        *pressed &= (u8)~J_A;
        return;
    }
    if (player_status_kind == QSTATUS_SLOW && (status_clock & 1)) {
        *keys &= (u8)~(J_LEFT | J_RIGHT | J_UP | J_DOWN);
        *pressed &= (u8)~(J_LEFT | J_RIGHT | J_UP | J_DOWN);
        return;
    }
    if (player_status_kind != QSTATUS_CONFUSION) return;
    // No reshuffle. Standing still for 1 s shortens the effect by 8 beats.
    if (!dirs) {
        if (++confusion_streak >= 60) {
            confusion_streak = 0;
            if (player_status_ticks > 8) player_status_ticks = (u8)(player_status_ticks - 8);
            else player_status_ticks = 1;
        }
    } else confusion_streak = 0;
    *keys = remap_dirs(*keys, confusion_mode);
    *pressed = remap_dirs(*pressed, confusion_mode);
}

u8 status_player_effective_stat(u8 stat) BANKED {
    u8 values[4];
    u8 hi, lo, i;
    values[0] = player.atk;
    values[1] = player.def;
    values[2] = player.spd;
    values[3] = player.lck;
    if (stat >= 4) return 0;
    // Pokemon-style Burn: half attack while it lasts. ATK 1 stays 1 so
    // a weak starting swing is not erased; ATK 0 stays 0.
    if (player_status_kind == QSTATUS_BURN && stat == QSTATUS_STAT_ATK) {
        if (values[0] > 1) values[0] >>= 1;
        return curse_adjust_stat(stat, values[0]);
    }
    if (player_status_kind != QSTATUS_INVERSION)
        return curse_adjust_stat(stat, values[stat]);
    hi = lo = (u8)(inversion_tie & 3);
    for (i = 1; i < 4; ++i) {
        u8 n = (u8)((i + inversion_tie) & 3);
        if (values[n] > values[hi]) hi = n;
        if (values[n] < values[lo]) lo = n;
    }
    if (stat == hi) return curse_adjust_stat(stat, values[lo]);
    if (stat == lo) return curse_adjust_stat(stat, values[hi]);
    return curse_adjust_stat(stat, values[stat]);
}

// One damage-over-time tick. A condition never takes the last half-heart:
// at the floor the tick only re-names itself, or, with an Antidote carried,
// the vial breaks and cures so the champion is not left pinned at half a
// heart. Every tick re-shows the condition so the drain is never silent.
// Returns 0 when the condition was cured (the caller must stop).
static u8 player_status_damage(void) {
    u8 kind = player_status_kind;
    if (player.hp <= 1) {
        if (antidote_try_rescue()) return 0;
        hud_show_status(kind);
        return 1;
    }
    player.hp--;
    player.iframes = player.iframes < 8 ? 8 : player.iframes;
    room_hurt_pose_ticks = 10;
    room_player_pose_locked = 1;
    room_player_pose_base = SPR_CLASS_HURT_BASE;
    room_shake(1, 4);
    sfx_play(SFX_HURT);
    hud_redraw_hp();
    hud_show_status(kind);
    return 1;
}

void status_enemy_moved(u8 idx) BANKED {
    entity_t *e;
    if (idx >= MAX_ENTITIES || enemy_status_kind[idx] != QSTATUS_BLEED) return;
    e = &entities[idx];
    if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) return;
    if (++enemy_status_aux[idx] >= 24) {
        enemy_status_aux[idx] = 0;
        if (e->hp > 1) e->hp--;
        e->ai_data[7] = 7;
    }
}

void status_update_enemy_condition(u8 idx) BANKED {
    entity_t *e;
    u8 kind;
    u8 halted;
    ppos_t old_x, old_y;
    if (idx >= MAX_ENTITIES) return;
    e = &entities[idx];
    kind = enemy_status_kind[idx];
    halted = (kind == QSTATUS_STOP)
        || (kind == QSTATUS_SLOW && (entity_anim_counter & 1))
        || (kind == QSTATUS_INVERSION
            && enemy_status_aux[idx] == QSTATUS_INVERT_SPEED
            && (entity_anim_counter & 1));
    old_x = e->x;
    old_y = e->y;
    status_enemy_actor = idx;
    if (!halted) enemy_update(e, idx);
    if (kind == QSTATUS_HASTE && (entity_anim_counter & 1)
        && (e->flags & EF_ACTIVE))
        enemy_update(e, idx);
    status_enemy_actor = 0xFF;
    if (kind == QSTATUS_BLEED && (old_x != e->x || old_y != e->y))
        status_enemy_moved(idx);
}


void status_tick(void) BANKED {
    if (confusion_immune) confusion_immune--;
    if (disarm_immune) disarm_immune--;
    powerup_tick_cooldown();
    if (player_status_kind == QSTATUS_CONFUSION)
        powerup_confusion_stars();
    u8 i;
    status_clock++;
    if (powerup_id) powerup_tick();
    if (player_status_kind == QSTATUS_BLEED) {
        if (player.x != bleed_last_x || player.y != bleed_last_y) {
            bleed_last_x = player.x;
            bleed_last_y = player.y;
            // Count frames spent moving. A full Normal Bleed (480 frames)
            // costs at most three half-hearts even while sprinting the whole
            // time; standing still costs nothing.
            if (++player_status_aux >= STATUS_BLEED_STRIDE) {
                player_status_aux = 0;
                if (!player_status_damage()) return;
            }
        }
    }
    if (status_clock & 7) return;

    if (player_status_kind != QSTATUS_NONE && player_status_ticks) {
        u8 kind = player_status_kind;
        player_status_ticks--;
        // Filter Mask (Veil charm): Poison ticks half as often.
        if ((kind == QSTATUS_POISON && (player_status_ticks
                & ((run_state.veil_charms & VEIL_CHARM_BIT(VEIL_FILTER_MASK))
                    ? 31 : 15)) == 0)
            || (kind == QSTATUS_BURN
                && (player_status_ticks % STATUS_BURN_PERIOD) == 0)) {
            if (!player_status_damage()) return;
        } else if (STATUS_KIND_IS_HARM(kind) && !hud_notice_ticks
            && (player_status_ticks & 15) == 8) {
            // Non-draining harm (and Bleed while standing) re-names itself
            // about every two seconds when the notice lane is free, so a
            // pickup card is never pushed aside by a reminder.
            hud_show_status(kind);
        } else if (kind == QSTATUS_REGEN && (player_status_ticks % 12) == 0
            && player.hp < player.hp_max) {
            player.hp++;
            hud_redraw_hp();
            sfx_play(SFX_HEART);
        }
        if ((player_status_ticks & 3) == 0)
            status_effect(kind,status_palette(kind),player.x+4,player.y+2);
        if (player_status_ticks == 0) {
            u8 was_blind = (kind == QSTATUS_BLIND);
            if (kind == QSTATUS_CONFUSION) confusion_immune = STATUS_CONFUSION_IMMUNE_FRAMES;
            if (kind == QSTATUS_DISARM) disarm_immune = 120;
            player_status_kind = QSTATUS_NONE;
            player_status_aux = 0;
            confusion_streak = 0;
            if (was_blind) room_status_blind_visual(0);
            fx_spawn(SPR_FX_IMPACT, 5,
                (i16)player.x + 4, (i16)player.y + 2, 10);
            // Harm that wears off says so; boons simply fade.
            if (STATUS_KIND_IS_HARM(kind)) hud_show_cured();
        }
    }

    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        u8 kind = enemy_status_kind[i];
        if (kind == QSTATUS_NONE || !enemy_status_ticks[i]
            || !(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        enemy_status_ticks[i]--;
        if ((enemy_status_ticks[i] & 7) == (i & 7)
            && (e->flags & EF_ON_SCREEN))
            status_effect(kind,status_palette(kind),e->x+4,e->y);
        // Enemy DOT bottoms out at one HP so status kills still resolve
        // through the ordinary reward/score/death path on the next strike.
        if (((kind == QSTATUS_POISON && (enemy_status_ticks[i] & 7) == 0)
                || (kind == QSTATUS_BURN && (enemy_status_ticks[i] & 3) == 0))
            && e->hp > 1
            /* During the Ember fight, authored invuln (closed vent, late
               husks) clears EF_ON_SCREEN. Do not let Poison/Burn chip
               through a window the player cannot punish. Other colossi
               and off-camera fodder keep their ordinary DOT. */
            && ((e->flags & EF_ON_SCREEN) || !cinder_pack_active)) {
            e->hp--;
            e->ai_data[7] = 7;
        } else if (kind == QSTATUS_REGEN
            && (enemy_status_ticks[i] % 12) == 0
            && e->hp < enemy_status_aux[i]) {
            e->hp++;
            e->ai_data[7] = 6;
        }
        if (enemy_status_ticks[i] == 0) {
            enemy_status_kind[i] = QSTATUS_NONE;
            enemy_status_aux[i] = 0;
        }
    }
}
