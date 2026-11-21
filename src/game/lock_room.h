#ifndef QUINTRA_GAME_LOCK_ROOM_H
#define QUINTRA_GAME_LOCK_ROOM_H

#include <gb/gb.h>
#include "core/types.h"

// M4 of the Ultima-depth spec: the optional Lockmire Ferry pocket in Toxic
// Mire. It teaches matching keys (Heart / Star / Moon: each opens only a
// door with its icon, one of each type held at a time, one Heart key for two
// Heart doors), a flip-conveyor, and the lure, then combines them: the lure
// wakes the Stone Jagger, the conveyor (flipped west) ferries it onto the
// weight plate, the plate holds the gate open, and the Heart key buys one of
// two rooms. Self-contained: WRAM only, rebuilt on entry; Pack RESET ROOM,
// the entrance plate and walking out all restore the entry state.
// See docs/superpowers/specs/2026-11-21-m4-lockmire-ferry-addendum.md.

#define LK_STAGE 4              // bosses_beaten: Toxic Mire
#define LK_X0 18                // world tile of the pocket's top-left wall
#define LK_Y0 11
#define LK_W 12
#define LK_H 18
#define LK_ENTRY_Y 6            // west-wall entrance rows 6..7

#define LK_RESET_X 1            // 2x2 plates / pedestals (local top-left)
#define LK_RESET_Y 4
#define LK_FLIP_X 7
#define LK_FLIP_Y 9
#define LK_LURE_X 8             // lure pedestal
#define LK_LURE_Y 5
#define LK_JX 9                 // Jagger rest (fenced: it can only go west)
#define LK_JY 11
#define LK_WX 1                 // weight plate (lane's west end)
#define LK_WY 11
#define LK_GOAL_X 9             // two BGT_SWITCH tiles in the vault
#define LK_GOAL_Y 16
#define LK_COIN_X 9             // Moon nook reward spot
#define LK_COIN_Y 1

// Key types (bits of lk_held / lk_ped).
#define LK_HEART 1
#define LK_STAR  2
#define LK_MOON  4

// Borrowed ids (Riftwild-only art in dungeons; reloaded every room entry).
#define LK_T_CONV_E  105        // BGT_WILD_MUD  (walkable)
#define LK_T_CONV_W  106        // BGT_WILD_SAND (walkable)
#define LK_T_WPLATE  107        // BGT_WILD_SNOW (walkable)
#define LK_T_WPRESS  96         // BGT_WILD_FLOWER (walkable)
#define LK_T_DOOR    37         // BGT_ROOF (solid)
#define LK_T_BARS    99         // BGT_WILD_STUMP (solid), M3's cage bars

#define LK_REGIONS 7            // lane, gate, star, moon, heart W, heart E, W

#define LK_J_IDLE    0
#define LK_J_SEEK    1
#define LK_J_SETTLED 2

extern u8 lk_live;
extern u8 lk_held, lk_ped, lk_open;     // keys held / on pedestals; doors open
extern u8 lk_dir, lk_gate, lk_wpress;   // lane west?; gate open; W pressed
extern u8 lk_lure, lk_lx, lk_ly;        // 0 pedestal, 1 held, 2 down (+ px)
extern u8 lk_jx, lk_jy, lk_jst;
extern u8 lk_cool, lk_frame;
extern u8 lk_resets, lk_refusals, lk_coins, lk_blink, lk_offcam_sfx, lk_drops;

u8 lk_prepare(void) BANKED;
void lk_tick(void) BANKED;
void lk_reset(void) BANKED;
void lk_pack_draw(u8 idx) BANKED;
u8 lk_pack_a(u8 idx) BANKED;
void lk_pack_apply(u8 idx) BANKED;
#define LK_SPR_MAX 26
extern u8 lk_spr_n;
extern u8 lk_spr_x[LK_SPR_MAX], lk_spr_y[LK_SPR_MAX], lk_spr_t[LK_SPR_MAX], lk_spr_p[LK_SPR_MAX];
void lk_sprites(void) BANKED;

#endif
