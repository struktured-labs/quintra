#pragma bank 9

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/tiles.h"

// Five independent bodies and eight delayed floor brands are the visual
// budget for this encounter. The dedicated renderer owns OAM 4..21; generic
// entities begin at 22 while the encounter is active.
u8 cinder_pack_active;
u8 cinder_boss_index = 0xFF;
u8 cinder_damage_open;
u8 cinder_phase;
u8 cinder_pattern;
u8 cinder_pack_alive;
u8 cinder_timer;
u8 cinder_pack_x[CINDER_KILNBACKS];
u8 cinder_pack_y[CINDER_KILNBACKS];

static u8 cinder_hazard_x[CINDER_HAZARDS];
static u8 cinder_hazard_y[CINDER_HAZARDS];
static u8 cinder_hazard_ttl[CINDER_HAZARDS];
static u8 cinder_hazard_delay[CINDER_HAZARDS];
static u8 cinder_hazard_cursor;
static u8 cinder_last_hp;
static u8 cinder_brand_variant;
static u8 cinder_rex_dir;
static u8 cinder_rex_facing;
static u8 cinder_rex_target_x;
static u8 cinder_late_split_spent;

extern u8 entity_anim_counter;

static u8 cinder_abs_diff(u8 a, u8 b) {
    return a > b ? (u8)(a - b) : (u8)(b - a);
}

static u8 cinder_step_toward(u8 value, u8 target, u8 speed) {
    if (value < target) {
        u8 gap = (u8)(target - value);
        return (gap < speed) ? target : (u8)(value + speed);
    }
    if (value > target) {
        u8 gap = (u8)(value - target);
        return (gap < speed) ? target : (u8)(value - speed);
    }
    return value;
}

static void cinder_move_member(u8 i, u8 x, u8 y, u8 speed) {
    cinder_pack_x[i] = cinder_step_toward(cinder_pack_x[i], x, speed);
    cinder_pack_y[i] = cinder_step_toward(cinder_pack_y[i], y, speed);
}

static void cinder_hurt_player(void) {
    if (player.iframes || player.shield_timer) return;
    player.hp = player.hp ? (u8)(player.hp - 1) : 0;
    // Easy is the deep-content inspection mode. Cinder's overlapping pack,
    // persistent brands, and ordinary bullet field all share this one damage
    // epoch, so give testers a full 2.5-second read without changing Normal's
    // authored 36-frame pressure or removing any pattern.
    player.iframes = RUN_IS_EASY() ? 150 : 36;
    hud_redraw_hp();
    room_shake(1, 8);
    sfx_play(SFX_HURT);
}

static void cinder_hazard_add(u8 x, u8 y, u8 delay, u8 ttl) {
    u8 i = cinder_hazard_cursor;
    cinder_hazard_cursor = (u8)((cinder_hazard_cursor + 1) & 7);
    cinder_hazard_x[i] = x;
    cinder_hazard_y[i] = y;
    cinder_hazard_delay[i] = delay;
    cinder_hazard_ttl[i] = ttl;
}

static void cinder_hazards_tick(void) {
    u8 i;
    u8 px = (u8)(player.x + 8);
    u8 py = (u8)(player.y + 12);
    for (i = 0; i < CINDER_HAZARDS; ++i) {
        if (!cinder_hazard_ttl[i]) continue;
        cinder_hazard_ttl[i]--;
        if (cinder_hazard_delay[i]) {
            cinder_hazard_delay[i]--;
            if (!cinder_hazard_delay[i]) sfx_play(SFX_TICK);
            continue;
        }
        if (cinder_abs_diff(px, cinder_hazard_x[i]) < 9
            && cinder_abs_diff(py, cinder_hazard_y[i]) < 9)
            cinder_hurt_player();
    }
}

