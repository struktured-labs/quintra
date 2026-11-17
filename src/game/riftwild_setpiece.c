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
u8 rw_ground_slot;
// Trails are worn earth: the door/earth slot in the Waking (tan dirt on
// every climate), the muted floor slot in the Hollow (its door and crystal
// slots are the loud void-cyan / magenta landmark colours). Set with
// rw_ground_slot.
static u8 rw_path_attr;
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
#define PIECE_SHARDS 7
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

// Row tables: no 2-D index multiply per cell. Rows 0..16 start in
// room_tilemap and continue at x >= 20 in room_world_extension (indexed
// from x - 20); rows 17..30 are whole rows of room_world_bottom. fits()
// probes thousands of cells per field build, so cell access stays cheap.
static u8 * const sp_row_lo[ROOM_WIDE_H_TILES] = {
    &room_tilemap[0][0], &room_tilemap[1][0], &room_tilemap[2][0],
    &room_tilemap[3][0], &room_tilemap[4][0], &room_tilemap[5][0],
    &room_tilemap[6][0], &room_tilemap[7][0], &room_tilemap[8][0],
    &room_tilemap[9][0], &room_tilemap[10][0], &room_tilemap[11][0],
    &room_tilemap[12][0], &room_tilemap[13][0], &room_tilemap[14][0],
    &room_tilemap[15][0], &room_tilemap[16][0], &room_world_bottom[0][0],
    &room_world_bottom[1][0], &room_world_bottom[2][0],
    &room_world_bottom[3][0], &room_world_bottom[4][0],
    &room_world_bottom[5][0], &room_world_bottom[6][0],
    &room_world_bottom[7][0], &room_world_bottom[8][0],
    &room_world_bottom[9][0], &room_world_bottom[10][0],
    &room_world_bottom[11][0], &room_world_bottom[12][0],
    &room_world_bottom[13][0]
};
static u8 * const sp_row_hi[ROOM_H] = {
    &room_world_extension[0][0], &room_world_extension[1][0],
    &room_world_extension[2][0], &room_world_extension[3][0],
    &room_world_extension[4][0], &room_world_extension[5][0],
    &room_world_extension[6][0], &room_world_extension[7][0],
    &room_world_extension[8][0], &room_world_extension[9][0],
    &room_world_extension[10][0], &room_world_extension[11][0],
    &room_world_extension[12][0], &room_world_extension[13][0],
    &room_world_extension[14][0], &room_world_extension[15][0],
    &room_world_extension[16][0]
};

static u8 *cell_ptr(u8 x, u8 y) {
    if (y < ROOM_H && x >= ROOM_W) return sp_row_hi[y] + (u8)(x - ROOM_W);
    return sp_row_lo[y] + x;
}

static u8 tile_at(u8 x, u8 y) {
    return *cell_ptr(x, y);
}

