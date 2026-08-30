#pragma bank 8

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/will.h"
#include "render/tiles.h"
#include "content.h"

u8 will_corvin_mark_slot = 0xFF;
u8 will_corvin_mark_ticks;
u8 will_corvin_mark_damage;
u8 will_howl_giant_hits;
u8 will_vespine_swarm_ticks;

u8 will_vespine_swarm_dir;
u8 will_vespine_swarm_damage;

static u8 dir_toward(i16 dx, i16 dy) {
    u16 ax = dx < 0 ? (u16)-dx : (u16)dx;
    u16 ay = dy < 0 ? (u16)-dy : (u16)dy;
    if (ax > (ay << 1)) return dx < 0 ? 6 : 2;
    if (ay > (ax << 1)) return dy < 0 ? 0 : 4;
    if (dx >= 0) return dy < 0 ? 1 : 3;
    return dy < 0 ? 7 : 5;
}

// MAX volleys are one authored attack. Mark their overlapping pieces with
// the existing chord limiter so spectacle does not become a one-frame boss
// deletion while each lane can still hit a different ordinary monster.
static u8 max_spawn(i8 dx, i8 dy, u8 damage, u8 kind) {
    u8 shot = projectile_spawn_player(dx, dy, damage, kind);
    if (shot != 0xFF)
        entities[shot].ai_data[3] |= PROJ_FLAG_CONVERGENCE;
    return shot;
}

static u8 corvin_mark_aimed(u8 dir, u8 damage) {
    u8 i;
    u8 best = 0xFF;
    u16 best_score = 0xFFFF;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 dx, dy;
        i16 dot, cross;
        u16 score;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        if (!(e->flags & EF_ON_SCREEN) && !(e->ai_data[3] & 1)) continue;
        dx = (i16)(FIX8_TO_INT(e->x) + 4) - (i16)(player.x + 8);
        dy = (i16)(FIX8_TO_INT(e->y) + 4) - (i16)(player.y + 8);
        dot = (i16)(dx * dir8_dx[dir] + dy * dir8_dy[dir]);
        cross = (i16)(dx * dir8_dy[dir] - dy * dir8_dx[dir]);
        if (cross < 0) cross = -cross;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        // A foe in the chosen half-plane wins over a merely closer body.
        // Cross-track error then breaks ties, so B follows the same visible
        // aim used by Corvin's primary weapon and by controller play.
        score = (u16)dx + (u16)dy + ((u16)cross << 1);
        if (dot <= 0) score = (u16)(score + 1024);
        if (score < best_score) {
            best_score = score;
            best = i;
        }
    }
    if (best == 0xFF) return 0;
    will_corvin_mark_slot = best;
    will_corvin_mark_ticks = 180;
    will_corvin_mark_damage = damage;
    fx_spawn(SPR_FX_IMPACT, 6,
        (i16)FIX8_TO_INT(entities[best].x),
        (i16)FIX8_TO_INT(entities[best].y), 12);
    // One opening dart makes the mark responsive even before the next held-A
    // cadence. It is a single focus lane—not Murderstorm's five-way fan.
    {
        i16 tx = (i16)(FIX8_TO_INT(entities[best].x) + 4)
            - (i16)(player.x + 8);
        i16 ty = (i16)(FIX8_TO_INT(entities[best].y) + 4)
            - (i16)(player.y + 8);
        u8 lock_dir = dir_toward(tx, ty);
        i = projectile_spawn_player(
            dir8_dx[lock_dir], dir8_dy[lock_dir], damage, PROJ_SHURIKEN);
    }
    if (i != 0xFF) {
        // The opening raven is responsive but cannot repeatedly blender the
        // same large body. Two later lock-on dives carry the sustained mark.
        entities[i].hp = 1;
        entities[i].hitbox = 0xBB;
    }
    return 1;
}

