#pragma bank 3
#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/projectile.h"
#include "game/player.h"
#include "game/room.h"
#include "render/tiles.h"
#include "content.h"

// Element bitmask stamped onto the next player shot (1=Fire 2=Ice 4=Lit
// 8=Shadow 16=Poison). Set by the fire code per class/weapon; combat
// doubles damage when it matches the target's weakness.
u8 g_shot_element;

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
    if ((kind == PROJ_SPIKE && player.class_id == 0
            && player.starter_weapon == classes[0].starter_weapon)
        || kind == PROJ_SPEAR) {
        if (dx < 0) e->ai_data[4] |= PROJ_VIS_FLIP_X;
        if (dy > 0) e->ai_data[4] |= PROJ_VIS_FLIP_Y;
    }
    // physical arc: no shimmer
    fx_spawn(SPR_FX_MUZZLE, 2, (i16)player.x + 2, (i16)player.y + 2, 6);
    sfx_play(SFX_FIRE);
    return idx;
}

// Core spawn with an explicit px/tick velocity — lets bosses mix bullet speeds
// (thin-fast streams vs. slow dense walls) within one pattern.
u8 projectile_spawn_enemy_v(i16 px, i16 py, i8 vx, i8 vy, u8 damage) BANKED {
    u8 idx;
    entity_t *e;
    if (vx == 0 && vy == 0) return 0xFF;
    idx = entity_spawn(ENT_PROJECTILE);
    if (idx == 0xFF) return 0xFF;
    e = &entities[idx];
    // No EF_PLAYER_PROJ: combat treats it as hostile
    e->x           = FIX8(px);
    e->y           = FIX8(py);
    e->vx          = vx;
    e->vy          = vy;
    e->sprite_tile = SPR_BULLET_B;
    e->palette     = 3;                   // crawler blue — reads hostile
    e->hp          = 1;
    e->state_timer = 110;
    e->hitbox      = (6 << 4) | 6;
    e->damage      = damage;
    return idx;
}

u8 projectile_spawn_enemy(i16 px, i16 py, i8 dx, i8 dy, u8 damage) BANKED {
    // Legacy 8-dir helper: unit deltas at the default 2 px/tick.
    return projectile_spawn_enemy_v(px, py, (i8)((i16)dx * 2), (i8)((i16)dy * 2), damage);
}

void projectile_update(entity_t *e, u8 idx) BANKED {
    if (e->state_timer == 0) { entity_kill(idx); return; }
    e->state_timer--;

    e->x = (ppos_t)(e->x + e->vx);
    e->y = (ppos_t)(e->y + e->vy);

    // Player bullets shimmer between 2 frames; physical melee arcs and enemy
    // bullets remain static so range and weapon category read immediately.
    if ((e->flags & EF_PLAYER_PROJ) && e->ai_data[2] == 0) {
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
        if (sx < 0) sx = 0; else if (sx > (ROOM_W * 8 - 1)) sx = ROOM_W * 8 - 1;
        if (sy < 0) sy = 0; else if (sy > (ROOM_H * 8 - 1)) sy = ROOM_H * 8 - 1;
        // sx/sy are clamped to the room above, so this is exactly the
        // in-bounds branch of room_tile_at_px().  Keep the hot projectile
        // path in this bank instead of paying a banked helper call for every
        // hostile bullet every frame.
        t = room_tilemap[(u8)(sy >> 3)][(u8)(sx >> 3)];

        if (t == BGT_WALL_CRACK && (e->flags & EF_PLAYER_PROJ)) {
            room_open_secret((u8)(sx >> 3), (u8)(sy >> 3));
            fx_spawn(SPR_FX_IMPACT, 2, px, py, 8);
            entity_kill(idx);
            return;
        }
        // Crystals shatter under PLAYER fire (mana nodes); they still
        // block enemy shots, so they double as destructible cover.
        if (t == BGT_CRYSTAL && (e->flags & EF_PLAYER_PROJ)) {
            room_break_crystal((u8)(sx >> 3), (u8)(sy >> 3));
            fx_spawn(SPR_FX_IMPACT, 2, px, py, 8);
            entity_kill(idx);
            return;
        }
        if (t == BGT_POT && (e->flags & EF_PLAYER_PROJ)) {
            room_break_pot((u8)(sx >> 3), (u8)(sy >> 3));
            fx_spawn(SPR_FX_IMPACT, 2, px, py, 8);
            entity_kill(idx);
            return;
        }
        if (t == BGT_WALL || t == BGT_PILLAR || t == BGT_CRYSTAL
            || t == BGT_WALL_CRACK || t == BGT_POT) {
            fx_spawn(SPR_FX_IMPACT, 2, px, py, 4);
            entity_kill(idx);
            return;
        }
        // Off-screen / past the room edge: despawn
        if (px < 8 || px > (ROOM_W * 8 - 8)
            || py < 8 || py > (ROOM_H * 8 - 8)) {
            entity_kill(idx);
            return;
        }
    }
}