static void tile_put(u8 x, u8 y, u8 t) {
    *cell_ptr(x, y) = t;
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
    u8 i;
    if (run_state.world_screen == 0 && y <= 6 && x >= 6 && x <= 13)
        return 1;
    // Placed stamps (and a one-tile margin) are never overdrawn by scatter:
    // a grove written over a column stamp left the stamp art on tree cells.
    for (i = 0; i < rw_stamp_n; ++i)
        if ((u8)(x + 1 - rw_stamp_x[i]) <= rw_stamp_w[i]
            && (u8)(y + 1 - rw_stamp_y[i]) <= rw_stamp_h[i]) return 1;
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


// open_ring()/soft() as one lookup for fits(), whose ring walk is the
// scatter's main cost: bit 0 = open ring ground, bit 1 = soft footprint.
// The field base is always one of the climate floors listed here.
static const u8 rw_fit[256] = {
    [BGT_GRASS] = 3, [BGT_WILD_FLOWER] = 3, [BGT_WILD_SNOW] = 3,
    [BGT_WILD_SAND] = 3, [BGT_WILD_MUD] = 3, [BGT_RUBBLE] = 3,
    [BGT_PATH] = 1, [BGT_TREE] = 2, [BGT_WILD_STONE] = 2,
    [BGT_WILD_STUMP] = 2,
};

// Footprint plus a two-tile ring must be open ground: the ring keeps every
// route around the piece at least 16px wide (the hero body is 12px), so a
// stamp can never cut a path, and nothing sits on a trail or a mouth. The
// footprint itself also stays off the reserved spots.
static u8 fits(u8 x0, u8 y0, u8 w, u8 h, u8 base) {
    u8 x, y, t, inrow, *p;
    u8 x1 = (u8)(x0 + w + 1), y1 = (u8)(y0 + h + 1);
    u8 xe = (u8)(x0 + w);
    if (x0 < 3 || y0 < 3 || x1 > 28 || y1 > 28) return 0;
    for (y = (u8)(y0 - 2); y <= y1; ++y) {
        inrow = y >= y0 && y < (u8)(y0 + h);
        p = cell_ptr((u8)(x0 - 2), y);
        for (x = (u8)(x0 - 2); x <= x1; ++x, ++p) {
            if (x == ROOM_W && y < ROOM_H) p = sp_row_hi[y];
            t = *p;
            if (inrow && x >= x0 && x < xe) {
                if (!(rw_fit[t] & 2) && !soft(t, base)) return 0;
                if (reserved(x, y)) return 0;
            } else if (!(rw_fit[t] & 1) && !open_ring(t, base)) {
                return 0;
            }
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

// Seeded clusters break the open ground: a grove (canopy art), a crag
// ridge (peak art) or a flower patch, weighted by climate row. Three or
// four are tried (two to four land once fits() rejects crowded spots), plus
// three or four complete standalone props (lone bush, rock, stump). The
// 2026-11-17 tiles pass cut this to 1..2 clusters and no singles, which read
// too sanitary; the tile-life pass restores a middle ground (~84-85% open).
static void scatter(u8 base) {
    static const u8 kinds[6][4] = {
        { BGT_WILD_MOUNTAIN, BGT_TREE, BGT_TREE, BGT_WILD_MOUNTAIN },
        { BGT_TREE, BGT_TREE, BGT_WILD_FLOWER, BGT_TREE },
        { BGT_WILD_MOUNTAIN, BGT_WILD_MOUNTAIN, BGT_TREE, BGT_TREE },
        { BGT_TREE, BGT_WILD_FLOWER, BGT_TREE, BGT_TREE },
        { BGT_TREE, BGT_WILD_REEDS, BGT_TREE, BGT_WILD_FLOWER },
        { BGT_WILD_MOUNTAIN, BGT_WILD_FLOWER, BGT_WILD_MOUNTAIN, BGT_TREE },
    };
    u8 zone = (u8)(run_state.world_screen / 6);
    u8 tries, placed = 0;
    static const u8 singles[6][4] = {
        { BGT_WILD_STONE, BGT_TREE, BGT_WILD_STONE, BGT_WILD_STUMP },
        { BGT_TREE, BGT_WILD_STONE, BGT_WILD_STUMP, BGT_TREE },
        { BGT_WILD_STONE, BGT_TREE, BGT_WILD_STUMP, BGT_WILD_STONE },
        { BGT_TREE, BGT_WILD_STUMP, BGT_WILD_STONE, BGT_TREE },
        { BGT_WILD_STUMP, BGT_TREE, BGT_WILD_STUMP, BGT_WILD_STONE },
        { BGT_WILD_STONE, BGT_WILD_STONE, BGT_TREE, BGT_WILD_STONE },
    };
    u8 want = (u8)(3 + (next_hash() & 1));
    u8 lone = (u8)(3 + (next_hash() & 1));
    for (tries = 0; tries < 8 && lone; ++tries) {
        u8 h = next_hash();
        u8 x0 = (u8)(3 + next_hash() % 25);
        u8 y0 = (u8)(3 + next_hash() % 25);
        if (!fits(x0, y0, 1, 1, base)) continue;
        tile_put(x0, y0, singles[zone][h & 3]);
        lone--;
    }
    for (tries = 0; tries < 16 && placed < want; ++tries) {
        u8 h = next_hash();
        u8 kind = kinds[zone][h & 3];
        u8 x0 = (u8)(4 + ((next_hash() % 22) & 0xFE));
        u8 y0 = (u8)(4 + ((next_hash() % 22) & 0xFE));
        // Small clusters: one 2x2 metatile, a 4x2 pair, or a 4x4 grove.
        u8 w = (h & 0x60) ? 4 : 2;
        u8 hgt = (w == 4 && (h & 0x10)) ? 4 : 2;
        if (kind == BGT_WILD_FLOWER || kind == BGT_WILD_REEDS) hgt = 2;
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
    rw_ground_slot = base == BGT_WILD_SNOW ? BGPAL_CRYSTAL
        : base == BGT_WILD_SAND ? BGPAL_DOOR : BGPAL_FLOOR;
    rw_path_attr = (u8)((RUN_RIFTWILD_IS_HOLLOW() ? BGPAL_FLOOR
        : BGPAL_DOOR) | 0x08);
    if (!run_state.world_mode || run_state.world_screen >= 36) return;
    // Fixture fields are tidied too: their authored layouts are written
    // after this pass, so the tidy only sees shared procgen/climate terrain.
    if (fixture_field(run_state.world_screen)) {
        riftwild_tidy_field(base);
        return;
    }
    hash_state = riftwild_field_salt(1);
    den_here = riftwild_den_in_field();
    lift_old_blobs(base);
    riftwild_tidy_field(base);
    // Neighbouring fields start from different pieces (screen * 3), and the
    // seed rotates the whole assignment; a piece that does not fit here
    // hands over to the next one in the library.
    // Prefer a large authored stamp. Tight fields (return landings, a lake
    // plus the trail cross) fall back to the compact 3x3..4x5 markers.
    id = (u8)((next_hash() + run_state.world_screen * 3u) % PIECE_LARGE);
    for (k = 0; k < PIECE_LARGE && riftwild_setpiece_id == RW_SETPIECE_NONE;
         ++k) {
        u8 w = piece_w[id], h = piece_h[id];
        // The shard meadow scatters eight lone glass shards: the busiest
        // piece in the library, retired by the tiles pass.
        if (id == PIECE_SHARDS) tries = 10;
        else tries = 0;
        for (; tries < 10; ++tries) {
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
// flips, trees and crags tile as 2x2 canopies/peaks, water and sinkholes grow
// shorelines (edges, outer and inner corners),
// ruins read as columns and flagstones, and set-piece stamps draw their
// multi-tile art. Everything is keyed by position plus the per-field salt,
// so a field redraws identically on every stream.
static u8 cell_attr;

// Worn trail: an edge piece frays into the ground wherever the neighbour
// is not trail. A neighbour outside the field counts as trail, so mouths run
// on into the next field. dress_trail() reads all four neighbours; the
// streamer's trail_cell() takes the two along its line from the line itself
// and the two across from row pointers prepared once per line.
#define RAW(x, y) (((y) < ROOM_H && (x) >= ROOM_W)                           \
    ? sp_row_hi[y][(u8)((x) - ROOM_W)] : sp_row_lo[y][x])
// Edge piece by open side (bit 0 N, 1 S, 2 W, 3 E = not trail): art, its
// flips, and the extra flip a hash bit adds (a single fray or the mid never
// repeats along a run).
static const u8 rw_tr_art[16] = {
    RWA_PATH_PLAIN, RWA_PATH_N, RWA_PATH_N, RWA_PATH_STRAIT_H,
    RWA_PATH_W, RWA_PATH_NW, RWA_PATH_NW, RWA_PATH_STRAIT_H,
    RWA_PATH_W, RWA_PATH_NW, RWA_PATH_NW, RWA_PATH_STRAIT_H,
    RWA_PATH_STRAIT_V, RWA_PATH_STRAIT_V, RWA_PATH_STRAIT_V,
    RWA_PATH_STRAIT_H,
};
static const u8 rw_tr_flip[16] = {
    0, 0, 0x40, 0, 0, 0, 0x40, 0, 0x20, 0x20, 0x60, 0, 0, 0, 0, 0,
};
static const u8 rw_tr_jit[16] = {
    0x20, 0x20, 0x20, 0, 0x40, 0, 0, 0, 0x40, 0, 0, 0, 0, 0, 0, 0,
};
static u8 trail_pick(u8 code, u8 h) {
    u8 a = (u8)(rw_path_attr | rw_tr_flip[code]);
    if (h & 0x80) a ^= rw_tr_jit[code];
    cell_attr = a;
    if (!code) return (h & 7) ? RWA_PATH_PLAIN : RWA_PATH_STONES;
    return rw_tr_art[code];
}
static u8 dress_trail(u8 x, u8 y, u8 h) {
    u8 code = 0;
    if (x >= ROOM_WIDE_W_TILES || y >= ROOM_WIDE_H_TILES) {
        cell_attr = rw_path_attr;
        return RWA_PATH_PLAIN;
    }
    if (y && RAW(x, (u8)(y - 1)) != BGT_PATH) code |= 1;
    if (y < (u8)(ROOM_WIDE_H_TILES - 1) && RAW(x, (u8)(y + 1)) != BGT_PATH)
        code |= 2;
    if (x && RAW((u8)(x - 1), y) != BGT_PATH) code |= 4;
    if (x < (u8)(ROOM_WIDE_W_TILES - 1) && RAW((u8)(x + 1), y) != BGT_PATH)
        code |= 8;
    return trail_pick(code, h);
}
static const u8 rw_bit[8] = { 1, 2, 4, 8, 16, 32, 64, 128 };

// Ground detail grows in small clumps: 2x2 cell blocks are picked by a
// seeded block hash (5 in 16 staggered blocks), and inside a picked block about
// three cells in four carry a mark whose variant is shared by the clump.
// Net ~23% of ground cells, never uniform noise. Per-axis tables keep the
// horizontal and vertical streamers in agreement without a multiply.
static const u8 rw_cx[16] = { 0x3A, 0xC5, 0x17, 0x8E, 0x61, 0xF2, 0x2D, 0xB9,
                              0x54, 0x0B, 0xE7, 0x9C, 0x76, 0x23, 0xAF, 0x48 };
static const u8 rw_cy[16] = { 0x9F, 0x26, 0xD1, 0x4C, 0x08, 0xB3, 0x6E, 0xF5,
                              0x31, 0x8A, 0x57, 0xEC, 0x12, 0x7D, 0xC0, 0x95 };
// rw_mk[b]: a clump block's mark art, or 0 off-clump. One lookup in the hot
// loop instead of the CLUMP test plus the variant pick: blocks with
// (b & 15) < 5 are clumps (5 in 16), and bits 5..6 pick tufts (two art) or
// pebbles with small flowers. The caller XORs h bit 5 into b first, so half
// a clump's cells swap within the pair: mixed, not stamped.
#define T RWA_GRASS_TUFT
#define B RWA_GRASS_TUFT_B
#define P RWA_GRASS_PEBBLE
#define F RWA_GRASS_BLOOM
static const u8 rw_mk[256] = {
    T, T, T, T, T, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    T, T, T, T, T, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    B, B, B, B, B, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    B, B, B, B, B, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    P, P, P, P, P, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    P, P, P, P, P, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    F, F, F, F, F, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    F, F, F, F, F, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    T, T, T, T, T, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    T, T, T, T, T, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    B, B, B, B, B, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    B, B, B, B, B, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    P, P, P, P, P, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    P, P, P, P, P, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    F, F, F, F, F, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    F, F, F, F, F, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
};
#undef T
#undef B
#undef P
#undef F
// A mark inside a clump on 3 of 4 cells, else a stray sprig on 1 in 32.
#define MARKED(c, h) ((c) ? ((h) & 3) : !((h) & 31))
// Blocks are staggered bricks (odd block rows shift a cell) so clumps
// never line up in a grid.
#define BX(x, y) rw_cx[((u8)((x) + (((y) >> 1) & 1)) >> 1) & 15]

static u8 block_whole(u8 x, u8 y) {
    return rw_block_ok[(u8)((y >> 1) << 1) + (x >> 4)] & rw_bit[(x >> 1) & 7];
}

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
        case BGT_CRYSTAL:
            cell_attr = a | 0x08;
            return RWA_SHARD;
        case BGT_GRASS: case BGT_WILD_SNOW: case BGT_WILD_SAND:
        case BGT_WILD_MUD: case BGT_PATH: case BGT_TREE:
        case BGT_WILD_MOUNTAIN: case BGT_PILLAR: case BGT_FLOOR:
        case BGT_WILD_WATER: case BGT_WILD_HOLE:
            break;
        default:
            cell_attr = a;
            return tile;
    }
    cell_attr = a;
    switch (tile) {
        case BGT_GRASS:
            cell_attr = a | 0x08 | ((h & 0x80) ? 0x20 : 0);
            i = rw_mk[(u8)(BX(x, y) ^ rw_cy[(y >> 1) & 15]
                ^ riftwild_render_salt ^ (h & 0x20))];
            if (!MARKED(i, h)) return RWA_GRASS_PLAIN;
            return i ? i : RWA_GRASS_SPRIG;
        case BGT_WILD_SNOW: case BGT_WILD_SAND: case BGT_WILD_MUD:
            i = (u8)(BX(x, y) ^ rw_cy[(y >> 1) & 15] ^ riftwild_render_salt);
            if (MARKED(rw_mk[i], h)) {
                cell_attr = a | 0x08 | ((h & 0x80) ? 0x20 : 0);
                if (tile == BGT_WILD_SNOW)
                    return (i & 0x40) ? RWA_SNOW_GLINT : RWA_SNOW_DRIFT;
                if (tile == BGT_WILD_SAND)
                    return (i & 0x40) ? RWA_SAND_CRACK : RWA_SAND_SHELL;
                return (i & 0x40) ? RWA_MUD_ROOTS : RWA_MUD_PUDDLE;
            }
            break;
        case BGT_PATH:
            return dress_trail(x, y, h);
        case BGT_TREE:
        case BGT_WILD_MOUNTAIN:
            cell_attr = a | 0x08;
            if (!block_whole(x, y))
                return tile == BGT_TREE ? RWA_TREE_LONE : RWA_CRAG_LONE;
            return (u8)((tile == BGT_TREE ? RWA_TREE_TL : RWA_CRAG_TL)
                + ((y & 1) << 1) + (x & 1));
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
        case BGT_WILD_WATER:
        case BGT_WILD_HOLE: {
            u8 body = tile;
            u8 n = view_at(x, (u8)(y - 1)) != body;
            u8 s = view_at(x, (u8)(y + 1)) != body;
            u8 w = view_at((u8)(x - 1), y) != body;
            u8 e = view_at((u8)(x + 1), y) != body;
            u8 id_n = (body == BGT_WILD_WATER) ? RWA_SHORE_N : RWA_HOLE_N;
            u8 id_w = (body == BGT_WILD_WATER) ? RWA_SHORE_W : RWA_HOLE_W;
            u8 id_nw = (body == BGT_WILD_WATER) ? RWA_SHORE_NW : RWA_HOLE_NW;
            u8 id_in = (body == BGT_WILD_WATER) ? RWA_SHORE_INNER : RWA_HOLE_INNER;
            u8 flip = (u8)((s && !n) ? 0x40 : 0);
            u8 land = (u8)(n + s + w + e);
            u8 water = body == BGT_WILD_WATER;
            if (e && !w) flip |= 0x20;
            // Pieces the edge/corner set cannot express (tiles pass).
            if (land == 4) {
                cell_attr = a | 0x08;
                return water ? RWA_SHORE_LONE : RWA_HOLE_LONE;
            }
            if (land == 3) {
                cell_attr = a | 0x08;
                if (!s) return water ? RWA_SHORE_CAP_N : RWA_HOLE_CAP_N;
                if (!n) { cell_attr |= 0x40;
                    return water ? RWA_SHORE_CAP_N : RWA_HOLE_CAP_N; }
                if (!e) return water ? RWA_SHORE_CAP_W : RWA_HOLE_CAP_W;
                cell_attr |= 0x20;
                return water ? RWA_SHORE_CAP_W : RWA_HOLE_CAP_W;
            }
            if (land == 2 && ((n && s) || (w && e))) {
                cell_attr = a | 0x08;
                if (n) return water ? RWA_SHORE_STRAIT_H : RWA_HOLE_STRAIT_H;
                return water ? RWA_SHORE_STRAIT_V : RWA_HOLE_STRAIT_V;
            }
            if ((n || s) && (w || e)) {
                cell_attr = a | 0x08 | flip;
                return id_nw;
            }
            if (n || s) {
                cell_attr = a | 0x08 | flip;
                return id_n;
            }
            if (w || e) {
                cell_attr = a | 0x08 | flip;
                return id_w;
            }
            // Inner corners: all cardinals are body, a diagonal is land.
            // One tile plus flips covers NW/NE/SW/SE and rounds diamond lakes.
            {
                u8 nw = view_at((u8)(x - 1), (u8)(y - 1)) != body;
                u8 ne = view_at((u8)(x + 1), (u8)(y - 1)) != body;
                u8 sw = view_at((u8)(x - 1), (u8)(y + 1)) != body;
                u8 se = view_at((u8)(x + 1), (u8)(y + 1)) != body;
                if (nw || ne || sw || se) {
                    if (nw) flip = 0;
                    else if (ne) flip = 0x20;
                    else if (sw) flip = 0x40;
                    else flip = (u8)(0x20 | 0x40);
                    cell_attr = a | 0x08 | flip;
                    return id_in;
                }
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
// nothing else pays dress_cell(). The per-cell hash is the
// same as before: h = x*0x1D + y*0x3B + salt; h ^= h >> 3; h += (y<<3) ^ x.
#define RWK_SKIP   0
#define RWK_GRASS  1   // plain, or a clumped mark (CLUMP)
#define RWK_SNOW   2   // snow / sand / mud: clumped marks, two art
#define RWK_SAND   3
#define RWK_MUD    4
#define RWK_PATH   5   // worn trail: trail_cell(), edge pieces from neighbours
#define RWK_TREE   6
#define RWK_CRAG   7
#define RWK_SLOW   8   // shoreline / ruin / stamp: dress_cell()
static const u8 rw_kind[256] = {
    [BGT_GRASS] = RWK_GRASS, [BGT_WILD_SNOW] = RWK_SNOW,
    [BGT_WILD_SAND] = RWK_SAND, [BGT_WILD_MUD] = RWK_MUD,
    [BGT_PATH] = RWK_PATH, [BGT_TREE] = RWK_TREE,
    [BGT_WILD_MOUNTAIN] = RWK_CRAG, [BGT_PILLAR] = RWK_SLOW,
    [BGT_FLOOR] = RWK_SLOW, [BGT_WILD_WATER] = RWK_SLOW,
    [BGT_WILD_HOLE] = RWK_SLOW, [BGT_CRYSTAL] = RWK_SLOW,
};
// (b & 0x40) ? alt_b : alt_a, matching dress_cell() for snow, sand and mud.
static const u8 rw_alt_a[5] = { 0, 0, RWA_SNOW_DRIFT, RWA_SAND_SHELL,
    RWA_MUD_PUDDLE };
static const u8 rw_alt_b[5] = { 0, 0, RWA_SNOW_GLINT, RWA_SAND_CRACK,
    RWA_MUD_ROOTS };

// Line invariants live in statics so the hot loop keeps its few locals in
// registers instead of shuffling an SDCC stack frame per cell.
static u8 dl_vertical, dl_fixed, dl_step, dl_mix, dl_par, dl_lo, dl_hi;
static u8 dl_bfix, dl_boff, dl_brow, dl_bhi, dl_bbit;

static void dress_slow(u8 *tp, u8 *ap, u8 i, u8 h) {
    u8 x = dl_vertical ? dl_fixed : i;
    u8 y = dl_vertical ? i : dl_fixed;
    *tp = dress_cell(*tp, *ap, x, y, h);
    *ap = cell_attr;
}

// One loop body per orientation, so the cell path never re-tests it.
// PAR(i): canopy/crag quarter from parity; MIX(i): the (y << 3) ^ x term;
// WHOLE(i): the cell's aligned 2x2 block is a complete tree/crag metatile.
// BLK(i): the cell's 2x2-block clump hash (rw_mk); trail cells go to
// trail_cell().
#define DRESS_RUN(name, PAR, MIX, WHOLE, BLK)                                  \
static void name(u8 *tp, u8 *ap, u8 i, u8 n, u8 hb) {                       \
    u8 k, h, b, i0 = i;                                                             \
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
            if (!(WHOLE(i))) {                                              \
                *tp = (k == RWK_TREE) ? RWA_TREE_LONE : RWA_CRAG_LONE;      \
                continue;                                                   \
            }                                                               \
            *tp = (u8)((k == RWK_TREE ? RWA_TREE_TL : RWA_CRAG_TL)          \
                + dl_par + (u8)(PAR(i)));                                   \
            continue;                                                       \
        }                                                                   \
        h = (u8)(hb ^ (hb >> 3)); h += (u8)(MIX(i));                        \
        if (k == RWK_PATH) {                                                \
            dl_ti = i; dl_tlast = (u8)(n == 1); dl_tfirst = (u8)(i == i0);  \
            trail_cell(tp, ap, h);                                          \
            continue;                                                       \
        }                                                                   \
        b = BLK(i);                                                         \
        if (k == RWK_GRASS) {                                               \
            *ap |= (u8)((h & 0x80) ? 0x28 : 0x08);                          \
            b = rw_mk[(u8)(b ^ (h & 0x20))];                                \
            *tp = !MARKED(b, h) ? RWA_GRASS_PLAIN : b ? b : RWA_GRASS_SPRIG; \
            continue;                                                       \
        }                                                                   \
        if (!MARKED(rw_mk[b], h)) continue;                                 \
        *ap |= (u8)((h & 0x80) ? 0x28 : 0x08);                              \
        *tp = (b & 0x40) ? rw_alt_b[k] : rw_alt_a[k];                       \
    }                                                                       \
}
#define PAR_H(i) ((i) & 1)
#define MIX_H(i) (dl_mix ^ (i))
#define PAR_V(i) (((i) & 1) << 1)
#define MIX_V(i) (((u8)((i) << 3)) ^ dl_fixed)
#define WHOLE_H(i) (rw_block_ok[(u8)(dl_brow + ((i) >> 4))]                 \
    & rw_bit[((i) >> 1) & 7])
#define WHOLE_V(i) (rw_block_ok[(u8)((((i) >> 1) << 1) + dl_bhi)] & dl_bbit)
#define BLK_H(i) (rw_cx[((u8)((i) + dl_boff) >> 1) & 15] ^ dl_bfix)
#define BLK_V(i) (BX(dl_fixed, (i)) ^ rw_cy[((i) >> 1) & 15] ^ dl_bfix)
// A dressed cell is trail when it holds bank-1 (attr bit 3) trail art; the
// bank check keeps raw bank-0 ids that share those numbers (flowers = 96)
// from reading as trail.
#define TRAIL_ART(t) ((t) == RWA_PATH_PLAIN || (t) == RWA_PATH_STONES            \
    || (u8)((t) - RWA_PATH_N) <= (u8)(RWA_PATH_STRAIT_V - RWA_PATH_N))
#define TRAIL_AT(tp, ap) ((*(ap) & 0x08) && TRAIL_ART(*(tp)))
static u8 dl_run_prev, dl_run_next, dl_ti, dl_tfirst, dl_tlast;
// Across-line neighbours for trail_cell(). Horizontal line y: the rows
// above/below as lo (x < split) and hi (x >= split, pre-offset by -ROOM_W)
// pointers; outside the field they point at an all-trail row. Vertical line
// x: columns x - 1 / x + 1 as row offsets and whether they sit in the
// extension (x >= ROOM_W) for rows above ROOM_H.
static const u8 rw_trail_row[32] = {
    BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH,
    BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH,
    BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH,
    BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH,
    BGT_PATH, BGT_PATH, BGT_PATH, BGT_PATH,
};
static const u8 *dl_up_lo, *dl_up_hi, *dl_dn_lo, *dl_dn_hi;
static u8 dl_up_split, dl_dn_split;
static u8 dl_wx, dl_ex, dl_wx_hi, dl_ex_hi, dl_wx_lo, dl_ex_lo;

static void trail_rows(u8 y, const u8 **lo, const u8 **hi, u8 *split) {
    if (y >= ROOM_WIDE_H_TILES) {        // also y - 1 from 0
        *lo = *hi = rw_trail_row; *split = 32;
    } else if (y < ROOM_H) {
        *lo = sp_row_lo[y]; *hi = sp_row_hi[y] - ROOM_W; *split = ROOM_W;
    } else {
        *lo = *hi = sp_row_lo[y]; *split = 32;
    }
}
// One streamed trail cell (kept out of the hot loop so the plain-ground
// path keeps its registers). Along-line neighbours come from the line
// itself: the dressed previous cell (or the run's carried-in edge) and the
// raw next one; past cell 30 is outside the field, which counts as trail.
static void trail_cell(u8 *tp, u8 *ap, u8 h) {
    u8 i = dl_ti, code = 0;
    if (i >= (u8)(ROOM_WIDE_W_TILES - 1)) {
        if (i > (u8)(ROOM_WIDE_W_TILES - 1)) {   // overscan cell 31
            *tp = RWA_PATH_PLAIN; *ap = rw_path_attr;
            return;
        }
    } else if ((dl_tlast ? dl_run_next : tp[1]) != BGT_PATH) {
        code = 2;                                // next along the line
    }
    if (dl_tfirst ? !dl_run_prev : !TRAIL_AT(tp - 1, ap - 1)) code |= 1;
    // Across the line: rows above/below (horizontal) or columns either side
    // (vertical), from the pointers riftwild_dress_line() prepared.
    if (dl_vertical) {
        // along = N (1) / S (2); across = W (4) / E (8)
        if (i < ROOM_H) {
            if ((dl_wx_hi ? sp_row_hi[i][dl_wx] : sp_row_lo[i][dl_wx])
                != BGT_PATH) code |= 4;
            if ((dl_ex_hi ? sp_row_hi[i][dl_ex] : sp_row_lo[i][dl_ex])
                != BGT_PATH) code |= 8;
        } else {
            if (sp_row_lo[i][dl_wx_lo] != BGT_PATH) code |= 4;
            if (sp_row_lo[i][dl_ex_lo] != BGT_PATH) code |= 8;
        }
        if (!dl_fixed) code &= (u8)~4;           // west of x 0: outside
    } else {
        // along = W (4) / E (8); across = N (1) / S (2)
        code = (u8)(((code & 1) << 2) | ((code & 2) << 2));
        if ((i < dl_up_split ? dl_up_lo[i] : dl_up_hi[i]) != BGT_PATH)
            code |= 1;
        if ((i < dl_dn_split ? dl_dn_lo[i] : dl_dn_hi[i]) != BGT_PATH)
            code |= 2;
    }
    *tp = trail_pick(code, h);
    *ap = cell_attr;
}
DRESS_RUN(dress_run_h, PAR_H, MIX_H, WHOLE_H, BLK_H)
DRESS_RUN(dress_run_v, PAR_V, MIX_V, WHOLE_V, BLK_V)

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
    dl_boff = (u8)((fixed >> 1) & 1);
    dl_bfix = (u8)((vertical ? 0 : rw_cy[(fixed >> 1) & 15])
        ^ riftwild_render_salt);
    dl_brow = (u8)((fixed >> 1) << 1);
    dl_bhi = (u8)(fixed >> 4);
    dl_bbit = rw_bit[(fixed >> 1) & 7];
    // Stamp cells along this line, as a logical [lo, hi) range.
    dl_lo = dl_hi = 0;
    if (rw_box_x0 != 0xFF) {
        if (vertical && fixed >= rw_box_x0 && fixed < rw_box_x1) {
            dl_lo = rw_box_y0; dl_hi = rw_box_y1;
        } else if (!vertical && fixed >= rw_box_y0 && fixed < rw_box_y1) {
            dl_lo = rw_box_x0; dl_hi = rw_box_x1;
        }
    }
    if (vertical) {
        u8 wx = fixed ? (u8)(fixed - 1) : 0;
        u8 ex = (u8)(fixed + 1);
        if (ex >= ROOM_WIDE_W_TILES) ex = (u8)(ROOM_WIDE_W_TILES - 1);
        dl_wx_lo = wx; dl_ex_lo = ex;
        dl_wx_hi = wx >= ROOM_W; dl_ex_hi = ex >= ROOM_W;
        dl_wx = dl_wx_hi ? (u8)(wx - ROOM_W) : wx;
        dl_ex = dl_ex_hi ? (u8)(ex - ROOM_W) : ex;
    } else {
        trail_rows((u8)(fixed - 1), &dl_up_lo, &dl_up_hi, &dl_up_split);
        trail_rows((u8)(fixed + 1), &dl_dn_lo, &dl_dn_hi, &dl_dn_split);
    }
    // Logical 0..first-1 sit at physical p..31, the rest wrap to 0. A run
    // carries its trail neighbours across the wrap: before logical 0 is
    // outside the field (trail); the first run's last cell is followed by
    // physical 0, still raw; the second run follows the dressed physical 31.
    dl_run_prev = 1;
    dl_run_next = p ? (u8)(tiles[0] == BGT_PATH) : 1;
    if (vertical) {
        dress_run_v(tiles + p, attrs + p, 0, first, hb);
        dl_run_prev = TRAIL_AT(tiles + 31, attrs + 31);
        dl_run_next = 1;
        if (p) dress_run_v(tiles, attrs, first, p,
            (u8)(hb + first * dl_step));
    } else {
        dress_run_h(tiles + p, attrs + p, 0, first, hb);
        dl_run_prev = TRAIL_AT(tiles + 31, attrs + 31);
        dl_run_next = 1;
        if (p) dress_run_h(tiles, attrs, first, p,
            (u8)(hb + first * dl_step));
    }
}
