#pragma bank 19
// Bank 19: dens (PR) already claimed bank 18.

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/riftwild_den.h"
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
// Union of every stamp footprint (x1/y1 exclusive); x0 = 0xFF when empty.
// One bounds test per streamed cell replaces the per-stamp scan.
static u8 rw_box_x0 = 0xFF, rw_box_y0, rw_box_x1, rw_box_y1;

// Template alphabet. Unlisted characters (space) leave the terrain alone.
//  .  base ground          f  meadow flowers      $  cache spot (ground)
//  T  tree                 S  standing stone      k  old stump
//  C  Worldglass shard     P  ruin column (2 tall = top+base art)
//  F  flagstones           r  rubble              w  water
//  m  crag (2x2 aligned)   R  reeds
//  V  Worldglass spire 2x3 U  guardian statue 2x3 G  elder tree 3x3
//  O  obelisk 1x2          +  covered by a stamp (skipped)
#define PIECE_LARGE 10
#define PIECE_CRAGS 5
#define PIECE_COUNT 14
static const u8 piece_w[PIECE_COUNT] = { 9, 8, 7, 9, 9, 8, 8, 8, 9, 7, 3, 4, 3, 4 };
static const u8 piece_h[PIECE_COUNT] = { 7, 6, 6, 7, 9, 7, 6, 7, 7, 7, 5, 4, 3, 4 };
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
    // 10 Waystone: compact obelisk, used when a large stamp cannot fit.
    "f.f"
    ".O."
    ".+."
    "f$f"
    ".f.",
    // 11 Twin stones.
    ".S.S"
    "...."
    ".S$S"
    "....",
    // 12 Crystal shard.
    ".C."
    "C$C"
    ".C.",
    // 13 Stump camp.
    "k..k"
    ".f$."
    ".ff."
    "k..k",
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

// Clearance around a stamp may already be a trail; PATH is walkable and
// must not block placement the way a tree or pond does. Climate floors
// that are not this field's base (a patch of snow in a meadow, etc.)
// also count as open ground for the ring.
static u8 open_ring(u8 t, u8 base) {
    return ground(t, base) || t == BGT_PATH || t == BGT_WILD_SNOW
        || t == BGT_WILD_SAND || t == BGT_WILD_MUD || t == BGT_RUBBLE;
}

// The footprint may clear soft scenery (groves, stones, stumps, rubble, a
// stray climate floor): the walkable two-tile ring around it is what keeps
// every route intact, so overwriting what sat inside cannot cut a path.
// Paths, water, sinkholes, ridges, reeds, gates and portals stay untouched,
// so climate silhouettes, den ponds and trail crosses survive. Requiring
// bare ground here left no room for any large piece in a real field (every
// field fell back to the 3x3 shard).
static u8 soft(u8 t, u8 base) {
    return open_ring(t, base) && t != BGT_PATH
        || t == BGT_TREE || t == BGT_WILD_STONE || t == BGT_WILD_STUMP;
}

// Keep every spot another system rewrites after this pass clear, so a
// stamp is never half-overwritten (its bank-1 art would then sit on the
// wrong collision). A den field carves its 7x7 clearing at (21..27,
// 19..25) and an approach down x 9..10 / along y 21..22 after this pass
// (riftwild_den_stamp_field); field 0 keeps its boss-exit landing apron.
// Reserved cells are also never cleared as part of a ring.
static u8 den_here;