u8 will_fire_signature(u8 dir, u8 damage) BANKED {
    u8 d;
    u8 shot;
    u8 made = 0;

    switch (player.class_id) {
        case 0:   // Wolfkin HOWL: eight crowd lanes, capped on Colossi
            will_howl_clear_nearby_shots();
            will_howl_giant_hits = 0;
            for (d = 0; d < 8; ++d) {
                shot = projectile_spawn_player(
                    dir8_dx[d], dir8_dy[d], damage, PROJ_SPIKE);
                if (shot != 0xFF) {
                    entities[shot].ai_data[3] |= PROJ_FLAG_HOWL;
                    made = 1;
                }
            }
            // Howl is a committed point-blank burst, not a durable shield.
            if (player.iframes < (room_weapon_surge_ticks ? 42 : 30))
                player.iframes = room_weapon_surge_ticks ? 42 : 30;
            sfx_play(SFX_ROAR);
            return 1; // the activation ward remains useful at entity capacity

        case 1:   // Sauran STONESKIN: timed shot/body shield
            player.shield_timer = room_weapon_surge_ticks ? 90 : 60;
            if (player.iframes < 8) player.iframes = 8;
            sfx_play(SFX_HIT);
            return 1;

        case 2:   // Corvin RAVEN MARK: aimed focus; no duplicate fan
            made = corvin_mark_aimed(dir,
                room_weapon_surge_ticks ? (u8)(damage + 1) : damage);
            if (made) sfx_play_weapon(PROJ_SHURIKEN);
            return made;

        case 3:   // Picsean UNDERTOW: directional bubble wall + guard
            shot = projectile_spawn_player(
                dir8_dx[dir], dir8_dy[dir], damage, PROJ_BUBBLE);
            if (shot != 0xFF && room_weapon_surge_ticks) entities[shot].hp++;
            shot = projectile_spawn_player(
                dir8_dx[(u8)((dir + 2) & 7)],
                dir8_dy[(u8)((dir + 2) & 7)], damage, PROJ_BUBBLE);
            if (shot != 0xFF && room_weapon_surge_ticks) entities[shot].hp++;
            shot = projectile_spawn_player(
                dir8_dx[(u8)((dir + 6) & 7)],
                dir8_dy[(u8)((dir + 6) & 7)], damage, PROJ_BUBBLE);
            if (shot != 0xFF && room_weapon_surge_ticks) entities[shot].hp++;
            if (player.shield_timer < (room_weapon_surge_ticks ? 112 : 100))
                player.shield_timer = room_weapon_surge_ticks ? 112 : 100;
            if (player.iframes < 8) player.iframes = 8;
            sfx_play_weapon(PROJ_BUBBLE);
            return 1;

        default:  // Vespine SWARM: six rotating stings over 1.6 seconds
            will_vespine_swarm_dir = dir;
            will_vespine_swarm_damage = (damage > 2) ? (u8)(damage - 2) : 1;
            if (room_weapon_surge_ticks) will_vespine_swarm_damage++;
            // 97 lets this frame's update launch the first aimed stinger,
            // followed by five turns at sixteen-frame intervals.
            will_vespine_swarm_ticks = 97;
            if (player.iframes < (room_weapon_surge_ticks ? 28 : 18))
                player.iframes = room_weapon_surge_ticks ? 28 : 18;
            sfx_play_weapon(PROJ_SPIKE);
            return 1;
    }
}