static void cinder_body_contact(const entity_t *e) {
    u8 i, count;
    u8 px = (u8)(player.x + 8);
    u8 py = (u8)(player.y + 12);
    if (player.iframes || player.shield_timer) return;
    if (cinder_phase == 2) {
        u8 x = (u8)FIX8_TO_INT(e->x);
        u8 y = (u8)FIX8_TO_INT(e->y);
        if (px >= x && px < (u8)(x + 40)
            && py >= y && py < (u8)(y + 16)) cinder_hurt_player();
        return;
    }
    count = (cinder_phase == 0) ? cinder_pack_alive : CINDER_KILNBACKS;
    for (i = 0; i < count; ++i) {
        if (px >= cinder_pack_x[i] && px < (u8)(cinder_pack_x[i] + 16)
            && py >= cinder_pack_y[i] && py < (u8)(cinder_pack_y[i] + 8)) {
            cinder_hurt_player();
            return;
        }
    }
}

static u8 cinder_shot_touches_body(const entity_t *shot, const entity_t *e) {
    u8 i, count;
    u8 x = (u8)(FIX8_TO_INT(shot->x) + 3);
    u8 y = (u8)(FIX8_TO_INT(shot->y) + 3);
    if (cinder_phase == 2) {
        u8 bx = (u8)FIX8_TO_INT(e->x);
        u8 by = (u8)FIX8_TO_INT(e->y);
        return x >= bx && x < (u8)(bx + 40)
            && y >= by && y < (u8)(by + 16);
    }
    count = cinder_phase == 0 ? cinder_pack_alive : CINDER_KILNBACKS;
    for (i = 0; i < count; ++i)
        if (x >= cinder_pack_x[i] && x < (u8)(cinder_pack_x[i] + 16)
            && y >= cinder_pack_y[i] && y < (u8)(cinder_pack_y[i] + 8))
            return 1;
    return 0;
}

static void cinder_armor_collision(entity_t *e) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)
            || entities[i].type != ENT_PROJECTILE
            || !(entities[i].flags & EF_PLAYER_PROJ)) continue;
        // During recovery the logical anchor is the one exposed vent/head;
        // leave that overlap for combat_resolve so crits, relics, MAX attacks,
        // and pierce keep their ordinary semantics. Every other visible pixel
        // remains furnace armor and must spark instead of letting a shot pass
        // confusingly through one of the five bodies or the long Rex torso.
        if (cinder_damage_open && e->hitbox
            && aabb_overlap_ee(&entities[i], e)) continue;
        if (!cinder_shot_touches_body(&entities[i], e)) continue;
        fx_spawn(SPR_FX_IMPACT, 0,
            FIX8_TO_INT(entities[i].x), FIX8_TO_INT(entities[i].y), 6);
        entity_kill(i);
        sfx_play(SFX_HIT);
    }
}

static u8 cinder_aim_dir(u8 x, u8 y) {
    i16 dx = (i16)player.x + 8 - x;
    i16 dy = (i16)player.y + 12 - y;
    i8 sx = dx > 7 ? 1 : dx < -7 ? -1 : 0;
    i8 sy = dy > 7 ? 1 : dy < -7 ? -1 : 0;
    u8 d;
    for (d = 0; d < 8; ++d)
        if (dir8_dx[d] == sx && dir8_dy[d] == sy) return d;
    return 0;
}

static void cinder_aimed_shot(u8 x, u8 y, i8 speed, u8 damage) {
    u8 d = cinder_aim_dir(x, y);
    projectile_spawn_enemy_v(x, y,
        (i8)(dir8_dx[d] * speed), (i8)(dir8_dy[d] * speed), damage);
}

static void cinder_pack_anchor(entity_t *e) {
    u8 vulnerable = cinder_pack_alive ? (u8)(cinder_pack_alive - 1) : 0;
    e->x = FIX8(cinder_pack_x[vulnerable]);
    e->y = FIX8(cinder_pack_y[vulnerable]);
    e->hitbox = 0xF8;
}

static void cinder_pack_fire(u8 mode, u8 damage) {
    u8 i;
    if (!cinder_pack_alive) return;
    i = (u8)((cinder_timer >> 3) % cinder_pack_alive);
    if (mode == 0) {
        // Crucible Wheel breathes both through and away from its own center.
        i8 dx = cinder_pack_x[i] < 104 ? 2 : -2;
        i8 dy = cinder_pack_y[i] < 64 ? 1 : -1;
        projectile_spawn_enemy_v((i16)cinder_pack_x[i] + 8,
            (i16)cinder_pack_y[i] + 4, dx, dy, damage);
        projectile_spawn_enemy_v((i16)cinder_pack_x[i] + 8,
            (i16)cinder_pack_y[i] + 4, (i8)-dx, (i8)-dy, damage);
    } else {
        cinder_aimed_shot((u8)(cinder_pack_x[i] + 8),
            (u8)(cinder_pack_y[i] + 4),
            (i8)(1 + ((cinder_timer >> 4) & 1)), damage);
    }
}

