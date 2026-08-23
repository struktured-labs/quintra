#pragma bank 11

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/combat.h"
#include "game/dungeon_director.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

// SDCC's banked argument window is not stable across a nested banked/FX call.
// Preserve the one projectile slot these cold rejection transactions retire
// in WRAM before spawning feedback, then consume that exact body afterward.
static u8 special_projectile_idx;

// These specialist transactions always consume a projectile, never an enemy.
// Retire that slot locally: calling the HOME entity helper after nested FX and
// audio bank traffic can lose the original SDCC banked argument window.
static void retire_special_projectile(void) {
    entity_t *shot = &entities[special_projectile_idx];
    shot->flags &= (u8)~(EF_ACTIVE | EF_ALIVE);
    shot->type = ENT_NONE;
    move_sprite(shot->oam_slot, 0, 0);
}

void enemy_patrol_init(entity_t *e, u8 enemy_content_id) BANKED {
    if (enemy_content_id == ENEMY_FACET_RAM) {
        // A long middle-scale body: visibly larger than the small roster,
        // but slimmer than a square bruiser or Colossus.
        e->hitbox = (u8)0xBD;
        e->state = (u8)((rng_next_u8() & 3) << 1);
        e->state_timer = (u8)(52 + (rng_next_u8() & 0x1F));
        e->ai_data[1] = (u8)(72 + (rng_next_u8() & 0x1F));
    } else {
        e->hitbox = (u8)0xCD;
        e->state = 0;
        e->state_timer = 0;
        e->ai_data[2] = 0;
        e->ai_data[3] = 78;
    }
}

void enemy_patrol_update(entity_t *e, u8 enemy_content_id) BANKED {
    if (enemy_content_id == ENEMY_FACET_RAM) facet_ram_update(e);
    else stage_reaper_update(e);
}

void stage_reaper_spawn_encounter(u8 stage) BANKED {
    u8 idx;
    if (run_state.dungeon_puzzles & RUN_REAPER_CLEARED_BIT) return;
    idx = enemy_spawn(ENEMY_STAGE_REAPER, 9, 6);
    if (idx == 0xFF) return;
    entities[idx].hp = (u8)(entities[idx].hp + (u8)(stage * 3));
    if (RUN_IS_EASY())
        entities[idx].hp = (u8)((entities[idx].hp + 1) >> 1);
    room_encounter_kind = ENCOUNTER_ELITE;
    room_encounter_target = idx;
}

void facet_ram_draw(entity_t *e, u8 oam, u8 bx, u8 by, u8 pal) BANKED {
    u8 t, t0, t1, t2, t3;
    u8 prop = pal;
    u8 facing = (u8)(e->state & 6);

    // Two authored views preserve the long rectangular silhouette. Cardinal
    // mirroring rotates the bright rear facet without four more OBJ tiles.
    if (facing == 6) {
        t = SPR_MEDIUM_FACET_RAM_H;
        t0 = (u8)(t + 1); t1 = t;
        t2 = (u8)(t + 3); t3 = (u8)(t + 2);
        prop |= S_FLIPX;
    } else if (facing == 0) {
        t = SPR_MEDIUM_FACET_RAM_V;
        t0 = (u8)(t + 2); t1 = (u8)(t + 3);
        t2 = t; t3 = (u8)(t + 1);
        prop |= S_FLIPY;
    } else {
        t = (facing == 4) ? SPR_MEDIUM_FACET_RAM_V
            : SPR_MEDIUM_FACET_RAM_H;
        t0 = t; t1 = (u8)(t + 1);
        t2 = (u8)(t + 2); t3 = (u8)(t + 3);
    }

    if (e->ai_data[7]) {
        e->ai_data[7]--;
        if (e->ai_data[7] & 1) {
            move_sprite(oam, 0, 0);
            move_sprite((u8)(oam + 1), 0, 0);
            move_sprite((u8)(oam + 2), 0, 0);
            move_sprite((u8)(oam + 3), 0, 0);
            return;
        }
    }
    set_sprite_tile(oam, t0);
    set_sprite_tile((u8)(oam + 1), t1);
    set_sprite_tile((u8)(oam + 2), t2);
    set_sprite_tile((u8)(oam + 3), t3);
    set_sprite_prop(oam, prop);
    set_sprite_prop((u8)(oam + 1), prop);
    set_sprite_prop((u8)(oam + 2), prop);
    set_sprite_prop((u8)(oam + 3), prop);
    move_sprite(oam, bx, by);
    move_sprite((u8)(oam + 1), (u8)(bx + 8), by);
    move_sprite((u8)(oam + 2), bx, (u8)(by + 8));
    move_sprite((u8)(oam + 3), (u8)(bx + 8), (u8)(by + 8));
}

