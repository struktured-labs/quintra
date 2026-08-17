#pragma bank 3
#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/projectile.h"
#include "game/player.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "render/tiles.h"
#include "content.h"

// Element bitmask stamped onto the next player shot (1=Fire 2=Ice 4=Lit
// 8=Shadow 16=Poison). Set by the fire code per class/weapon; combat
// doubles damage when it matches the target's weakness.
u8 g_shot_element;
u8 g_player_ricochet;
u8 g_player_attack_traits;

// Keep the reversal out of projectile_update(). SDCC otherwise expands that
// dense per-shot function's stack frame from 16 to 25 bytes and spills
// registers throughout the hostile-bullet hot path, even though hostile shots
// can never ricochet.
static void projectile_ricochet(entity_t *e, i16 px, i16 py) {
    e->x = (ppos_t)(e->x - e->vx);
    e->y = (ppos_t)(e->y - e->vy);
    e->vx = (i8)-e->vx;
    e->vy = (i8)-e->vy;
    // Preserve an independent Convergence chord tag if this rebound came
    // from the A+B volley; only the one-use wall charge is consumed.
    e->ai_data[3] &= (u8)~PROJ_FLAG_RICOCHET;
    fx_spawn(SPR_FX_IMPACT, 0x06, px, py, 8);
    sfx_play(SFX_HIT);
}

u8 projectile_spawn_player(i8 dx, i8 dy, u8 damage, u8 kind) BANKED {
    u8 idx;
    entity_t *e;
    u8 speed, ttl, pierce;
    if (dx == 0 && dy == 0) return 0xFF;

    // Kind shapes the projectile's physics:
    switch (kind) {
        case PROJ_SPIKE:      // melee arc: a short, physical forward stroke
            // Wolfkin is the dedicated melee champion: its claw occupies only
            // adjacent body space. Other spike weapons retain a short lunge.
            // Wolfkin's form is now a contact weapon rather than a tiny
            // sword-shaped shot. Its blade starts at the weapon edge then
            // advances three pixels per frame for eighteen frames: enough reach to
            // strike across a deliberate lane, never enough to read as a
            // ranged bullet. The broad/slash versus narrow/stab choice is
            // shaped by room.c's input handling, not by projectile distance.
            if (player.class_id == 0
                && player.starter_weapon == classes[0].starter_weapon) {
                speed = 3; ttl = 18; pierce = 2;
            }
            else { speed = 4; ttl = 12; pierce = 1; }
            break;
        case PROJ_SHURIKEN:   // pierces 2 enemies
            speed = 3; ttl = 60; pierce = 2; break;
        case PROJ_FLAIL:      // broad physical sweep: mid-range, three targets
            speed = 3; ttl = 17; pierce = 3; break;
        case PROJ_SPEAR:      // narrow, committed long-reach physical thrust
            speed = 4; ttl = 22; pierce = 1; break;
        case PROJ_BUBBLE:     // slow drifting, pierces across one full room
            // 120 ticks kept ~17 rapid-fire bubbles resident and starved the
            // 32-entity pool of Tidal Wave/enemy slots. 80 ticks still travels
            // 160px—the full viewport—without pathological saturation.
            speed = 2; ttl = 80; pierce = 2; break;
        default:              // bullet/bolt baseline
            speed = 3; ttl = 75; pierce = 1; break;
    }

    idx = entity_spawn(ENT_PROJECTILE);
    if (idx == 0xFF) return 0xFF;
    e = &entities[idx];
    e->flags      |= EF_PLAYER_PROJ;
    e->x           = FIX8((i16)player.x + 2);
    e->y           = FIX8((i16)player.y + 2);
    // Wolfkin's sword starts at the visible weapon edge, not in the middle of
    // its fist and not beyond a dead 24px gap. An 8px lead plus eighteen
    // three-pixel thrust beats gives Wolfkin a compact 64px steel lane that
    // can strike both an adjacent body and a retreating target.
    // turning the basic stab into a traveling projectile. Tail Spike and
    // Stinger keep their established projectile origin/range; they share
    // physical arc rendering without silently changing their seeded combat
    // geometry or wall-clearance behaviour.
    if (player.class_id == 0 && kind == PROJ_SPIKE
        && player.starter_weapon == classes[0].starter_weapon) {
        e->x = (ppos_t)(e->x + (i16)dx * 8);
        e->y = (ppos_t)(e->y + (i16)dy * 8);
    }
    e->vx          = (i8)((i16)dx * speed);
    e->vy          = (i8)((i16)dy * speed);
    e->sprite_tile = (kind == PROJ_SPEAR) ? SPR_FX_SPEAR
        : (kind == PROJ_SPIKE || kind == PROJ_FLAIL) ? SPR_FX_SWING
        : SPR_BULLET;
    e->palette     = 2;
    e->hp          = pierce;
    e->state_timer = ttl;
    // The Wolfkin blade art occupies its full 8x8 tile. Match the contact
    // box to that visible edge so a diagonal Fang Stab does not appear to
    // touch a small enemy while missing by the old one-pixel square gap.
    // Other projectiles retain their established 7x7 collision geometry.
    e->hitbox      = (player.class_id == 0 && kind == PROJ_SPIKE
        && player.starter_weapon == classes[0].starter_weapon) ? 0x88 : 0x77;
    e->damage      = damage;
    e->ai_data[0]  = 0;              // anim phase
    e->ai_data[1]  = g_shot_element; // element for weakness bonus
    e->ai_data[2]  = (kind == PROJ_SPIKE || kind == PROJ_FLAIL
        || kind == PROJ_SPEAR) ? 1 : 0;
    // Ricochet Rune marks each newly created primary/signature attack with
    // one stone rebound. The marker lives on the projectile, so buying the
    // relic changes all five champions and alternate weapons naturally.
    e->ai_data[3] = g_player_ricochet ? PROJ_FLAG_RICOCHET : 0;
    // Run relics mutate the actual attack silhouette and travel, not only a
    // number in the Pack. PowerStone broadens every weapon one pixel per
    // side; Swift Fang visibly accelerates its trajectory; VampSigil stains
    // it red to connect the strike with its fifth-kill healing contract.
    if ((g_player_attack_traits & ATTACK_TRAIT_POWER)
        && e->hitbox <= 0xAA) e->hitbox = (u8)(e->hitbox + 0x11);
    if (g_player_attack_traits & ATTACK_TRAIT_SWIFT) {
        if (e->vx > 0) e->vx++;
        else if (e->vx < 0) e->vx--;
        if (e->vy > 0) e->vy++;
        else if (e->vy < 0) e->vy--;
        e->palette = 5;
    }
    if (g_player_attack_traits & (ATTACK_TRAIT_POWER | ATTACK_TRAIT_BLOOD))
        e->palette = 4;
    // A long-lived physical arc used to re-hit one overlapping body on the
    // next collision sweep, so Fang's nominal two-target cleave silently
    // became two full hits on the same enemy. Remember its last body slot;
    // combat still lets the stroke continue into a distinct second target.
    if (player.class_id == 0 && kind == PROJ_SPIKE
        && player.starter_weapon == classes[0].starter_weapon) {
        e->ai_data[5] = 0xFF;
        e->ai_data[6] = PROJ_AUX_WOLFKIN_FANG;
    }
    if ((kind == PROJ_SPIKE && player.class_id == 0
            && player.starter_weapon == classes[0].starter_weapon)
        || kind == PROJ_SPEAR) {
        if (dx < 0) e->ai_data[4] |= PROJ_VIS_FLIP_X;
        if (dy > 0) e->ai_data[4] |= PROJ_VIS_FLIP_Y;
    }
    // physical arc: no shimmer
    fx_spawn(SPR_FX_MUZZLE, 2, (i16)player.x + 2, (i16)player.y + 2, 6);
    if (kind == PROJ_FLAIL || kind == PROJ_SPEAR || kind == PROJ_SPIKE)
        sfx_play_weapon(kind);
    else sfx_play(SFX_FIRE);
    return idx;
}