static void cinder_wheel_tick(u8 speed, u8 damage) {
    static const u8 ax[8] = { 96,160,184,160,96,32,16,32 };
    static const u8 ay[8] = { 20,28,56,96,108,96,56,28 };
    u8 i, step = (u8)(cinder_timer / 24);
    for (i = 0; i < cinder_pack_alive; ++i) {
        u8 a = (u8)((step + i) & 7);
        // The rear beast leapfrogs through the center instead of simply
        // rotating, breaking the familiar circle read on its second beat.
        if (i == (u8)(cinder_pack_alive - 1)
            && cinder_timer >= 52 && cinder_timer < 78)
            cinder_move_member(i, 104, 60, (u8)(speed + 1));
        else cinder_move_member(i, ax[a], ay[a], speed);
    }
    if ((cinder_timer % 24) == 12) cinder_pack_fire(0, damage);
}

static void cinder_press_tick(u8 damage) {
    u8 i;
    u8 y = cinder_timer < 112
        ? (u8)(16 + (((u16)cinder_timer * 3u) >> 2)) : 100;
    for (i = 0; i < cinder_pack_alive; ++i) {
        u8 x = (u8)(12 + i * 40);
        // One furnace vaults sideways across the apparent safe lane while the
        // rest keep the top-to-bottom press intact.
        if (i == (u8)(cinder_pack_alive >> 1)
            && cinder_timer >= 52 && cinder_timer < 92)
            x = (u8)(x + ((cinder_timer & 0x20) ? 20 : 232));
        cinder_move_member(i, x, y, 2);
    }
    if (cinder_timer == 96 || cinder_timer == 120) {
        for (i = 0; i < cinder_pack_alive; ++i)
            projectile_spawn_enemy_v((i16)cinder_pack_x[i] + 8,
                cinder_pack_y[i], 0, (i8)(cinder_timer == 96 ? -2 : -3), damage);
        sfx_play(SFX_ROAR);
    }
}

static void cinder_brand_tick(u8 fast, u8 damage) {
    static const u8 nx[9] = { 24,104,184,24,104,184,24,104,184 };
    static const u8 ny[9] = { 24,24,24,64,64,64,104,104,104 };
    static const u8 paths[4][8] = {
        { 0,1,2,5,8,7,6,3 }, // squared spiral
        { 0,4,8,5,2,1,3,7 }, // unlock-glyph diagonal
        { 6,3,0,4,2,5,8,7 }, // hooked lightning
        { 2,4,6,7,3,0,1,5 }, // false finish, then cross
    };
    u8 i, beat = fast ? 10 : 18;
    u8 step = (u8)(cinder_timer / beat);
    u8 variant = RUN_IS_EASY() ? 0 : cinder_brand_variant;
    for (i = 0; i < cinder_pack_alive; ++i) {
        u8 node = paths[variant][(u8)((step + i) & 7)];
        cinder_move_member(i, nx[node], ny[node], fast ? 3 : 2);
    }
    if ((cinder_timer % beat) == 0) {
        u8 node = paths[variant][step & 7];
        cinder_hazard_add((u8)(nx[node] + 8), (u8)(ny[node] + 4),
            fast ? 8 : 18, fast ? 64 : 92);
    }
    if ((cinder_timer % (fast ? 20 : 36)) == 10)
        cinder_pack_fire(1, damage);
}

