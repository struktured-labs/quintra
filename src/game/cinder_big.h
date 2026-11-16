#ifndef QUINTRA_GAME_CINDER_BIG_H
#define QUINTRA_GAME_CINDER_BIG_H

#include <gb/gb.h>
#include "core/types.h"

/* Bigger Ember boss (bank 18). Cinder Rex is a 48x32 (6x4) body drawn from
   VRAM bank-1 OBJ 64..111, and its fire pools are painted into the
   background (bank-1 BG 64..71) so they cost no OAM at any size. */
#define CINDER_REX_W 48
#define CINDER_REX_H 32
#define CINDER_REX_OAM 24
#define CINDER_REX_OAM_BASE 16   /* Rex owns OAM 16..39 */
#define CINDER_FIRE_TILE 64
#define CINDER_FIRE_TILES 8

/* OAM window of the generic entity pass while the Ember boss is active:
   [cinder_oam_end, cinder_oam_limit). Pack: 4 + 4 per Kilnback .. 40.
   Rex: 4 .. 16, because Rex itself owns 16..39. */
extern u8 cinder_oam_end;
extern u8 cinder_oam_limit;
/* Live fire pools, exported for headless tests: tile-space origin, size in
   tiles (2 or 3), remaining warning frames and lifetime. */
extern u8 cinder_fire_tx[8];
extern u8 cinder_fire_ty[8];
extern u8 cinder_fire_size[8];
extern u8 cinder_fire_delay[8];
extern u8 cinder_fire_ttl[8];

void cinder_big_load(void) BANKED;          /* Rex OBJ + fire BG tiles */
void cinder_rex_big_load(void) BANKED;      /* generated: Rex OBJ only */
void cinder_fire_reset(void) BANKED;        /* forget pools, no VRAM */
void cinder_fire_clear_all(void) BANKED;    /* restore floor under pools */
/* x/y are the world-pixel centre. size 2 = 16x16 pool, 3 = 24x24. */
void cinder_fire_add(u8 x, u8 y, u8 delay, u8 ttl, u8 size) BANKED;
/* Ages pools; returns 1 when the champion's feet stand in a lit pool. */
u8 cinder_fire_tick(void) BANKED;
/* Re-stamp every pool after the room renderer redrew the background. */
void cinder_fire_repaint(void) BANKED;
/* 6x4 Rex at screen (sx, sy) top-left. facing 1 = west (atlas), 0 = east.
   pose bit0 = head band roars, bit1 = leg band strides. */
void cinder_rex_big_draw(i16 sx, i16 sy, u8 facing, u8 pose, u8 prop) BANKED;
void cinder_rex_big_park(void) BANKED;      /* hide OAM 16..39 */

#endif
