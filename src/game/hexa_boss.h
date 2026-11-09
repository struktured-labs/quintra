// Hexa Dragmar — hidden colossus after Void Lord.
// New gameplay lives in an autobank. Callers must see BANKED prototypes.
#ifndef QUINTRA_GAME_HEXA_BOSS_H
#define QUINTRA_GAME_HEXA_BOSS_H

#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"

#define HEXA_STAGE 9

#define HEXA_LIMB_IDLE 0
#define HEXA_LIMB_TELEGRAPH 1
#define HEXA_LIMB_ACTIVE 2
#define HEXA_LIMB_RECOVERY 3
#define HEXA_LIMB_BROKEN 4

extern u8 hexa_boss_active;
extern u8 hexa_core_entity;
extern u8 hexa_spotlight_limb;
extern u8 hexa_spotlight_timer;
extern u8 hexa_phase;
extern u8 hexa_limb_state[5];
extern u8 hexa_limb_timer[5];
extern u8 hexa_mark_x;
extern u8 hexa_mark_y;
extern u8 hexa_audio_ch1_claims;
extern u8 hexa_audio_ch2_claims;
extern u8 hexa_audio_ch3_claims;
extern u8 hexa_audio_ch4_claims;

void hexa_sanctum_enter(void) BANKED;
void hexa_boss_clear(void) BANKED;
void hexa_refresh_attrs(void) BANKED;
void hexa_boss_tick(entity_t *e) BANKED;
u8 hexa_boss_draw(u8 oam) BANKED;
u8 hexa_shot_overlap(const entity_t *shot) BANKED;
u8 hexa_filter_damage(u8 dmg) BANKED;
u8 hexa_touches_player(void) BANKED;

#endif