static void cinder_broken_tick(u8 damage) {
    static const u8 split_x[5] = { 28,52,156,180,104 };
    static const u8 split_y[5] = { 28,92,28,92,60 };
    static const u8 cage_x[5]  = { 44,164,164,44,104 };
    static const u8 cage_y[5]  = { 28,28,96,96,60 };
    u8 i;
    if (cinder_timer < 36) {
        // It deliberately begins as a familiar Wheel restart.
        cinder_wheel_tick(2, damage);
    } else if (cinder_timer < 76) {
        for (i = 0; i < cinder_pack_alive; ++i)
            cinder_move_member(i, split_x[i], split_y[i], 3);
    } else if (cinder_timer < 124) {
        // Two and three cross in opposing zigzags, like an irregular phone
        // unlock gesture rather than a second rotation.
        u8 flip = (u8)((cinder_timer >> 4) & 1);
        for (i = 0; i < cinder_pack_alive; ++i) {
            u8 x = ((i + flip) & 1) ? (u8)(172 - i * 9) : (u8)(24 + i * 9);
            u8 y = (u8)(24 + i * 19);
            cinder_move_member(i, x, y, 3);
        }
    } else {
        // The obvious center gap closes; the real exit is behind the final
        // furnace, whose rear vent is also the damage window.
        for (i = 0; i < cinder_pack_alive; ++i)
            cinder_move_member(i, cage_x[i], cage_y[i], 2);
    }
    if ((cinder_timer % 22) == 11) cinder_pack_fire(1, damage);
}

static void cinder_update_alive(entity_t *e) {
    u8 half = (u8)(e->ai_data[6] >> 1);
    u8 span = (u8)(e->ai_data[6] - half);
    u8 step = (u8)(span / CINDER_KILNBACKS);
    u8 next;
    if (!step) step = 1;
    if (e->hp <= half) next = 0;
    else {
        u8 remaining = (u8)(e->hp - half);
        next = (u8)((remaining + step - 1) / step);
        if (next > CINDER_KILNBACKS) next = CINDER_KILNBACKS;
    }
    while (next < cinder_pack_alive) {
        u8 fallen = (u8)(cinder_pack_alive - 1);
        cinder_hazard_add((u8)(cinder_pack_x[fallen] + 8),
            (u8)(cinder_pack_y[fallen] + 4), 0, 40);
        cinder_pack_alive--;
        room_shake(1, 14);
        sfx_play(SFX_DEATH);
    }
    cinder_last_hp = e->hp;
}

static void cinder_pack_phase_tick(entity_t *e, u8 damage) {
    cinder_update_alive(e);
    if (!cinder_pack_alive) {
        cinder_phase = 1;
        cinder_timer = 0;
        cinder_damage_open = 0;
        e->hitbox = 0;
        room_shake(2, 28);
        sfx_play(SFX_ROAR);
        return;
    }

    // Normal keeps its brief 44-frame vent. Easy is the hands-on inspection
    // mode: the same formation and attacks play, but the peel becomes
    // targetable earlier so a tester can actually progress to later stages.
    cinder_damage_open = cinder_timer >= (RUN_IS_EASY() ? 80 : 140);
    switch (cinder_pattern) {
        case 0: cinder_wheel_tick(2, damage); break;
        case 1: cinder_press_tick(damage); break;
        case 2: cinder_brand_tick(0, damage); break;
        default: cinder_broken_tick(damage); break;
    }
    // The final furnace peels away from the formation before its vent opens.
    // Anchor that tell to the champion's current camera neighborhood so a
    // wide-arena scroll can never place the only punish window off-screen.
    if (cinder_timer >= 120) {
        u8 vulnerable = (u8)(cinder_pack_alive - 1);
        // Primary weapons own cardinal lanes. The old 40x28 diagonal follow
        // point made the bright vent continuously evade those lanes unless a
        // player happened to pin it against an arena boundary. Alternate a
        // horizontal peel and a vertical peel by formation: positioning is
        // still required, but the announced recovery is genuinely hittable.
        i16 target_x = player.x;
        i16 target_y = player.y;
        if (cinder_pattern & 1)
            target_y = player.y < 64
                ? (i16)player.y + 40 : (i16)player.y - 40;
        else
            target_x = player.x < 112
                ? (i16)player.x + 48 : (i16)player.x - 48;
        if (target_x < 8) target_x = 8;
        if (target_x > 200) target_x = 200;
        if (target_y < 16) target_y = 16;
        if (target_y > 108) target_y = 108;
        cinder_move_member(vulnerable, (u8)target_x, (u8)target_y, 4);
    }
    cinder_pack_anchor(e);
    e->state = cinder_pattern;
    if (cinder_damage_open && (cinder_timer & 7) == 0) {
        e->ai_data[7] = 5;
        sfx_play(SFX_TICK);
    }
    cinder_timer++;
    if (cinder_timer >= 184) {
        cinder_timer = 0;
        cinder_pattern = (u8)((cinder_pattern + 1) & 3);
        cinder_damage_open = 0;
        sfx_play(SFX_ROAR);
    }
}

