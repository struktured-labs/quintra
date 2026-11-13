#ifndef QUINTRA_GAME_WOLFKIN_WAVE_H
#define QUINTRA_GAME_WOLFKIN_WAVE_H

#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"

// Wolfkin's full-Will Moonfang Rush throws a wave of force ahead of him.
// Spec: docs/superpowers/specs/2026-11-12-wolfkin-will-wave.md
//
// The rush's body dash lasts nine frames after the frame it fires. The
// frontal guard covers exactly those ten frames (it is decremented before
// combat reads it, hence eleven). No i-frames: sides and back stay open,
// and once the rush ends he is ordinary Wolfkin again.
#define WOLFKIN_WAVE_GUARD_FRAMES 11
#define WOLFKIN_WAVE_FX_FRAMES    14
#define WOLFKIN_WAVE_TTL          12
#define WOLFKIN_WAVE_EAT_REACH    28

// OBJ slots 200..203 are otherwise unused (180..199 hurt poses end at 199,
// waygear begins at 204). Reloaded on every cast so a menu that borrowed
// the shared 0x8800 tile block cannot leave stale art behind.
#define SPR_FX_WAVE_E_A 200
#define SPR_FX_WAVE_E_B 201
#define SPR_FX_WAVE_S_A 202
#define SPR_FX_WAVE_S_B 203

extern u8 wolfkin_wave_guard_ticks;
extern u8 wolfkin_wave_fx_ticks;

// Called by will_fire_max in the Moonfang branch. dir is the dir8 index.
void wolfkin_wave_begin(u8 dir, u8 damage) BANKED;
// Once per combat frame while either counter is live: eats frontal shots,
// animates the crescent, and ends the Will palette flash.
void wolfkin_wave_tick(void) BANKED;
// While the guard is up, a hostile touching Wolfkin from the front is
// absorbed (a shot is destroyed, a body deals nothing). No knockback.
u8 wolfkin_wave_absorb(u8 idx) BANKED;

#endif
