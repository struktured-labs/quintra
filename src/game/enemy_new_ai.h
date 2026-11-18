#ifndef QUINTRA_GAME_ENEMY_NEW_AI_H
#define QUINTRA_GAME_ENEMY_NEW_AI_H

#include <gb/gb.h>
#include "game/entity.h"
#include "content.h"

// New specialist ticks live in bank 25 (bank 31 is magic.c).
void new_monster_update(entity_t *e, const enemy_def_t *def) BANKED;
void new_monsters_post_spawn(void) BANKED;
void new_monsters_draw(void) BANKED;
void new_monsters_foyer_warp(void) BANKED;
void bane_brute_apply_knockback(i8 kx, i8 ky) BANKED;
void leybeam_clear_beam(void) BANKED;
void leybeam_vblank_flush(void) BANKED;
u8   vault_hand_may_act(void) BANKED;

extern u8 pending_foyer_warp;
extern u8 vault_hand_holding;
extern u8 leybeam_beam_live;
extern u8 leybeam_flush_pending;
extern u8 new_monsters_busy;
extern u8 new_monsters_in_room;

#endif