static void cinder_transform_tick(entity_t *e) {
    u8 i;
    for (i = 0; i < CINDER_KILNBACKS; ++i)
        cinder_move_member(i, (u8)(80 + i * 8), 58, 2);
    if ((cinder_timer & 7) == 0) {
        cinder_hazard_add((u8)(88 + (cinder_timer & 31)), 62, 4, 24);
        room_shake(1, 5);
    }
    if (++cinder_timer >= 64) {
        cinder_phase = 2;
        cinder_pattern = 0;
        cinder_timer = 0;
        e->x = FIX8(96);
        e->y = FIX8(56);
        e->hitbox = 0xFD;
        e->state = 0;
        e->ai_data[7] = 16;
        room_shake(3, 30);
        sfx_play(SFX_DEATH);
    }
}

static void cinder_rex_step(entity_t *e, u8 dir, u8 steps) {
    u8 n;
    for (n = 0; n < steps; ++n) {
        u8 moved = 0;
        if (dir8_dx[dir]) moved |= enemy_try_step(e, dir8_dx[dir], 0);
        if (dir8_dy[dir]) moved |= enemy_try_step(e, 0, dir8_dy[dir]);
        if (!moved) break;
    }
    if (dir8_dx[dir] < 0) cinder_rex_facing = 1;
    else if (dir8_dx[dir] > 0) cinder_rex_facing = 0;
}

static u8 cinder_cardinal_aim(entity_t *e) {
    i16 dx = (i16)player.x - FIX8_TO_INT(e->x);
    i16 dy = (i16)player.y - FIX8_TO_INT(e->y);
    if (dx < 0) dx = -dx;
    if (dy < 0) dy = -dy;
    if (dx >= dy) return ((i16)player.x < FIX8_TO_INT(e->x)) ? 6 : 2;
    return ((i16)player.y < FIX8_TO_INT(e->y)) ? 0 : 4;
}

static void cinder_rex_begin(entity_t *e) {
    i16 px = player.x;
    cinder_rex_target_x = (u8)(px < 112 ? px + 56 : px - 56);
    if (cinder_rex_target_x > 184) cinder_rex_target_x = 184;
    cinder_rex_dir = cinder_cardinal_aim(e);
    e->ai_data[7] = 12;
    sfx_play(SFX_TICK);
}

static void cinder_furnace_wall(entity_t *e, u8 from_bottom, u8 damage) {
    u8 k;
    u8 gap = (u8)(((u8)(player.x - room_camera_x) + 10) / 20);
    u8 base = (u8)(room_camera_x + 10);
    for (k = 0; k < 8; ++k) {
        if (k == gap) continue;
        projectile_spawn_enemy_v((i16)base + k * 20,
            from_bottom ? 116 : 12, 0, from_bottom ? -2 : 2, damage);
    }
    room_shake(2, 16);
    sfx_play(SFX_ROAR);
    e->ai_data[7] = 10;
}

