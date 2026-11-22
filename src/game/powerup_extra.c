#pragma bank 29

// Phase 2-4 bodies: roulette, shrines, fire copies, Wingmates,
// Confusion stars. Pinned with relic_runtime in bank 29 so bank 31
// can hold elemental magic without opening a 1MB (bank 32) cartridge.
// Called through BANKED prototypes in powerup.h.

#include <gb/gb.h>
#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/powerup.h"
#include "game/wolfkin_sword.h"
#include "game/procgen.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "render/tiles.h"
#include "content.h"

#ifndef RIFT_DEN_SCREEN_BASE
#define RIFT_DEN_SCREEN_BASE 36
#endif

#define ROULETTE_LOCK_FRAMES 20
#define ROULETTE_MAX_FACES   6
#define SPR_STATUS_STAR      229

static u8 roulette_faces[ROULETTE_MAX_FACES];
static u8 roulette_count;
static u8 roulette_index;
static u8 roulette_lock;     // 0 spinning, 1..20 freeze, 0xFF done
static u8 roulette_flags;
static u8 roulette_slot;     // entity index, 0xFF if none

static u8 buddy_idx[2];
static u8 buddy_hp[2];
static i16 trail_x[4];
static i16 trail_y[4];
static u8 trail_p;

static u8 fire_count;        // Halo / Wingmates / Corvin-Vespine cadence
static u8 blast_cool;
static u8 volley_tag;
static u8 volley_boss_hits;
static u8 last_volley;

static const u8 face_tile[POWERUP_COUNT] = {
    0, SPR_ITEM_WARD_CHARM, SPR_ITEM_MANA_GEM, SPR_HEART,
    SPR_FX_SWING, SPR_SURGE_ORB, SPR_FX_SPEAR, SPR_ITEM_BLAST_SEED,
    SPR_FX_IMPACT
};
static const u8 face_pal[POWERUP_COUNT] = {
    0, 0x01, 0x06, 0x07, 0x02, 0x05, 0x04, 0x04, 0x01
};
// Silhouette buckets so adjacent roulette faces change shape, not just hue.
static const u8 face_shape[POWERUP_COUNT] = {
    0, 1, 2, 3, 4, 5, 6, 7, 8
};

static u8 free_slots(void) {
    u8 i, n = 0;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if (!(entities[i].flags & EF_ACTIVE)) n++;
    return n;
}

static u8 in_boss_room(void) {
    return (procgen_current_room_is_boss || run_state_is_boss_room()
        || run_state_is_miniboss()) ? 1 : 0;
}

static void refresh_world_live(void) {
    u8 i;
    powerup_world_live = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_PICKUP
            && (entities[i].ai_data[0] == PICKUP_ROULETTE
                || entities[i].ai_data[0] == PICKUP_POWERUP)) {
            powerup_world_live = 1;
            return;
        }
    }
}

static void shuffle_faces(u8 min_id, u8 max_id, u8 want) {
    u8 pool[8];
    u8 n = 0, i, j, tmp, id;
    for (id = min_id; id <= max_id && n < 8; ++id) pool[n++] = id;
    // Fisher-Yates with the run RNG.
    for (i = n; i > 1; --i) {
        j = rng_range(i);
        tmp = pool[i - 1];
        pool[i - 1] = pool[j];
        pool[j] = tmp;
    }
    if (want < 4) want = 4;
    if (want > n) want = n;
    if (want > ROULETTE_MAX_FACES) want = ROULETTE_MAX_FACES;
    roulette_count = want;
    for (i = 0; i < want; ++i) roulette_faces[i] = pool[i];
    // Adjacent (and wrap) faces must differ in palette and silhouette.
    for (i = 0; i < want; ++i) {
        u8 a = roulette_faces[i];
        u8 b = roulette_faces[(u8)((i + 1) % want)];
        if (face_pal[a] == face_pal[b] || face_shape[a] == face_shape[b]) {
            for (j = 0; j < n; ++j) {
                u8 c = pool[j];
                u8 used = 0, k;
                for (k = 0; k < want; ++k) if (roulette_faces[k] == c) used = 1;
                if (used) continue;
                if (face_pal[a] != face_pal[c] && face_shape[a] != face_shape[c]) {
                    roulette_faces[(u8)((i + 1) % want)] = c;
                    break;
                }
            }
        }
    }
}

