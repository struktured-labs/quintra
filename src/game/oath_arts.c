#pragma bank 8

#include <gb/gb.h>
#include <gbdk/console.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/oath_arts.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "render/text.h"
#include "render/tiles.h"
#include "content.h"

static const char *const oath_names[OATH_ART_COUNT] = {
    "SHARD WAKE", "ROOT CALL", "CINDERSTEP", "STILL WAVE",
    "MIASMA", "GLOAM SHIFT", "SUN TURN", "RED HARVEST",
    "RIFT EXCHANGE",
};

static u8 unlocked_count(void) {
    return run_state.bosses_beaten < OATH_ART_COUNT
        ? run_state.bosses_beaten : OATH_ART_COUNT;
}

static void sanitize_selection(void) {
    u8 n = unlocked_count();
    if (!n || player.active_oath >= n) player.active_oath = 0;
}

void oath_arts_draw_pack(void) BANKED {
    sanitize_selection();
    gotoxy(3, 16);
    set_sprite_tile(9, SPR_ITEM_ASCEND);
    set_sprite_prop(9, 3);
    move_sprite(9, 16, 144);
    text_write("                ");
    gotoxy(3, 16);
    if (!unlocked_count()) {
        text_write("^vOATH LOCKED    ");
        return;
    }
    text_write("^v");
    text_write(oath_names[player.active_oath]);
}

u8 oath_arts_pack_input(u8 pressed) BANKED {
    u8 n = unlocked_count();
    if (!n || !(pressed & (J_UP | J_DOWN))) return 0;
    sanitize_selection();
    if (pressed & J_UP)
        player.active_oath = player.active_oath
            ? (u8)(player.active_oath - 1) : (u8)(n - 1);
    else {
        player.active_oath++;
        if (player.active_oath >= n) player.active_oath = 0;
    }
    oath_arts_draw_pack();
    sfx_play(SFX_DOOR);
    return 1;
}

static u8 oath_shot(i8 dx, i8 dy, u8 damage, u8 kind, u8 pierce) {
    u8 shot = projectile_spawn_player(dx, dy, damage, kind);
    if (shot != 0xFF) {
        entities[shot].hp = pierce;
        // A single eight-lane art may hit a crowd freely, but uses the same
        // per-cast Colossus cap as Spirit Convergence.
        entities[shot].ai_data[3] |= PROJ_FLAG_CONVERGENCE;
        return 1;
    }
    return 0;
}

static u8 oath_attack(void) {
    return STATUS_PLAYER_INVERTED()
        ? status_player_effective_stat(QSTATUS_STAT_ATK) : player.atk;
}

static u8 shard_wake(void) {
    u8 d, made = 0;
    g_shot_element = 2; // crystal-cold: also bridges authored spike beds
    for (d = 0; d < 8; ++d)
        made |= oath_shot(dir8_dx[d], dir8_dy[d],
            (u8)(oath_attack() + 2), PROJ_SHURIKEN, 3);
    return made;
}

static u8 root_call(void) {
    u8 i, step, touched = 0;
    // Pull bodies into one dangerous knot. This is crowd composition, not a
    // stun: the champion creates an opening for flails, bombs, or MAX arts
    // and must still survive what was gathered.
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 ex, ey;
        i8 dx, dy;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        ex = FIX8_TO_INT(e->x) + 4;
        ey = FIX8_TO_INT(e->y) + 4;
        dx = ex < (i16)player.x + 8 ? 1 : ex > (i16)player.x + 8 ? -1 : 0;
        dy = ey < (i16)player.y + 8 ? 1 : ey > (i16)player.y + 8 ? -1 : 0;
        for (step = 0; step < 3; ++step)
            touched |= enemy_try_step(e, dx, dy);
        e->ai_data[7] = 6;
    }
    // Roots still have a close-range presence in an empty lane.
    g_shot_element = 16;
    touched |= oath_shot(0, -1, (u8)(oath_attack() + 1), PROJ_SPIKE, 2);
    touched |= oath_shot(1, 0, (u8)(oath_attack() + 1), PROJ_SPIKE, 2);
    touched |= oath_shot(0, 1, (u8)(oath_attack() + 1), PROJ_SPIKE, 2);
    touched |= oath_shot(-1, 0, (u8)(oath_attack() + 1), PROJ_SPIKE, 2);
    return touched;
}

