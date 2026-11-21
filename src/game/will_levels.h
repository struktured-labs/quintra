#ifndef QUINTRA_GAME_WILL_LEVELS_H
#define QUINTRA_GAME_WILL_LEVELS_H

#include <gb/gb.h>
#include "core/types.h"

// Max-Will art cap (1..4) and intra-tier XP. Spec:
// docs/superpowers/specs/2026-11-21-max-will-levels.md
// will_level remains banked pips; this cap is mastery.

#define MAXWILL_MIN 1
#define MAXWILL_MAX 4

// First-pip spend thresholds (gentler 1 / 1.5 / 2 / 2.5). L4 = 40,
// today's clock. Recast frames 180 / 240 / 300 / 360.
u8  will_levels_clamp(u8 level) BANKED;
u8  will_levels_art(void) BANKED;          // 1..4, the art you fire
u8  will_levels_clock(void) BANKED;        // 1..4, charge/lock index
u8  will_levels_charge_spend(void) BANKED; // 16 / 24 / 32 / 40
u16 will_levels_recast_frames(void) BANKED;

void will_levels_init_run(void) BANKED;    // new run: L1 / 0 XP
void will_levels_on_load(void) BANKED;     // Continue clamp
// kind: 0 ordinary, 1 elite/alpha/rare, 2 colossus/large boss/hexa
void will_levels_on_kill(u8 kind) BANKED;
void will_levels_on_max_cast(void) BANKED; // +2 if the fired art is the cap

void will_levels_hud_pips(void) BANKED;
// Fill Tide Vortex caps for the current art level. rmax is
// in/out (already the corner distance). L4 leaves bonuses
// and wash as the shipped art (mul 0).
void will_levels_vortex_setup(u8 *rmax, u8 *life, u8 *grow,
    u8 *mul, u8 *heavy) BANKED;

#endif