static void apply_face(entity_t *e, u8 id) {
    if (id == POWERUP_NONE || id >= POWERUP_COUNT) return;
    e->ai_data[1] = id;
    e->ai_data[2] = id;     // latched visible face (lock rule)
    e->sprite_tile = face_tile[id];
    e->palette = (roulette_lock && roulette_lock < ROULETTE_LOCK_FRAMES
        && (roulette_lock & 1)) ? 0x00 : face_pal[id];
}

u8 powerup_spawn_roulette(fix8_t x, fix8_t y, u8 flags) BANKED {
    u8 idx, want;
    if (flags & ROULETTE_UNCOMMON)
        shuffle_faces(POWERUP_FORMATION, POWERUP_WINGMATES, 5);
    else {
        want = (u8)(4 + rng_range(3));
        shuffle_faces(POWERUP_AEGIS, POWERUP_WINGMATES, want);
    }
    idx = pickup_spawn(PICKUP_ROULETTE, x, y);
    if (idx == 0xFF) return 0xFF;
    roulette_index = 0;
    roulette_lock = 0;
    roulette_flags = flags;
    roulette_slot = idx;
    entities[idx].hitbox = 0x88;
    entities[idx].state_timer = 255;
    entities[idx].state = 0;
    apply_face(&entities[idx], roulette_faces[0]);
    powerup_note_drop();
    powerup_world_live = 1;
    return idx;
}

static i16 iabs16(i16 v) { return (v < 0) ? (i16)-v : v; }

static void roulette_tick_one(entity_t *e, u8 idx) {
    u8 period, near, shrine;
    i16 px, py, ex, ey, dx, dy;
    if (roulette_lock == 0xFF) return;
    px = (i16)player.x;
    py = (i16)player.y;
    ex = FIX8_TO_INT(e->x);
    ey = FIX8_TO_INT(e->y);
    dx = (i16)(px + 4 - ex);
    dy = (i16)(py + 4 - ey);
    shrine = (u8)(roulette_flags & ROULETTE_SHRINE);
    near = (iabs16(dx) < 24 && iabs16(dy) < 24) ? 1 : 0;
    // Skill window: drift toward the player once inside 24 px.
    if (near && !roulette_lock && (e->state_timer & 3) == 0) {
        if (dx > 1) e->x = (ppos_t)(e->x + FIX8(1));
        else if (dx < -1) e->x = (ppos_t)(e->x - FIX8(1));
        if (dy > 1) e->y = (ppos_t)(e->y + FIX8(1));
        else if (dy < -1) e->y = (ppos_t)(e->y - FIX8(1));
    }
    if (roulette_lock) {
        apply_face(e, e->ai_data[2]);
        roulette_lock++;
        if (roulette_lock > ROULETTE_LOCK_FRAMES) {
            u8 id = e->ai_data[2];
            roulette_lock = 0xFF;
            powerup_collect(id);
            if (shrine) {
                if (run_state.world_mode) {
                    u8 bit = (u8)(PU_SHRINE_RIFT_0 << run_state.riftwild_region);
                    run_state.powerup_shrines |= bit;
                } else {
                    run_state.powerup_shrines |= PU_SHRINE_DUNGEON;
                }
            }
            entity_kill(idx);
            roulette_slot = 0xFF;
            refresh_world_live();
        }
        return;
    }
    // Carbon: 8 frames/face Normal, 12 Easy. Shrine drum-roll at 12
    // frames/face once the hero is within 16 px.
    period = RUN_IS_EASY() ? 12 : 8;
    if (shrine && iabs16(dx) < 16 && iabs16(dy) < 16) period = 12;
    e->state++;
    if (e->state >= period) {
        e->state = 0;
        roulette_index++;
        if (roulette_index >= roulette_count) roulette_index = 0;
        apply_face(e, roulette_faces[roulette_index]);
    } else {
        // Keep the latched face in ai_data[2] matching the visible tile.
        e->ai_data[2] = e->ai_data[1];
    }
    (void)idx;
}

