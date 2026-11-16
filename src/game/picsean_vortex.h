#ifndef QUINTRA_GAME_PICSEAN_VORTEX_H
#define QUINTRA_GAME_PICSEAN_VORTEX_H

#include <gb/gb.h>
#include "core/types.h"

// Picsean's full-Will Moon Tide becomes the Tide Vortex: four spiral arms
// spin out from the cast point and grow until the front sweeps the whole view.
// Spec: docs/superpowers/specs/2026-11-15-picsean-tide-vortex.md

// Logic ticks. The front grows for VORTEX_GROW_TICKS on a smoothstep and
// then holds at full size while the arms spin out (the crest).
#define PICSEAN_VORTEX_TICKS      84
#define PICSEAN_VORTEX_GROW_TICKS 72
#define PICSEAN_VORTEX_START_R    10
#define PICSEAN_VORTEX_MAX_R      240
// Front and arm damage over the MAX damage; heavy bodies (Colossi, the
// Reaper, elites, alphas, rares, the Hexa sanctum) take at most
// PICSEAN_VORTEX_HEAVY_CAP per hit before LCK/weakness, two hits total.
#define PICSEAN_VORTEX_FRONT_BONUS 4
#define PICSEAN_VORTEX_ARM_BONUS   2
#define PICSEAN_VORTEX_HEAVY_CAP   6

// The arms borrow Wolfkin's free OBJ tiles 200..203. Only one champion is
// ever in a run, and both arts reload their cels on every cast.
#define SPR_FX_VORTEX_DROP  200
#define SPR_FX_VORTEX_CURL  201
#define SPR_FX_VORTEX_CREST 202
#define SPR_FX_VORTEX_EYE   203
// OAM 24..35 carry the arms (12 per frame, two alternating sets of 12 =
// 24 arm points). The entity pass keeps 4..23 and the raft/boss overlay
// keeps 36..39. While the Serpent owns 4..31 the arms shrink to 32..35.
#define PICSEAN_VORTEX_OAM_LO 24
#define PICSEAN_VORTEX_OAM_HI 36
#define PICSEAN_VORTEX_SEGS   12

// Ticks remaining; 0 when idle. Read by combat and room_draw.
extern u8 picsean_vortex_ticks;
// Current front radius in px (debug/test telemetry).
extern u8 picsean_vortex_radius;
// Set by entity_init_room: the next tick ends the vortex in the new room.
extern u8 picsean_vortex_abort;

void picsean_vortex_begin(u8 damage) BANKED;
void picsean_vortex_tick(void) BANKED;
void picsean_vortex_draw(void) BANKED;
// room_draw tail: Serpent, Cinder pack, then the vortex arms.
void room_draw_overlays(void) BANKED;

#endif
