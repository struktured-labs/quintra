#pragma bank 18

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/riftwild_setpiece.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/riftwild_art.h"
#include "render/tiles.h"

BANKREF(riftwild_setpiece_apply)

u8 rw_stamp_n;
u8 rw_stamp_x[RW_STAMP_MAX];
u8 rw_stamp_y[RW_STAMP_MAX];
u8 rw_stamp_w[RW_STAMP_MAX];
u8 rw_stamp_h[RW_STAMP_MAX];
u8 rw_stamp_art[RW_STAMP_MAX];
u8 rw_stamp_attr[RW_STAMP_MAX];
u8 riftwild_setpiece_id = RW_SETPIECE_NONE;
u8 riftwild_setpiece_x;
u8 riftwild_setpiece_y;
u8 riftwild_cache_x = 0xFF;
u8 riftwild_cache_y = 0xFF;
u8 riftwild_render_salt;

// Template alphabet. Unlisted characters (space) leave the terrain alone.
//  .  base ground          f  meadow flowers      $  cache spot (ground)
//  T  tree                 S  standing stone      k  old stump
//  C  Worldglass shard     P  ruin column (2 tall = top+base art)
//  F  flagstones           r  rubble              w  water
//  m  crag (2x2 aligned)   R  reeds
//  V  Worldglass spire 2x3 U  guardian statue 2x3 G  elder tree 3x3
//  O  obelisk 1x2          +  covered by a stamp (skipped)
#define PIECE_COUNT 10
static const u8 piece_w[PIECE_COUNT] = { 9, 8, 7, 9, 9, 8, 8, 8, 9, 7 };
static const u8 piece_h[PIECE_COUNT] = { 7, 6, 6, 7, 9, 7, 6, 7, 7, 7 };
static const char *const piece_rows[PIECE_COUNT] = {
    // 0 Worldglass garden: three glass spires around a hidden hollow.
    ".V+...V+."
    ".++.C.++."
    ".++...++."
    "...f$f..."
    "C..V+...C"
    "...++...."
    "...++....",
    // 1 Warden's watch: two guardian statues over a flagstone court.
    ".U+..U+."
    ".++FF++."
    ".++FF++."
    "..FFFF.."
    "..F$FF.."
    "..FFFF..",
    // 2 Elder tree: one giant lone tree in a flower ring.
    "f.....f"
    ".fG++f."
    "..+++.."
    "..+++.."
    ".f.$.f."
    "f.....f",
    // 3 Old ruins: broken colonnade on a flagstone floor.
    ".P..P..P."
    ".P.FFF.P."
    "..FFFFF.."
    ".PFF$FFr."
    ".PFFFFF.."
    "..rFFF.P."
    ".......P.",
    // 4 Standing ring: stones around a rune obelisk.
    "...S.S..."
    ".S.....S."
    "........."
    "S...O...S"
    "....+...."
    "S..f$f..S"
    "........."
    ".S.....S."
    "...S.S...",
    // 5 Rock teeth: a crag cluster with a sheltered nook.
    "mm..mm.."
    "mm..mm.."
    "..mm..f."
    "..mm...."
    "mm..$.mm"
    "mm....mm"
    "........",
    // 6 Still pool: a small lake with reeds (shoreline art).
    "..wwww.."
    ".wwwwwwR"
    ".wwwwwwR"
    "..wwww.."
    "f..$...f"
    "........",
    // 7 Shard meadow: scattered Worldglass in flowers.
    "f..C...f"
    "..f..C.."
    ".C..f..."
    "...f$.C."
    "C.f....f"
    "...C..f."
    "f.....C.",
    // 8 Barrow field: rows of old headstones.
    "........."
    ".S..S..S."
    "........."
    ".S..$..S."
    "........."
    ".S..S..S."
    ".........",
    // 9 Fairy ring: stumps around a meadow.
    "..kkk.."
    ".k...k."
    "k.fff.k"
    "..f$f.."
    "..fff.."
    ".k...k."
    "..kkk..",
};

// Ordinary fields only. Fixtures keep their authored layouts: the Riftwell,
// Warden arenas, cave, arches, class groves, old boss landmark and vault.
static u8 fixture_field(u8 screen) {
    switch (screen) {
        case 1: case 3: case 5: case 8: case 16: case 17: case 21:
        case 23: case 27: case 29: case 30: case 32: case 34:
            return 1;
    }
    return 0;
}

static u8 hash_state;

static u8 next_hash(void) {
    // 8-bit xorshift; never zero once seeded non-zero.
    hash_state ^= (u8)(hash_state << 3);
    hash_state ^= (u8)(hash_state >> 5);
    hash_state ^= (u8)(hash_state << 4);
    return hash_state;
}

