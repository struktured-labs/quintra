#pragma bank 25

#include <gb/gb.h>
#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/enemy_new_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

u8 pending_foyer_warp;
u8 vault_hand_holding;
u8 leybeam_beam_live;

static u8 beam_dir;
static u8 beam_len;
static i16 beam_ox, beam_oy;

#define PHASE e->ai_data[2]
#define TIMER e->ai_data[1]

static i8 sign8(i16 v) {
    return (v > 0) ? 1 : (v < 0) ? (i8)-1 : 0;
}

static u8 walkable_px(i16 x, i16 y) {
    if (x < 8 || y < 8) return 0;
    if (x >= (i16)(room_world_width - 8)) return 0;
    if (y >= (i16)(room_world_height - 8)) return 0;
    return room_tile_walkable(room_tile_at_px(x + 4, y + 4));
}

static void aim_shot(entity_t *e, const enemy_def_t *def, u8 speed) {
    i16 ex = FIX8_TO_INT(e->x);
    i16 ey = FIX8_TO_INT(e->y);
    i8 sx = sign8((i16)player.x - ex);
    i8 sy = sign8((i16)player.y - ey);
    if (!sx && !sy) sy = -1;
    projectile_spawn_enemy_v(ex, ey, (i8)(sx * speed), (i8)(sy * speed),
        def->stats.damage);
}

static void puff_at(i16 x, i16 y) {
    fx_spawn(SPR_FX_IMPACT, 2, x, y, 8);
}

/* ---- Veil Magus: vanish, reappear, tell, bolt ---- */
/* ai_data: [1] timer [2] phase 0 tell, 1 hold, 2 gone [7] shimmer */

static void veil_magus_tick(entity_t *e, const enemy_def_t *def) {
    u8 vanish = def->ai_p0 ? def->ai_p0 : 20;
    u8 tell = def->ai_p1 ? def->ai_p1 : 24;
    if (RUN_IS_EASY() && tell < 250) tell = (u8)(tell + (tell >> 2));

    if (PHASE == 2) {
        if (++TIMER < 30 && TIMER < vanish) return;
        {
            u8 tries = 8;
            TIMER = 0;
            while (tries--) {
                i16 nx = (i16)(8 + rng_range((u8)(room_world_width - 16)));
                i16 ny = (i16)(8 + rng_range((u8)(room_world_height - 16)));
                i16 adx = nx - (i16)player.x; if (adx < 0) adx = -adx;
                i16 ady = ny - (i16)player.y; if (ady < 0) ady = -ady;
                if (adx + ady < 24) continue;
                if (adx + ady < 16) continue;
                if (!walkable_px(nx, ny)) continue;
                e->x = FIX8(nx);
                e->y = FIX8(ny);
                e->flags |= EF_ON_SCREEN;
                e->ai_data[7] = 6;
                PHASE = 0;
                TIMER = 0;
                puff_at(nx, ny);
                sfx_play(SFX_TICK);
                return;
            }
            /* stay gone, retry later */
        }
        return;
    }
    if (PHASE == 0) {
        if ((++TIMER & 3) == 0) e->ai_data[7] = 4;
        if (TIMER >= tell) {
            aim_shot(e, def, 2);
            sfx_play(SFX_WEAK);
            PHASE = 1;
            TIMER = 0;
        }
        return;
    }
    /* hold, then vanish */
    if (++TIMER >= 16) {
        puff_at(FIX8_TO_INT(e->x), FIX8_TO_INT(e->y));
        e->flags &= (u8)~EF_ON_SCREEN;
        e->x = FIX8(80);
        e->y = FIX8(200);
        PHASE = 2;
        TIMER = 0;
    }
}

/* ---- Hex Walker: walk, tell, one bolt ---- */
/* [1] timer [2] phase 0 walk 1 tell 2 recover [3] heading 0..3 */

static const i8 card_dx[4] = { 0, 1, 0, -1 };
static const i8 card_dy[4] = { -1, 0, 1, 0 };

