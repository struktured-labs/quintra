#pragma bank 255
// Mire Heart's floor roots. BG overlay on the nine colossus slots, which the
// stage-4 tilemap does not use. room_tilemap stays floor, so shots pass over.

#include <gb/gb.h>

#include "audio/boss_voice.h"
#include "audio/sfx.h"
#include "content.h"
#include "game/boss_phase.h"
#include "game/mire_roots.h"
#include "game/player.h"
#include "game/room.h"
#include "render/tiles.h"

u8 mire_root_active;
u8 mire_root_windup;
u8 mire_root_u;

static u8 root_variant;
static u8 cell_count;
static u8 draw_stamp;
static i16 anchor_x, anchor_y;
static u8 cell_tx[24];
static u8 cell_ty[24];
static u8 cell_kind[24];
static u8 cell_step[24];

// Two patterns, four branches, six steps. Variants 2 and 3 rotate these.
// Steps 1..4 are the continuous inner vein. Steps 5..6 are the outer fork,
// two tiles farther out, so the tiles in between stay walkable.
static const i8 pat_dx[2][4][6] = {
    {
        {  2,  3,  4,  5,  8,  8 },
        {  0,  0,  0, -1,  0, -2 },
        { -2, -3, -4, -5, -8, -8 },
        {  0,  0,  0,  1,  0,  2 },
    },
    {
        {  2,  3,  4,  5,  8,  7 },
        { -2, -3, -4, -5, -8, -7 },
        { -2, -3, -4, -5, -8, -7 },
        {  2,  3,  4,  5,  8,  7 },
    },
};
static const i8 pat_dy[2][4][6] = {
    {
        {  0,  0,  0,  1,  0,  2 },
        { -2, -3, -4, -5, -8, -8 },
        {  0,  0,  0,  1,  0,  2 },
        {  2,  3,  4,  5,  8,  8 },
    },
    {
        { -2, -3, -4, -5, -8, -6 },
        { -2, -3, -4, -5, -8, -6 },
        {  2,  3,  4,  5,  8,  6 },
        {  2,  3,  4,  5,  8,  6 },
    },
};
static const u8 pat_k[2][4][6] = {
    {
        { 1, 1, 1, 4, 1, 2 },
        { 2, 2, 2, 3, 2, 1 },
        { 1, 1, 1, 3, 1, 2 },
        { 2, 2, 2, 4, 2, 1 },
    },
    {
        { 4, 4, 4, 4, 4, 1 },
        { 3, 3, 3, 3, 3, 1 },
        { 4, 4, 4, 4, 4, 1 },
        { 3, 3, 3, 3, 3, 1 },
    },
};

static u8 rot_kind(u8 kind) {
    static const u8 map[9] = { 0, 2, 1, 4, 3, 8, 7, 5, 6 };
    return map[kind < 9 ? kind : 0];
}

static void rot90(i8 *x, i8 *y) {
    i8 nx = (i8)-(*y);
    *y = *x;
    *x = nx;
}

static u8 in_arena(u8 tx, u8 ty) {
    u8 max_x = (u8)((room_world_width >> 3) - 1);
    u8 max_y = (u8)((room_world_height >> 3) - 1);
    if (!tx || !ty || tx >= max_x || ty >= max_y) return 0;
    return room_tile_walkable(room_tile_at_px((i16)tx << 3, (i16)ty << 3));
}

static u8 body_covers(u8 tx, u8 ty) {
    i16 x0 = (i16)(anchor_x + 4);
    i16 y0 = (i16)(anchor_y - 2);
    i16 px = (i16)tx << 3;
    i16 py = (i16)ty << 3;
    return (px < x0 + 24 && px + 8 > x0 && py < y0 + 36 && py + 8 > y0) ? 1 : 0;
}

static u8 cell_at(u8 tx, u8 ty) {
    u8 i;
    for (i = 0; i < cell_count; ++i)
        if (cell_tx[i] == tx && cell_ty[i] == ty) return 1;
    return 0;
}

