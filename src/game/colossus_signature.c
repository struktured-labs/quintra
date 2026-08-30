#pragma bank 9

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/tiles.h"

// One giant exists at a time, so three WRAM bytes can retain an announced
// lane/impact point without stealing any boss's movement scratch fields.
static u8 signature_dir;
static u8 signature_x;
static u8 signature_y;

static i16 signature_abs(i16 value) {
    return value < 0 ? -value : value;
}

static void signature_hurt(entity_t *e) {
    u8 damage;
    if (player.iframes || player.shield_timer) return;
    damage = e->damage;
    if (damage < 2) damage = 2;
    if (damage > 4) damage = 4;
    if (RUN_IS_EASY()) damage = 1;
    player.hp = (player.hp > damage) ? (u8)(player.hp - damage) : 0;
    player.iframes = 50;
    hud_redraw_hp();
    sfx_play(SFX_HURT);
}

static u8 signature_damage(const entity_t *e) {
    u8 damage = e->damage;
    if (damage > 3) damage = 3;
    return RUN_IS_EASY() ? 1 : damage;
}

static void signature_ring(entity_t *e, i16 x, i16 y, i8 speed) {
    u8 d;
    u8 damage = signature_damage(e);
    for (d = 0; d < 8; ++d)
        projectile_spawn_enemy_v(x, y,
            (i8)(dir8_dx[d] * speed), (i8)(dir8_dy[d] * speed), damage);
}

static void signature_fat_lane(entity_t *e, u8 count, i8 speed, u8 width) {
    static const i8 offsets[5] = { -12, -6, 0, 6, 12 };
    u8 k, start = (u8)((5 - count) >> 1);
    u8 damage = signature_damage(e);
    i16 cx = FIX8_TO_INT(e->x) + 12;
    i16 cy = FIX8_TO_INT(e->y) + 12;
    i16 px = (i16)player.x + 8;
    i16 py = (i16)player.y + 12;
    i16 perpendicular;
    u8 forward;

    for (k = start; k < (u8)(start + count); ++k) {
        i8 offset = offsets[k];
        projectile_spawn_enemy_v(
            cx + ((signature_dir & 2) ? 0 : offset),
            cy + ((signature_dir & 2) ? offset : 0),
            (i8)(dir8_dx[signature_dir] * speed),
            (i8)(dir8_dy[signature_dir] * speed), damage);
    }
    if (signature_dir & 2) {
        perpendicular = signature_abs(py - cy);
        forward = (signature_dir == 2) ? px >= cx : px <= cx;
    } else {
        perpendicular = signature_abs(px - cx);
        forward = (signature_dir == 4) ? py >= cy : py <= cy;
    }
    if (forward && perpendicular < width) signature_hurt(e);
}

static void signature_arm(entity_t *e) {
    i16 cx = FIX8_TO_INT(e->x) + 12;
    i16 cy = FIX8_TO_INT(e->y) + 12;
    i16 dx = (i16)player.x + 8 - cx;
    i16 dy = (i16)player.y + 12 - cy;
    signature_x = (u8)(player.x + 8);
    signature_y = (u8)(player.y + 12);
    if (signature_abs(dx) >= signature_abs(dy))
        signature_dir = dx >= 0 ? 2 : 6;
    else signature_dir = dy >= 0 ? 4 : 0;
}

static void signature_warn(entity_t *e) {
    u8 stage = e->ai_data[2];
    u8 step = (u8)((48 - e->ai_data[1]) >> 3);
    i16 cx = FIX8_TO_INT(e->x) + 12;
    i16 cy = FIX8_TO_INT(e->y) + 12;
    i16 x = cx, y = cy;
    i16 distance;

    if (stage == 0 || stage == 2 || stage == 7) {
        distance = (i16)(16 + step * 12);
        x += (i16)dir8_dx[signature_dir] * distance;
        y += (i16)dir8_dy[signature_dir] * distance;
    } else if (stage == 5) {
        x = (i16)(20 + step * 32);
        y = signature_y;
    } else if (stage == 6) {
        x = signature_x; y = signature_y;
        distance = (i16)(8 + step * 6);
        x += (i16)dir8_dx[(step & 3) << 1] * distance;
        y += (i16)dir8_dy[(step & 3) << 1] * distance;
    } else if (stage == 3) {
        distance = (i16)(12 + step * 8);
        if (step & 1) x += (step & 2) ? distance : -distance;
        else y += (step & 2) ? distance : -distance;
    } else {
        distance = (i16)(10 + step * 8);
        x += (i16)dir8_dx[(step & 3) << 1] * distance;
        y += (i16)dir8_dy[(step & 3) << 1] * distance;
    }
    fx_spawn(SPR_SHIELD_AURA, 2, x, y, 10);
    e->ai_data[7] = 5;
    sfx_play(SFX_TICK);
}