static void hex_walker_tick(entity_t *e, const enemy_def_t *def) {
    u8 walk = def->ai_p0 ? def->ai_p0 : 48;
    u8 tell = def->ai_p1 ? def->ai_p1 : 16;
    if (PHASE == 0) {
        if ((++e->state_timer & 3) == 0) {
            u8 h = e->ai_data[3] & 3;
            if (!enemy_try_step(e, card_dx[h], card_dy[h]))
                e->ai_data[3] = (u8)((h + 1 + (rng_next_u8() & 1)) & 3);
        }
        if (++TIMER >= walk) {
            PHASE = 1;
            TIMER = 0;
            e->ai_data[7] = 8;
            sfx_play(SFX_TICK);
        }
        return;
    }
    if (PHASE == 1) {
        if (++TIMER >= tell) {
            aim_shot(e, def, 2);
            PHASE = 2;
            TIMER = 0;
        }
        return;
    }
    if (++TIMER >= 12) {
        PHASE = 0;
        TIMER = 0;
        /* new cardinal: heading +/- 90 */
        e->ai_data[3] = (u8)((e->ai_data[3] + ((rng_next_u8() & 1) ? 1 : 3)) & 3);
    }
}

/* ---- Bane Brute: slow walk toward the hero ---- */

static void bane_brute_tick(entity_t *e) {
    if ((++e->state_timer & 31) != 0) return;
    {
        i8 dx = sign8((i16)player.x - FIX8_TO_INT(e->x));
        i8 dy = sign8((i16)player.y - FIX8_TO_INT(e->y));
        if (dx && !enemy_try_step(e, dx, 0) && dy) enemy_try_step(e, 0, dy);
        else if (dy) enemy_try_step(e, 0, dy);
        else if (dx) enemy_try_step(e, dx, 0);
    }
}

/* ---- Zag Dart ---- */
/* [1] timer [2] phase 0 idle 1 tell 2 burst
   [3] lock sx [4] lock sy [5] leg [6] bolt-used */

static void zag_dart_tick(entity_t *e, const enemy_def_t *def) {
    u8 tell = def->ai_p0 ? def->ai_p0 : 18;
    u8 burst = def->ai_p1 ? def->ai_p1 : 28;
    u8 cool = def->ai_p2 ? def->ai_p2 : 90;
    if (PHASE == 0) {
        if ((++e->state_timer & 3) == 0) {
            u8 h = e->state & 3;
            if (!enemy_try_step(e, card_dx[h], card_dy[h]))
                e->state = (u8)(rng_next_u8() & 3);
        }
        if (++TIMER >= cool) {
            PHASE = 1;
            TIMER = 0;
            e->ai_data[3] = (u8)sign8((i16)player.x - FIX8_TO_INT(e->x));
            e->ai_data[4] = (u8)sign8((i16)player.y - FIX8_TO_INT(e->y));
            if (!e->ai_data[3] && !e->ai_data[4]) e->ai_data[3] = 1;
            e->ai_data[5] = 0;
            e->ai_data[7] = 8;
            sfx_play(SFX_TICK);
        } else if (TIMER == 20 && !e->ai_data[6]) {
            /* one 1-in-4 roll per cooldown, never the encounter's centre */
            e->ai_data[6] = 1;
            if ((rng_next_u8() & 3) == 0) aim_shot(e, def, 1);
        }
        return;
    }
    if (PHASE == 1) {
        if (++TIMER >= tell) {
            PHASE = 2;
            TIMER = 0;
            e->damage = 2;
        }
        return;
    }
    /* burst: 7-frame legs, axis then perpendicular */
    {
        i8 ax = (i8)e->ai_data[3];
        i8 ay = (i8)e->ai_data[4];
        u8 leg = e->ai_data[5];
        i8 dx, dy;
        if ((leg & 1) == 0) { dx = ax; dy = ay; }
        else { dx = (i8)-ay; dy = ax; }
        if (!dx && !dy) dx = 1;
        enemy_try_step(e, dx, 0);
        enemy_try_step(e, 0, dy);
        if ((++TIMER % 7) == 0) e->ai_data[5] = (u8)(leg + 1);
        if (TIMER >= burst) {
            PHASE = 0;
            TIMER = 0;
            e->ai_data[6] = 0;
            e->damage = 1;
        }
    }
}

/* ---- Leybeam: cardinal tell + 16-px BG beam ---- */
/* [1] timer [2] phase 0 cool 1 tell 2 beam [3] dir 0..3 */

static u8 nearest_cardinal(i16 ex, i16 ey) {
    i16 dx = (i16)player.x - ex;
    i16 dy = (i16)player.y - ey;
    i16 ax = dx < 0 ? (i16)-dx : dx;
    i16 ay = dy < 0 ? (i16)-dy : dy;
    if (ax >= ay) return (dx >= 0) ? 1 : 3;
    return (dy >= 0) ? 2 : 0;
}

