#pragma bank 30

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

extern u8 puzzle_block_x;
extern u8 puzzle_block_y;

static void clear_all_cairns(void) {
    u8 x, y;
    for (y = 1; y < ROOM_H - 1; ++y) {
        for (x = 1; x < ROOM_W - 1; ++x) {
            u8 t = room_tilemap[y][x];
            if (t == BGT_BLOCK || t == BGT_BLOCK_TR
                || t == BGT_BLOCK_BL || t == BGT_BLOCK_BR)
                room_tilemap[y][x] = BGT_FLOOR;
        }
    }
}

static void floor_rect(u8 x0, u8 y0, u8 w, u8 h) {
    u8 x, y;
    for (y = y0; y < (u8)(y0 + h); ++y)
        for (x = x0; x < (u8)(x0 + w); ++x)
            room_tilemap[y][x] = BGT_FLOOR;
}

/* ---- tone-path block puzzle (spec 2026-11-21) ---- */

#define TONE_BANK_LEN 8
#define TONE_LEN 4
#define TONE_TEASER_GAP 24
#define TONE_TEASER_COOLDOWN 150
#define TONE_HINT_FLASH 20
#define TONE_LECTURE_FLASH 12

/* Packed first-to-last: each phrase ends West (tonic C5). */
static const u8 tone_bank[TONE_BANK_LEN] = {
    /* 2x2 crate and socket must be at least 2 tiles apart on one axis. */
    (u8)(DIR_N | (DIR_E << 2) | (DIR_N << 4) | (DIR_W << 6)), /* 0 E G E C  (+1,-2) */
    (u8)(DIR_N | (DIR_N << 2) | (DIR_E << 4) | (DIR_W << 6)), /* 1 E E G C  (+1,-2) */
    (u8)(DIR_E | (DIR_N << 2) | (DIR_N << 4) | (DIR_W << 6)), /* 2 G E E C  (0,-2) */
    (u8)(DIR_E | (DIR_S << 2) | (DIR_S << 4) | (DIR_W << 6)), /* 3 G D D C  (0,+2) */
    (u8)(DIR_S | (DIR_E << 2) | (DIR_S << 4) | (DIR_W << 6)), /* 4 D G D C  (+1,+2) */
    (u8)(DIR_N | (DIR_N << 2) | (DIR_W << 4) | (DIR_W << 6)), /* 5 E E C C  (-2,-2) */
    (u8)(DIR_N | (DIR_W << 2) | (DIR_N << 4) | (DIR_W << 6)), /* 6 E C E C  (-2,-2) */
    (u8)(DIR_S | (DIR_W << 2) | (DIR_S << 4) | (DIR_W << 6)), /* 7 D C D C  (-2,+2) */
};

static const i8 tone_dx[4] = { 0, 1, 0, (i8)-1 };
static const i8 tone_dy[4] = { (i8)-1, 0, 1, 0 };
/* DIR_N,E,S,W -> E5, G5, D5, C5 */
static const u8 tone_pitch[4] = { 2, 3, 1, 0 };

static u8 tone_dirs[TONE_LEN];
static u8 tone_progress;
static u8 tone_start_x, tone_start_y;
static u8 tone_misses;
static u8 tone_teaser_cd;
static u8 tone_teaser_step;
static u8 tone_teaser_timer;
static u8 tone_approach;
static u8 tone_hint_timer;
static u8 tone_hint_x, tone_hint_y;
static u8 tone_hint_tile[4], tone_hint_attr[4];
static u8 tone_lecture_step;

static u8 tone_dir_at(u8 packed, u8 i) {
    return (u8)((packed >> (u8)(i * 2)) & 3);
}

static u8 tone_door_slit(u8 x, u8 y) {
    if (((x <= 3 || x >= 15) && y <= 10 && (u8)(y + 1) >= 7)) return 1;
    if (((y <= 3 || y >= 12) && x <= 12 && (u8)(x + 1) >= 7)) return 1;
    return 0;
}