u8 powerup_roulette_try_lock(u8 idx) BANKED {
    entity_t *e;
    if (idx >= MAX_ENTITIES) return 0;
    e = &entities[idx];
    if (!(e->flags & EF_ACTIVE) || e->type != ENT_PICKUP
        || e->ai_data[0] != PICKUP_ROULETTE) return 0;
    if (roulette_slot != 0xFF && idx != roulette_slot) return 0;
    if (roulette_lock == 0xFF) return 1;
    if (!roulette_lock) {
        // Lock the face drawn this frame (already latched in ai_data[2]).
        roulette_lock = 1;
        roulette_slot = idx;
        sfx_play(SFX_TICK);
        apply_face(e, e->ai_data[2]);
    }
    return 0;
}

static void blink_capsule(entity_t *e) {
    // Last ~3 s of the pickup lifespan: blink the sprite.
    if (e->state_timer && e->state_timer < 45 && e->ai_data[1] < POWERUP_COUNT)
        e->palette = (e->state_timer & 4) ? 0x00 : face_pal[e->ai_data[1]];
}

static void world_tick(void) {
    u8 i, any = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_PICKUP) continue;
        if (e->ai_data[0] == PICKUP_ROULETTE) {
            any = 1;
            if (roulette_slot == 0xFF) roulette_slot = i;
            roulette_tick_one(e, i);
        } else if (e->ai_data[0] == PICKUP_POWERUP) {
            any = 1;
            blink_capsule(e);
        }
    }
    powerup_world_live = any;
    // Leaving a room mid-freeze used to leave roulette_lock set, so the
    // next capsule could auto-award or entity_kill a stale slot.
    if (!any) {
        roulette_lock = 0;
        roulette_slot = 0xFF;
    }
}

static void handle_test_cmd(void) {
    u8 cmd = powerup_test_cmd;
    powerup_test_cmd = 0;
    if (cmd == 1)
        powerup_spawn_roulette(FIX8((i16)player.x + 40),
            FIX8((i16)player.y), 0);
    else if (cmd == 2)
        powerup_spawn_roulette(FIX8((i16)player.x + 40),
            FIX8((i16)player.y),
            (u8)(ROULETTE_SHRINE | ROULETTE_UNCOMMON));
    else if (cmd == 3)
        powerup_spawn(POWERUP_WINGMATES,
            FIX8((i16)player.x + 24), FIX8((i16)player.y));
    else if (cmd == 4)
        powerup_place_room_shrine();
}

void powerup_tick_cooldown(void) BANKED {
    static u8 sub;
    if (powerup_test_cmd) handle_test_cmd();
    if (powerup_world_live || roulette_lock) world_tick();
    if (blast_cool) blast_cool--;
    if (!powerup_drop_cool) return;
    if (++sub < 8) return;
    sub = 0;
    powerup_drop_cool--;
}

static u8 copy_from(u8 primary, i16 x, i16 y, i8 vx, i8 vy, u8 dmg, u8 ttl) {
    u8 idx;
    entity_t *s, *e;
    if (primary >= MAX_ENTITIES) return 0xFF;
    s = &entities[primary];
    if (!(s->flags & EF_ACTIVE)) return 0xFF;
    idx = entity_spawn(ENT_PROJECTILE);
    if (idx == 0xFF) return 0xFF;
    e = &entities[idx];
    *e = *s;
    e->flags |= (u8)(EF_ACTIVE | EF_PLAYER_PROJ);
    e->x = FIX8(x);
    e->y = FIX8(y);
    e->vx = vx;
    e->vy = vy;
    e->damage = dmg ? dmg : 1;
    if (ttl) e->state_timer = ttl;
    e->ai_data[3] |= (u8)(PROJ_FLAG_CONVERGENCE | PROJ_FLAG_PU_COPY);
    return idx;
}

