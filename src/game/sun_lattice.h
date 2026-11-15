#ifndef QUINTRA_GAME_SUN_LATTICE_H
#define QUINTRA_GAME_SUN_LATTICE_H

// Sun Lattice light-reflection puzzle (Stage 3+ Trial / Waystone rooms).
// See docs/superpowers/specs/2026-11-15-sun-lattice-light-puzzles.md.
//
// The generator and tracer in sun_lattice_gen.c are plain C with no GBDK
// dependency so scripts/test_sun_lattice_parity.py can compile them on the
// host and compare them with the Rust reference in quintra-procgen.

#include "core/types.h"

#ifdef SL_HOST
#define SL_BANKED
#else
#include <gb/gb.h>
#define SL_BANKED BANKED
#endif

#define SL_MAX_FIX   20
#define SL_MAP_W     20
#define SL_MAP_H     17
#define SL_BITS      43   // ceil(20 * 17 / 8)
#define SL_DWELL     12   // frames every Obelisk must stay lit
#define SL_DEBOUNCE  8    // frames before the same vane may turn again

// Fixture kinds. Every fixture occupies one 8x8 cell and is BGT_PILLAR in
// room_tilemap, so collision, enemies and hostile shots treat it like any
// other solid post; only the lattice layer knows what it really is.
enum {
    SLK_EMITTER = 1,   // Sun Brazier, fires sl_dir[i]
    SLK_VANE,          // rotatable Helio Vane
    SLK_FIXED,         // Fixed Vane: reflects, never rotates
    SLK_BIFROST,       // Bifrost Wedge T-splitter
    SLK_OBELISK,       // Solar Obelisk target
};

// sl_ang: 0 = '/', 1 = '\'. Directions: 0 N, 1 E, 2 S, 3 W.
extern u8 sl_n;
extern u8 sl_x[SL_MAX_FIX];
extern u8 sl_y[SL_MAX_FIX];
extern u8 sl_kind[SL_MAX_FIX];
extern u8 sl_ang[SL_MAX_FIX];     // vane angle, or emitter direction
extern u8 sl_solved_ang[SL_MAX_FIX];
extern u8 sl_lit[SL_MAX_FIX];     // obelisk lit this trace
extern u8 sl_crystal_x, sl_crystal_y; // 0xFF when the room has no blocker
extern u8 sl_beam_h[SL_BITS];
extern u8 sl_beam_v[SL_BITS];
extern u8 sl_fixbits[SL_BITS];
extern u8 sl_attempts;            // generator attempts used (0xFF = fallback)

// Build the solved optical tree for this seed and stage, then scramble it.
// role: 0 Trial, 1 Waystone; bosses_beaten: run_state.bosses_beaten.
void sl_generate(u32 seed, u8 bosses_beaten, u8 role) SL_BANKED;
// Trace every beam into sl_beam_h / sl_beam_v and sl_lit. When use_map is
// nonzero, room_tilemap terrain can stop a beam (walls, pillars, crystals).
// Returns 1 when every Obelisk is lit.
u8 sl_trace(u8 use_map) SL_BANKED;

#ifndef SL_HOST
// Runtime layer (sun_lattice.c).
void sun_lattice_prepare(u32 seed, u8 role, u8 solved) BANKED;
void sun_lattice_paint_all(void) BANKED;
// A player strike landed on solid cell (tx, ty). Returns 1 when that cell
// is a lattice fixture (the shot is consumed), rotating a vane if allowed.
u8 sun_lattice_strike(u8 tx, u8 ty) BANKED;
// Hookshot tip reached (tx, ty). Returns 1 when it snagged and spun a
// rotatable vane; the hook then retracts instead of pulling the champion.
u8 sun_lattice_hook(u8 tx, u8 ty) BANKED;
// Terrain changed (crystal shattered): retrace and repaint.
void sun_lattice_retrace(void) BANKED;
// Per-frame: debounce and the lit dwell. Returns 1 on the solve frame.
u8 sun_lattice_tick(void) BANKED;
#endif

#endif
