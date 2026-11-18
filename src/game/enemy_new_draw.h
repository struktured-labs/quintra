#ifndef QUINTRA_GAME_ENEMY_NEW_DRAW_H
#define QUINTRA_GAME_ENEMY_NEW_DRAW_H
#include <gb/gb.h>
#include "core/types.h"

/* Bomb state owned by enemy_new_ai.c (bank 25), drawn by enemy_new_draw.c. */
#define FUSE_BOMB_MAX 2
#define FUSE_RADIUS 18   /* Chebyshev reach, blast centre to hero centre: fireball r16 + half hurtbox */
#define BLAST_PAL    4   /* heart red: orange-red body, dark rim, yellow core */
extern u8  fb_live[FUSE_BOMB_MAX];
extern u8  fb_phase[FUSE_BOMB_MAX];
extern u8  fb_timer[FUSE_BOMB_MAX];
extern i16 fb_x[FUSE_BOMB_MAX], fb_y[FUSE_BOMB_MAX];
extern u8  nm_xo_hi;

BANKREF_EXTERN(nm_extras_draw)
void nm_extras_draw(void) BANKED;
void nm_extras_park(void) BANKED;

#endif