static u8 tone_origin_ok(u8 x, u8 y) {
    if (x < 4 || y < 3 || x > 14 || y > 11) return 0;
    if (tone_door_slit(x, y)) return 0;
    return 1;
}

static u8 tone_attr(u8 x, u8 y, u8 tile) {
    if (tile == BGT_FLOOR3 && PUZZLE_SOCKET_AT(x, y)) return BGPAL_DOOR;
    if (tile == BGT_BLOCK || tile == BGT_BLOCK_TR
        || tile == BGT_BLOCK_BL || tile == BGT_BLOCK_BR)
        return BGPAL_WALL;
    if (tile == BGT_FLOOR2) return BGPAL_CRYSTAL;
    return BGPAL_FLOOR;
}

static void tone_flush_range(u8 x0, u8 y0, u8 x1, u8 y1) {
    u8 x, y, tile, attr;
    wait_vbl_done();
    VBK_REG = 0;
    for (y = y0; y <= y1; ++y)
        for (x = x0; x <= x1; ++x)
            set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1,
                &room_tilemap[y][x]);
    VBK_REG = 1;
    for (y = y0; y <= y1; ++y)
        for (x = x0; x <= x1; ++x) {
            tile = room_tilemap[y][x];
            attr = tone_attr(x, y, tile);
            set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &attr);
        }
    VBK_REG = 0;
}

static void tone_clear_crate(u8 x, u8 y) {
    u8 i, j;
    for (j = 0; j < 2; ++j)
        for (i = 0; i < 2; ++i) {
            u8 tx = (u8)(x + i), ty = (u8)(y + j);
            room_tilemap[ty][tx] = PUZZLE_SOCKET_AT(tx, ty)
                ? BGT_FLOOR3 : BGT_FLOOR;
        }
}

static void tone_draw_crate(u8 x, u8 y) {
    room_tilemap[y][x] = BGT_BLOCK;
    room_tilemap[y][x + 1] = BGT_BLOCK_TR;
    room_tilemap[y + 1][x] = BGT_BLOCK_BL;
    room_tilemap[y + 1][x + 1] = BGT_BLOCK_BR;
}

static void tone_restore_socket(void) {
    u8 i, j;
    for (j = 0; j < 2; ++j)
        for (i = 0; i < 2; ++i) {
            u8 tx = (u8)(room_socket_x + i), ty = (u8)(room_socket_y + j);
            if (room_tilemap[ty][tx] == BGT_FLOOR
                || room_tilemap[ty][tx] == BGT_FLOOR2
                || room_tilemap[ty][tx] == BGT_FLOOR3)
                room_tilemap[ty][tx] = BGT_FLOOR3;
        }
}

static void tone_place_crate(u8 nx, u8 ny) {
    u8 x0, y0, x1, y1;
    tone_clear_crate(puzzle_block_x, puzzle_block_y);
    tone_draw_crate(nx, ny);
    tone_restore_socket();
    puzzle_block_x = nx;
    puzzle_block_y = ny;
    x0 = nx; y0 = ny; x1 = (u8)(nx + 1); y1 = (u8)(ny + 1);
    if (tone_start_x < x0) x0 = tone_start_x;
    if (tone_start_y < y0) y0 = tone_start_y;
    if ((u8)(tone_start_x + 1) > x1) x1 = (u8)(tone_start_x + 1);
    if ((u8)(tone_start_y + 1) > y1) y1 = (u8)(tone_start_y + 1);
    if (room_socket_x < x0) x0 = room_socket_x;
    if (room_socket_y < y0) y0 = room_socket_y;
    if ((u8)(room_socket_x + 1) > x1) x1 = (u8)(room_socket_x + 1);
    if ((u8)(room_socket_y + 1) > y1) y1 = (u8)(room_socket_y + 1);
    tone_flush_range(x0, y0, x1, y1);
}

