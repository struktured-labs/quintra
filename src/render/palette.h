// CGB palette helpers — load 4-color palettes into the 8 BG and 8 OBJ slots.
#ifndef QUINTRA_RENDER_PALETTE_H
#define QUINTRA_RENDER_PALETTE_H

#include <gb/gb.h>
#include "core/types.h"

// Pack 5-bit r/g/b channels into BGR555 word (CGB native).
#define BGR555(r,g,b)  ((u16)((((b) & 0x1F) << 10) | (((g) & 0x1F) << 5) | ((r) & 0x1F)))

// Boss arenas share one quiet neutral floor ramp so biome-coloured bodies
// stay readable. Fixed-bank palette data keeps it callable from room code.
extern const u16 boss_arena_floor_palette[4];

// Load 4-color palette into BG palette slot 0..7
void palette_bg_load(u8 slot, const u16 *colors);

// Load 4-color palette into OBJ palette slot 0..7
void palette_obj_load(u8 slot, const u16 *colors);

// Cached OBJ palettes. Title fills this, sets palette_obj_pending_commit
// to PALETTE_OBJ_COMMIT_PASSES, and loop_run writes the cache during
// VBlank after wait_vbl_done(). Re-arming OCPS per color avoids index
// desync if a write is dropped.
#define PALETTE_OBJ_COMMIT_PASSES 16
void palette_obj_commit_vblank(void) BANKED;
// Five champion palettes plus black slots 0, 6 and 7. Lives with the
// VBlank commit so title.c (bank 12) does not hold the copy loop.
void palette_obj_cache_title(void) BANKED;
extern u16 obj_pal_cache[8][4];
extern volatile u8 palette_obj_pending_commit;

// Load N consecutive BG palettes starting at slot
void palette_bg_load_n(u8 first_slot, u8 n, const u16 *colors);

// Set every visible background cell to one known CGB palette. Text screens
// must call this after font setup so dungeon attributes cannot leak through.
void palette_bg_fill_attrs(u8 slot);

#endif