static void cinder_rex_tick(entity_t *e, u8 damage) {
    u8 i;
    if (cinder_timer == 0) cinder_rex_begin(e);
    cinder_damage_open = cinder_timer >= (RUN_IS_EASY() ? 64 : 112);
    e->state = (u8)(4 + cinder_pattern);
    switch (cinder_pattern) {
        case 0: // Furnace Breath: two broad walls with different approach.
            if ((entity_anim_counter & 3) == 0) {
                u8 ex = (u8)FIX8_TO_INT(e->x);
                if (ex < cinder_rex_target_x) cinder_rex_step(e, 2, 1);
                else if (ex > cinder_rex_target_x) cinder_rex_step(e, 6, 1);
            }
            if (cinder_timer == 36) cinder_furnace_wall(e, 0, damage);
            if (cinder_timer == 76) cinder_furnace_wall(e, 1, damage);
            break;
        case 1: // Slag Spit: mixed-speed globs plus delayed molten pools.
            if (cinder_timer == 28 || cinder_timer == 68) {
                u8 x = (u8)(FIX8_TO_INT(e->x) + 16);
                u8 y = (u8)(FIX8_TO_INT(e->y) + 8);
                cinder_aimed_shot(x, y, 1, damage);
                cinder_aimed_shot(x, y, 2, damage);
                cinder_hazard_add((u8)(player.x + 8),
                    (u8)(player.y + 12), 28, 104);
                cinder_hazard_add((u8)(player.x + (cinder_timer == 28 ? 28 : 236)),
                    (u8)(player.y + 12), 36, 96);
                sfx_play(SFX_ROAR);
            }
            break;
        case 2: // Kiln Stomp / Backdraft: marked footprints ignite later.
            if (cinder_timer == 20) {
                u8 px = (u8)(player.x + 8), py = (u8)(player.y + 12);
                cinder_hazard_add(px, py, 44, 112);
                cinder_hazard_add((u8)(px + 28), py, 52, 112);
                cinder_hazard_add((u8)(px - 28), py, 52, 112);
                cinder_hazard_add(px, (u8)(py + 28), 60, 112);
                cinder_hazard_add(px, (u8)(py - 28), 60, 112);
                cinder_rex_dir = cinder_cardinal_aim(e);
            }
            if (cinder_timer >= 42 && cinder_timer < 88) {
                cinder_rex_step(e, cinder_rex_dir, 1);
                if ((cinder_timer & 7) == 0)
                    cinder_hazard_add((u8)(FIX8_TO_INT(e->x) + 16),
                        (u8)(FIX8_TO_INT(e->y) + 12), 30, 88);
            }
            if (cinder_timer == 88) {
                for (i = 0; i < 8; i += 2)
                    projectile_spawn_enemy_v(FIX8_TO_INT(e->x) + 16,
                        FIX8_TO_INT(e->y) + 8,
                        (i8)(dir8_dx[i] * 2), (i8)(dir8_dy[i] * 2), damage);
                room_shake(3, 22);
            }
            break;
        default: // Rex Charge + slab-tail hammer.
            if (cinder_timer == 16) {
                cinder_rex_dir = cinder_cardinal_aim(e);
                e->ai_data[7] = 18;
                sfx_play(SFX_TICK);
            }
            if (cinder_timer >= 34 && cinder_timer < 78)
                cinder_rex_step(e, cinder_rex_dir, 3);
            if (cinder_timer == 88) {
                u8 x = (u8)(FIX8_TO_INT(e->x) + 16);
                u8 y = (u8)(FIX8_TO_INT(e->y) + 8);
                for (i = 0; i < 5; ++i)
                    cinder_hazard_add((u8)(x + (i * 16) - 32), y, 12, 72);
                room_shake(3, 24);
                sfx_play(SFX_DEATH);
            }
            break;
    }
    if (cinder_damage_open && (cinder_timer & 7) == 0) {
        e->ai_data[7] = 5;
        sfx_play(SFX_TICK);
    }
    cinder_timer++;
    if (cinder_timer >= 160) {
        cinder_timer = 0;
        cinder_pattern = (u8)((cinder_pattern + 1) & 3);
        cinder_damage_open = 0;
    }
}

static void cinder_fire_pack_tick(entity_t *e, u8 damage) {
    cinder_pack_alive = CINDER_KILNBACKS;
    cinder_brand_tick(1, damage);
    e->x = FIX8(cinder_pack_x[4]);
    e->y = FIX8(cinder_pack_y[4]);
    e->hitbox = 0;
    if (++cinder_timer >= 96) {
        cinder_phase = 2;
        cinder_pattern = 3;
        cinder_timer = 0;
        e->x = FIX8(96);
        e->y = FIX8(56);
        e->hitbox = 0xFD;
        e->ai_data[7] = 14;
        room_shake(2, 20);
        sfx_play(SFX_ROAR);
    }
}