static u8 cinderstep(u8 dir) {
    u8 step, made = 0;
    i8 dx = dir8_dx[dir], dy = dir8_dy[dir];
    // A committed 24px fire lunge. Each pixel is collision-checked; the art
    // can cross a bullet lane but never phase into solid room geometry.
    for (step = 0; step < 24; ++step) {
        i16 nx = (i16)(player.x + dx);
        i16 ny = (i16)(player.y + dy);
        if (!room_player_position_clear(nx, ny)) break;
        player.x = (ppos_t)nx;
        player.y = (ppos_t)ny;
        made = 1;
    }
    g_shot_element = 1;
    made |= oath_shot(dx, dy, (u8)(oath_attack() + 3), PROJ_BOMB, 3);
    made |= oath_shot(dir8_dx[(u8)((dir + 1) & 7)],
        dir8_dy[(u8)((dir + 1) & 7)], (u8)(oath_attack() + 2), PROJ_BOMB, 2);
    made |= oath_shot(dir8_dx[(u8)((dir + 7) & 7)],
        dir8_dy[(u8)((dir + 7) & 7)], (u8)(oath_attack() + 2), PROJ_BOMB, 2);
    if (player.iframes < 20) player.iframes = 20;
    return made;
}

static u8 still_wave(void) {
    u8 i, d, made = 0;
    u8 tx = (u8)((player.x + 8) >> 3);
    u8 ty = (u8)((player.y + 12) >> 3);
    // Existing bullets remain on screen but lose half their lane speed. The
    // readable pattern changes instead of being deleted by another shield.
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_PROJECTILE
            || (e->flags & EF_PLAYER_PROJ)) continue;
        if (e->vx > 1 || e->vx < -1) e->vx /= 2;
        if (e->vy > 1 || e->vy < -1) e->vy /= 2;
        e->palette = 6;
        made = 1;
    }
    // Freeze only the local footing; authored remote hazards remain a route
    // concern and the same rule is shared with ordinary ice projectiles.
    for (i = 0; i < 5; ++i) {
        i8 ox = (i8)i - 2;
        u8 x = (u8)((i16)tx + ox);
        if ((i16)tx + ox >= 0)
            made |= room_elemental_tile(x, ty, 2);
    }
    g_shot_element = 2;
    for (d = 0; d < 8; d += 2)
        made |= oath_shot(dir8_dx[d], dir8_dy[d],
            (u8)(oath_attack() + 1), PROJ_BUBBLE, 3);
    return made;
}

static u8 miasma(void) {
    u8 i, touched = 0;
    // Corrode, never execute: ordinary combat still owns death, drops,
    // Colossus rewards, and phase transitions. High-HP bodies lose at most
    // six points, so this remains setup rather than a percentage boss delete.
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        u8 loss;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY || e->hp <= 1)
            continue;
        loss = (u8)(e->hp >> 3);
        if (!loss) loss = 1;
        if (loss > 6) loss = 6;
        if (loss >= e->hp) loss = (u8)(e->hp - 1);
        e->hp = (u8)(e->hp - loss);
        e->ai_data[7] = 10;
        touched = 1;
    }
    return touched;
}