static u8 reserved(u8 x, u8 y) {
    if (run_state.world_screen == 0 && y <= 6 && x >= 6 && x <= 13)
        return 1;
    if (!den_here) return 0;
    if (x >= 19 && x <= 28 && y >= 17 && y <= 27) return 1;
    if (x >= 8 && x <= 11 && y >= 10 && y <= 23) return 1;
    if (x >= 8 && x <= 21 && y >= 20 && y <= 23) return 1;
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
            u8 inside = (x >= x0 && y >= y0
                && x < (u8)(x0 + w) && y < (u8)(y0 + h));
            if (inside) {
                if (!soft(tile_at(x, y), base) || reserved(x, y))
                    return 0;
            } else if (!open_ring(tile_at(x, y), base)) {
                return 0;
            }
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
    rw_box_x0 = 0xFF;
    riftwild_setpiece_id = RW_SETPIECE_NONE;
    riftwild_cache_x = riftwild_cache_y = 0xFF;
    riftwild_render_salt = riftwild_field_salt(0);
    if (!run_state.world_mode || fixture_field(run_state.world_screen))
        return;
    hash_state = riftwild_field_salt(1);
    den_here = riftwild_den_in_field();
    lift_old_blobs(base);
    // Neighbouring fields start from different pieces (screen * 3), and the
    // seed rotates the whole assignment; a piece that does not fit here
    // hands over to the next one in the library.
    // Prefer a large authored stamp. Tight fields (return landings, a lake
    // plus the trail cross) fall back to the compact 3x3..4x5 markers.
    id = (u8)((next_hash() + run_state.world_screen * 3u) % PIECE_LARGE);
    for (k = 0; k < PIECE_LARGE && riftwild_setpiece_id == RW_SETPIECE_NONE;
         ++k) {
        u8 w = piece_w[id], h = piece_h[id];
        for (tries = 0; tries < 10; ++tries) {
            // Any anchor with room for the ring (x0 >= 3, x0 + w + 1 <= 28).
            // The crag piece keeps even anchors so its 2x2 peak art lines
            // up with the field's crag quarters.
            u8 x0 = (u8)(3 + next_hash() % (u8)(25 - w));
            u8 y0 = (u8)(3 + next_hash() % (u8)(25 - h));
            if (id == PIECE_CRAGS) {
                x0 = (u8)((x0 + 1) & 0xFE);
                y0 = (u8)((y0 + 1) & 0xFE);
            }
            if (fits(x0, y0, w, h, base)) {
                stamp_piece(id, x0, y0, next_hash() & 1, base);
                riftwild_setpiece_id = id;
                riftwild_setpiece_x = x0;
                riftwild_setpiece_y = y0;
                break;
            }
        }
        if (++id >= PIECE_LARGE) id = 0;
    }
    if (riftwild_setpiece_id == RW_SETPIECE_NONE) {
        // Tight fields (return landings, a lake plus the trail cross) fall
        // back to the compact 3x3..4x5 markers, from a seeded start. A coarse
        // 2-tile lattice from a seeded origin keeps the worst case to ~130
        // fits() probes per marker, all inside the field build, with no
        // frame yields (yielding here stalled the seam camera and input).
        id = (u8)(PIECE_LARGE + (next_hash() & 3));
        for (k = PIECE_LARGE;
             k < PIECE_COUNT && riftwild_setpiece_id == RW_SETPIECE_NONE;
             ++k) {
            u8 w = piece_w[id], h = piece_h[id];
            u8 span_x = (u8)(26 - w);
            u8 span_y = (u8)(26 - h);
            u8 xs = (u8)(next_hash() % span_x);
            u8 ys = (u8)(next_hash() % span_y);
            u8 dx, dy, x0, y0;
            for (dy = 0; dy < span_y
                 && riftwild_setpiece_id == RW_SETPIECE_NONE; dy += 2) {
                for (dx = 0; dx < span_x
                     && riftwild_setpiece_id == RW_SETPIECE_NONE;
                     dx += 2) {
                    x0 = (u8)(3 + (xs + dx) % span_x);
                    y0 = (u8)(3 + (ys + dy) % span_y);
                    if (fits(x0, y0, w, h, base)) {
                        stamp_piece(id, x0, y0, next_hash() & 1, base);
                        riftwild_setpiece_id = id;
                        riftwild_setpiece_x = x0;
                        riftwild_setpiece_y = y0;
                    }
                }
            }
            if (++id >= PIECE_COUNT) id = PIECE_LARGE;
        }
    }
    scatter(base);
    for (k = 0; k < rw_stamp_n; ++k) {
        u8 x1 = (u8)(rw_stamp_x[k] + rw_stamp_w[k]);
        u8 y1 = (u8)(rw_stamp_y[k] + rw_stamp_h[k]);
        if (rw_box_x0 == 0xFF) {
            rw_box_x0 = rw_stamp_x[k]; rw_box_y0 = rw_stamp_y[k];
            rw_box_x1 = x1; rw_box_y1 = y1;
            continue;
        }
        if (rw_stamp_x[k] < rw_box_x0) rw_box_x0 = rw_stamp_x[k];
        if (rw_stamp_y[k] < rw_box_y0) rw_box_y0 = rw_stamp_y[k];
        if (x1 > rw_box_x1) rw_box_x1 = x1;
        if (y1 > rw_box_y1) rw_box_y1 = y1;
    }
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

static u8 dress_cell(u8 tile, u8 a, u8 x, u8 y, u8 h) {
    u8 i;
    if (x >= rw_box_x0 && x < rw_box_x1 && y >= rw_box_y0 && y < rw_box_y1) {
        for (i = 0; i < rw_stamp_n; ++i) {
            u8 dx = (u8)(x - rw_stamp_x[i]);
            u8 dy = (u8)(y - rw_stamp_y[i]);
            if (dx < rw_stamp_w[i] && dy < rw_stamp_h[i]) {
                cell_attr = rw_stamp_attr[i];
                return (u8)(rw_stamp_art[i] + dy * rw_stamp_w[i] + dx);
            }
        }
    }
    // Undressed ids leave the cell exactly as the base renderer drew it.
    switch (tile) {
        case BGT_GRASS: case BGT_WILD_SNOW: case BGT_WILD_SAND:
        case BGT_WILD_MUD: case BGT_PATH: case BGT_TREE:
        case BGT_WILD_MOUNTAIN: case BGT_PILLAR: case BGT_FLOOR:
        case BGT_WILD_WATER:
            break;
        default:
            cell_attr = a;
            return tile;
    }
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
// once per row/column, for all 32 rows when a field is prepared and for each
// streamed seam line, so it is on the field-entry and scroll budget. Plain
// ground, canopy and crag quarters resolve inline from a kind table and an
// incremental hash (no multiply, no call); only stamps, shorelines, ruins and
// the 1-in-4 dressed ground cell pay dress_cell(). The per-cell hash is the
// same as before: h = x*0x1D + y*0x3B + salt; h ^= h >> 3; h += (y<<3) ^ x.
#define RWK_SKIP   0
#define RWK_GRASS  1   // dressed when !(h & 3), three tuft variants
#define RWK_SNOW   2   // snow / sand / mud: dressed when !(h & 3), two art
#define RWK_SAND   3
#define RWK_MUD    4
#define RWK_PATH   5   // dressed when !(h & 7)
#define RWK_TREE   6
#define RWK_CRAG   7
#define RWK_SLOW   8   // shoreline / ruin / stamp: dress_cell()
static const u8 rw_kind[256] = {
    [BGT_GRASS] = RWK_GRASS, [BGT_WILD_SNOW] = RWK_SNOW,
    [BGT_WILD_SAND] = RWK_SAND, [BGT_WILD_MUD] = RWK_MUD,
    [BGT_PATH] = RWK_PATH, [BGT_TREE] = RWK_TREE,
    [BGT_WILD_MOUNTAIN] = RWK_CRAG, [BGT_PILLAR] = RWK_SLOW,
    [BGT_FLOOR] = RWK_SLOW, [BGT_WILD_WATER] = RWK_SLOW,
};
// (h & 0x10) ? alt_b : alt_a, matching dress_cell() for snow, sand and mud.
static const u8 rw_alt_a[5] = { 0, 0, RWA_SNOW_DRIFT, RWA_SAND_SHELL,
    RWA_MUD_PUDDLE };
static const u8 rw_alt_b[5] = { 0, 0, RWA_SNOW_GLINT, RWA_SAND_CRACK,
    RWA_MUD_ROOTS };

// Line invariants live in statics so the hot loop keeps its few locals in
// registers instead of shuffling an SDCC stack frame per cell.
static u8 dl_vertical, dl_fixed, dl_step, dl_mix, dl_par, dl_lo, dl_hi;

static void dress_slow(u8 *tp, u8 *ap, u8 i, u8 h) {
    u8 x = dl_vertical ? dl_fixed : i;
    u8 y = dl_vertical ? i : dl_fixed;
    *tp = dress_cell(*tp, *ap, x, y, h);
    *ap = cell_attr;
}

// One loop body per orientation, so the cell path never re-tests it.
// PAR(i): canopy/crag quarter from parity; MIX(i): the (y << 3) ^ x term.
#define DRESS_RUN(name, PAR, MIX)                                           \
static void name(u8 *tp, u8 *ap, u8 i, u8 n, u8 hb) {                       \
    u8 k, h;                                                                \
    for (; n; --n, ++tp, ++ap, ++i, hb += dl_step) {                        \
        k = rw_kind[*tp];                                                   \
        if (!k) continue;                                                   \
        if (i >= dl_lo && i < dl_hi) k = RWK_SLOW;                          \
        if (k >= RWK_TREE) {                                                \
            if (k == RWK_SLOW) {                                            \
                h = (u8)(hb ^ (hb >> 3)); h += (u8)(MIX(i));                \
                dress_slow(tp, ap, i, h);                                   \
                continue;                                                   \
            }                                                               \
            *ap |= 0x08;                                                    \
            *tp = (u8)((k == RWK_TREE ? RWA_TREE_TL : RWA_CRAG_TL)          \
                + dl_par + (u8)(PAR(i)));                                   \
            continue;                                                       \
        }                                                                   \
        h = (u8)(hb ^ (hb >> 3)); h += (u8)(MIX(i));                        \
        if (k == RWK_PATH) {                                                \
            if (h & 7) continue;                                            \
            *ap |= 0x08;                                                    \
            *tp = RWA_PATH_STONES;                                          \
            continue;                                                       \
        }                                                                   \
        if (h & 3) continue;                                                \
        *ap |= (u8)((h & 0x80) ? 0x28 : 0x08);                              \
        if (k == RWK_GRASS) {                                               \
            h = (u8)((h >> 3) & 3);                                         \
            *tp = (u8)(RWA_GRASS_TUFT + (h == 3 ? 0 : h));                  \
        } else {                                                            \
            *tp = (h & 0x10) ? rw_alt_b[k] : rw_alt_a[k];                   \
        }                                                                   \
    }                                                                       \
}
#define PAR_H(i) ((i) & 1)
#define MIX_H(i) (dl_mix ^ (i))
#define PAR_V(i) (((i) & 1) << 1)
#define MIX_V(i) (((u8)((i) << 3)) ^ dl_fixed)
DRESS_RUN(dress_run_h, PAR_H, MIX_H)
DRESS_RUN(dress_run_v, PAR_V, MIX_V)

void riftwild_dress_line(u8 *tiles, u8 *attrs, u8 fixed, u8 vertical,
                         u8 origin) BANKED {
    u8 p = (u8)(origin & 31);
    u8 first = (u8)(32 - p);
    u8 hb;
    dl_vertical = vertical;
    dl_fixed = fixed;
    dl_step = vertical ? 0x3Bu : 0x1Du;
    hb = (u8)(fixed * (vertical ? 0x1Du : 0x3Bu) + riftwild_render_salt);
    dl_mix = (u8)(fixed << 3);
    dl_par = vertical ? (u8)(fixed & 1) : (u8)((fixed & 1) << 1);
    // Stamp cells along this line, as a logical [lo, hi) range.
    dl_lo = dl_hi = 0;
    if (rw_box_x0 != 0xFF) {
        if (vertical && fixed >= rw_box_x0 && fixed < rw_box_x1) {
            dl_lo = rw_box_y0; dl_hi = rw_box_y1;
        } else if (!vertical && fixed >= rw_box_y0 && fixed < rw_box_y1) {
            dl_lo = rw_box_x0; dl_hi = rw_box_x1;
        }
    }
    // Logical 0..first-1 sit at physical p..31, the rest wrap to 0.
    if (vertical) {
        dress_run_v(tiles + p, attrs + p, 0, first, hb);
        if (p) dress_run_v(tiles, attrs, first, p,
            (u8)(hb + first * dl_step));
    } else {
        dress_run_h(tiles + p, attrs + p, 0, first, hb);
        if (p) dress_run_h(tiles, attrs, first, p,
            (u8)(hb + first * dl_step));
    }
}