static u8 half_dmg(u8 d) {
    u8 v = (u8)((d + 1) >> 1);
    return v ? v : 1;
}

u8 powerup_try_collect(u8 slot) BANKED {
    entity_t *e = &entities[slot];
    if (e->ai_data[0] == PICKUP_ROULETTE) {
        powerup_roulette_try_lock(slot);
        return 1;
    }
    powerup_collect(e->ai_data[1]);
    if (e->ai_data[3] & ROULETTE_SHRINE) {
        if (run_state.world_mode)
            run_state.powerup_shrines |= (u8)(PU_SHRINE_RIFT_0
                << run_state.riftwild_region);
        else
            run_state.powerup_shrines |= PU_SHRINE_DUNGEON;
    }
    return 0;
}

void pickup_roll_elite_bonus(fix8_t x, fix8_t y) BANKED {
    // Elites already drop a guaranteed heart or coin; this is the doubled
    // Capsule chance (6% Normal, 8% Easy) on top.
    // Mix the chance and Capsule id from the run seed, clock and drop
    // cell so this roll does not consume the encounter RNG stream.
    // Attract-demo AI (and any later drops in the same room) stay on
    // the Phase 1 sequence.
    u8 r = (u8)run_state.run_seed
        ^ (u8)(run_state.run_seed >> 8)
        ^ (u8)(run_state.run_seed >> 16)
        ^ (u8)(run_state.run_seed >> 24)
        ^ (u8)run_state.run_timer
        ^ (u8)((u16)x * 3u)
        ^ (u8)((u16)y * 5u);
    u8 idmix;
    if (RUN_IS_EASY()) {
        if (r >= 20) return;
    } else if (r >= 15) {
        return;
    }
    idmix = (u8)(r * 37u + (u8)(run_state.run_seed >> 11));
    if (idmix < 179) r = (u8)(POWERUP_AEGIS + (idmix % 3));
    else if (idmix < 243) r = (u8)(POWERUP_FORMATION + ((u8)(idmix >> 2) & 3));
    else r = POWERUP_WINGMATES;
    powerup_try_spawn_capsule(r, x, y);
}


void powerup_echo_primary(u8 primary, u8 dir, u8 damage) BANKED {
    pickup_echo_primary(primary, dir, damage);
    if (powerup_id >= POWERUP_FORMATION)
        powerup_on_primary_fire(primary, dir, damage);
}