static void tone_hint_restore(void) {
    u8 i, j, n, x, y;
    if (!tone_hint_timer) return;
    for (j = 0, n = 0; j < 2; ++j)
        for (i = 0; i < 2; ++i, ++n) {
            x = (u8)(tone_hint_x + i);
            y = (u8)(tone_hint_y + j);
            if (room_tilemap[y][x] == BGT_FLOOR2) {
                room_tilemap[y][x] = tone_hint_tile[n];
            }
        }
    tone_flush_range(tone_hint_x, tone_hint_y,
        (u8)(tone_hint_x + 1), (u8)(tone_hint_y + 1));
    tone_hint_timer = 0;
}

static u8 tone_cell_is_crate(u8 x, u8 y) {
    u8 t = room_tilemap[y][x];
    return (u8)(t == BGT_BLOCK || t == BGT_BLOCK_TR
        || t == BGT_BLOCK_BL || t == BGT_BLOCK_BR);
}

static void tone_flash_cell(u8 x, u8 y, u8 frames) {
    u8 i, j, n, tx, ty, tile = BGT_FLOOR2, attr = BGPAL_CRYSTAL;
    tone_hint_restore();
    tone_hint_x = x;
    tone_hint_y = y;
    for (j = 0, n = 0; j < 2; ++j)
        for (i = 0; i < 2; ++i, ++n) {
            tx = (u8)(x + i);
            ty = (u8)(y + j);
            tone_hint_tile[n] = room_tilemap[ty][tx];
            tone_hint_attr[n] = tone_attr(tx, ty, tone_hint_tile[n]);
            if (!tone_cell_is_crate(tx, ty))
                room_tilemap[ty][tx] = tile;
        }
    tone_hint_timer = frames;
    wait_vbl_done();
    VBK_REG = 0;
    for (j = 0; j < 2; ++j)
        for (i = 0; i < 2; ++i) {
            tx = (u8)(x + i); ty = (u8)(y + j);
            if (room_tilemap[ty][tx] == tile)
                set_bkg_tiles(ROOM_BG_MAP_X(tx), ROOM_BG_MAP_Y(ty), 1, 1, &tile);
        }
    VBK_REG = 1;
    for (j = 0; j < 2; ++j)
        for (i = 0; i < 2; ++i) {
            tx = (u8)(x + i); ty = (u8)(y + j);
            if (room_tilemap[ty][tx] == tile)
                set_bkg_tiles(ROOM_BG_MAP_X(tx), ROOM_BG_MAP_Y(ty), 1, 1, &attr);
        }
    VBK_REG = 0;
}

static void tone_flash_next(u8 frames) {
    u8 dir, x, y;
    if (tone_progress >= TONE_LEN) return;
    dir = tone_dirs[tone_progress];
    x = (u8)(puzzle_block_x + tone_dx[dir]);
    y = (u8)(puzzle_block_y + tone_dy[dir]);
    tone_flash_cell(x, y, frames);
}

void tone_start_teaser(void) BANKED {
    tone_teaser_step = 0;
    tone_teaser_timer = 1;
    tone_teaser_cd = TONE_TEASER_COOLDOWN;
}

static void tone_cancel_teaser(void) {
    tone_teaser_step = 0xFF;
    tone_teaser_timer = 0;
}

static u8 tone_feet_in_crate(u8 cx, u8 cy, u8 px, u8 py) {
    return (u8)(px >= cx && px < (u8)(cx + 2)
        && py >= cy && py < (u8)(cy + 2));
}