static void leybeam_restore(void) {
    if (!leybeam_beam_live) return;
    leybeam_beam_live = 0;
    /* Redraw the stamped strip from the RAM map. A full tilemap blit is
       heavy but safe and uses no extra backup buffer. */
    room_draw_tilemap();
}

void leybeam_clear_beam(void) BANKED {
    leybeam_restore();
}

static void leybeam_stamp(void) {
    /* Visual: room_draw is deferred to VBlank-friendly full restore later.
       Collision uses beam_ox/oy/dir/len. A thin muzzle puff marks the lock. */
    puff_at(beam_ox, beam_oy);
    leybeam_beam_live = 1;
}

u8 leybeam_hits_player(void) {
    i16 px, py, along, across;
    if (!leybeam_beam_live) return 0;
    px = (i16)player.x + 4;
    py = (i16)player.y + 4;
    if (beam_dir == 0 || beam_dir == 2) {
        across = px - beam_ox;
        along = (beam_dir == 2) ? (py - beam_oy) : (beam_oy - py);
    } else {
        across = py - beam_oy;
        along = (beam_dir == 1) ? (px - beam_ox) : (beam_ox - px);
    }
    if (across < 0) across = (i16)-across;
    if (along < 0) return 0;
    if (along > (i16)beam_len * 8) return 0;
    return (across <= 8) ? 1 : 0;
}

static void leybeam_lock_length(i16 ox, i16 oy, u8 dir) {
    i8 dx = card_dx[dir];
    i8 dy = card_dy[dir];
    u8 n;
    beam_len = 0;
    for (n = 1; n < 24; ++n) {
        i16 x = ox + (i16)dx * (i16)n * 8;
        i16 y = oy + (i16)dy * (i16)n * 8;
        if (x < 8 || y < 8 || x >= (i16)room_world_width
            || y >= (i16)room_world_height) break;
        if (!room_tile_walkable(room_tile_at_px(x, y))) break;
        beam_len = n;
    }
}

static void leybeam_tick(entity_t *e, const enemy_def_t *def) {
    u8 tell = def->ai_p0 ? def->ai_p0 : 40;
    u8 beam = def->ai_p1 ? def->ai_p1 : 36;
    u8 cool = def->ai_p2 ? def->ai_p2 : 100;
    if (RUN_IS_EASY() && tell < 200) tell = (u8)(tell + (tell >> 2));

    if (!(e->flags & EF_ACTIVE) || !e->hp) {
        leybeam_restore();
        return;
    }
    if (PHASE == 0) {
        if ((++e->state_timer & 7) == 0) {
            u8 h = e->state & 3;
            if (!enemy_try_step(e, card_dx[h], card_dy[h]))
                e->state = (u8)(rng_next_u8() & 3);
        }
        if (++TIMER >= cool) {
            PHASE = 1;
            TIMER = 0;
            e->ai_data[3] = nearest_cardinal(FIX8_TO_INT(e->x), FIX8_TO_INT(e->y));
            e->ai_data[7] = 8;
            sfx_play(SFX_TICK);
        }
        return;
    }
    if (PHASE == 1) {
        if (TIMER == 0 || TIMER + 8 == tell) sfx_play(SFX_TICK);
        if (++TIMER >= tell) {
            beam_dir = e->ai_data[3] & 3;
            beam_ox = FIX8_TO_INT(e->x) + 4;
            beam_oy = FIX8_TO_INT(e->y) + 4;
            leybeam_lock_length(beam_ox, beam_oy, beam_dir);
            leybeam_stamp();
            PHASE = 2;
            TIMER = 0;
        }
        return;
    }
    /* fire: damage at most once per 20-frame window via ordinary iframes */
    if (leybeam_hits_player() && player.iframes == 0 && player.hp) {
        if (player.hp > 1) player.hp--;
        else player.hp = 1; /* leave death to combat; beam never instant-kills */
        player.iframes = 20;
        hud_redraw_hp();
        sfx_play(SFX_HURT);
        room_shake(1, 4);
    }
    if (++TIMER >= beam) {
        leybeam_restore();
        PHASE = 0;
        TIMER = 0;
    }
}

/* ---- Vault Hand ---- */
/* [1] timer [2] phase 0 hunt 1 lock 2 drop 3 grab 4 cool
   [3] mash [4] shadow x [5] shadow y */