void powerup_on_primary_fire(u8 primary, u8 dir, u8 damage) BANKED {
    entity_t *s;
    u8 id = powerup_id;
    u8 dmg, i;
    i16 x, y;
    if (primary == 0xFF || id < POWERUP_FORMATION || id >= POWERUP_COUNT)
        return;
    if (dir >= 8) dir = 0;
    s = &entities[primary];
    x = FIX8_TO_INT(s->x);
    y = FIX8_TO_INT(s->y);
    if (++volley_tag == 0) volley_tag = 1;
    last_volley = volley_tag;
    volley_boss_hits = 0;
    fire_count++;
    dmg = half_dmg(damage);

    if (id == POWERUP_LONGREACH) {
        if (!(player.class_id == 0 && s->ai_data[6] == PROJ_AUX_WOLFKIN_FANG)) {
            u8 hb = s->hitbox;
            u8 w = (u8)((hb >> 4) & 0x0F);
            u8 h = (u8)(hb & 0x0F);
            w = (u8)(w << 1); if (w > 0x0F) w = 0x0F;
            h = (u8)(h << 1); if (h > 0x0F) h = 0x0F;
            s->hitbox = (u8)((w << 4) | h);
            if (s->vx || s->vy)
                s->state_timer = (u8)(s->state_timer + (s->state_timer >> 1));
        }
    }

    if (id == POWERUP_FORMATION && free_slots() > 8) {
        i8 ox = (i8)(dir8_dy[dir] * 8);
        i8 oy = (i8)(-dir8_dx[dir] * 8);
        u8 ttl = s->state_timer;
        if (player.class_id == 1 && ttl > 8) ttl = (u8)(ttl - 8); // Sauran: shorter
        if (player.class_id == 3) {
            // Picsean copies pop after 24 px.
            i8 svx = s->vx;
            i8 svy = s->vy;
            u8 spd = (u8)(svx < 0 ? (u8)(-svx) : (u8)svx);
            if (!spd) spd = (u8)(svy < 0 ? (u8)(-svy) : (u8)svy);
            if (spd) ttl = (u8)(24 / spd); if (ttl < 4) ttl = 4;
        }
        if (player.class_id == 0) {
            /* Claw Sword: two 2-damage beams at ±45°, ttl 28, 1 OAM each. */
            u8 ttl = 28;
            u8 a = wolfkin_beam_spawn((i16)player.x + 4, (i16)player.y + 4,
                (u8)((dir + 1) & 7), 2, ttl, PROJ_AUX_SWORD_PU);
            u8 b = wolfkin_beam_spawn((i16)player.x + 4, (i16)player.y + 4,
                (u8)((dir + 7) & 7), 2, ttl, PROJ_AUX_SWORD_PU);
            if (a != 0xFF) entities[a].ai_data[3] |= PROJ_FLAG_PU_COPY;
            if (b != 0xFF) entities[b].ai_data[3] |= PROJ_FLAG_PU_COPY;
        } else {
            u8 a = copy_from(primary, (i16)(x + ox), (i16)(y + oy),
                s->vx, s->vy, dmg, ttl);
            u8 b = copy_from(primary, (i16)(x - ox), (i16)(y - oy),
                s->vx, s->vy, dmg, ttl);
            if (player.class_id == 4) {
                if (a != 0xFF) entities[a].hp = 1;
                if (b != 0xFF) entities[b].hp = 1;
            }
        }
    }

    if (id == POWERUP_HALO && (fire_count % 3) == 0 && free_slots() > 10) {
        if (player.class_id == 0) {
            /* 4-way ring, alternating cardinals then diagonals. */
            static u8 halo_diag;
            u8 i, base = halo_diag ? 1 : 0;
            halo_diag = (u8)(halo_diag ? 0 : 1);
            for (i = 0; i < 4; ++i) {
                u8 d = (u8)((base + (u8)(i << 1)) & 7);
                u8 idx = wolfkin_beam_spawn((i16)player.x + 4, (i16)player.y + 4,
                    d, 2, 28, PROJ_AUX_SWORD_PU);
                if (idx != 0xFF) entities[idx].ai_data[3] |= PROJ_FLAG_PU_COPY;
            }
        } else {
            for (i = 0; i < 8; ++i) {
                i8 vx = (i8)(dir8_dx[i] * 2);
                i8 vy = (i8)(dir8_dy[i] * 2);
                // Range 40 px: ttl = 40 / speed.
                copy_from(primary, x, y, vx, vy, dmg, 20);
            }
        }
    }

    if (id == POWERUP_BLAST) {
        u8 every = (player.class_id == 2 || player.class_id == 4) ? 2 : 1;
        if ((fire_count % every) == 0 && blast_cool == 0) {
            if (g_player_attack_traits & ATTACK_TRAIT_SPLASH) {
                // Already owned: mark the shot so the bloom is bigger, not
                // doubled (projectile_spawn_splash reads powerup_id).
                s->ai_data[3] |= PROJ_FLAG_SPLASH;
            } else if (player.class_id == 2 || player.class_id == 4) {
                // Faster classes: a lobbed bomb on every 2nd shot.
                u8 bomb = copy_from(primary, x, y,
                    (i8)(s->vx >> 1), (i8)(s->vy >> 1),
                    dmg, 40);
                if (bomb != 0xFF)
                    entities[bomb].ai_data[3] |= PROJ_FLAG_SPLASH;
            } else {
                s->ai_data[3] |= PROJ_FLAG_SPLASH;
            }
            blast_cool = 20;
        }
    }

    if (id == POWERUP_WINGMATES && (fire_count & 1) && free_slots() > 8) {
        for (i = 0; i < 2; ++i) {
            u8 b = buddy_idx[i];
            i16 bx, by;
            if (b >= MAX_ENTITIES || !(entities[b].flags & EF_ACTIVE))
                continue;
            bx = FIX8_TO_INT(entities[b].x);
            by = FIX8_TO_INT(entities[b].y);
            if (player.class_id == 0) {
                u8 idx = wolfkin_beam_spawn(bx, by, dir, 2, 28, PROJ_AUX_SWORD_PU);
                if (idx != 0xFF) entities[idx].ai_data[3] |= PROJ_FLAG_PU_COPY;
            } else {
                copy_from(primary, bx, by, s->vx, s->vy, dmg, s->state_timer);
            }
        }
    }
}