void cinder_pack_reset(void) BANKED {
    static const u8 start_x[CINDER_KILNBACKS] = { 40,72,104,136,168 };
    static const u8 start_y[CINDER_KILNBACKS] = { 28,44,60,76,92 };
    u8 i;
    cinder_pack_active = 0;
    cinder_boss_index = 0xFF;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE)
            && entities[i].type == ENT_ENEMY
            && entities[i].ai_data[0] == ENEMY_STONE_SENTINEL
            && (entities[i].ai_data[3] & 1)
            && entities[i].ai_data[2] == 2) {
            cinder_boss_index = i;
            break;
        }
    }
    if (cinder_boss_index == 0xFF) return;
    for (i = 0; i < CINDER_KILNBACKS; ++i) {
        cinder_pack_x[i] = start_x[i];
        cinder_pack_y[i] = start_y[i];
    }
    for (i = 0; i < CINDER_HAZARDS; ++i) {
        cinder_hazard_ttl[i] = 0;
        cinder_hazard_delay[i] = 0;
    }
    cinder_hazard_cursor = 0;
    cinder_phase = 0;
    cinder_pattern = 0;
    cinder_pack_alive = CINDER_KILNBACKS;
    cinder_timer = 0;
    cinder_damage_open = 0;
    cinder_last_hp = entities[cinder_boss_index].hp;
    cinder_brand_variant = RUN_IS_EASY() ? 0 : (u8)(rng_next_u8() & 3);
    cinder_rex_dir = 2;
    cinder_rex_facing = 0;
    cinder_late_split_spent = 0;
    entities[cinder_boss_index].state = 0;
    entities[cinder_boss_index].state_timer = 0;
    entities[cinder_boss_index].vx = entities[cinder_boss_index].vy = 0;
    entities[cinder_boss_index].hitbox = 0xF8;
    cinder_pack_anchor(&entities[cinder_boss_index]);
    cinder_pack_active = 1;
}

void cinder_pack_retire(void) BANKED {
    u8 oam;
    cinder_pack_active = 0;
    cinder_damage_open = 0;
    cinder_boss_index = 0xFF;
    for (oam = 4; oam < 22; ++oam) move_sprite(oam, 0, 0);
}

void cinder_boss_tick(entity_t *e) BANKED {
    u8 damage = e->damage > 3 ? 3 : e->damage;
    if (!damage) damage = 1;
    if (!cinder_pack_active) return;
    // The late Rex surprise is a much faster reprise of Brandwalk: five fire
    // silhouettes separate, trace one glyph, then lock back together.
    if (cinder_phase == 2 && !cinder_late_split_spent && e->hp <= 40) {
        u8 i;
        cinder_late_split_spent = 1;
        cinder_phase = 3;
        cinder_pattern = cinder_brand_variant;
        cinder_timer = 0;
        cinder_damage_open = 0;
        for (i = 0; i < CINDER_KILNBACKS; ++i) {
            cinder_pack_x[i] = (u8)(FIX8_TO_INT(e->x) + 8);
            cinder_pack_y[i] = (u8)(FIX8_TO_INT(e->y) + 4);
        }
        room_shake(2, 18);
        sfx_play(SFX_DEATH);
    }
    cinder_hazards_tick();
    if (cinder_phase == 0) cinder_pack_phase_tick(e, damage);
    else if (cinder_phase == 1) cinder_transform_tick(e);
    else if (cinder_phase == 2) cinder_rex_tick(e, damage);
    else cinder_fire_pack_tick(e, damage);
    cinder_body_contact(e);
    // EF_ON_SCREEN is also combat's authoritative targetability bit. Keep the
    // logical anchor untargetable behind furnace brick, while this bank still
    // consumes colliding shots with a visible armor spark. The exposed vent
    // restores ordinary combat resolution and all champion/relic semantics.
    cinder_armor_collision(e);
    if (cinder_damage_open) e->flags |= EF_ON_SCREEN;
    else e->flags &= (u8)~EF_ON_SCREEN;
}