void projectile_update_one(entity_t *e, u8 idx) {
    // Cache flags for the dense bullet path. SDCC otherwise reloads this
    // struct byte for each material check below; twelve simultaneous hostile
    // shots are enough for those redundant reads to cost a video frame.
    u8 flags = e->flags;
    if (e->state_timer == 0) { entity_kill(idx); return; }
    e->state_timer--;

    e->x = (ppos_t)(e->x + e->vx);
    e->y = (ppos_t)(e->y + e->vy);

    // Player bullets shimmer between 2 frames; physical melee arcs and enemy
    // bullets remain static so range and weapon category read immediately.
    if ((flags & EF_PLAYER_PROJ) && e->ai_data[2] == 0) {
        e->ai_data[0] = (u8)(e->ai_data[0] + 1);
        e->sprite_tile = (u8)((e->ai_data[0] & 0x02) ? SPR_BULLET_B : SPR_BULLET);
    }

    {
        i16 px = FIX8_TO_INT(e->x);
        i16 py = FIX8_TO_INT(e->y);
        // Sample the tile FIRST (clamped into bounds) so a shot that reaches
        // a north/west border tile still triggers the crack — the old order
        // despawned on the OOB guard before ever testing the wall, making
        // ~half of all cracked walls unshootable.
        i16 sx = px + 4, sy = py + 4;
        u8 t;
        if (!(flags & EF_PLAYER_PROJ)) {
            // Hostile shots cannot open secrets. Reject their out-of-bounds
            // path first, then sample known-valid coordinates without four
            // clamps per bullet. This is the ordinary bullet-hell hot path.
            if (px < 8 || px > (i16)(room_world_width - 8)
                || py < 8 || py > (i16)(room_world_height - 8)) {
                entity_kill(idx);
                return;
            }
        } else {
            // Player fire samples the border before despawning so a shot that
            // reaches a north/west cracked wall can still open it.
            if (sx < 0) sx = 0;
            else if (sx > (i16)(room_world_width - 1))
                sx = room_world_width - 1;
            if (sy < 0) sy = 0;
            else if (sy > (i16)(room_world_height - 1))
                sy = room_world_height - 1;
        }
        // sx/sy are clamped to the room above, so this is exactly the
        // in-bounds branch of room_tile_at_px().  Keep the hot projectile
        // path in this bank instead of paying a banked helper call for every
        // hostile bullet every frame.
        // A one-screen room guarantees every clamped sample belongs to the
        // compact tilemap. Avoid two signed 16-bit comparisons per hostile
        // bullet; wide courts retain the exact streamed-coordinate test.
        t = (room_world_width == ROOM_VIEW_W_PX
                || (sx < ROOM_VIEW_W_PX && sy < ROOM_VIEW_H_PX))
            ? room_tilemap[(u8)(sy >> 3)][(u8)(sx >> 3)]
            : room_tile_at_px(sx, sy);

        if (flags & EF_PLAYER_PROJ) {
            if ((t == BGT_TREE || t == BGT_SPIKES || t == BGT_SWITCH)
                && room_elemental_tile((u8)(sx >> 3), (u8)(sy >> 3),
                    e->ai_data[1])) {
                fx_spawn(SPR_FX_IMPACT, 6, px, py, 10);
                entity_kill(idx);
                return;
            }
            if (t == BGT_WALL
                && puzzle_try_hidden_shot((u8)(sx >> 3), (u8)(sy >> 3))) {
                fx_spawn(SPR_FX_IMPACT, 2, px, py, 10);
                entity_kill(idx);
                return;
            }
            if (t == BGT_WALL_CRACK) {
                room_open_secret((u8)(sx >> 3), (u8)(sy >> 3));
                fx_spawn(SPR_FX_IMPACT, 2, px, py, 8);
                entity_kill(idx);
                return;
            }
            // Crystals shatter under PLAYER fire (mana nodes); they still
            // block enemy shots, so they double as destructible cover.
            if (t == BGT_CRYSTAL) {
                room_break_crystal((u8)(sx >> 3), (u8)(sy >> 3));
                fx_spawn(SPR_FX_IMPACT, 2, px, py, 8);
                entity_kill(idx);
                return;
            }
            if (t == BGT_POT) {
                room_break_pot((u8)(sx >> 3), (u8)(sy >> 3));
                fx_spawn(SPR_FX_IMPACT, 2, px, py, 8);
                entity_kill(idx);
                return;
            }
            // Keep the relic branch inside the existing player-projectile
            // split. Hostile bullet-hell shots are the dense hot path and
            // must not pay another ownership test every frame.
            if ((e->ai_data[3] & PROJ_FLAG_RICOCHET)
                && (t == BGT_WALL || t == BGT_PILLAR)) {
                // Back out before reversing both axes: a clean one-use
                // pinball return without trapping a diagonal scrape.
                projectile_ricochet(e, px, py);
                return;
            }
        } else if (e->damage >= 2 && t == BGT_CRYSTAL) {
            // Powerful enemy and Colossus patterns reshape their own arena:
            // cover is temporary, but the shattered mana remains claimable.
            room_break_crystal((u8)(sx >> 3), (u8)(sy >> 3));
            fx_spawn(SPR_FX_IMPACT, 2, px, py, 8);
            entity_kill(idx);
            return;
        } else if (e->damage >= 2 && t == BGT_POT) {
            room_break_pot((u8)(sx >> 3), (u8)(sy >> 3));
            fx_spawn(SPR_FX_IMPACT, 2, px, py, 8);
            entity_kill(idx);
            return;
        }
        if (t == BGT_WALL || t == BGT_PILLAR || t == BGT_TREE || t == BGT_CRYSTAL
            || t == BGT_WALL_CRACK || t == BGT_POT) {
            fx_spawn(SPR_FX_IMPACT, 2, px, py, 4);
            entity_kill(idx);
            return;
        }
        // Off-screen / past the room edge: despawn
        if ((flags & EF_PLAYER_PROJ)
            && (px < 8 || px > (i16)(room_world_width - 8)
                || py < 8 || py > (i16)(room_world_height - 8))) {
            entity_kill(idx);
            return;
        }
    }
}