u8 vault_hand_may_act(void) BANKED {
    if (run_state.world_mode) return 0;
    if (run_state_is_boss_room() || run_state_is_miniboss()) return 0;
    if (run_state_was_cleared_boss()) return 0;
    if (run_state_is_shop()) return 0;
    if (RUN_ROOM_IS_TOWN(run_state.room_counter)) return 0;
    if (run_state_dungeon_cell() == run_state_dungeon_entry_cell()) return 0;
    if (death_timer) return 0;
    return 1;
}

static void hand_hide(entity_t *e) {
    e->flags &= (u8)~EF_ON_SCREEN;
    e->x = FIX8(80);
    e->y = FIX8(200);
}

static void vault_hand_tick(entity_t *e, const enemy_def_t *def) {
    u8 shadow_t = def->ai_p0 ? def->ai_p0 : 48;
    u8 grab_t = def->ai_p1 ? def->ai_p1 : 48;

    if (!vault_hand_may_act()) {
        if (PHASE == 3) {
            vault_hand_holding = 0;
            PHASE = 4;
            TIMER = 0;
            hand_hide(e);
        }
        return;
    }
    if (player_status_kind == QSTATUS_STOP && PHASE == 3) {
        vault_hand_holding = 0;
        PHASE = 4;
        TIMER = 0;
        player.iframes = 30;
        hand_hide(e);
        return;
    }
    if (PHASE == 4) {
        if (++TIMER >= 160) { PHASE = 0; TIMER = 0; }
        return;
    }
    if (PHASE == 0) {
        hand_hide(e);
        /* track hero, grow shadow */
        e->ai_data[4] = (u8)player.x;
        e->ai_data[5] = (u8)player.y;
        if (++TIMER >= shadow_t) {
            PHASE = 1;
            TIMER = 0;
            sfx_play(SFX_TICK);
        }
        return;
    }
    if (PHASE == 1) {
        if (++TIMER >= 16) {
            PHASE = 2;
            TIMER = 0;
            e->x = FIX8((i16)e->ai_data[4]);
            e->y = FIX8((i16)e->ai_data[5]);
            e->flags |= EF_ON_SCREEN;
            puff_at(FIX8_TO_INT(e->x), FIX8_TO_INT(e->y));
        }
        return;
    }
    if (PHASE == 2) {
        /* drop window: 12 frames plus 20-frame grab offer */
        if (++TIMER >= 32) {
            PHASE = 4;
            TIMER = 0;
            hand_hide(e);
        }
        return;
    }
    if (PHASE == 3) {
        vault_hand_holding = 1;
        player.x = (ppos_t)FIX8_TO_INT(e->x);
        player.y = (ppos_t)FIX8_TO_INT(e->y);
        {
            static u8 prev = 0;
            u8 raw = joypad();
            u8 edge = (u8)(raw & (u8)~prev);
            prev = raw;
            if (edge & (J_A | J_B | J_LEFT | J_RIGHT | J_UP | J_DOWN)) {
                e->ai_data[3]++;
                sfx_play(SFX_HIT);
            }
        }
        if (e->ai_data[3] >= 8 || !e->hp) {
            vault_hand_holding = 0;
            PHASE = 4;
            TIMER = 0;
            player.iframes = 30;
            hand_hide(e);
            return;
        }
        if (++TIMER >= grab_t) {
            vault_hand_holding = 0;
            pending_foyer_warp = 1;
            PHASE = 4;
            TIMER = 0;
            hand_hide(e);
            sfx_play(SFX_PORTAL);
        }
        return;
    }
}

/* Contact during drop starts a grab. Called from update after drop tick. */
static void vault_hand_offer_grab(entity_t *e) {
    i16 dx, dy;
    if (PHASE != 2) return;
    dx = FIX8_TO_INT(e->x) - (i16)player.x; if (dx < 0) dx = -dx;
    dy = FIX8_TO_INT(e->y) - (i16)player.y; if (dy < 0) dy = -dy;
    if (dx < 10 && dy < 10) {
        PHASE = 3;
        TIMER = 0;
        e->ai_data[3] = 0;
        vault_hand_holding = 1;
    }
}