static u8 facet_ram_hit_from_rear(const entity_t *shot, const entity_t *ram) {
    i16 sx = FIX8_TO_INT(shot->x) + (i16)((shot->hitbox >> 4) >> 1);
    i16 sy = FIX8_TO_INT(shot->y) + (i16)((shot->hitbox & 0x0F) >> 1);
    i16 rx = FIX8_TO_INT(ram->x) + 6;
    i16 ry = FIX8_TO_INT(ram->y) + 7;

    // A location-only half-plane lets a fast or wide shot enter through an
    // armored face, cross the body's centre between collision samples, and
    // then look like a rear hit. Require both pieces of the Darknut read:
    // contact on the back half *and* travel from back toward front. A
    // stationary splash has no travel vector, so its own centre must simply
    // be behind the Ram; centered/front AOE cannot bypass the armor.
    switch (ram->state & 6) {
        case 0:
            return sy > ry && (shot->vy < 0 || (!shot->vx && !shot->vy));
        case 2:
            return sx < rx && (shot->vx > 0 || (!shot->vx && !shot->vy));
        case 4:
            return sy < ry && (shot->vy > 0 || (!shot->vx && !shot->vy));
        default:
            return sx > rx && (shot->vx < 0 || (!shot->vx && !shot->vy));
    }
}

static u8 facet_ram_reject_hit(u8 shot_idx, u8 ram_idx) {
    if (facet_ram_hit_from_rear(&entities[shot_idx], &entities[ram_idx]))
        return 0;
    entities[ram_idx].ai_data[7] = 5;
    fx_spawn(SPR_FX_IMPACT, 3,
        FIX8_TO_INT(entities[shot_idx].x),
        FIX8_TO_INT(entities[shot_idx].y), 7);
    sfx_play(SFX_HIT);
    retire_special_projectile();
    return 1;
}

void enemy_special_reject_hit(u8 shot_idx, u8 enemy_idx) BANKED {
    entity_t *enemy;
    u8 eid;
    if (shot_idx >= MAX_ENTITIES || enemy_idx >= MAX_ENTITIES) return;
    special_projectile_idx = shot_idx;
    enemy = &entities[enemy_idx];
    eid = enemy->ai_data[0];
    if (eid == ENEMY_FACET_RAM) {
        (void)facet_ram_reject_hit(shot_idx, enemy_idx);
        return;
    }
    if (eid < N_ENEMIES && enemies[eid].ai_kind == AI_COUNTER_GUARD
        && enemy->state == 0) {
        enemy->state = 1;
        enemy->state_timer = enemies[eid].ai_p1;
        enemy->ai_data[6] = enemies[eid].ai_p0;
        enemy->palette = 4;
        enemy->ai_data[7] = 10;
        fx_spawn(SPR_FX_IMPACT, 3,
            FIX8_TO_INT(entities[shot_idx].x),
            FIX8_TO_INT(entities[shot_idx].y), 8);
        sfx_play(SFX_WEAK);
        retire_special_projectile();
        return;
    }
    if (eid == ENEMY_FOLD_STAR && enemy->state != 0) {
        sfx_play(SFX_HIT);
        fx_spawn(SPR_FX_IMPACT, 0,
            FIX8_TO_INT(entities[shot_idx].x),
            FIX8_TO_INT(entities[shot_idx].y), 5);
        retire_special_projectile();
        return;
    }
}

void stage_reaper_mortal_hit(u8 projectile_idx) BANKED {
    special_projectile_idx = projectile_idx;
    if (player.hp > 2) player.hp = 2;
    player.iframes = RUN_IS_EASY() ? 90 : 45;
    g_hitstop = 6;
    room_shake(2, 14);
    hud_redraw_hp();
    sfx_play(SFX_HURT);
    retire_special_projectile();
}

// Facet Ram facing uses cardinal dir8 values: 0 north, 2 east, 4 south,
// 6 west. Most turns are indifferent patrol choices; one quarter lean toward
// the champion's dominant axis, enough affinity to feel alert without
// becoming another homing enemy.
static u8 facet_choose_facing(entity_t *e) {
    u8 roll = rng_next_u8();
    if ((roll & 3) == 0) {
        i16 ex = FIX8_TO_INT(e->x) + 6;
        i16 ey = FIX8_TO_INT(e->y) + 7;
        i16 dx = (i16)player.x + 8 - ex;
        i16 dy = (i16)player.y + 8 - ey;
        i16 ax = dx < 0 ? -dx : dx;
        i16 ay = dy < 0 ? -dy : dy;
        if (ax >= ay) return dx >= 0 ? 2 : 6;
        return dy >= 0 ? 4 : 0;
    }
    return (u8)((roll & 3) << 1);
}