u8 riftwild_field_salt(u8 k) BANKED {
    u8 s = (u8)run_state.run_seed;
    s ^= (u8)(run_state.run_seed >> 8) * 3u;
    s ^= (u8)(run_state.run_seed >> 16) * 5u;
    s ^= (u8)(run_state.run_seed >> 24) * 7u;
    s += (u8)(run_state.world_screen * 0x35u);
    s ^= (u8)(run_state.riftwild_region * 0x71u);
    s += (u8)(k * 0x9Du);
    s ^= (u8)(s >> 4);
    s += (u8)(s << 3);
    return s ? s : 0x5A;
}

static u8 tile_at(u8 x, u8 y) {
    if (y < ROOM_H) {
        if (x < ROOM_W) return room_tilemap[y][x];
        return room_world_extension[y][x - ROOM_W];
    }
    return room_world_bottom[y - ROOM_H][x];
}

static void tile_put(u8 x, u8 y, u8 t) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = t;
        else room_world_extension[y][x - ROOM_W] = t;
    } else room_world_bottom[y - ROOM_H][x] = t;
}

static u8 ground(u8 t, u8 base) {
    return t == BGT_GRASS || t == base || t == BGT_WILD_FLOWER;
}

// Keep the hidden dens' quadrant tells (spec: 4..8 tiles off the trail
// cross, at about (7,7) (23,7) (7,23) (23,23)) and the boss-exit landing
// apron clear, so this pass never claims a spot another system needs.
static u8 reserved(u8 x, u8 y) {
    u8 qx = (x >= 5 && x <= 9) || (x >= 21 && x <= 25);
    u8 qy = (y >= 5 && y <= 9) || (y >= 21 && y <= 25);
    if (qx && qy) return 1;
    if (run_state.world_screen == 0 && y <= 6 && x >= 6 && x <= 13)
        return 1;
    return 0;
}

// Out-of-field neighbours read as the tree line, matching tiles_area.c.
static u8 view_at(u8 x, u8 y) {
    if (x >= ROOM_WIDE_W_TILES || y >= ROOM_WIDE_H_TILES) return BGT_TREE;
    return tile_at(x, y);
}

// Footprint plus a two-tile ring must be open ground: the ring keeps every
// route around the piece at least 16px wide (the hero body is 12px), so a
// stamp can never cut a path, and nothing sits on a trail or a mouth. The
// footprint itself also stays off the reserved spots.
static u8 fits(u8 x0, u8 y0, u8 w, u8 h, u8 base) {
    u8 x, y;
    u8 x1 = (u8)(x0 + w + 1), y1 = (u8)(y0 + h + 1);
    if (x0 < 3 || y0 < 3 || x1 > 28 || y1 > 28) return 0;
    for (y = (u8)(y0 - 2); y <= y1; ++y)
        for (x = (u8)(x0 - 2); x <= x1; ++x) {
            if (!ground(tile_at(x, y), base)) return 0;
            if (x >= x0 && y >= y0 && x < (u8)(x0 + w) && y < (u8)(y0 + h)
                && reserved(x, y)) return 0;
        }
    return 1;
}

static void add_stamp(u8 x, u8 y, u8 w, u8 h, u8 art, u8 attr) {
    if (rw_stamp_n >= RW_STAMP_MAX) return;
    rw_stamp_x[rw_stamp_n] = x;
    rw_stamp_y[rw_stamp_n] = y;
    rw_stamp_w[rw_stamp_n] = w;
    rw_stamp_h[rw_stamp_n] = h;
    rw_stamp_art[rw_stamp_n] = art;
    rw_stamp_attr[rw_stamp_n] = attr;
    rw_stamp_n++;
}

static void fill(u8 x, u8 y, u8 w, u8 h, u8 t) {
    u8 i, j;
    for (j = 0; j < h; ++j)
        for (i = 0; i < w; ++i) tile_put((u8)(x + i), (u8)(y + j), t);
}