static u8 build(entity_t *e, u8 variant, u8 prune) {
    u8 pat = (u8)(variant & 1);
    u8 spin = (variant & 2) ? 1 : 0;
    u8 cx = (u8)((FIX8_TO_INT(e->x) + 16) >> 3);
    u8 cy = (u8)((FIX8_TO_INT(e->y) + 16) >> 3);
    u8 branches = 0;
    u8 b, s;
    cell_count = 0;
    for (b = 0; b < 4; ++b) {
        u8 grew = 0;
        if (prune & (u8)(1 << b)) continue;
        for (s = 0; s < 6; ++s) {
            i8 dx = pat_dx[pat][b][s];
            i8 dy = pat_dy[pat][b][s];
            u8 kind = pat_k[pat][b][s];
            i16 tx, ty;
            if (spin) {
                rot90(&dx, &dy);
                kind = rot_kind(kind);
            }
            tx = (i16)cx + dx;
            ty = (i16)cy + dy;
            if (tx < 1 || ty < 1 || tx > 30 || ty > 30) break;
            if (!in_arena((u8)tx, (u8)ty)) break;
            if (cell_count >= 24) break;
            cell_tx[cell_count] = (u8)tx;
            cell_ty[cell_count] = (u8)ty;
            cell_kind[cell_count] = kind;
            cell_step[cell_count] = (u8)(s + 1);
            cell_count++;
            grew = 1;
        }
        if (grew) branches++;
    }
    return branches;
}

static u8 safe_tile(u8 tx, u8 ty) {
    if (!in_arena(tx, ty)) return 0;
    if (cell_at(tx, ty)) return 0;
    if (body_covers(tx, ty)) return 0;
    return 1;
}

// 9x9 window around the player. A safe pocket is three connected floor tiles
// the player is already on, or one step away from.
static u8 escape_ok(void) {
    static u8 seen[9][9];
    u8 qx[32], qy[32];
    u8 ptx = (u8)((player.x + 8) >> 3);
    u8 pty = (u8)((player.y + 12) >> 3);
    u8 ox = (ptx > 4) ? (u8)(ptx - 4) : 0;
    u8 oy = (pty > 4) ? (u8)(pty - 4) : 0;
    u8 start;
    static const i8 ndx[4] = { 1, -1, 0, 0 };
    static const i8 ndy[4] = { 0, 0, 1, -1 };
    for (start = 0; start < 5; ++start) {
        u8 sx = ptx;
        u8 sy = pty;
        u8 head = 0, tail = 0, count = 0;
        u8 n, m, lx, ly;
        for (n = 0; n < 9; ++n)
            for (m = 0; m < 9; ++m) seen[n][m] = 0;
        if (start) {
            sx = (u8)((i16)ptx + ndx[start - 1]);
            sy = (u8)((i16)pty + ndy[start - 1]);
        }
        if (sx < ox || sy < oy || sx >= (u8)(ox + 9) || sy >= (u8)(oy + 9))
            continue;
        if (!safe_tile(sx, sy)) continue;
        if (!start && !safe_tile(ptx, pty)) continue;
        qx[0] = sx;
        qy[0] = sy;
        tail = 1;
        seen[sy - oy][sx - ox] = 1;
        while (head < tail) {
            u8 d;
            lx = qx[head];
            ly = qy[head];
            head++;
            count++;
            if (count >= 3) return 1;
            for (d = 0; d < 4; ++d) {
                u8 nx = (u8)((i16)lx + ndx[d]);
                u8 ny = (u8)((i16)ly + ndy[d]);
                if (nx < ox || ny < oy || nx >= (u8)(ox + 9) || ny >= (u8)(oy + 9))
                    continue;
                if (seen[ny - oy][nx - ox]) continue;
                if (!safe_tile(nx, ny)) continue;
                if (tail >= 32) continue;
                seen[ny - oy][nx - ox] = 1;
                qx[tail] = nx;
                qy[tail] = ny;
                tail++;
            }
        }
    }
    return 0;
}

static void pack_state(entity_t *e) {
    e->ai_data[4] = (u8)((root_variant & 3) | ((u8)((mire_root_u >> 1) + 1) << 2));
}

static void accept(entity_t *e, u8 variant) {
    root_variant = (u8)(variant & 3);
    mire_root_active = 1;
    draw_stamp = 0xFF;
    pack_state(e);
}

