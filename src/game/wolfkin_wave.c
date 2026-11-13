#pragma bank 255

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/wolfkin_wave.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

// Wolfkin's full-Will Moonfang Rush: a chunky two-cel crescent of force
// ahead of him plus a frontal guard for the length of the body dash.
// Spec: docs/superpowers/specs/2026-11-12-wolfkin-will-wave.md

u8 wolfkin_wave_guard_ticks;
u8 wolfkin_wave_fx_ticks;
static i8 wave_dx, wave_dy;
static u8 wave_slot[3];
// Bodies met head-on this rush: ramming through one keeps it blocked even
// once its centre slips behind him. Cleared on every cast.
static u8 wave_met[MAX_ENTITIES / 8];

// E-facing ")" crescent and its ragged crash cel; S-facing is the
// transpose. Flip bits mirror them for W and N.
static const u8 wave_tiles[64] = {
    0x30, 0x30, 0x18, 0x1C, 0x0C, 0x0E, 0x0D, 0x0E,
    0x0D, 0x0E, 0x0C, 0x0E, 0x18, 0x1C, 0x30, 0x30,
    0x48, 0x4C, 0x39, 0x3C, 0x1C, 0x1E, 0x0F, 0x8E,
    0x0F, 0x8E, 0x1C, 0x1E, 0x39, 0x3C, 0x48, 0x4C,
    0x00, 0x00, 0x00, 0x00, 0x81, 0x81, 0xC3, 0xC3,
    0x7E, 0x7E, 0x3C, 0x7E, 0x00, 0x3C, 0x18, 0x00,
    0x00, 0x18, 0x81, 0x81, 0x42, 0x42, 0x66, 0x66,
    0xFF, 0xFF, 0x3C, 0xFF, 0x18, 0x3C, 0x5A, 0x00,
};

// The Will meter's own violet ramp (hud.c), borrowed by the hero and his
// weapon slot for the length of the wave.
static const u16 will_flash_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555( 9,  5, 14),
    BGR555(24,  8, 31),
    BGR555(31, 23, 31),
};

// Is a hostile in Wolfkin's forward 90-degree cone? Measured from his
// 6x6 feet hurtbox centre to the hostile's hitbox centre.
static u8 wave_in_front(const entity_t *e, u8 reach) {
    i16 rx = (i16)(e->x + (i16)(e->hitbox >> 5)) - (i16)(player.x + 8);
    i16 ry = (i16)(e->y + (i16)((e->hitbox & 0x0F) >> 1)) - (i16)(player.y + 12);
    i16 dot = (i16)(rx * wave_dx + ry * wave_dy);
    i16 cross = (i16)(rx * wave_dy - ry * wave_dx);
    if (cross < 0) cross = -cross;
    if (dot <= 0 || dot < cross) return 0;
    if (reach) {
        if (rx < 0) rx = -rx;
        if (ry < 0) ry = -ry;
        if (rx + ry > reach) return 0;
    }
    return 1;
}

