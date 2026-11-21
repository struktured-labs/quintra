#ifndef QUINTRA_GAME_REWRITE_ROOM_H
#define QUINTRA_GAME_REWRITE_ROOM_H

#include <gb/gb.h>
#include "core/types.h"

// M2 of the Ultima-depth spec: the optional Cairn Ford pocket in Ember
// Depths. It teaches exactly one verb, material rewrite:
//   Switch A (round plate)  raises every rewrite bed to a CAIRN (rock).
//   Switch B (square plate) turns every cairn into a FORD (shallow water
//                           bridge) and back.
// Beds are a CHASM (solid) or a SILL (carved floor socket, walkable).
// Plates toggle on a step or when a player shot crosses them. The pocket is
// self-contained: WRAM only, rebuilt on entry, Pack RESET ROOM + entrance
// plate restore the whole machine. See
// docs/superpowers/specs/2026-11-21-m2-cairn-ford-addendum.md.

#define RW_STAGE 2              // bosses_beaten: Ember Depths
#define RW_X0 18                // world tile of the pocket's top-left wall
#define RW_Y0 11
#define RW_W 12
#define RW_H 20

#define RW_PLATE_A_X 1          // 2x2 Switch A (round), foyer
#define RW_PLATE_A_Y 4
#define RW_PLATE_A2_X 9         // the same Switch A glyph again, alcove (same meaning)
#define RW_PLATE_A2_Y 6
#define RW_PLATE_B_X 9          // 2x2 Switch B (square), alcove dead end
#define RW_PLATE_B_Y 1
#define RW_RESET_X 3            // 2x2 entrance reset plate
#define RW_RESET_Y 1
#define RW_GOAL_X 4             // two BGT_SWITCH goal tiles (4,17) (5,17)
#define RW_GOAL_Y 17
#define RW_ENTRY_Y 6            // west-wall entrance rows 6..7

// Material ids. Logical ids are Riftwild-only slots whose collision and
// palette already fit; their VRAM art is replaced while the pocket is live
// (tiles_load_dungeon_bg restores it on the next room entry).
#define RW_T_CAIRN_TL 98        // BGT_WILD_STONE   solid, WALL palette
#define RW_T_CAIRN_TR 109       // BGT_WILD_MOUNTAIN
#define RW_T_CAIRN_BL 110       // BGT_WILD_REEDS
#define RW_T_CAIRN_BR 39        // BGT_TREE
#define RW_T_FORD     107       // BGT_WILD_SNOW    walkable, CRYSTAL palette
#define RW_T_CHASM    108       // BGT_WILD_HOLE    solid, CRACK palette
#define RW_T_SILL     105       // BGT_WILD_MUD     walkable, FLOOR palette

#define RW_REGIONS 3

extern u8 rw_live;
extern u8 rw_a, rw_b;           // phase mask: A raised, B fords
extern u8 rw_resets;
extern u8 rw_blink;             // regions changed off-camera, not yet seen
extern u8 rw_offcam_sfx;        // count of off-camera rewrite cues (tests)
extern u8 rw_refusals;          // count of refused presses (tests)

u8 rw_prepare(void) BANKED;
void rw_tick(void) BANKED;
void rw_reset(void) BANKED;
void rw_art_load(void) BANKED;
void rw_bg_art_load(void) BANKED;

#endif