static void try_begin(entity_t *e) {
    u8 base = (player.x > FIX8_TO_INT(e->x)) ? 1 : 0;
    u8 r, b;
    anchor_x = FIX8_TO_INT(e->x);
    anchor_y = FIX8_TO_INT(e->y);
    for (r = 0; r < 4; ++r) {
        u8 variant = (u8)((base + r) & 3);
        if (build(e, variant, 0) >= 2 && escape_ok()) {
            accept(e, variant);
            boss_voice(4, BOSS_VOICE_ATTACK);
            sfx_play(SFX_TICK);
            return;
        }
    }
    for (r = 0; r < 4; ++r) {
        u8 variant = (u8)((base + r) & 3);
        for (b = 0; b < 4; ++b) {
            if (build(e, variant, (u8)(1 << b)) >= 2 && escape_ok()) {
                accept(e, variant);
                boss_voice(4, BOSS_VOICE_ATTACK);
                sfx_play(SFX_TICK);
                return;
            }
        }
    }
    cell_count = 0;
    mire_root_active = 0;
    mire_root_windup = 0;
    e->ai_data[4] = 0;
}

static u8 step_hot(u8 step) {
    if (mire_root_u < 48 || mire_root_u >= 88) return 0;
    if (mire_root_u >= 72) return 1;
    return step <= (u8)(((mire_root_u - 48) >> 2) + 1);
}

static u8 on_vein(u8 kind, u8 relx, u8 rely) {
    i8 d;
    if (!kind || kind > 8) return 0;
    if (kind == 1) return (rely >= 2 && rely <= 5) ? 1 : 0;
    if (kind == 2) return (relx >= 2 && relx <= 5) ? 1 : 0;
    if (kind == 3) {
        d = (i8)relx - (i8)rely;
        if (d < 0) d = (i8)-d;
        return d <= 1;
    }
    if (kind == 4) {
        d = (i8)((i8)relx + (i8)rely - 7);
        if (d < 0) d = (i8)-d;
        return d <= 1;
    }
    // Junctions: 4px hub plus only the painted arms.
    if (relx >= 2 && relx <= 5 && rely >= 2 && rely <= 5) return 1;
    if ((kind == 5 || kind == 7 || kind == 8) && relx >= 2 && relx <= 5 && rely < 2)
        return 1;
    if ((kind == 6 || kind == 7) && relx >= 2 && relx <= 5 && rely > 5) return 1;
    if ((kind == 5 || kind == 6 || kind == 8) && rely >= 2 && rely <= 5 && relx < 2)
        return 1;
    if ((kind == 5 || kind == 6 || kind == 7) && rely >= 2 && rely <= 5 && relx > 5)
        return 1;
    return 0;
}

static u8 paint_stamp(void) {
    if (mire_root_u < 8) return 0;
    if (mire_root_u < 36) return 1;
    if (mire_root_u < 48) return (u8)(2 + ((mire_root_u >> 2) & 1));
    if (mire_root_u < 88) return (u8)(4 + ((mire_root_u - 48) >> 2));
    return 9;
}

