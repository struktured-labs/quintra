#ifndef QUINTRA_GAME_RIFTWILD_SETPIECE_H
#define QUINTRA_GAME_RIFTWILD_SETPIECE_H
#include "core/types.h"

// One authored set piece per ordinary Riftwild field (audit L2), seeded
// clumps of trees and crags, and a few one-visit caches. Logical tiles keep
// their ordinary collision ids; multi-tile art (Worldglass spires, guardian
// statues, the elder tree, obelisks) is drawn from VRAM bank 1 through the
// render stamps below. See docs/superpowers/specs/2026-11-15-riftwild-wonder-audit.md.

#define RW_STAMP_MAX 4
#define RW_SETPIECE_NONE 0xFF
// Cache claims use shop_civic bits 4..7 (bits 0..3 are the village civic
// screens). shop_civic resets when the next dungeon begins, so each
// Riftwild visit has fresh caches but none can be farmed by backtracking.
#define RW_CACHE_BIT_SHIFT 4

extern u8 rw_stamp_n;
extern u8 rw_stamp_x[RW_STAMP_MAX];
extern u8 rw_stamp_y[RW_STAMP_MAX];
extern u8 rw_stamp_w[RW_STAMP_MAX];
extern u8 rw_stamp_h[RW_STAMP_MAX];
extern u8 rw_stamp_art[RW_STAMP_MAX];
extern u8 rw_stamp_attr[RW_STAMP_MAX];
// Current field's set piece (for tests and the cache spawn), or NONE.
extern u8 riftwild_setpiece_id;
extern u8 riftwild_setpiece_x;
extern u8 riftwild_setpiece_y;
extern u8 riftwild_cache_x;   // tile coords, 0xFF when the piece has none
extern u8 riftwild_cache_y;
// Per-field render salt for ground variants (all 32 seed bits).
extern u8 riftwild_render_salt;

// Whole 2x2 tree/crag metatiles: 16 block rows x 2 bytes (bit = block x
// & 7 of byte x >> 3). Written by riftwild_meta_scan() after the field's
// final terrain write; the renderer draws canopy/peak quarters only inside
// set blocks and a self-contained lone tile everywhere else.
#define RW_BLOCK_BYTES 32
extern u8 rw_block_ok[RW_BLOCK_BYTES];
// Palette slot of this field's ground (trails are drawn in it).
extern u8 rw_ground_slot;
void riftwild_tidy_field(u8 base) BANKED;
void riftwild_meta_scan(void) BANKED;
// Wide-seam hook, once per slide step: step 0 rescans the destination's
// metatiles (fixtures and events write terrain after procgen); step 8 of an
// N/S slide swaps the shared ground colour 0 between climate rows.
void riftwild_hollow_reeds(void) BANKED;
// Fire burned one cell of a tree: redraw the rest of its 2x2 canopy as
// lone trees so no orphan quarter is left on screen.
void riftwild_tree_burned(u8 tx, u8 ty) BANKED;
void riftwild_seam_step(u8 step, u8 dir) BANKED;

void riftwild_setpiece_apply(u8 base) BANKED;
void riftwild_setpiece_spawn(void) BANKED;
u8   riftwild_field_salt(u8 k) BANKED;
// Render pass for one BG row (vertical=0, fixed=y) or column (fixed=x).
void riftwild_dress_line(u8 *tiles, u8 *attrs, u8 fixed, u8 vertical,
                         u8 origin) BANKED;

#endif