static u8 gloam_shift(u8 dir) {
    u8 dist;
    i8 dx = dir8_dx[dir], dy = dir8_dy[dir];
    ppos_t best_x = player.x, best_y = player.y;
    // Test eight-pixel destinations independently: a one-tile wall can be
    // crossed, but the champion must materialize on legal footing.
    for (dist = 8; dist <= 48; dist = (u8)(dist + 8)) {
        i16 nx = (i16)(player.x + (i16)dx * dist);
        i16 ny = (i16)(player.y + (i16)dy * dist);
        if (room_player_position_clear(nx, ny)) {
            best_x = (ppos_t)nx;
            best_y = (ppos_t)ny;
        }
    }
    if (best_x == player.x && best_y == player.y) return 0;
    fx_spawn(SPR_FX_IMPACT, 6, (i16)player.x + 4, (i16)player.y + 4, 14);
    player.x = best_x;
    player.y = best_y;
    fx_spawn(SPR_FX_IMPACT, 6, (i16)player.x + 4, (i16)player.y + 4, 14);
    if (player.iframes < 24) player.iframes = 24;
    return 1;
}

static u8 sun_turn(void) {
    u8 i, x, y, turned = 0;
    // Rotate the live bullet field clockwise. It remains hostile and visible,
    // making this a pattern-editing verb rather than a reusable Mirror Shard.
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i8 vx;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_PROJECTILE
            || (e->flags & EF_PLAYER_PROJ)) continue;
        vx = e->vx;
        e->vx = (i8)-e->vy;
        e->vy = vx;
        e->palette = 5;
        turned = 1;
    }
    // A Golden oath can throw one authored phase switch anywhere in the
    // current field, joining combat rhythm to dungeon routing.
    for (y = 0; y < (u8)(room_world_height >> 3); ++y) {
        for (x = 0; x < (u8)(room_world_width >> 3); ++x) {
            if (room_tile_at_px((i16)x << 3, (i16)y << 3) == BGT_SWITCH
                && room_elemental_tile(x, y, 4)) return 1;
        }
    }
    return turned;
}

static u8 red_harvest(void) {
    u8 i, drained = 0;
    for (i = 0; i < MAX_ENTITIES && drained < 5; ++i) {
        entity_t *e = &entities[i];
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY || e->hp <= 1)
            continue;
        e->hp--;
        e->ai_data[7] = 8;
        drained++;
    }
    if (!drained) return 0;
    if (player.hp < player.hp_max && !STATUS_PLAYER_HEALING_BLOCKED())
        player.hp++;
    return 1;
}

static u8 rift_exchange(void) {
    u8 i, best = 0xFF;
    u16 best_dist = 0xFFFF;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 dx, dy;
        u16 dist;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY
            || ((e->hitbox >> 4) >= 12) || ((e->hitbox & 0x0F) >= 12))
            continue;
        dx = FIX8_TO_INT(e->x) - (i16)player.x;
        dy = FIX8_TO_INT(e->y) - (i16)player.y;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        dist = (u16)(dx + dy);
        if (dist < best_dist
            && room_player_position_clear(FIX8_TO_INT(e->x),
                FIX8_TO_INT(e->y))) {
            best_dist = dist;
            best = i;
        }
    }
    if (best == 0xFF) return 0;
    {
        entity_t *e = &entities[best];
        ppos_t old_x = player.x, old_y = player.y;
        player.x = FIX8_TO_INT(e->x);
        player.y = FIX8_TO_INT(e->y);
        e->x = FIX8(old_x);
        e->y = FIX8(old_y);
        fx_spawn(SPR_FX_IMPACT, 6, (i16)old_x + 4, (i16)old_y + 4, 16);
        fx_spawn(SPR_FX_IMPACT, 6, (i16)player.x + 4, (i16)player.y + 4, 16);
    }
    if (player.iframes < 30) player.iframes = 30;
    return 1;
}

u8 oath_arts_fire(u8 dir) BANKED {
    u8 art;
    sanitize_selection();
    if (!unlocked_count()) return 0;
    art = player.active_oath;
    if (dir > 7) dir = 0;
    switch (art) {
        case 0: return shard_wake();
        case 1: return root_call();
        case 2: return cinderstep(dir);
        case 3: return still_wave();
        case 4: return miasma();
        case 5: return gloam_shift(dir);
        case 6: return sun_turn();
        case 7: return red_harvest();
        default: return rift_exchange();
    }
}
