#pragma bank 30

#include <gb/gb.h>
#include "game/bomb_wall.h"
#include "game/mission_graph.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/secret_merchant.h"
#include "game/entity.h"
#include "render/tiles.h"
#include "core/types.h"

static u32 mix32(u32 a, u32 b) {
    u32 x = a ^ (b * 0x9E3779B9UL);
    x ^= x >> 16;
    x *= 0x7FEB352DUL;
    x ^= x >> 15;
    x *= 0x846CA68BUL;
    x ^= x >> 16;
    return x;
}

static u8 cell_eligible(u8 cell, u8 size, u8 entry, u8 cache, u8 veil) {
    if (cell >= 32) return 0;
    if (cell == 0 || cell == entry || cell == cache || cell == veil) return 0;
    if (cell + 3 >= size) return 0;
    if (cell == 2 || cell == 5 || cell == 8 || cell == 11
        || cell == 15 || cell == 17 || cell == 23) return 0;
    return mission_graph_cell_is_role(cell) ? 0 : 1;
}

static u8 cell_degree(u8 cell) {
    u8 dir, n = 0;
    for (dir = DIR_N; dir <= DIR_W; ++dir)
        if (run_state_dungeon_cell_neighbor(cell, dir) != 0xFF) n++;
    return n;
}

static u8 host_count(void) {
    return (run_state.bosses_beaten < 3) ? 2 : 3;
}

/* Fill out[0..n) with distinct eligible local cells. n <= 3. */
static u8 pick_hosts(u8 *out) {
    u8 size, entry, cache, veil, want, n, pass, start, i, cell;
    u32 h;
    mission_graph_ensure();
    size = run_state_dungeon_size();
    entry = run_state_dungeon_entry_cell();
    cache = run_state_dungeon_cache_cell();
    veil = secret_merchant_host_cell();
    want = host_count();
    h = mix32(run_state.run_seed, 0x424F4D42UL ^ (u32)run_state.bosses_beaten);
    start = (u8)(h % size);
    n = 0;
    for (pass = 0; pass < 2 && n < want; ++pass) {
        for (i = 0; i < size && n < want; ++i) {
            u8 k, seen = 0;
            cell = (u8)(start + i);
            if (cell >= size) cell = (u8)(cell - size);
            if (!cell_eligible(cell, size, entry, cache, veil)) continue;
            if (pass == 0 && cell_degree(cell) != 1) continue;
            for (k = 0; k < n; ++k) if (out[k] == cell) seen = 1;
            if (seen) continue;
            out[n++] = cell;
        }
    }
    return n;
}

u8 bomb_wall_is_host(u8 local) BANKED {
    u8 hosts[3];
    u8 n, i;
    if (run_state.world_mode) return 0;
    n = pick_hosts(hosts);
    for (i = 0; i < n; ++i) if (hosts[i] == local) return 1;
    return 0;
}

static u8 legal_pos(u8 side, u8 pos) {
    if (side < 2) {
        /* N/S: skip door-lane cols 8-10 (open_secret uses tx+1). */
        if (pos < 2 || pos > (u8)(ROOM_W - 2)) return 0;
        if (pos >= 8 && pos <= 10) return 0;
        if (side == 0 && (pos == 6 || pos == 7)) return 0; /* cairn pair */
        return 1;
    }
    /* E/W: skip door-lane rows 7-9 (open_secret uses ty+1). */
    if (pos < 2 || pos > (u8)(ROOM_H - 2)) return 0;
    if (pos >= 7 && pos <= 9) return 0;
    return 1;
}

static void pair_of(u8 side, u8 pos, u8 *x, u8 *y, u8 *x2, u8 *y2) {
    if (side == 0) { *x = pos; *y = 0; *x2 = (u8)(pos + 1); *y2 = 0; }
    else if (side == 1) {
        *x = pos; *y = (u8)(ROOM_H - 1);
        *x2 = (u8)(pos + 1); *y2 = (u8)(ROOM_H - 1);
    } else if (side == 2) { *x = 0; *y = pos; *x2 = 0; *y2 = (u8)(pos + 1); }
    else {
        *x = (u8)(ROOM_W - 1); *y = pos;
        *x2 = (u8)(ROOM_W - 1); *y2 = (u8)(pos + 1);
    }
}

static u8 is_wallish(u8 t) {
    return (t == BGT_WALL || t == BGT_WALL_CRACK || t == BGT_WALL_BOMB) ? 1 : 0;
}

/* Stateless (side,pos) for this cell. Returns 1 and writes coords if a
   legal wall pair exists. */
static u8 choose_pair(u8 local, u8 *ox, u8 *oy, u8 *ox2, u8 *oy2) {
    u32 h = mix32(run_state.run_seed,
        0x57414C4CUL ^ ((u32)run_state.bosses_beaten << 8) ^ (u32)local);
    u8 s0 = (u8)(h & 3);
    u8 i, j, side, pos, x, y, x2, y2;
    for (i = 0; i < 4; ++i) {
        side = (u8)((s0 + i) & 3);
        for (j = 0; j < 12; ++j) {
            u8 span = (side < 2) ? (u8)(ROOM_W - 4) : (u8)(ROOM_H - 4);
            pos = (u8)(2 + ((h >> 8) + (u32)j * 5u) % span);
            if (!legal_pos(side, pos)) continue;
            pair_of(side, pos, &x, &y, &x2, &y2);
            if (is_wallish(room_tilemap[y][x]) && is_wallish(room_tilemap[y2][x2])) {
                *ox = x; *oy = y; *ox2 = x2; *oy2 = y2;
                return 1;
            }
        }
    }
    return 0;
}