static void stamp_piece(u8 id, u8 x0, u8 y0, u8 mirror, u8 base) {
    const char *row = piece_rows[id];
    u8 w = piece_w[id], h = piece_h[id];
    u8 dx, dy;
    for (dy = 0; dy < h; ++dy) {
        for (dx = 0; dx < w; ++dx) {
            char c = row[(u8)(dy * w + (mirror ? (u8)(w - 1 - dx) : dx))];
            u8 x = (u8)(x0 + dx), y = (u8)(y0 + dy);
            // Multi-tile stamps anchor on their left column in the
            // template; mirrored, the anchor is the block's right column.
            u8 ax = x;
            switch (c) {
                case '.': tile_put(x, y, base); break;
                case 'f': tile_put(x, y, BGT_WILD_FLOWER); break;
                case '$':
                    tile_put(x, y, base);
                    riftwild_cache_x = x;
                    riftwild_cache_y = y;
                    break;
                case 'T': tile_put(x, y, BGT_TREE); break;
                case 'S': tile_put(x, y, BGT_WILD_STONE); break;
                case 'k': tile_put(x, y, BGT_WILD_STUMP); break;
                case 'C': tile_put(x, y, BGT_CRYSTAL); break;
                case 'P': tile_put(x, y, BGT_PILLAR); break;
                case 'F': tile_put(x, y, BGT_FLOOR); break;
                case 'r': tile_put(x, y, BGT_RUBBLE); break;
                case 'w': tile_put(x, y, BGT_WILD_WATER); break;
                case 'm': tile_put(x, y, BGT_WILD_MOUNTAIN); break;
                case 'R': tile_put(x, y, BGT_WILD_REEDS); break;
                case 'V':
                    if (mirror) ax = (u8)(x - 1);
                    fill(ax, y, 2, 3, BGT_CRYSTAL);
                    add_stamp(ax, y, 2, 3, RWA_SPIRE_0_0,
                        BGPAL_CRYSTAL | 0x08);
                    break;
                case 'U':
                    if (mirror) ax = (u8)(x - 1);
                    fill(ax, y, 2, 3, BGT_PILLAR);
                    add_stamp(ax, y, 2, 3, RWA_STATUE_0_0,
                        BGPAL_DOOR | 0x08);
                    break;
                case 'G':
                    if (mirror) ax = (u8)(x - 2);
                    fill(ax, y, 3, 3, BGT_TREE);
                    add_stamp(ax, y, 3, 3, RWA_GREAT_TREE_0_0,
                        BGPAL_WALL | 0x08);
                    break;
                case 'O':
                    fill(x, y, 1, 2, BGT_WILD_STONE);
                    add_stamp(x, y, 1, 2, RWA_OBELISK_TOP,
                        BGPAL_CRYSTAL | 0x08);
                    break;
                default: break;  // '+' and ' ' keep what is there
            }
        }
    }
}

// The old "landmark family" stamped the same 2x2 blob at the same eight
// coordinates in every field. The set piece replaces it; lift the blobs
// back into the surrounding terrain (or ground) so fields stop matching.
static void lift_old_blobs(u8 base) {
    static const u8 bx[7] = { 5, 13, 21, 24, 28, 14, 24 };
    static const u8 by[7] = { 4, 11, 4, 11, 6, 19, 26 };
    u8 i, x, y;
    for (i = 0; i < 7; ++i) {
        u8 left = tile_at((u8)(bx[i] - 1), by[i]);
        u8 right = tile_at((u8)(bx[i] + 2), by[i]);
        u8 fillt = (left == right && left != BGT_PATH
            && left != BGT_WILD_FLOWER && left != BGT_WILD_STONE
            && left != BGT_WILD_STUMP) ? left : base;
        for (y = by[i]; y <= (u8)(by[i] + 1); ++y)
            for (x = bx[i]; x <= (u8)(bx[i] + 1); ++x) {
                u8 t = tile_at(x, y);
                if (t == BGT_WILD_FLOWER || t == BGT_WILD_WATER
                    || t == BGT_WILD_STONE || t == BGT_WILD_STUMP)
                    tile_put(x, y, fillt);
            }
    }
}

// A few seeded clumps break the open ground: a grove (canopy art), a crag
// (peak art), a lone stone or a flower patch, weighted by climate row.
static void scatter(u8 base) {
    static const u8 kinds[6][4] = {
        { BGT_WILD_MOUNTAIN, BGT_WILD_STONE, BGT_TREE, BGT_WILD_MOUNTAIN },
        { BGT_TREE, BGT_TREE, BGT_WILD_FLOWER, BGT_WILD_STUMP },
        { BGT_WILD_MOUNTAIN, BGT_WILD_MOUNTAIN, BGT_WILD_STONE, BGT_TREE },
        { BGT_TREE, BGT_WILD_FLOWER, BGT_TREE, BGT_WILD_STONE },
        { BGT_WILD_STUMP, BGT_WILD_REEDS, BGT_TREE, BGT_WILD_FLOWER },
        { BGT_WILD_MOUNTAIN, BGT_WILD_STONE, BGT_WILD_MOUNTAIN, BGT_WILD_FLOWER },
    };
    u8 zone = (u8)(run_state.world_screen / 6);
    u8 tries, placed = 0;
    u8 want = (u8)(3 + (next_hash() & 3));
    for (tries = 0; tries < 14 && placed < want; ++tries) {
        u8 h = next_hash();
        u8 kind = kinds[zone][h & 3];
        u8 x0 = (u8)(4 + ((next_hash() % 22) & 0xFE));
        u8 y0 = (u8)(4 + ((next_hash() % 22) & 0xFE));
        u8 w = 2, hgt = 2;
        if (kind == BGT_TREE && (h & 0x10)) w = 4;
        if (kind == BGT_WILD_STONE || kind == BGT_WILD_STUMP) w = hgt = 1;
        if (kind == BGT_WILD_FLOWER) { w = 3; hgt = 2; }
        if (!fits(x0, y0, w, hgt, base)) continue;
        fill(x0, y0, w, hgt, kind);
        placed++;
    }
}