// Blast Assist marks PROJ_FLAG_SPLASH; combat_shot_hit.c already blooms
// on that flag (same path as Blast Seed). This helper is kept for tests
// or a wall-expiry hook, and is safe to call more than once (clears the flag).
void powerup_on_proj_impact(u8 idx, i16 x, i16 y) BANKED {
    entity_t *e;
    u8 dmg;
    if (powerup_id != POWERUP_BLAST || idx >= MAX_ENTITIES) return;
    e = &entities[idx];
    if (!(e->ai_data[3] & PROJ_FLAG_SPLASH)) return;
    dmg = half_dmg(e->damage);
    if (g_player_attack_traits & ATTACK_TRAIT_SPLASH) dmg = (u8)(dmg + 1);
    projectile_spawn_splash(x, y, dmg, idx);
    e->ai_data[3] &= (u8)~PROJ_FLAG_SPLASH; // one bloom
}

u8 powerup_copy_hit_ok(void) BANKED {
    if (in_boss_room()) {
        if (volley_boss_hits >= 2) return 0;
        volley_boss_hits++;
    }
    return 1;
}

static u8 buddy_tile(void) {
    if (player.class_id == 2) return SPR_FX_IMPACT; // raven stand-in
    if (player.class_id == 4) return SPR_FX_SWING;  // hornet stand-in
    return SPR_SURGE_ORB;
}

static void spawn_buddy(u8 which) {
    u8 idx = entity_spawn(ENT_FX);
    i16 x = (i16)player.x + (which ? 16 : -16);
    i16 y = (i16)player.y - 4;
    if (idx == 0xFF) {
        buddy_idx[which] = 0xFF;
        return;
    }
    entities[idx].x = FIX8(x);
    entities[idx].y = FIX8(y);
    entities[idx].sprite_tile = buddy_tile();
    entities[idx].palette = 1;
    entities[idx].state_timer = 255;
    entities[idx].hitbox = 0x88;
    entities[idx].flags |= EF_ACTIVE;
    buddy_idx[which] = idx;
    buddy_hp[which] = 1;
}

void powerup_helpers_on_collect(u8 id) BANKED {
    u8 i;
    if (id != POWERUP_WINGMATES) return;
    for (i = 0; i < 4; ++i) {
        trail_x[i] = (i16)player.x;
        trail_y[i] = (i16)player.y;
    }
    trail_p = 0;
    spawn_buddy(0);
    spawn_buddy(1);
}

void powerup_helpers_on_end(void) BANKED {
    u8 i;
    for (i = 0; i < 2; ++i) {
        if (buddy_idx[i] < MAX_ENTITIES
            && (entities[buddy_idx[i]].flags & EF_ACTIVE)
            && entities[buddy_idx[i]].type == ENT_FX)
            entity_kill(buddy_idx[i]);
        buddy_idx[i] = 0xFF;
        buddy_hp[i] = 0;
    }
}