static void strip_gold_cracks(u8 keep_x, u8 keep_y, u8 keep_x2, u8 keep_y2) {
    u8 i;
    for (i = 0; i < ROOM_W; ++i) {
        if (room_tilemap[0][i] == BGT_WALL_CRACK
            && !((i == keep_x && 0 == keep_y) || (i == keep_x2 && 0 == keep_y2)))
            room_tilemap[0][i] = BGT_WALL;
        if (room_tilemap[ROOM_H - 1][i] == BGT_WALL_CRACK
            && !((i == keep_x && (ROOM_H - 1) == keep_y)
                || (i == keep_x2 && (ROOM_H - 1) == keep_y2)))
            room_tilemap[ROOM_H - 1][i] = BGT_WALL;
    }
    for (i = 0; i < ROOM_H; ++i) {
        if (room_tilemap[i][0] == BGT_WALL_CRACK
            && !((0 == keep_x && i == keep_y) || (0 == keep_x2 && i == keep_y2)))
            room_tilemap[i][0] = BGT_WALL;
        if (room_tilemap[i][ROOM_W - 1] == BGT_WALL_CRACK
            && !(((ROOM_W - 1) == keep_x && i == keep_y)
                || ((ROOM_W - 1) == keep_x2 && i == keep_y2)))
            room_tilemap[i][ROOM_W - 1] = BGT_WALL;
    }
}

static void write_open_pair(u8 x, u8 y, u8 x2, u8 y2) {
    room_tilemap[y][x] = BGT_DOOR;
    room_tilemap[y2][x2] = BGT_DOOR;
    secret_door_x = x;
    secret_door_y = y;
    secret_door_x2 = x2;
    secret_door_y2 = y2;
}

void bomb_wall_prepare_room(void) BANKED {
    u8 local, x, y, x2, y2;
    if (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter)
        || run_state.secret_pending) return;
    if (run_state_is_sanctuary() || run_state_is_shop()
        || run_state_is_boss_room()) return;
    local = run_state_dungeon_local();
    if (!bomb_wall_is_host(local)) return;
    if (secret_merchant_host_cell() == local) return;
    if (room_hidden_secret_kind != HIDDEN_SECRET_NONE) return;
    if (!choose_pair(local, &x, &y, &x2, &y2)) return;
    strip_gold_cracks(x, y, x2, y2);
    if (local < 32 && (run_state.bomb_walls_open & (1UL << local))) {
        write_open_pair(x, y, x2, y2);
        return;
    }
    room_tilemap[y][x] = BGT_WALL_BOMB;
    if (room_tilemap[y2][x2] == BGT_WALL_CRACK)
        room_tilemap[y2][x2] = BGT_WALL;
}

static u8 pair_origin(u8 tx, u8 ty, u8 *ox, u8 *oy) {
    if (tx >= ROOM_W || ty >= ROOM_H) return 0;
    if (room_tilemap[ty][tx] == BGT_WALL_BOMB) {
        *ox = tx; *oy = ty; return 1;
    }
    if ((ty == 0 || ty == ROOM_H - 1) && tx > 0
        && room_tilemap[ty][(u8)(tx - 1)] == BGT_WALL_BOMB) {
        *ox = (u8)(tx - 1); *oy = ty; return 1;
    }
    if ((tx == 0 || tx == ROOM_W - 1) && ty > 0
        && room_tilemap[(u8)(ty - 1)][tx] == BGT_WALL_BOMB) {
        *ox = tx; *oy = (u8)(ty - 1); return 1;
    }
    return 0;
}

u8 bomb_wall_try_open(u8 tx, u8 ty) BANKED {
    u8 ox, oy, local;
    if (!pair_origin(tx, ty, &ox, &oy)) return 0;
    local = run_state_dungeon_local();
    if (local < 32) run_state.bomb_walls_open |= (1UL << local);
    room_open_secret(ox, oy);
    return 1;
}

static void glint_at(u8 tx, u8 ty) {
    fx_spawn(SPR_FX_IMPACT, 0x06, (i16)((u16)tx << 3) - 4,
        (i16)((u16)ty << 3) - 4, 40);
}

u8 bomb_wall_chime(void) BANKED {
    u8 i, n = 0;
    if (run_state.world_mode) return 0;
    for (i = 1; i < ROOM_W - 1; ++i) {
        if (room_tilemap[0][i] == BGT_WALL_BOMB) { glint_at(i, 0); n++; }
        if (room_tilemap[ROOM_H - 1][i] == BGT_WALL_BOMB) {
            glint_at(i, ROOM_H - 1); n++;
        }
    }
    for (i = 1; i < ROOM_H - 1; ++i) {
        if (room_tilemap[i][0] == BGT_WALL_BOMB) { glint_at(0, i); n++; }
        if (room_tilemap[i][ROOM_W - 1] == BGT_WALL_BOMB) {
            glint_at(ROOM_W - 1, i); n++;
        }
    }
    return n;
}