void riftwild_setpiece_apply(u8 base) BANKED {
    u8 id, tries, k;
    rw_stamp_n = 0;
    riftwild_setpiece_id = RW_SETPIECE_NONE;
    riftwild_cache_x = riftwild_cache_y = 0xFF;
    riftwild_render_salt = riftwild_field_salt(0);
    if (!run_state.world_mode || fixture_field(run_state.world_screen))
        return;
    hash_state = riftwild_field_salt(1);
    lift_old_blobs(base);
    // Neighbouring fields start from different pieces (screen * 3), and the
    // seed rotates the whole assignment; a piece that does not fit here
    // hands over to the next one in the library.
    id = (u8)((next_hash() + run_state.world_screen * 3u) % PIECE_COUNT);
    for (k = 0; k < PIECE_COUNT && riftwild_setpiece_id == RW_SETPIECE_NONE;
         ++k) {
        u8 w = piece_w[id], h = piece_h[id];
        for (tries = 0; tries < 8; ++tries) {
            // Even anchors keep 2x2 crag and canopy art aligned.
            u8 x0 = (u8)(4 + ((next_hash() % (u8)(23 - w)) & 0xFE));
            u8 y0 = (u8)(4 + ((next_hash() % (u8)(23 - h)) & 0xFE));
            if (fits(x0, y0, w, h, base)) {
                stamp_piece(id, x0, y0, next_hash() & 1, base);
                riftwild_setpiece_id = id;
                riftwild_setpiece_x = x0;
                riftwild_setpiece_y = y0;
                break;
            }
        }
        if (++id >= PIECE_COUNT) id = 0;
    }
    scatter(base);
}

// Called after entity_init_room(). About one ordinary field in four holds a
// cache; four claim bits per visit, so a cache never refills by
// backtracking. Coins and a heart, tagged so they wait for the hero.
void riftwild_setpiece_spawn(void) BANKED {
    u8 h, bit, idx;
    if (!run_state.world_mode || riftwild_cache_x == 0xFF) return;
    h = riftwild_field_salt(2);
    if (h & 0x30) return;
    bit = (u8)(1u << (RW_CACHE_BIT_SHIFT + (h & 3)));
    if (run_state.shop_civic & bit) return;
    run_state.shop_civic |= bit;
    idx = pickup_spawn(PICKUP_COIN_5,
        FIX8((u16)riftwild_cache_x << 3), FIX8((u16)riftwild_cache_y << 3));
    if (idx != 0xFF) entities[idx].ai_data[5] = 0xB2;
    idx = pickup_spawn((h & 0x40) ? PICKUP_HEART_HALF : PICKUP_COIN_5,
        FIX8(((u16)riftwild_cache_x << 3) + 10),
        FIX8((u16)riftwild_cache_y << 3));
    if (idx != 0xFF) entities[idx].ai_data[5] = 0xB2;
    idx = pickup_spawn(PICKUP_COIN_5,
        FIX8(((u16)riftwild_cache_x << 3) - 10),
        FIX8((u16)riftwild_cache_y << 3));
    if (idx != 0xFF) entities[idx].ai_data[5] = 0xB2;
}

// Riftwild render pass (audit L2/L3). Logical ids and collision never
// change; only the VRAM cell does. Ground picks seeded bank-1 variants and
// flips, trees and crags tile as 2x2 canopies/peaks, water grows shorelines,
// ruins read as columns and flagstones, and set-piece stamps draw their
// multi-tile art. Everything is keyed by position plus the per-field salt,
// so a field redraws identically on every stream.
static u8 cell_attr;