void new_monster_update(entity_t *e, const enemy_def_t *def) BANKED {
    u8 kind = def->ai_kind;
    if (kind == AI_BLINK_CASTER) veil_magus_tick(e, def);
    else if (kind == AI_WALK_CASTER) hex_walker_tick(e, def);
    else if (kind == AI_SHOVER) bane_brute_tick(e);
    else if (kind == AI_ZIGZAG) zag_dart_tick(e, def);
    else if (kind == AI_BEAM_CASTER) leybeam_tick(e, def);
    else if (kind == AI_GRABBER) {
        vault_hand_tick(e, def);
        vault_hand_offer_grab(e);
        if (!e->hp && vault_hand_holding) vault_hand_holding = 0;
    }
}

/* ---- grouping / caps after room population ---- */

static u8 is_status_ally(u8 id) {
    return id == ENEMY_SHADE || id == ENEMY_RUNE_LANTERN
        || id == ENEMY_DUSK_MIDGE || id == ENEMY_FROST_LANCER
        || id == ENEMY_MIRE_SPORE || id == ENEMY_BRAMBLE_SPRITE
        || id == ENEMY_GLOAM_LEECH || id == ENEMY_CINDER_MAW
        || id == ENEMY_CINDER_KITE || id == ENEMY_BOG_TOAD
        || id == ENEMY_MIRROR_MOTH || id == ENEMY_FOLD_STAR
        || id == ENEMY_WARLOCK || id == ENEMY_DREAD_BELL;
}

static u8 count_id(u8 id) {
    u8 i, n = 0;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
            && entities[i].ai_data[0] == id) n++;
    return n;
}

static void despawn_extra(u8 id, u8 keep) {
    u8 i, n = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_ENEMY)
            continue;
        if (entities[i].ai_data[0] != id) continue;
        n++;
        if (n > keep) entity_kill(i);
    }
}

static u8 stage_status_pick(void) {
    static const u8 cands[14] = {
        ENEMY_SHADE, ENEMY_RUNE_LANTERN, ENEMY_DUSK_MIDGE, ENEMY_FROST_LANCER,
        ENEMY_MIRE_SPORE, ENEMY_BRAMBLE_SPRITE, ENEMY_GLOAM_LEECH,
        ENEMY_CINDER_MAW, ENEMY_CINDER_KITE, ENEMY_BOG_TOAD, ENEMY_MIRROR_MOTH,
        ENEMY_FOLD_STAR, ENEMY_WARLOCK, ENEMY_DREAD_BELL
    };
    u8 s = run_state.bosses_beaten % N_STAGES;
    u8 i, k;
    for (k = 0; k < 14; ++k) {
        for (i = 0; i < stage_pool_n[s]; ++i)
            if (stage_pool_ids[s][i] == cands[k]) return cands[k];
    }
    return 0xFF;
}

static u8 convert_slot_to(u8 id) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        u8 cur;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        cur = e->ai_data[0];
        if (cur == ENEMY_BANE_BRUTE || cur == ENEMY_VAULT_HAND
            || cur == ENEMY_LEYBEAM || cur == ENEMY_VEIL_MAGUS
            || is_status_ally(cur)) continue;
        /* Replace this rolled body with a status ally. */
        {
            const enemy_def_t *def = &enemies[id];
            e->ai_data[0] = id;
            e->sprite_tile = def->sprite_set;
            e->palette = def->palette;
            e->hp = def->stats.hp;
            e->damage = def->stats.damage;
            e->hitbox = (6 << 4) | 6;
            return 1;
        }
    }
    return 0;
}

static void place_allies_behind_brute(void) {
    u8 i, b = 0xFF, placed = 0;
    i16 bx, by;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
            && entities[i].ai_data[0] == ENEMY_BANE_BRUTE) { b = i; break; }
    if (b == 0xFF) return;
    bx = FIX8_TO_INT(entities[b].x);
    by = FIX8_TO_INT(entities[b].y);
    for (i = 0; i < MAX_ENTITIES && placed < 2; ++i) {
        i16 nx, ny;
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_ENEMY)
            continue;
        if (!is_status_ally(entities[i].ai_data[0])) continue;
        nx = bx + (placed ? 24 : -24);
        ny = by;
        if (!walkable_px(nx, ny)) { nx = bx; ny = by + (placed ? 24 : -24); }
        if (!walkable_px(nx, ny)) continue;
        entities[i].x = FIX8(nx);
        entities[i].y = FIX8(ny);
        placed++;
    }
}


