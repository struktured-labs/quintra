#pragma bank 31
// M4 Lockmire Ferry (OBJ list, Pack line, guards; bank 31): matching keys, flip-conveyor, lure (spec 6.7-6.9, M4).
// This file: bank 31 (rules in 27, view in 23, art in 24). The Stone Jagger here is a
// puzzle-owned actor (not an entity): nothing can hurt it, and its touch
// only shoves the hero back. All state is WRAM rebuilt on entry.
#include <gb/gb.h>
#include <gbdk/console.h>
#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/enemy_new_ai.h"
#include "game/lock_room.h"
#include "game/conduit_room.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/rime_room.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/lock_art.h"
#include "render/text.h"
#include "render/tiles.h"
#include "content.h"

#include "game/lock_room_int.h"
#define WX(lx) ((u8)(LK_X0 + (lx)))
#define WY(ly) ((u8)(LK_Y0 + (ly)))
#define PX(lx) ((u8)(WX(lx) << 3))
#define PY(ly) ((u8)(WY(ly) << 3))

static void evict_enemies(void) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 cx, cy;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        cx = e->x + 8; cy = e->y + 8;
        if (cx < (i16)puzzle_keep_x0 || cy < (i16)puzzle_keep_y0
            || cy >= (i16)puzzle_keep_y1) continue;
        e->x = (i16)PX(-4);
        e->y = (i16)PY(LK_ENTRY_Y);
    }
}

static void absorb_shots(void) {
    u8 i, hit = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        u8 w, h;
        if ((e->flags & (EF_ACTIVE | EF_PLAYER_PROJ))
            != (EF_ACTIVE | EF_PLAYER_PROJ) || e->type != ENT_PROJECTILE) continue;
        w = (u8)(e->hitbox >> 4); h = (u8)(e->hitbox & 0x0F);
        if (e->x + w <= (i16)lk_jx + 1 || e->x >= (i16)lk_jx + 15) continue;
        if (e->y + h <= (i16)lk_jy + 1 || e->y >= (i16)lk_jy + 16) continue;
        entity_kill(i);
        hit = 1;
    }
    if (hit) sfx_play(SFX_TICK);
}

void lk_guard_step(void) BANKED {
    absorb_shots();
    if (!(lk_frame & 7) || lk_frame == 1) evict_enemies();
}

// Pack TOOL entries: 0 = LURE (drop at the feet), 1 = RESET ROOM.
void lk_pack_draw(u8 idx) BANKED {
    gotoxy(3, 15);
    if (idx == 0) {
        text_write("TOOL LURE x");
        text_u16(lk_lure == 1 ? 1 : 0);
        text_write("   ");
        set_sprite_tile(8, LK_TILE_LURE_PIP);
        set_sprite_prop(8, 5 | 0x08);
    } else {
        text_write("TOOL RESET ROOM");
        set_sprite_tile(8, LK_TILE_PLATE);
        set_sprite_prop(8, 5 | 0x08);
    }
    move_sprite(8, 16, 135);
}

/* ---- OBJ list for nm_extras_draw (kept here: the draw file's bank is full) ---- */
u8 lk_spr_n;
u8 lk_spr_x[LK_SPR_MAX], lk_spr_y[LK_SPR_MAX], lk_spr_t[LK_SPR_MAX], lk_spr_p[LK_SPR_MAX];
static const u8 lk_bow_pal[3] = { 4 | 0x08, 5 | 0x08, 0 | 0x08 };
static const u8 lk_ped_x[3] = { 2, 5, 1 }, lk_ped_y[3] = { 1, 1, 15 };
static const u8 lk_door_x[4] = { 5, 9, 3, 8 }, lk_door_y[4] = { 8, 3, 15, 15 };
static const u8 lk_door_k[4] = { 1, 2, 0, 0 };
static void sp(u8 x, u8 y, u8 t, u8 p) {
    u8 n = lk_spr_n;
    if (n >= LK_SPR_MAX) return;
    lk_spr_x[n] = x; lk_spr_y[n] = y; lk_spr_t[n] = t; lk_spr_p[n] = p;
    lk_spr_n = (u8)(n + 1);
}
static void sq(u8 x, u8 y, u8 t, u8 p) {
    sp(x, y, t, p); sp((u8)(x + 8), y, (u8)(t + 1), p);
    sp(x, (u8)(y + 8), (u8)(t + 2), p); sp((u8)(x + 8), (u8)(y + 8), (u8)(t + 3), p);
}
void lk_sprites(void) BANKED {
    u8 k, n = 0, i = 0, x, y;
    if (cd_live) { cd_sprites(); return; }
    lk_spr_n = 0;
    sq(lk_jx, lk_jy, (lk_jst == LK_J_SEEK && ((entity_anim_counter >> 3) & 1))
        ? LK_TILE_JAGGER_WALK : LK_TILE_JAGGER, 0 | 0x08);
    sq(PX(LK_RESET_X), PY(LK_RESET_Y), LK_TILE_PLATE, 5 | 0x08);
    x = PX(LK_FLIP_X); y = PY(LK_FLIP_Y);
    if (!lk_dir) sq(x, y, LK_TILE_FLIP, 3 | 0x08);
    else {
        /* West: the same glyph mirrored. */
        sp(x, y, (u8)(LK_TILE_FLIP + 1), 3 | 0x08 | 0x20);
        sp((u8)(x + 8), y, LK_TILE_FLIP, 3 | 0x08 | 0x20);
        sp(x, (u8)(y + 8), (u8)(LK_TILE_FLIP + 3), 3 | 0x08 | 0x20);
        sp((u8)(x + 8), (u8)(y + 8), (u8)(LK_TILE_FLIP + 2), 3 | 0x08 | 0x20);
    }
    if (lk_lure == 0) sq(PX(LK_LURE_X), PY(LK_LURE_Y), LK_TILE_LURE, 5 | 0x08);
    else if (lk_lure == 2) sq(lk_lx, lk_ly, LK_TILE_LURE, 5 | 0x08);
    for (k = 0; k < 3; ++k) {
        if (lk_held & (1 << k)) n++;
        if (!(lk_ped & (1 << k))) continue;
        x = (u8)(PX(lk_ped_x[k]) + 4); y = PY(lk_ped_y[k]);
        sp(x, y, (u8)(LK_TILE_BOW + k), lk_bow_pal[k]);
        sp(x, (u8)(y + 8), LK_TILE_SHAFT, lk_bow_pal[k]);
    }
    /* Door plaques: the icon of the key each door takes. */
    for (k = 0; k < 4; ++k) {
        if (lk_open & (1 << k)) continue;
        x = PX(lk_door_x[k]); y = PY(lk_door_y[k]);
        if (k < 2) x += 4; else y += 4;
        sp(x, y, (u8)(LK_TILE_BOW + lk_door_k[k]), lk_bow_pal[lk_door_k[k]]);
    }
    /* Held pips above the hero: keys, then the lure. */
    if (lk_lure == 1) n++;
    if (!n) return;
    x = (u8)((u8)player.x + 4 - (u8)((n - 1) << 2));
    y = (u8)((u8)player.y - 9);
    for (k = 0; k < 3; ++k)
        if (lk_held & (1 << k)) { sp((u8)(x + (i << 3)), y, (u8)(LK_TILE_BOW + k), lk_bow_pal[k]); i++; }
    if (lk_lure == 1) sp((u8)(x + (i << 3)), y, LK_TILE_LURE_PIP, 5 | 0x08);
}
