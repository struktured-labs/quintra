#ifndef QUINTRA_GAME_RIME_ROOM_H
#define QUINTRA_GAME_RIME_ROOM_H

#include <gb/gb.h>
#include "core/types.h"

// M1 of the Ultima-depth spec (2026-11-19-ultima-puzzle-depth.md): one tiny
// optional chamber in Verdant Hollow, the dungeon before the Ember Conduit
// floor. It teaches exactly two verbs: Rime Pipes (a room-local freeze-all
// charge) and the Stone Jagger (a roamer no weapon can touch). The chamber
// is a walled 9x14 pocket in the south-east corner of the 31x31 field, with
// one always-open entrance, an entrance reset plate, and Pack "RESET ROOM".

#define RIME_STAGE 1            // bosses_beaten: Verdant Hollow
#define RIME_X0 21              // world tile of the chamber's top-left wall
#define RIME_Y0 15
#define RIME_W 9
#define RIME_H 14

// Local chamber cells (add RIME_X0 / RIME_Y0 for world tiles).
#define RIME_LANE_Y     5       // Jagger lane rows 5..6
#define RIME_LANE_X0    1       // Jagger left tile range 1..6
#define RIME_LANE_X1    6
#define RIME_JAGGER_X   4       // entry rest cell, mid-lane
#define RIME_PED_FOYER_X 5      // 2x2 pedestal, foyer
#define RIME_PED_FOYER_Y 8
#define RIME_PED_VAULT_X 1      // 2x2 pedestal, vault
#define RIME_PED_VAULT_Y 2
#define RIME_PLATE_X    1       // 2x2 entrance reset plate
#define RIME_PLATE_Y    11
#define RIME_GOAL_X     5       // two BGT_SWITCH goal tiles (5,2) (6,2)
#define RIME_GOAL_Y     2
#define RIME_ENTRY_Y    9       // west-wall entrance gap rows 9..10

#define RIME_FREEZE_NORMAL 45   // beats of four frames (spec 6.3)
#define RIME_FREEZE_EASY   56

// dungeon_puzzles bit 5 was the last free bit (spec 2.5). Set once the
// vault plate is pressed so the reward is not farmable by leaving.
// Pixel rect (entity centre) no ordinary enemy may enter: the chamber and
// the tile column in front of its doorway. Checked inline by enemy_try_step.
#define RIME_KEEP_X0 ((RIME_X0 - 1) * 8)
#define RIME_KEEP_Y0 (RIME_Y0 * 8)
#define RIME_KEEP_Y1 ((RIME_Y0 + RIME_H) * 8)

#define RUN_RIME_SOLVED_BIT ((u8)(1u << 5))

extern u8 rime_live;            // this room is the Rime chamber
extern u8 rime_cell;            // chosen local cell this stage, 0xFF none
extern u8 rime_charge;          // hero holds a Pipes charge (0/1)
extern u8 room_freeze_beats;    // room-wide freeze clock (enemy_update gate)
extern u8 rime_jx, rime_jy;     // Jagger world px (top-left of 16x16)
extern u8 rime_jagger_hold;     // frames the Jagger waits after a reset
extern u8 rime_resets;          // telemetry: resets this visit

u8 rime_pick_cell(void) BANKED;
// Called by puzzle_prepare_room for a non-role cell; returns 1 when the
// chamber was authored here.
u8 rime_prepare(void) BANKED;
void rime_tick(void) BANKED;
void rime_use_pipes(void) BANKED;
void rime_reset(void) BANKED;
void rime_art_load(void) BANKED;
void rime_pack_draw(u8 pipes) BANKED;
u8 rime_pack_a(u8 pipes) BANKED;

// Shared by every optional puzzle pocket (M1 rime_room, M2 rewrite_room).
extern u8 puzzle_keep_on;       // ordinary enemies stay out of the pocket
extern u8 puzzle_keep_x0, puzzle_keep_y0, puzzle_keep_y1;   // entity-centre px box
extern u8 puzzle_pack_n;        // extra Pack TOOL entries after the 4 tools
void puzzle_pack_draw(u8 idx) BANKED;
u8 puzzle_pack_a(u8 idx) BANKED;
void puzzle_pack_apply(u8 idx) BANKED;

#endif