static void tone_eject_occupants(u8 toward_x, u8 toward_y) {
    u8 ptx, pty, i;
    ppos_t dest_x, dest_y;
    ptx = (u8)((player.x + 8) >> 3);
    pty = (u8)((player.y + 12) >> 3);
    dest_x = (ppos_t)(toward_x * 8);
    dest_y = (ppos_t)(toward_y * 8 - 8);
    if (tone_feet_in_crate(tone_start_x, tone_start_y, ptx, pty)
        || tone_feet_in_crate(tone_start_x, tone_start_y,
            (u8)((player.x + 2) >> 3), (u8)((player.y + 8) >> 3))
        || tone_feet_in_crate(tone_start_x, tone_start_y,
            (u8)((player.x + 13) >> 3), (u8)((player.y + 15) >> 3))) {
        player.x = dest_x;
        player.y = dest_y;
    }
    for (i = 0; i < MAX_ENTITIES; ++i) {
        u8 ex, ey;
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        if (entities[i].type != ENT_ENEMY) continue;
        ex = (u8)((FIX8_TO_INT(entities[i].x) + 8) >> 3);
        ey = (u8)((FIX8_TO_INT(entities[i].y) + 8) >> 3);
        if (tone_feet_in_crate(tone_start_x, tone_start_y, ex, ey)) {
            entities[i].x = (ppos_t)(toward_x * 8);
            entities[i].y = (ppos_t)(toward_y * 8);
        }
    }
}

static void tone_reset_crate(void) {
    u8 from_x = puzzle_block_x, from_y = puzzle_block_y;
    tone_hint_restore();
    tone_cancel_teaser();
    tone_lecture_step = 0;
    tone_eject_occupants(from_x, from_y);
    tone_place_crate(tone_start_x, tone_start_y);
    tone_progress = 0;
}

static void tone_tick_teaser(void) {
    if (tone_teaser_cd) tone_teaser_cd--;
    if (tone_teaser_step == 0xFF) return;
    if (--tone_teaser_timer) return;
    if (tone_teaser_step >= TONE_LEN) {
        tone_teaser_step = 0xFF;
        return;
    }
    sfx_play_rune_echo(tone_pitch[tone_dirs[tone_teaser_step]]);
    tone_teaser_step++;
    tone_teaser_timer = TONE_TEASER_GAP;
}

static void tone_tick_hints(void) {
    if (tone_hint_timer) {
        tone_hint_timer--;
        if (!tone_hint_timer) {
            tone_hint_timer = 1;
            tone_hint_restore();
            if (tone_lecture_step && tone_lecture_step < TONE_LEN) {
                u8 i, x = tone_start_x, y = tone_start_y;
                for (i = 0; i <= tone_lecture_step; ++i) {
                    x = (u8)(x + tone_dx[tone_dirs[i]]);
                    y = (u8)(y + tone_dy[tone_dirs[i]]);
                }
                tone_lecture_step++;
                tone_flash_cell(x, y, TONE_LECTURE_FLASH);
            } else {
                tone_lecture_step = 0;
            }
        }
    }
}

static void tone_on_miss(void) {
    if (tone_misses < 8) tone_misses++;
    sfx_play_tone_miss();
    tone_reset_crate();
    if (tone_misses == 6) {
        tone_lecture_step = 0;
        tone_flash_next(TONE_LECTURE_FLASH);
        tone_lecture_step = 1;
    } else if (tone_misses >= 3) {
        tone_flash_next(TONE_HINT_FLASH);
    }
}

static u8 tone_follow_block(u8 old_x, u8 old_y, u8 *nx, u8 *ny) {
    *nx = old_x;
    *ny = old_y;
    if (old_x + 1 < ROOM_W && room_tilemap[old_y][old_x + 1] == BGT_BLOCK)
        *nx = (u8)(old_x + 1);
    else if (old_x && room_tilemap[old_y][old_x - 1] == BGT_BLOCK)
        *nx = (u8)(old_x - 1);
    else if (old_y + 1 < ROOM_H && room_tilemap[old_y + 1][old_x] == BGT_BLOCK)
        *ny = (u8)(old_y + 1);
    else if (old_y && room_tilemap[old_y - 1][old_x] == BGT_BLOCK)
        *ny = (u8)(old_y - 1);
    else return 0;
    return 1;
}

static u8 tone_dir_from_delta(u8 ox, u8 oy, u8 nx, u8 ny) {
    if (nx == (u8)(ox + 1) && ny == oy) return DIR_E;
    if (ox && nx == (u8)(ox - 1) && ny == oy) return DIR_W;
    if (ny == (u8)(oy + 1) && nx == ox) return DIR_S;
    if (oy && ny == (u8)(oy - 1) && nx == ox) return DIR_N;
    return DIR_NONE;
}