static u8 cinder_draw_member(u8 oam, u8 x, u8 y, u8 tile, u8 pal) {
    i16 sx = (i16)x - room_camera_x + 8;
    i16 sy = (i16)y - room_camera_y + 16;
    if (sx < -15 || sx >= ROOM_VIEW_W_PX || sy < -7 || sy >= ROOM_VIEW_H_PX)
        return oam;
    set_sprite_tile(oam, tile);
    set_sprite_tile((u8)(oam + 1), (u8)(tile + 1));
    set_sprite_prop(oam, pal);
    set_sprite_prop((u8)(oam + 1), pal);
    move_sprite(oam, (u8)sx, (u8)sy);
    move_sprite((u8)(oam + 1), (u8)(sx + 8), (u8)sy);
    return (u8)(oam + 2);
}

void cinder_draw(void) BANKED {
    entity_t *e;
    u8 i, oam = 4, pal, flash;
    if (!cinder_pack_active || cinder_boss_index >= MAX_ENTITIES) return;
    e = &entities[cinder_boss_index];
    if (!(e->flags & EF_ACTIVE)) { cinder_pack_retire(); return; }
    pal = e->palette;
    flash = e->ai_data[7] ? 1 : 0;
    if (flash) e->ai_data[7]--;

    if (cinder_phase == 2) {
        i16 sx = FIX8_TO_INT(e->x) - room_camera_x + 8;
        i16 sy = FIX8_TO_INT(e->y) - room_camera_y + 16;
        static const u8 stretched_col[5] = { 0,1,2,2,3 };
        u8 r, c;
        for (r = 0; r < 2; ++r) {
            for (c = 0; c < 5; ++c) {
                u8 col = cinder_rex_facing
                    ? stretched_col[4 - c] : stretched_col[c];
                u8 prop = (flash && (e->ai_data[7] & 1)) ? 0 : pal;
                if (cinder_rex_facing) prop |= S_FLIPX;
                set_sprite_tile(oam, (u8)(SPR_CINDER_REX + r * 4 + col));
                set_sprite_prop(oam, prop);
                move_sprite(oam, (u8)(sx + c * 8), (u8)(sy + r * 8));
                oam++;
            }
        }
    } else {
        u8 count = cinder_phase == 0 ? cinder_pack_alive : CINDER_KILNBACKS;
        for (i = 0; i < count; ++i) {
            u8 tile;
            u8 member_pal = pal;
            if (cinder_phase == 1 || cinder_phase == 3) tile = SPR_KILNBACK_HUSK;
            else if (cinder_damage_open && i == (u8)(cinder_pack_alive - 1)) {
                tile = SPR_KILNBACK_VENT;
                member_pal = (entity_anim_counter & 8) ? 0 : pal;
            } else tile = (entity_anim_counter & 8)
                ? SPR_KILNBACK_WALK_B : SPR_KILNBACK_WALK_A;
            if (flash && i == (u8)(count - 1) && (e->ai_data[7] & 1))
                member_pal = 0;
            oam = cinder_draw_member(oam, cinder_pack_x[i],
                cinder_pack_y[i], tile, member_pal);
        }
    }

    for (i = 0; i < CINDER_HAZARDS && oam < 22; ++i) {
        i16 sx, sy;
        u8 tile, hazard_pal;
        if (!cinder_hazard_ttl[i]) continue;
        sx = (i16)cinder_hazard_x[i] - room_camera_x + 4;
        sy = (i16)cinder_hazard_y[i] - room_camera_y + 12;
        if (sx < -7 || sx >= ROOM_VIEW_W_PX || sy < -7 || sy >= ROOM_VIEW_H_PX)
            continue;
        tile = cinder_hazard_delay[i] ? SPR_FX_IMPACT : SPR_BULLET_B;
        hazard_pal = cinder_hazard_delay[i] ? 0 : pal;
        set_sprite_tile(oam, tile);
        set_sprite_prop(oam, hazard_pal);
        move_sprite(oam, (u8)sx, (u8)sy);
        oam++;
    }
    while (oam < 22) move_sprite(oam++, 0, 0);
}