static void stamp_cell(u8 i, u8 restore) {
    u8 tx = cell_tx[i];
    u8 ty = cell_ty[i];
    u8 tile, attr;
    u8 mx = ROOM_BG_MAP_X(tx);
    u8 my = ROOM_BG_MAP_Y(ty);
    if (restore || mire_root_u < 8) {
        tile = room_tile_at_px((i16)tx << 3, (i16)ty << 3);
        attr = (tile == BGT_WALL) ? BGPAL_WALL
            : (tile == BGT_DOOR) ? BGPAL_DOOR : BGPAL_FLOOR;
    } else if (step_hot(cell_step[i])) {
        tile = (u8)(BGT_COLOSSUS_VOID + cell_kind[i]);
        attr = BGPAL_CRYSTAL;
    } else {
        // Ghost preview and the harmless wither share the dotted bud.
        tile = BGT_COLOSSUS_VOID;
        attr = (mire_root_u >= 36 && mire_root_u < 48 && ((mire_root_u >> 2) & 1))
            ? BGPAL_CRYSTAL : BGPAL_WALL;
    }
    VBK_REG = 0;
    set_bkg_tiles(mx, my, 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(mx, my, 1, 1, &attr);
    VBK_REG = 0;
}

static void redraw(u8 restore) {
    u8 i;
    for (i = 0; i < cell_count; ++i) stamp_cell(i, restore);
}

static u8 sample_hits(i16 px, i16 py) {
    u8 i;
    u8 tx, ty, relx, rely;
    if (px < 0 || py < 0) return 0;
    tx = (u8)(px >> 3);
    ty = (u8)(py >> 3);
    relx = (u8)(px & 7);
    rely = (u8)(py & 7);
    for (i = 0; i < cell_count; ++i) {
        if (cell_tx[i] != tx || cell_ty[i] != ty) continue;
        if (!step_hot(cell_step[i])) return 0;
        return on_vein(cell_kind[i], relx, rely);
    }
    return 0;
}

static u8 roots_touch(void) {
    i16 x = player.x;
    i16 y = player.y;
    if (sample_hits((i16)(x + 8), (i16)(y + 12))) return 1;
    if (sample_hits((i16)(x + 5), (i16)(y + 10))) return 1;
    if (sample_hits((i16)(x + 11), (i16)(y + 10))) return 1;
    if (sample_hits((i16)(x + 5), (i16)(y + 14))) return 1;
    if (sample_hits((i16)(x + 11), (i16)(y + 14))) return 1;
    return 0;
}

static void clear_entity(entity_t *e) {
    if (cell_count) redraw(1);
    cell_count = 0;
    mire_root_active = 0;
    mire_root_windup = 0;
    mire_root_u = 0;
    draw_stamp = 0;
    if (e && e->ai_data[2] == 4) {
        if (e->ai_data[1] < 20) e->ai_data[1] = 20;
        e->ai_data[4] = 0;
    }
}

static entity_t *mire_boss(void) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (entities[i].type == ENT_ENEMY && (entities[i].flags & EF_ACTIVE)
            && entities[i].ai_data[0] == ENEMY_STONE_SENTINEL
            && (entities[i].ai_data[3] & 1) && entities[i].ai_data[2] == 4)
            return &entities[i];
    }
    return 0;
}

void mire_roots_clear(void) BANKED {
    clear_entity(mire_boss());
}

void mire_roots_redraw(void) BANKED {
    if (!mire_root_active || mire_root_u < 8) return;
    draw_stamp = 0xFF;
    redraw(0);
}

static u8 restore_cast(entity_t *e) {
    u8 packed = e->ai_data[4];
    u8 half = (u8)(packed >> 2);
    u8 u;
    if (!half) return 0;
    u = (u8)((half - 1) << 1);
    if (u < 8 || boss_phase_clock < 1 || boss_phase_clock > 96) {
        e->ai_data[4] = 0;
        return 0;
    }
    anchor_x = FIX8_TO_INT(e->x);
    anchor_y = FIX8_TO_INT(e->y);
    root_variant = (u8)(packed & 3);
    if (build(e, root_variant, 0) < 2) {
        e->ai_data[4] = 0;
        cell_count = 0;
        return 0;
    }
    mire_root_active = 1;
    draw_stamp = 0xFF;
    return 1;
}

u8 mire_roots_service(entity_t *e) BANKED {
    u8 stamp;
    u8 hit = 0;
    if (e->ai_data[2] != 4 || !(e->ai_data[3] & 1)) {
        if (mire_root_active) clear_entity(e);
        return 0;
    }
    if (e->x_pad || (e->ai_data[3] & 0x40)) {
        clear_entity(e);
        return 0;
    }
    if (mire_root_active && (boss_phase_clock == 0 || boss_phase_clock > 96)) {
        clear_entity(e);
        return 0;
    }
    if (!mire_root_active && e->ai_data[4]) restore_cast(e);
    if (!mire_root_active && boss_phase_clock == 1) try_begin(e);
    if (!mire_root_active) {
        mire_root_windup = 0;
        return 0;
    }
    if (boss_phase_clock >= 1 && boss_phase_clock <= 96)
        mire_root_u = (u8)(boss_phase_clock - 1);
    mire_root_windup = (mire_root_u < 48) ? 1 : 0;
    pack_state(e);
    if (mire_root_u == 48 || mire_root_u == 60) sfx_play(SFX_TICK);
    stamp = paint_stamp();
    if (stamp != draw_stamp) {
        draw_stamp = stamp;
        if (stamp) redraw(0);
    }
    if (roots_touch()) hit = 1;
    return hit;
}