static u8 overlaps(entity_t *a, entity_t *b) {
    i16 ax = FIX8_TO_INT(a->x), ay = FIX8_TO_INT(a->y);
    i16 bx = FIX8_TO_INT(b->x), by = FIX8_TO_INT(b->y);
    i16 aw = (i16)(((a->hitbox >> 4) & 0x0F) + 4);
    i16 ah = (i16)((a->hitbox & 0x0F) + 4);
    i16 bw = (i16)(((b->hitbox >> 4) & 0x0F) + 4);
    i16 bh = (i16)((b->hitbox & 0x0F) + 4);
    if (ax + aw < bx || bx + bw < ax) return 0;
    if (ay + ah < by || by + bh < ay) return 0;
    return 1;
}

void powerup_helpers_tick(void) BANKED {
    u8 i, j, aged;
    if (powerup_id == POWERUP_LONGREACH && (trail_p & 1) == 0) {
        for (i = 0; i < MAX_ENTITIES; ++i) {
            entity_t *e = &entities[i];
            if ((e->flags & (EF_ACTIVE | EF_PLAYER_PROJ))
                == (EF_ACTIVE | EF_PLAYER_PROJ) && e->type == ENT_PROJECTILE)
                fx_spawn(SPR_FX_IMPACT, 5, FIX8_TO_INT(e->x),
                    FIX8_TO_INT(e->y), 4);
        }
    }
    if (powerup_id != POWERUP_WINGMATES) return;
    trail_x[trail_p] = (i16)player.x;
    trail_y[trail_p] = (i16)player.y;
    trail_p = (u8)((trail_p + 1) & 3);
    aged = trail_p; // 4 frames old
    for (i = 0; i < 2; ++i) {
        entity_t *b;
        i16 tx, ty;
        if (buddy_idx[i] >= MAX_ENTITIES
            || !(entities[buddy_idx[i]].flags & EF_ACTIVE)
            || entities[buddy_idx[i]].type != ENT_FX) {
            if (buddy_hp[i]) spawn_buddy(i);
            if (buddy_idx[i] >= MAX_ENTITIES
                || !(entities[buddy_idx[i]].flags & EF_ACTIVE)
                || entities[buddy_idx[i]].type != ENT_FX)
                continue;
        }
        b = &entities[buddy_idx[i]];
        tx = trail_x[aged] + (i ? 16 : -16);
        ty = trail_y[aged] - 4;
        b->x = FIX8(tx);
        b->y = FIX8(ty);
        b->state_timer = 255;
        if (in_boss_room()) continue; // no contact pop vs boss bodies
        for (j = 0; j < MAX_ENTITIES; ++j) {
            entity_t *h = &entities[j];
            if (j == buddy_idx[i]) continue;
            if (!(h->flags & EF_ACTIVE) || h->type != ENT_PROJECTILE) continue;
            if (h->flags & EF_PLAYER_PROJ) continue;
            if (!overlaps(b, h)) continue;
            entity_kill(j);
            entity_kill(buddy_idx[i]);
            buddy_idx[i] = 0xFF;
            buddy_hp[i] = 0;
            fx_spawn(SPR_FX_IMPACT, 1, tx, ty, 10);
            sfx_play(SFX_HIT);
            break;
        }
    }
    if (!buddy_hp[0] && !buddy_hp[1]) {
        // Both lost: the power-up ends (spec: 20 s or both lost).
        powerup_ticks = 1;
    }
}

void powerup_confusion_stars(void) BANKED {
    static u8 star_clock;
    i16 cx, cy;
    u8 ph;
    if (free_slots() <= 3) return; // status FX cap of 3, leave a slot
    star_clock++;
    if (star_clock & 3) return;
    cx = (i16)player.x + 4;
    cy = (i16)player.y - 6;
    ph = (u8)((star_clock >> 3) & 3);
    // Orbit 8 px, 32-frame period, alternating palettes 6 and 5.
    if (ph == 0) fx_spawn(SPR_STATUS_STAR, 6, cx + 8, cy, 8);
    else if (ph == 2) fx_spawn(SPR_STATUS_STAR, 5, cx - 8, cy, 8);
}

