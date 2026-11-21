#ifndef QUINTRA_GAME_KITE_ROOM_H
#define QUINTRA_GAME_KITE_ROOM_H

#include <gb/gb.h>
#include "core/types.h"

// M3 of the Ultima-depth spec: the optional Kite Kennel pocket in Frost
// Vault. It teaches the tool-beast chain: release -> build -> route -> tool.
//   Lever L (round plate)   opens the kennel gate (bars -> rift-stream).
//   Stream plates (diamond) turn a cairn segment of the channel into
//                           rift-stream and back.
// L and the second stream plate S2 are one linked switch: the gate opens
// exactly when segment B closes, so the Cinder Kite must be released, wait
// on segment A, and only then be let through. At the end of the channel it
// breathes on the crystal lock that plugs the vault doorway, then flies
// home. Nothing but the Kite's breath breaks the lock. The Kite is a
// puzzle-owned actor (not an entity): weapons and companions pass through
// it. Left blocked in the cold too long it gutters out and re-forms in the
// kennel. The pocket is self-contained: WRAM only, rebuilt on entry, Pack
// RESET ROOM + entrance plate restore the whole machine. See
// docs/superpowers/specs/2026-11-21-m3-kite-kennel-addendum.md.

#define KT_STAGE 3              // bosses_beaten: Frost Vault
#define KT_X0 18                // world tile of the pocket's top-left wall
#define KT_Y0 11
#define KT_W 12
#define KT_H 18

#define KT_RESET_X 1            // 2x2 plates (drawn as OBJ glyphs on floor)
#define KT_RESET_Y 1
#define KT_LEVER_X 6
#define KT_LEVER_Y 3
#define KT_S1_X 6
#define KT_S1_Y 5
#define KT_S2_X 6
#define KT_S2_Y 7
#define KT_GOAL_X 4             // two BGT_SWITCH goal tiles (4,15) (5,15)
#define KT_GOAL_Y 15
#define KT_ENTRY_Y 6            // west-wall entrance rows 6..7
#define KT_CHAN_X 9             // channel column (9..10)
#define KT_HOME_Y 1             // kennel niche rows 1..2
#define KT_END_Y 11             // channel end rows 11..12
#define KT_LOCK_X 6             // crystal lock (6..7, 11..12)
#define KT_LOCK_Y 11

// Logical ids: Riftwild/outdoor-only slots whose collision already fits
// (all solid to the hero); VRAM art is replaced while the pocket is live.
#define KT_T_CAIRN_TL 98        // same ids and art as M2's cairn
#define KT_T_CAIRN_TR 109
#define KT_T_CAIRN_BL 110
#define KT_T_CAIRN_BR 39
#define KT_T_BARS     99        // BGT_WILD_STUMP
#define KT_T_STREAM   108       // BGT_WILD_HOLE
#define KT_T_LOCK_T   37        // BGT_ROOF  (right column X-flipped)
#define KT_T_LOCK_B   38        // BGT_FENCE

#define KT_REGIONS 4            // gate, segment A, segment B, lock

#define KT_HOME   0
#define KT_DOWN   1
#define KT_BREATH 2
#define KT_RETURN 3
#define KT_DEAD   4

extern u8 kt_live;
extern u8 kt_s1, kt_x;          // segment A stream; linked gate-open/B-closed
extern u8 kt_broken;            // crystal lock shattered
extern u8 kt_state, kt_ky, kt_cold, kt_frame;
extern u8 kt_resets, kt_deaths, kt_refusals, kt_blink, kt_offcam_sfx;

u8 kt_prepare(void) BANKED;
void kt_tick(void) BANKED;
void kt_reset(void) BANKED;
void kt_art_load(void) BANKED;
void kt_bg_art_load(void) BANKED;

#endif
