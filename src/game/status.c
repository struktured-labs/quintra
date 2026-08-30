#pragma bank 13

#include <gb/gb.h>
#include <gbdk/console.h>
#include <string.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/curse.h"
#include "game/enemy_ai.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "render/hud.h"
#include "render/text.h"
#include "render/tiles.h"
#include "content.h"

u8 player_status_kind;
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
static u8 player_status_aux;
static u8 confusion_mode;
static u8 confusion_streak;
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
        case QSTATUS_CONFUSION: return 90;
        case QSTATUS_MUTE:      return 75;
        case QSTATUS_BRITTLE:   return 75;
        case QSTATUS_BLEED:     return 90;
        case QSTATUS_CURSE:     return 90;
        case QSTATUS_REGEN:     return 90;
        case QSTATUS_HASTE:     return 90;
        case QSTATUS_INVERSION: return 75;
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
    fx_spawn(SPR_FX_IMPACT, status_palette(kind), x, y, 12);
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
    status_clear_enemies();
    player_status_kind = QSTATUS_NONE;
    player_status_ticks = 0;
    player_status_aux = 0;
    status_clock = 0;
    confusion_mode = 0;
    confusion_streak = 0;
    inversion_tie = 0;
    bleed_last_x = bleed_last_y = 0;
}

void status_player_cure(void) BANKED {
    u8 was_blind = (player_status_kind == QSTATUS_BLIND);
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

void status_player_apply(u8 kind, u8 ticks) BANKED {
    u8 was_blind;
    if (kind == QSTATUS_NONE || kind >= QSTATUS_COUNT) return;
    was_blind = (player_status_kind == QSTATUS_BLIND);
    if (!ticks) ticks = status_duration(kind);
    // Easy is the deep-route tester assist. Keep every condition mechanically
    // present, but halve hostile duration so one unlucky proc cannot erase a
    // long test run after the initiating enemy is already gone.
    if (RUN_IS_EASY() && kind != QSTATUS_REGEN && kind != QSTATUS_HASTE)
        ticks = (u8)((ticks + 1) >> 1);
    player_status_kind = kind;
    player_status_ticks = ticks;
    player_status_aux = 0;
    if (kind == QSTATUS_CONFUSION) {
        confusion_mode = (u8)(rng_next_u8() & 3);
        confusion_streak = 0;
    }
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
    const enemy_def_t *def;
    if (eid >= N_ENEMIES) return QSTATUS_INVERT_SPEED;
    def = &enemies[eid];
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
    if ((e->flags & (EF_ELITE | EF_ALPHA)) || (e->ai_data[3] & 1)) {
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
    kind = (e->type == ENT_PROJECTILE)
        ? (e->ai_data[5]
            ? status_hostile_kind_for_enemy((u8)(e->ai_data[5] - 1))
            : QSTATUS_NONE)
        : status_hostile_kind_for_enemy(e->ai_data[0]);
    if (kind == QSTATUS_NONE || kind >= QSTATUS_COUNT) return;
    chance = RUN_IS_EASY() ? 16 : 42;
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
    if (player_status_kind == QSTATUS_SLOW && (status_clock & 1)) {
        *keys &= (u8)~(J_LEFT | J_RIGHT | J_UP | J_DOWN);
        *pressed &= (u8)~(J_LEFT | J_RIGHT | J_UP | J_DOWN);
        return;
    }
    if (player_status_kind != QSTATUS_CONFUSION) return;
    if (dirs) {
        if (++confusion_streak >= 36) {
            // Change as soon as a sustained input suggests the player has
            // adapted. The flash/click announces the new mapping fairly.
            confusion_streak = 0;
            confusion_mode = (u8)((confusion_mode + 1
                + (rng_next_u8() & 1)) & 3);
            status_signal_at(QSTATUS_CONFUSION,
                (i16)player.x + 4, (i16)player.y + 2);
        }
    } else if (confusion_streak) confusion_streak--;
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

static void player_status_damage(void) {
    if (player.hp) player.hp--;
    player.iframes = player.iframes < 8 ? 8 : player.iframes;
    room_hurt_pose_ticks = 10;
    room_player_pose_locked = 1;
    room_player_pose_base = SPR_CLASS_HURT_BASE;
    room_shake(1, 4);
    sfx_play(SFX_HURT);
    hud_redraw_hp();
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
    u8 i;
    status_clock++;
    if (player_status_kind == QSTATUS_BLEED) {
        if (player.x != bleed_last_x || player.y != bleed_last_y) {
            bleed_last_x = player.x;
            bleed_last_y = player.y;
            // Count meaningful travel, not each animation beat. At 64 pixels
            // a full Normal Bleed can punish sustained flight several times,
            // but cannot consume an entire healthy champion by itself.
            if (++player_status_aux >= 64) {
                player_status_aux = 0;
                player_status_damage();
            }
        }
    }
    if (status_clock & 7) return;

    if (player_status_kind != QSTATUS_NONE && player_status_ticks) {
        u8 kind = player_status_kind;
        player_status_ticks--;
        if ((kind == QSTATUS_POISON && (player_status_ticks & 15) == 0)
            || (kind == QSTATUS_BURN && (player_status_ticks & 7) == 0)) {
            player_status_damage();
        } else if (kind == QSTATUS_REGEN && (player_status_ticks % 12) == 0
            && player.hp < player.hp_max) {
            player.hp++;
            hud_redraw_hp();
            sfx_play(SFX_HEART);
        }
        if ((player_status_ticks & 15) == 0)
            fx_spawn(SPR_FX_IMPACT, status_palette(kind),
                (i16)player.x + 4, (i16)player.y + 2, 8);
        if (player_status_ticks == 0) {
            u8 was_blind = (kind == QSTATUS_BLIND);
            player_status_kind = QSTATUS_NONE;
            player_status_aux = 0;
            confusion_streak = 0;
            if (was_blind) room_status_blind_visual(0);
            fx_spawn(SPR_FX_IMPACT, 5,
                (i16)player.x + 4, (i16)player.y + 2, 10);
        }
    }

    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        u8 kind = enemy_status_kind[i];
        if (kind == QSTATUS_NONE || !enemy_status_ticks[i]
            || !(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        enemy_status_ticks[i]--;
        // Enemy DOT bottoms out at one HP so status kills still resolve
        // through the ordinary reward/score/death path on the next strike.
        if (((kind == QSTATUS_POISON && (enemy_status_ticks[i] & 7) == 0)
                || (kind == QSTATUS_BURN && (enemy_status_ticks[i] & 3) == 0))
            && e->hp > 1) {
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