u8 tone_on_block_moved(u8 old_x, u8 old_y) BANKED {
    u8 nx, ny, dir, expected;
    tone_cancel_teaser();
    tone_hint_restore();
    tone_lecture_step = 0;
    if (old_x != puzzle_block_x || old_y != puzzle_block_y) return 0;
    if (!tone_follow_block(old_x, old_y, &nx, &ny)) return 0;
    dir = tone_dir_from_delta(old_x, old_y, nx, ny);
    /* room.c already wrote the crate at nx,ny. Point the tracker there
       so a miss snap-back clears the wrong cell, not the vacated origin. */
    puzzle_block_x = nx;
    puzzle_block_y = ny;
    if (dir == DIR_NONE || tone_progress >= TONE_LEN) {
        tone_on_miss();
        return 0;
    }
    expected = tone_dirs[tone_progress];
    if (dir != expected) {
        tone_on_miss();
        return 0;
    }
    tone_hint_restore();
    tone_restore_socket();
    {
        u8 x0 = (nx < old_x) ? nx : old_x;
        u8 y0 = (ny < old_y) ? ny : old_y;
        u8 x1 = (u8)(x0 + 2), y1 = (u8)(y0 + 2);
        if (room_socket_x < x0) x0 = room_socket_x;
        if (room_socket_y < y0) y0 = room_socket_y;
        if ((u8)(room_socket_x + 1) > x1) x1 = (u8)(room_socket_x + 1);
        if ((u8)(room_socket_y + 1) > y1) y1 = (u8)(room_socket_y + 1);
        tone_flush_range(x0, y0, x1, y1);
    }
    tone_progress++;
    if (tone_progress >= TONE_LEN
        && nx == room_socket_x && ny == room_socket_y) {
        sfx_play_rune_final(tone_pitch[dir]);
        return 1;
    }
    sfx_play_rune(tone_pitch[dir]);
    return 0;
}

static u8 tone_phrase_fits(u8 packed, u8 sx, u8 sy, u8 *cx, u8 *cy,
    u8 *minx, u8 *miny, u8 *maxx, u8 *maxy) {
    u8 i, x, y, seen_x[5], seen_y[5], n;
    i8 net_x = 0, net_y = 0;
    for (i = 0; i < TONE_LEN; ++i) {
        u8 d = tone_dir_at(packed, i);
        net_x = (i8)(net_x + tone_dx[d]);
        net_y = (i8)(net_y + tone_dy[d]);
    }
    if (!net_x && !net_y) return 0;
    /* 2x2 bodies overlap unless they are 2 tiles apart on at least one axis. */
    if (((net_x < 0) ? (u8)(-net_x) : (u8)net_x) < 2
        && ((net_y < 0) ? (u8)(-net_y) : (u8)net_y) < 2)
        return 0;
    x = (u8)((i8)sx - net_x);
    y = (u8)((i8)sy - net_y);
    if (!tone_origin_ok(x, y)) return 0;
    if (x == sx && y == sy) return 0;
    seen_x[0] = x; seen_y[0] = y; n = 1;
    *minx = x; *miny = y; *maxx = x; *maxy = y;
    for (i = 0; i < TONE_LEN; ++i) {
        u8 d = tone_dir_at(packed, i);
        u8 k;
        x = (u8)((i8)x + tone_dx[d]);
        y = (u8)((i8)y + tone_dy[d]);
        if (!tone_origin_ok(x, y) && !(x == sx && y == sy)) return 0;
        for (k = 0; k < n; ++k)
            if (seen_x[k] == x && seen_y[k] == y) return 0;
        seen_x[n] = x; seen_y[n] = y; n++;
        if (x < *minx) *minx = x;
        if (y < *miny) *miny = y;
        if (x > *maxx) *maxx = x;
        if (y > *maxy) *maxy = y;
    }
    if (x != sx || y != sy) return 0;
    *cx = (u8)((i8)sx - net_x);
    *cy = (u8)((i8)sy - net_y);
    return 1;
}

