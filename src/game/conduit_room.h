#ifndef QUINTRA_GAME_CONDUIT_ROOM_H
#define QUINTRA_GAME_CONDUIT_ROOM_H

#include <gb/gb.h>
#include "core/types.h"

// M5a of the Ultima-depth spec: the Conduit, the combine-under-pressure
// pocket (spec 5, 6.2, 6.3, 6.4, 6.6, M5). Verbs taught in M1-M4 run
// together: freeze + the Stone Jagger, a rolling-stone lane that crushes a
// frozen Jagger, a spawn plate with a teleport skip, a turret whose shots
// strike a gold switch that churns a side door, and a Star key behind it
// that opens the vault. Self-contained: WRAM only, rebuilt on entry; Pack
// RESET ROOM, the entrance plate and walking out restore the entry state.
// See docs/superpowers/specs/2026-11-21-m5a-conduit-addendum.md.

#define CD_STAGE 5              // bosses_beaten: the dungeon after M4
#define CD_X0 18                // world tile of the pocket's top-left wall
#define CD_Y0 11
#define CD_W 12
#define CD_H 18
#define CD_ENTRY_Y 6            // west-wall entrance rows 6..7

#define CD_TP_X 1               // teleport pad (2x2) ...
#define CD_TP_Y 1
#define CD_TPD_Y 9              // ... lands the hero in the hall, row 9
#define CD_TUR_X 9              // turret alcove (2x2)
#define CD_TUR_Y 1
#define CD_SW_X 9               // gold switch (2x2), in the turret's S lane
#define CD_SW_Y 4
#define CD_SIDE_X 6             // side door (1x2), churned by the switch
#define CD_SIDE_Y 3
#define CD_RESET_X 1            // entrance reset plate (2x2)
#define CD_RESET_Y 4
#define CD_FRZ_X 4              // freeze (Rime) pedestal (2x2)
#define CD_FRZ_Y 5
#define CD_KEY_X 8              // Star key pedestal (2x2)
#define CD_KEY_Y 6
#define CD_SPAWN_X 4            // spawn plate (2x2) in the hall gap
#define CD_SPAWN_Y 8
#define CD_LANE_Y 10            // rolling-stone lane rows 10..11
#define CD_DOOR_X 5             // Star door (2x1) to the vault
#define CD_DOOR_Y 12
#define CD_GOAL_X 5             // two BGT_SWITCH goal tiles
#define CD_GOAL_Y 15

#define CD_T_TRACK 105          // borrowed walkable id: stone groove
#define CD_T_DOOR  37           // borrowed solid id: Star door (M4 art)
#define CD_T_BARS  99           // borrowed solid id: side door bars (M3)

#define CD_J_GUARD 0
#define CD_J_DEAD  1

#define CD_WX(lx) ((u8)(CD_X0 + (lx)))
#define CD_WY(ly) ((u8)(CD_Y0 + (ly)))
#define CD_PX(lx) ((u8)(CD_WX(lx) << 3))
#define CD_PY(ly) ((u8)(CD_WY(ly) << 3))

extern u8 cd_live;
extern u8 cd_side;              // side door open
extern u8 cd_key, cd_held, cd_open;   // Star key on pedestal / held / vault door open
extern u8 cd_charge;            // hero holds a Rime charge
extern u8 cd_jx, cd_jy, cd_jst; // Jagger (16x16 top-left, world px)
extern u8 cd_sst, cd_sx, cd_st; // stone: 0 idle, 1 rumble, 2 rolling; x; timer
extern u8 cd_thp, cd_tt, cd_tell, cd_thead, cd_lock, cd_tflash;   // turret
extern u8 cd_shot[2];           // entity slots of in-flight turret shots
extern u8 cd_armed, cd_pack[2]; // spawn plate fired; pack entity slots
extern u8 cd_pend;              // side-door flip held while the hero is in it
extern u8 cd_frame, cd_resets, cd_refusals, cd_flips, cd_crushed, cd_shoves;
extern u8 cd_pack_id;           // enemy id for the pack (one already in the room)

u8 cd_prepare(void) BANKED;
void cd_tick(void) BANKED;
void cd_reset(void) BANKED;
void cd_pack_draw(u8 idx) BANKED;
u8 cd_pack_a(u8 idx) BANKED;
void cd_pack_apply(u8 idx) BANKED;
void cd_sprites(void) BANKED;         // fills the shared lk_spr_* OBJ list
void cd_lane_step(void) BANKED;       // conduit_lane.c (bank 16)
// conduit_paint.c (bank 16)
void cd_paint(u8 r) BANKED;     // 0 side door, 1 Star door: world + VRAM
void cd_redress(void) BANKED;
void cd_solve(void) BANKED;
void cd_restore(void) BANKED;
// art (bank 22)
void cd_art_load(void) BANKED;
void cd_bg_art_load(void) BANKED;

#endif