void facet_ram_update(entity_t *e) BANKED {
    u8 facing = (u8)(e->state & 6);

    if (e->state_timer) e->state_timer--;
    if (e->state_timer == 0) {
        e->state = facet_choose_facing(e);
        facing = (u8)(e->state & 6);
        e->state_timer = (u8)(56 + (rng_next_u8() & 0x3F));
    }

    // Deliberate cardinal patrol: one pixel every three frames. A blocked
    // face turns next frame instead of scraping forever along the obstacle.
    if (++e->ai_data[2] >= 3) {
        e->ai_data[2] = 0;
        if (!enemy_try_step(e, dir8_dx[facing], dir8_dy[facing]))
            e->state_timer = 0;
    }

    if (e->ai_data[1]) {
        e->ai_data[1]--;
        if (e->ai_data[1] == 14) {
            // A blink/click makes the high-damage reversal learnable. The
            // projectile still emerges behind the creature, contrary to the
            // familiar front-facing armored-patrol expectation.
            e->ai_data[7] = 10;
            sfx_play(SFX_TICK);
        }
    } else {
        i8 dx = dir8_dx[(u8)((facing + 4) & 7)];
        i8 dy = dir8_dy[(u8)((facing + 4) & 7)];
        i16 x = FIX8_TO_INT(e->x) + 4 + (i16)dx * 7;
        i16 y = FIX8_TO_INT(e->y) + 5 + (i16)dy * 7;
        u8 shot = projectile_spawn_enemy_v(x, y,
            (i8)(dx * 3), (i8)(dy * 3), 6); // three hearts before DEF
        if (shot != 0xFF) {
            entities[shot].palette = 4;
            entities[shot].hitbox = (u8)0x88;
        }
        e->ai_data[1] = (u8)(100 + (rng_next_u8() & 0x1F));
    }
}

// Reaper phase: 0 stalk/cooldown, 1 announced mortal cast, 2 recovery.
void stage_reaper_update(entity_t *e) BANKED {
    u8 phase = e->ai_data[2];
    if (phase == 0) {
        if (++e->ai_data[1] >= 4) {
            i16 ex = FIX8_TO_INT(e->x), ey = FIX8_TO_INT(e->y);
            i16 dx = (i16)player.x - ex, dy = (i16)player.y - ey;
            i16 ax = dx < 0 ? -dx : dx, ay = dy < 0 ? -dy : dy;
            e->ai_data[1] = 0;
            if (ax >= ay) {
                if (!enemy_try_step(e, dx >= 0 ? 1 : -1, 0) && dy)
                    enemy_try_step(e, 0, dy >= 0 ? 1 : -1);
            } else if (!enemy_try_step(e, 0, dy >= 0 ? 1 : -1) && dx) {
                enemy_try_step(e, dx >= 0 ? 1 : -1, 0);
            }
        }
        if (e->ai_data[3]) e->ai_data[3]--;
        if (e->ai_data[3] == 0) {
            i16 ex = FIX8_TO_INT(e->x) + 5;
            i16 ey = FIX8_TO_INT(e->y) + 6;
            i16 dx = (i16)player.x + 8 - ex;
            i16 dy = (i16)player.y + 8 - ey;
            i16 ax = dx < 0 ? -dx : dx, ay = dy < 0 ? -dy : dy;
            u8 dir;
            if (ax > (i16)(ay << 1)) dir = dx >= 0 ? 2 : 6;
            else if (ay > (i16)(ax << 1)) dir = dy >= 0 ? 4 : 0;
            else if (dx >= 0) dir = dy >= 0 ? 3 : 1;
            else dir = dy >= 0 ? 5 : 7;
            e->ai_data[4] = dir;
            e->ai_data[2] = 1;
            e->ai_data[3] = 42;
            e->palette = 4;
            e->ai_data[7] = 14;
            sfx_play(SFX_ROAR);
        }
        return;
    }

    if (phase == 1) {
        if (e->ai_data[3]) e->ai_data[3]--;
        if (e->ai_data[3] == 20 || e->ai_data[3] == 8) {
            fx_spawn(SPR_FX_IMPACT, 4,
                FIX8_TO_INT(e->x) + 4, FIX8_TO_INT(e->y) + 5, 10);
            sfx_play(SFX_TICK);
        }
        if (e->ai_data[3] == 0) {
            u8 dir = (u8)(e->ai_data[4] & 7);
            u8 shot = projectile_spawn_enemy_v(
                FIX8_TO_INT(e->x) + 4,
                FIX8_TO_INT(e->y) + 5,
                (i8)(dir8_dx[dir] * 2), (i8)(dir8_dy[dir] * 2), 1);
            if (shot != 0xFF) {
                entities[shot].sprite_tile = SPR_FX_MORTAL_SCYTHE;
                entities[shot].palette = 4;
                entities[shot].hitbox = (u8)0xAA;
                entities[shot].state_timer = 100;
                entities[shot].ai_data[6] = PROJ_AUX_MORTAL_SCYTHE;
            }
            e->palette = enemies[ENEMY_STAGE_REAPER].palette;
            e->ai_data[2] = 2;
            e->ai_data[3] = 88;
        }
        return;
    }

    if (e->ai_data[3]) e->ai_data[3]--;
    if (e->ai_data[3] == 0) {
        e->ai_data[2] = 0;
        e->ai_data[3] = 70;
    }
}