void prepare_tone_path(u32 seed) BANKED {
    u8 sel = (u8)(seed >> 4) & 3;
    u8 sx = (sel & 1) ? 10 : 8;
    u8 sy = (sel & 2) ? 8 : 6;
    u8 start = (u8)(seed >> 5) & (u8)(TONE_BANK_LEN - 1);
    u8 try, i, cx = 8, cy = 6, packed = tone_bank[start];
    u8 x0, x1, y0, y1, found = 0;
    u8 minx = 8, miny = 6, maxx = 8, maxy = 6;
    for (try = 0; try < TONE_BANK_LEN; ++try) {
        packed = tone_bank[(u8)((start + try) & (u8)(TONE_BANK_LEN - 1))];
        if (tone_phrase_fits(packed, sx, sy, &cx, &cy,
                &minx, &miny, &maxx, &maxy)) {
            found = 1;
            break;
        }
    }
    if (!found) {
        packed = tone_bank[0];
        sx = 10; sy = 8;
        if (!tone_phrase_fits(packed, sx, sy, &cx, &cy,
                &minx, &miny, &maxx, &maxy)) {
            sx = 8; sy = 6;
            tone_phrase_fits(packed, sx, sy, &cx, &cy,
                &minx, &miny, &maxx, &maxy);
        }
    }
    for (i = 0; i < TONE_LEN; ++i)
        tone_dirs[i] = tone_dir_at(packed, i);
    /* Bounding box of every visited origin, plus a 1-tile wrong-shove apron. */
    x0 = (u8)(minx - 1); if (x0 < 1 || x0 > minx) x0 = 1;
    y0 = (u8)(miny - 1); if (y0 < 1 || y0 > miny) y0 = 1;
    x1 = (u8)(maxx + 2 + 1); if (x1 > 18) x1 = 18;
    y1 = (u8)(maxy + 2 + 1); if (y1 > 15) y1 = 15;
    clear_all_cairns();
    floor_rect(x0, y0, (u8)(x1 - x0 + 1), (u8)(y1 - y0 + 1));
    room_socket_x = sx;
    room_socket_y = sy;
    room_tilemap[sy][sx] = room_tilemap[sy][sx + 1] = BGT_FLOOR3;
    room_tilemap[sy + 1][sx] = room_tilemap[sy + 1][sx + 1] = BGT_FLOOR3;
    tone_start_x = cx;
    tone_start_y = cy;
    tone_draw_crate(cx, cy);
    puzzle_block_x = cx;
    puzzle_block_y = cy;
    tone_progress = 0;
    tone_misses = 0;
    tone_teaser_cd = 0;
    tone_teaser_step = 0xFF;
    tone_approach = 0;
    tone_hint_timer = 0;
    tone_lecture_step = 0;
    room_puzzle_locked = 1;
}

void tone_tick_player(void) BANKED {
    u8 tx, ty, near, dx, dy;
    tone_tick_teaser();
    tone_tick_hints();
    tx = (u8)((player.x + 8) >> 3);
    ty = (u8)((player.y + 12) >> 3);
    dx = (tx < room_socket_x) ? (u8)(room_socket_x - tx)
        : (tx > (u8)(room_socket_x + 1)) ? (u8)(tx - (u8)(room_socket_x + 1)) : 0;
    dy = (ty < room_socket_y) ? (u8)(room_socket_y - ty)
        : (ty > (u8)(room_socket_y + 1)) ? (u8)(ty - (u8)(room_socket_y + 1)) : 0;
    near = (dx <= 2 && dy <= 2) ? 1 : 0;
    if (near && !tone_approach) {
        tone_approach = 1;
        if (tone_teaser_cd == 0 && tone_teaser_step == 0xFF
            && !(puzzle_block_x == room_socket_x
                && puzzle_block_y == room_socket_y))
            tone_start_teaser();
    } else if (!near) {
        tone_approach = 0;
    }
}