static u8 dress_cell(u8 tile, u8 a, u8 x, u8 y) {
    u8 h, i;
    for (i = 0; i < rw_stamp_n; ++i) {
        u8 dx = (u8)(x - rw_stamp_x[i]);
        u8 dy = (u8)(y - rw_stamp_y[i]);
        if (dx < rw_stamp_w[i] && dy < rw_stamp_h[i]) {
            cell_attr = rw_stamp_attr[i];
            return (u8)(rw_stamp_art[i] + dy * rw_stamp_w[i] + dx);
        }
    }
    h = (u8)(x * 0x1Du + y * 0x3Bu + riftwild_render_salt);
    h ^= (u8)(h >> 3);
    h += (u8)(y << 3) ^ x;
    cell_attr = a;
    switch (tile) {
        case BGT_GRASS:
            if (!(h & 3)) {
                cell_attr = a | 0x08 | ((h & 0x80) ? 0x20 : 0);
                h = (u8)((h >> 3) & 3);
                return (u8)(RWA_GRASS_TUFT + (h == 3 ? 0 : h));
            }
            break;
        case BGT_WILD_SNOW:
            if (!(h & 3)) {
                cell_attr = a | 0x08 | ((h & 0x80) ? 0x20 : 0);
                return (h & 0x10) ? RWA_SNOW_GLINT : RWA_SNOW_DRIFT;
            }
            break;
        case BGT_WILD_SAND:
            if (!(h & 3)) {
                cell_attr = a | 0x08 | ((h & 0x80) ? 0x20 : 0);
                return (h & 0x10) ? RWA_SAND_CRACK : RWA_SAND_SHELL;
            }
            break;
        case BGT_WILD_MUD:
            if (!(h & 3)) {
                cell_attr = a | 0x08 | ((h & 0x80) ? 0x20 : 0);
                return (h & 0x10) ? RWA_MUD_ROOTS : RWA_MUD_PUDDLE;
            }
            break;
        case BGT_PATH:
            if (!(h & 7)) {
                cell_attr = a | 0x08;
                return RWA_PATH_STONES;
            }
            break;
        case BGT_TREE:
            cell_attr = a | 0x08;
            return (u8)(RWA_TREE_TL + ((y & 1) << 1) + (x & 1));
        case BGT_WILD_MOUNTAIN:
            cell_attr = a | 0x08;
            return (u8)(RWA_CRAG_TL + ((y & 1) << 1) + (x & 1));
        case BGT_PILLAR:
            cell_attr = BGPAL_DOOR | 0x08;
            if (view_at(x, (u8)(y - 1)) == BGT_PILLAR)
                return RWA_COLUMN_BASE;
            if (view_at(x, (u8)(y + 1)) == BGT_PILLAR)
                return RWA_COLUMN_TOP;
            return RWA_COLUMN_BROKEN;
        case BGT_FLOOR:
            cell_attr = BGPAL_DOOR | 0x08 | ((h & 0x40) ? 0x20 : 0);
            return RWA_FLAGSTONE;
        case BGT_WILD_WATER: {
            u8 n = view_at(x, (u8)(y - 1)) != BGT_WILD_WATER;
            u8 s = view_at(x, (u8)(y + 1)) != BGT_WILD_WATER;
            u8 w = view_at((u8)(x - 1), y) != BGT_WILD_WATER;
            u8 e = view_at((u8)(x + 1), y) != BGT_WILD_WATER;
            u8 flip = (u8)((s && !n) ? 0x40 : 0);
            if (e && !w) flip |= 0x20;
            if ((n || s) && (w || e)) {
                cell_attr = a | 0x08 | flip;
                return RWA_SHORE_NW;
            }
            if (n || s) {
                cell_attr = a | 0x08 | flip;
                return RWA_SHORE_N;
            }
            if (w || e) {
                cell_attr = a | 0x08 | flip;
                return RWA_SHORE_W;
            }
            cell_attr = a | ((h & 0x40) ? 0x20 : 0);
            break;
        }
        default:
            break;
    }
    return tile;
}

// Dress one streamed BG line in place. The arrays are in physical (rotated)
// order: logical cell i lives at slot (origin + i) & 31. Called from bank 11
// once per row/column, so the per-cell work never pays a banked call.
void riftwild_dress_line(u8 *tiles, u8 *attrs, u8 fixed, u8 vertical,
                         u8 origin) BANKED {
    u8 i;
    for (i = 0; i < 32; ++i) {
        u8 p = (u8)((origin + i) & 31);
        tiles[p] = vertical ? dress_cell(tiles[p], attrs[p], fixed, i)
                            : dress_cell(tiles[p], attrs[p], i, fixed);
        attrs[p] = cell_attr;
    }
}
