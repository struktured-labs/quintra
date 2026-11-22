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
#define CD_DOOR_X 6             // Star door (2x1) to the vault
#define CD_DOOR_Y 12
#define CD_GOAL_X 1             // two BGT_SWITCH goal tiles (alcove behind Heart door B)
#define CD_GOAL_Y 14

#define CD_T_TRACK 105          // borrowed walkable id: stone groove
#define CD_T_DOOR  37           // borrowed solid id: Star door (M4 art)
#define CD_T_BARS  99           // borrowed solid id: side door bars (M3)

// ---- M5b vault: rewrite switches, Kite chain, Heart two-door choice ----
#define CD_SWA_X 1              // rewrite switch A (1x1, hall row 9, west dead end): flips A and B
#define CD_SWB_X 10             // rewrite switch B (east dead end): flips B only
#define CD_SW_ROW 9
#define CD_HDB_X 3              // Heart door B (1x2) -> goal alcove (1..2,13..14)
#define CD_HDA_X 8              // Heart door A (1x2) -> treasure closet (9..10,13..14)
#define CD_HD_Y 13
#define CD_LOCK_X 4             // crystal lock (2x2) holding the Heart key
#define CD_LOCK_Y 13
#define CD_REL_X 6              // Kite release plate (2x1) under the Star door
#define CD_REL_Y 14
#define CD_STREAM_Y 15          // rift-stream rows 15..16 (Kite only)
#define CD_RA_X 7               // cairn region A (2x2)
#define CD_RB_X 5               // cairn region B (2x2)
#define CD_KITE_HOME 9          // Kite kennel cols 9..10; it flies west
#define CD_KITE_STOP 4          // ... to cols 4..5, under the lock
#define CD_COIN_X 9
#define CD_COIN_Y 13
#define CD_T_CAIRN_TL 98        // M2/M3 cairn ids and art (solid)
#define CD_T_CAIRN_TR 109
#define CD_T_CAIRN_BL 110
#define CD_T_CAIRN_BR 39
#define CD_T_STREAM 108         // M3 rift-stream (solid to the hero)
#define CD_T_LOCK 38            // M3 crystal lock plug (solid)
#define CD_T_GLYPH_ROCK 35      // two-state switch glyphs (walkable)
#define CD_T_GLYPH_STREAM 36
#define CD_K_HOME 0             // Kite states
#define CD_K_FLY 1
#define CD_K_BREATH 2
#define CD_K_DONE 3

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
// cd_held: bit 0 Star key, bit 1 Heart key (one of each at a time)
extern u8 cd_ra, cd_rb;         // regions A/B: 1 = rift-stream, 0 = cairn
extern u8 cd_kx, cd_kst, cd_kt; // Kite x (world px), state, timer
extern u8 cd_lockup;            // crystal lock intact (Heart key inside)
extern u8 cd_hkey;              // Heart key: 1 in the lock, 0 taken
extern u8 cd_hdoor;             // Heart doors open: bit 0 A (closet), bit 1 B (goal)
extern u8 cd_coin_given, cd_rewrites;

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
// M5b: conduit_vault.c (bank 6), conduit_vdoor.c (10), conduit_vpaint.c (31), conduit_vstate.c + conduit_vart.c (29)
void cd_vault_tick(void) BANKED;
void cd_vault_prepare(void) BANKED;
void cd_vault_restore(void) BANKED;
void cd_vault_redress(void) BANKED;
void cd_vpaint(u8 r) BANKED;    // 0 region A, 1 region B, 2 lock, 3 door A, 4 door B
void cd_vblk(u8 lx, u8 ly, u8 w, u8 h) BANKED;   // cd_vt/cd_va -> world (+VRAM if live)
void cd_vfill(u8 t, u8 a) BANKED;
void cd_vault_doors(void) BANKED;   // conduit_vdoor.c (bank 10)
extern u8 cd_vt[4], cd_va[4];
void cd_vart_load(void) BANKED;
// art (bank 22)
void cd_art_load(void) BANKED;
void cd_bg_art_load(void) BANKED;

#endif