static u8 shrine_reserved_cell(u8 cell) {
    if (cell == run_state_dungeon_entry_cell()) return 1;
    if (cell == run_state_dungeon_cache_cell()) return 1;
    if (cell == run_state.mission_trial_cell) return 1;
    if (cell == run_state.mission_sigil_cell) return 1;
    if (cell == run_state.mission_warden_cell) return 1;
    if (cell == run_state.mission_waystone_cell) return 1;
    if (cell == run_state.mission_deep_warden_cell) return 1;
    return 0;
}

// 0xFE = not yet computed this dungeon. 0xFF = no eligible dead-end.
static u8 shrine_cell_cache = 0xFE;
static u8 shrine_cell_beaten;
static u32 shrine_cell_seed;

static u8 dungeon_shrine_cell(void) {
    u8 size, start, tries, dir, found;
    if (shrine_cell_cache != 0xFE
        && shrine_cell_beaten == run_state.bosses_beaten
        && shrine_cell_seed == run_state.run_seed)
        return shrine_cell_cache;
    found = 0xFF;
    size = run_state_dungeon_size();
    if (size && size != 0xFF) {
        start = (u8)((u8)(run_state.run_seed >> 8) + run_state.bosses_beaten * 17);
        for (tries = 0; tries < size; ++tries) {
            u8 c = (u8)((start + tries) % size);
            u8 degree = 0;
            if (shrine_reserved_cell(c)) continue;
            for (dir = 0; dir < 4; ++dir)
                if (run_state_dungeon_cell_neighbor(c, dir) != 0xFF) degree++;
            if (degree == 1) { found = c; break; }
        }
    }
    shrine_cell_cache = found;
    shrine_cell_beaten = run_state.bosses_beaten;
    shrine_cell_seed = run_state.run_seed;
    return found;
}

static u8 rift_shrine_screen(void) {
    u8 start = (u8)((u8)run_state.run_seed + run_state.riftwild_region * 29);
    u8 tries;
    for (tries = 0; tries < 36; ++tries) {
        u8 s = (u8)((start + tries) % 36);
        if (s >= RIFT_DEN_SCREEN_BASE) continue;
        if (s == 0) continue;
        return s;
    }
    return 0xFF;
}

void powerup_place_room_shrine(void) BANKED {
    if (run_state.world_mode) {
        u8 bit, screen;
        if (run_state.riftwild_region > 2) return;
        bit = (u8)(PU_SHRINE_RIFT_0 << run_state.riftwild_region);
        if (run_state.powerup_shrines & bit) return;
        screen = rift_shrine_screen();
        if (screen == 0xFF || run_state.world_screen != screen) return;
        // Fixed seed-chosen Rare: Wingmates Capsule on a centre pedestal.
        {
            u8 idx = powerup_spawn(POWERUP_WINGMATES, FIX8(80), FIX8(72));
            if (idx != 0xFF)
                entities[idx].ai_data[3] = ROULETTE_SHRINE;
        }
        powerup_world_live = 1;
        return;
    }
    if (run_state.powerup_shrines & PU_SHRINE_DUNGEON) return;
    // The entry cell is reserved, so it can never host the shrine. Skip the
    // neighbor walk on foyer/stage-start entry: that search is too heavy to
    // run inside room_enter (it delayed the stage-fade pop by ~10 frames).
    if (run_state_dungeon_local() == run_state_dungeon_entry_cell()) return;
    if (run_state_dungeon_local() != dungeon_shrine_cell()) return;
    powerup_spawn_roulette(FIX8(80), FIX8(72),
        (u8)(ROULETTE_SHRINE | ROULETTE_UNCOMMON));
}

u8 powerup_shrine_map_mark(u8 cell) BANKED {
    if (run_state.world_mode) return 0;
    if (run_state.powerup_shrines & PU_SHRINE_DUNGEON) return 0;
    return (cell == dungeon_shrine_cell()) ? 1 : 0;
}
