#ifndef QUINTRA_GAME_WILL_MAXFX_H
#define QUINTRA_GAME_WILL_MAXFX_H

#include <gb/gb.h>
#include "core/types.h"

// Max-Will v2: authored full-Will arts for Sauran, Vespine, Corvin and the
// second beat of Wolfkin's Moonfang. Picsean's Tide Vortex is the bar and
// keeps its own controller (picsean_vortex.c).
// Spec: docs/superpowers/specs/2026-11-17-max-will-v2.md
//
// One controller runs at a time (one champion per run). It rides the Tide
// Vortex's dispatch: begin sets picsean_vortex_ticks, so combat's vortex tick,
// room_draw_overlays and entity_init_room's abort reach it with no new hooks
// in the hot combat loop. Damage goes through
// one inert PROJ_AUX_VORTEX carrier and combat_apply_player_shot_hit, so
// weakness, LCK, status, Colossus caps and kill rewards match every other
// weapon. Each body is hit at most once per beat (per-cast hit masks).
// Visuals: CGB palette washes (0 OAM), OBJ tiles 200..203 reloaded per cast,
// FX cels (put 0..3) always land in OAM 32..35, the legacy 4-slot tail.
// Aftershock's T-fault wall reuses those same four slots after the pylons
// hide (t>=48). Hits stay on the carrier / AABB, so dropped cosmetics
// never take a hit with them.
#define WILL_MAXFX_OAM_LO 32
#define WILL_MAXFX_OAM_N  4
#define WILL_MAXFX_TILE   200

// Lifetimes in combat ticks.
#define WILL_MAXFX_SAURAN_TICKS  64
#define WILL_MAXFX_VESPINE_TICKS 54
#define WILL_MAXFX_CORVIN_TICKS  48
#define WILL_MAXFX_WOLFKIN_TICKS 42

// Every starter MAX shares the Tide Vortex's 360-frame recast lock
// (picsean_vortex_slow_charge / picsean_vortex_ready_at).
#define WILL_MAXFX_HEAVY_CAP 6

// Nonzero while an art runs: 1 + class id.
extern u8 will_maxfx_live;
// Ticks elapsed since the cast (test telemetry).
extern u8 will_maxfx_t;

// Nonzero when the shared MAX recast lock still holds.
u8 will_maxfx_locked(void) BANKED;
// Arm the shared 360-frame lock (Picsean's begin arms it itself).
void will_maxfx_arm_lock(void) BANKED;
// Start the class's art. dir is the dir8 index, damage the MAX damage
// (tier already added). Returns nonzero if it committed (carrier allocated).
u8 will_maxfx_begin(u8 class_id, u8 dir, u8 damage) BANKED;
// Called from picsean_vortex_tick/draw while will_maxfx_live is set.
void will_maxfx_tick(void) BANKED;
void will_maxfx_draw(void) BANKED;
// Picsean's crest: surf crash then a three-note bubbling run (step 0..6).
void will_maxfx_surf(u8 step) BANKED;

#endif