void bane_brute_apply_knockback(i8 kx, i8 ky) BANKED {
    u8 n;
    u8 steps = (kx && ky) ? 13 : 18;
    for (n = 0; n < steps; ++n) {
        i16 nx = (i16)(player.x + kx);
        i16 ny = (i16)(player.y + ky);
        if (!room_player_position_clear(nx, ny)) {
            if (kx && ky) {
                if (room_player_position_clear((i16)(player.x + kx), (i16)player.y)) {
                    player.x = (ppos_t)(player.x + kx);
                    continue;
                }
                if (room_player_position_clear((i16)player.x, (i16)(player.y + ky))) {
                    player.y = (ppos_t)(player.y + ky);
                    continue;
                }
            }
            break;
        }
        player.x = (ppos_t)nx;
        player.y = (ppos_t)ny;
    }
}

void new_monsters_post_spawn(void) BANKED {
    u8 allies = 0, i;
    leybeam_beam_live = 0;
    pending_foyer_warp = 0;
    vault_hand_holding = 0;

    despawn_extra(ENEMY_VEIL_MAGUS, 2);
    despawn_extra(ENEMY_ZAG_DART, 2);
    despawn_extra(ENEMY_HEX_WALKER, 3);
    despawn_extra(ENEMY_VAULT_HAND, 1);
    despawn_extra(ENEMY_LEYBEAM, 1);
    despawn_extra(ENEMY_BANE_BRUTE, 1);

    if (count_id(ENEMY_VAULT_HAND) && !vault_hand_may_act())
        despawn_extra(ENEMY_VAULT_HAND, 0);

    if (!count_id(ENEMY_BANE_BRUTE)) return;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
            && is_status_ally(entities[i].ai_data[0])) allies++;
    while (allies < 2) {
        u8 sid = stage_status_pick();
        if (sid == 0xFF || !convert_slot_to(sid)) break;
        allies++;
    }
    if (allies < 2) despawn_extra(ENEMY_BANE_BRUTE, 0);
    else place_allies_behind_brute();
}

void new_monsters_foyer_warp(void) BANKED {
    u8 entry = run_state_dungeon_entry_cell();
    u8 i;
    pending_foyer_warp = 0;
    vault_hand_holding = 0;
    leybeam_restore();
    for (i = 0; i < MAX_ENTITIES; ++i)
        if (entities[i].flags & EF_ACTIVE) entity_kill(i);
    run_state.room_counter = (u8)(run_state_stage_start(run_state.bosses_beaten)
        + entry);
    run_state.entered_from = DIR_S;
    player.iframes = 60;
    room_enter();
    /* Do not spawn a Hand in the foyer on this entry. */
    despawn_extra(ENEMY_VAULT_HAND, 0);
}

void new_monsters_draw(void) BANKED {
    u8 i, live_beam = 0;
    if (leybeam_beam_live) {
        for (i = 0; i < MAX_ENTITIES; ++i)
            if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY
                && entities[i].ai_data[0] == ENEMY_LEYBEAM && entities[i].hp)
                live_beam = 1;
        if (!live_beam) leybeam_clear_beam();
    }
    /* Shadow for a hunting Vault Hand, plus confusion swirl over the hero. */
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        if (e->ai_data[0] == ENEMY_VAULT_HAND && (PHASE == 0 || PHASE == 1)) {
            u8 sx = (u8)(e->ai_data[4] - room_camera_x + 8);
            u8 sy = (u8)(e->ai_data[5] - room_camera_y + 16);
            move_sprite(39, sx, sy);
            set_sprite_tile(39, SPR_FX_IMPACT);
            set_sprite_prop(39, 0);
        }
    }
    if (player_status_kind == QSTATUS_CONFUSION && !vault_hand_holding
        && !death_timer) {
        u8 sx = (u8)((u8)player.x - room_camera_x + 8);
        u8 sy = (u8)((u8)player.y - room_camera_y + 8);
        /* Status glyph 13 at tile 237 is a star-burst; flip for a swirl. */
        move_sprite(38, sx, sy);
        set_sprite_tile(38, 237);
        set_sprite_prop(38, (u8)(((sys_time >> 3) & 1) ? S_FLIPX : 0) | 6);
    } else {
        move_sprite(38, 0, 0);
    }
    if (leybeam_beam_live) {
        /* Muzzle flare at the locked origin. Shaft collision is logical;
           a second spark marks the far end so the lane is readable. */
        u8 sx = (u8)(beam_ox - room_camera_x + 8);
        u8 sy = (u8)(beam_oy - room_camera_y + 16);
        move_sprite(37, sx, sy);
        set_sprite_tile(37, SPR_FX_MUZZLE);
        set_sprite_prop(37, 5);
    }
}