u8 will_fire_max(u8 weapon_index, u8 dir, u8 damage) BANKED {
    u8 first = 0xFF;
    u8 shot;
    u8 d;
    u8 kind = (weapon_index < N_ITEMS) ? items[weapon_index].p2 : PROJ_BULLET;

    // Fang Forms — Moonfang Rush. Three steel lanes travel with a brief
    // body-dash applied by room.c: broad enough to read as a slash, short
    // enough to remain the game's true melee MAX.
    if (player.class_id == 0 && weapon_index == classes[0].starter_weapon) {
        first = max_spawn(dir8_dx[dir], dir8_dy[dir],
            (u8)(damage + 3), PROJ_SPIKE);
        max_spawn(dir8_dx[(u8)((dir + 1) & 7)],
            dir8_dy[(u8)((dir + 1) & 7)], (u8)(damage + 2), PROJ_SPIKE);
        max_spawn(dir8_dx[(u8)((dir + 7) & 7)],
            dir8_dy[(u8)((dir + 7) & 7)], (u8)(damage + 2), PROJ_SPIKE);
    // Tail Spike — Thunderline. One unusually long, wide, penetrating lane.
    } else if (weapon_index == classes[1].starter_weapon) {
        first = max_spawn(dir8_dx[dir], dir8_dy[dir],
            (u8)(damage + 4), PROJ_SPEAR);
        if (first != 0xFF) {
            entities[first].state_timer = 54;
            entities[first].hp = 6;
            entities[first].hitbox = 0x99;
        }
    // Featherbarb — Murderstorm. A five-lane returning fan.
    } else if (weapon_index == classes[2].starter_weapon) {
        for (d = 6; d != 3; ++d) {
            shot = max_spawn(dir8_dx[(u8)((dir + d) & 7)],
                dir8_dy[(u8)((dir + d) & 7)],
                (u8)(damage + 2), PROJ_SHURIKEN);
            if (first == 0xFF) first = shot;
            if (shot != 0xFF) entities[shot].hp = 4;
        }
    // BubbleBolt — Moon Tide. A five-lane forward ice breaker: the broad,
    // piercing center carries the damage while widening side currents fill
    // the forward half-plane. Protection belongs to B's Undertow, so MAX is
    // now an offensive positioning commitment rather than a second shield.
    } else if (weapon_index == classes[3].starter_weapon) {
        first = max_spawn(dir8_dx[dir], dir8_dy[dir],
            (u8)(damage + 4), PROJ_BUBBLE);
        if (first != 0xFF) {
            entities[first].hp = 6;
            entities[first].hitbox = 0xBB;
        }
        shot = max_spawn(dir8_dx[(u8)((dir + 1) & 7)],
            dir8_dy[(u8)((dir + 1) & 7)],
            (u8)(damage + 3), PROJ_BUBBLE);
        if (shot != 0xFF) { entities[shot].hp = 4; entities[shot].hitbox = 0x99; }
        shot = max_spawn(dir8_dx[(u8)((dir + 7) & 7)],
            dir8_dy[(u8)((dir + 7) & 7)],
            (u8)(damage + 3), PROJ_BUBBLE);
        if (shot != 0xFF) { entities[shot].hp = 4; entities[shot].hitbox = 0x99; }
        shot = max_spawn(dir8_dx[(u8)((dir + 2) & 7)],
            dir8_dy[(u8)((dir + 2) & 7)],
            (u8)(damage + 2), PROJ_BUBBLE);
        if (shot != 0xFF) { entities[shot].hp = 3; entities[shot].hitbox = 0x88; }
        shot = max_spawn(dir8_dx[(u8)((dir + 6) & 7)],
            dir8_dy[(u8)((dir + 6) & 7)],
            (u8)(damage + 2), PROJ_BUBBLE);
        if (shot != 0xFF) { entities[shot].hp = 3; entities[shot].hitbox = 0x88; }
    // Stinger — Queen's Needle. A fast central venom lance with two biting
    // side-lines: visually and tactically unlike Sauran's single heavy lane.
    } else if (weapon_index == classes[4].starter_weapon) {
        first = max_spawn(dir8_dx[dir], dir8_dy[dir],
            (u8)(damage + 3), PROJ_SPEAR);
        if (first != 0xFF) {
            entities[first].hp = 5;
            entities[first].state_timer = 38;
        }
        max_spawn(dir8_dx[(u8)((dir + 1) & 7)],
            dir8_dy[(u8)((dir + 1) & 7)], (u8)(damage + 2), PROJ_SPIKE);
        max_spawn(dir8_dx[(u8)((dir + 7) & 7)],
            dir8_dy[(u8)((dir + 7) & 7)], (u8)(damage + 2), PROJ_SPIKE);
    // Rift Flail — Worldwheel. A close eight-way sweep clears breathing room.
    } else if (kind == PROJ_FLAIL) {
        for (d = 0; d < 8; ++d) {
            shot = max_spawn(dir8_dx[d], dir8_dy[d],
                (u8)(damage + 3), PROJ_FLAIL);
            if (first == 0xFF) first = shot;
        }
    // Astral Spear (and future spear-class weapons) — Farstrike.
    } else if (kind == PROJ_SPEAR) {
        first = max_spawn(dir8_dx[dir], dir8_dy[dir],
            (u8)(damage + 5), PROJ_SPEAR);
        if (first != 0xFF) {
            entities[first].state_timer = 64;
            entities[first].hp = 8;
            entities[first].hitbox = 0x99;
        }
    // Generated future weapons receive a useful three-lane expression until
    // content gives them a bespoke branch above.
    } else {
        first = max_spawn(dir8_dx[dir], dir8_dy[dir],
            (u8)(damage + 3), kind);
        max_spawn(dir8_dx[(u8)((dir + 1) & 7)],
            dir8_dy[(u8)((dir + 1) & 7)], (u8)(damage + 2), kind);
        max_spawn(dir8_dx[(u8)((dir + 7) & 7)],
            dir8_dy[(u8)((dir + 7) & 7)], (u8)(damage + 2), kind);
    }

    if (first != 0xFF) {
        room_shake(2, 12);
        sfx_play(SFX_ROAR);
        return 1;
    }
    return 0;
}