void wolfkin_wave_begin(u8 dir, u8 damage) BANKED {
    i8 k;
    u8 vertical;
    wave_dx = dir8_dx[dir & 7];
    wave_dy = dir8_dy[dir & 7];
    vertical = wave_dx == 0;
    set_sprite_data(SPR_FX_WAVE_E_A, 4, wave_tiles);
    for (k = 0; k < (i8)sizeof(wave_met); ++k) wave_met[k] = 0;
    for (k = -1; k <= 1; ++k) {
        // Perpendicular offsets fan the three pieces into one crescent;
        // the flanks trail four pixels behind the centre.
        i16 px = (i16)player.x + 4 + wave_dx * 12 - wave_dy * k * 9;
        i16 py = (i16)player.y + 6 + wave_dy * 12 + wave_dx * k * 9;
        u8 shot;
        if (k) {
            px -= wave_dx * 4;
            py -= wave_dy * 4;
        }
        shot = projectile_spawn_player(wave_dx, wave_dy,
            (u8)(damage + (k ? 3 : 4)), PROJ_SPIKE);
        wave_slot[k + 1] = shot;
        if (shot == 0xFF) continue;
        entities[shot].x = px;
        entities[shot].y = py;
        entities[shot].vx = (i8)(wave_dx * 4);
        entities[shot].vy = (i8)(wave_dy * 4);
        entities[shot].hp = 4;                 // pierce: a wide crowd hit
        entities[shot].state_timer = WOLFKIN_WAVE_TTL;
        entities[shot].hitbox = 0xBB;
        entities[shot].palette = 2;
        entities[shot].sprite_tile = vertical ? SPR_FX_WAVE_S_A : SPR_FX_WAVE_E_A;
        entities[shot].ai_data[4] = (u8)((wave_dx < 0 ? PROJ_VIS_FLIP_X : 0)
            | (wave_dy < 0 ? PROJ_VIS_FLIP_Y : 0));
        // One authored MAX: the convergence limiter keeps overlapping
        // pieces from deleting a Colossus in a single frame.
        entities[shot].ai_data[3] |= PROJ_FLAG_CONVERGENCE | PROJ_FLAG_WILL_WAVE;
    }
    fx_spawn(SPR_FX_IMPACT, 2,
        (i16)player.x + 4 + wave_dx * 20, (i16)player.y + 6 + wave_dy * 20, 10);
    palette_obj_load(1, will_flash_palette);
    palette_obj_load(2, will_flash_palette);
    wolfkin_wave_guard_ticks = WOLFKIN_WAVE_GUARD_FRAMES;
    wolfkin_wave_fx_ticks = WOLFKIN_WAVE_FX_FRAMES;
}

u8 wolfkin_wave_absorb(u8 idx) BANKED {
    entity_t *e = &entities[idx];
    u8 bit = (u8)(1 << (idx & 7));
    if (!wolfkin_wave_guard_ticks) return 0;
    if (e->type == ENT_PROJECTILE) {
        // The Reaper's warned scythe keeps its own contract.
        if (e->ai_data[6] == PROJ_AUX_MORTAL_SCYTHE
            || !wave_in_front(e, 0)) return 0;
        fx_spawn(SPR_FX_IMPACT, 2, (i16)e->x, (i16)e->y, 7);
        entity_kill(idx);
        return 1;
    }
    if (wave_met[idx >> 3] & bit) return 1;
    if (!wave_in_front(e, 0)) return 0;
    wave_met[idx >> 3] |= bit;
    return 1;
}

void wolfkin_wave_tick(void) BANKED {
    u8 i;
    if (wolfkin_wave_guard_ticks) {
        wolfkin_wave_guard_ticks--;
        // The wave front eats hostile shots before they reach him.
        for (i = 0; i < MAX_ENTITIES; ++i) {
            entity_t *e = &entities[i];
            if ((e->flags & EF_ACTIVE) && e->type == ENT_PROJECTILE
                && !(e->flags & EF_PLAYER_PROJ)
                && e->ai_data[6] != PROJ_AUX_MORTAL_SCYTHE
                && wave_in_front(e, WOLFKIN_WAVE_EAT_REACH)) {
                fx_spawn(SPR_FX_IMPACT, 2, (i16)e->x, (i16)e->y, 7);
                entity_kill(i);
            }
        }
    }
    if (wolfkin_wave_fx_ticks) {
        wolfkin_wave_fx_ticks--;
        for (i = 0; i < 3; ++i) {
            u8 s = wave_slot[i];
            entity_t *e;
            if (s == 0xFF) continue;
            e = &entities[s];
            if (!(e->flags & EF_ACTIVE) || e->type != ENT_PROJECTILE
                || e->sprite_tile < SPR_FX_WAVE_E_A
                || e->sprite_tile > SPR_FX_WAVE_S_B) {
                wave_slot[i] = 0xFF;
                continue;
            }
            // Two-cel crash: swap every three frames.
            e->sprite_tile = (u8)((e->sprite_tile & 0xFE)
                | ((wolfkin_wave_fx_ticks / 3) & 1));
        }
        if (!wolfkin_wave_fx_ticks) room_refresh_player_appearance(0);
    }
}