static void signature_fire(entity_t *e) {
    u8 stage = e->ai_data[2];
    u8 d;
    i16 cx = FIX8_TO_INT(e->x) + 12;
    i16 cy = FIX8_TO_INT(e->y) + 12;
    i16 px = (i16)player.x + 8;
    i16 py = (i16)player.y + 12;
    i16 dx, dy;

    room_shake(3, 28);
    e->ai_data[7] = 12;
    switch (stage) {
        case 0: // Crystal: three-wide Prism Lance
            signature_fat_lane(e, 3, 3, 13);
            break;
        case 1: // Serpent: Coil Tempest around the mobile hood
            signature_ring(e, cx, cy, 2);
            dx = signature_abs(px - cx); dy = signature_abs(py - cy);
            if (dx < 76 && dy < 76) signature_hurt(e);
            break;
        case 2: // Maw: five-wide Furnace Breath
            signature_fat_lane(e, 5, 3, 19);
            break;
        case 3: // Spider: two crossing Web Crucifix bands
            for (d = 0; d < 8; d += 2) {
                projectile_spawn_enemy_v(cx, cy,
                    (i8)(dir8_dx[d] * 2), (i8)(dir8_dy[d] * 2),
                    signature_damage(e));
                projectile_spawn_enemy_v(cx + dir8_dy[d] * 8,
                    cy - dir8_dx[d] * 8,
                    (i8)(dir8_dx[d] * 2), (i8)(dir8_dy[d] * 2),
                    signature_damage(e));
            }
            if (signature_abs(px - cx) < 12 || signature_abs(py - cy) < 12)
                signature_hurt(e);
            break;
        case 4: // Mire: Miasma Bloom
            signature_ring(e, cx, cy, 1);
            if (signature_abs(px - cx) < 64 && signature_abs(py - cy) < 64)
                signature_hurt(e);
            break;
        case 5: { // Reaper: horizontal Death Sweep through the marked row
            static const i8 offsets[5] = { -12, -6, 0, 6, 12 };
            i8 speed = signature_x >= cx ? 3 : -3;
            for (d = 0; d < 5; ++d)
                projectile_spawn_enemy_v(cx, signature_y + offsets[d],
                    speed, 0, signature_damage(e));
            if (signature_abs(py - signature_y) < 16) signature_hurt(e);
            break;
        }
        case 6: // Golem: Sunfall at the announced ground point
            signature_ring(e, signature_x, signature_y, 2);
            if (signature_abs(px - signature_x) < 36
                && signature_abs(py - signature_y) < 36) signature_hurt(e);
            break;
        case 7: // Hydra: five-wide Threefold Deluge
            signature_fat_lane(e, 5, 3, 19);
            break;
        case 8: // Void Lord: Event Horizon beneath recurring World Collapse
        default:
            signature_ring(e, cx, cy, 3);
            if (signature_abs(px - cx) < 96 && signature_abs(py - cy) < 96)
                signature_hurt(e);
            break;
    }
    sfx_play(SFX_DEATH);
}

u8 colossus_signature_tick(entity_t *e) BANKED {
    if (!(e->ai_data[3] & 1)) return 0;
    if (e->ai_data[3] & 0x40) {
        if (e->ai_data[1] <= 1) {
            e->ai_data[3] &= (u8)~0x40;
            signature_fire(e);
            e->ai_data[1] = 36;
            return 1;
        }
        if ((e->ai_data[1] & 7) == 0) signature_warn(e);
        e->ai_data[1]--;
        return 1;
    }
    if (!(e->ai_data[3] & 0x80)
        && e->hp <= (u8)(e->ai_data[6] >> 1)) {
        e->ai_data[3] |= 0xC0;
        e->ai_data[1] = 48;
        e->ai_data[7] = 20;
        signature_arm(e);
        room_shake(1, 16);
        sfx_play(SFX_ROAR);
        return 1;
    }
    // A second, faster crisis at quarter health prevents an otherwise solved
    // first half from becoming a stationary damage race. Bit 5 records this
    // repeat independently of the original spent/charging flags.
    if ((e->ai_data[3] & 0x80) && !(e->ai_data[3] & 0x20)
        && e->hp <= (u8)(e->ai_data[6] >> 2)) {
        e->ai_data[3] |= 0x60;
        e->ai_data[1] = 36;
        e->ai_data[7] = 20;
        signature_arm(e);
        room_shake(2, 18);
        sfx_play(SFX_ROAR);
        return 1;
    }
    return 0;
}
