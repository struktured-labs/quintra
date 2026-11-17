// Stage-transition vignettes (spec 2026-11-16 §2): a framed 3 s picture with
// the place name, motto, the champion walking in, and one cheap effect.
// The screen loads its art under black palettes (no LCD-off), plays once per
// run per vignette, and returns through the room resume path like PACK.
#ifndef QUINTRA_GAME_VIGNETTE_H
#define QUINTRA_GAME_VIGNETTE_H

#include <gb/gb.h>
#include "core/types.h"
#include "game/screen.h"

// Per-run seen bits, one per vignette id. Cleared by run_state_init.

void vignette_enter(void);
screen_id_t vignette_tick(u8 keys, u8 pressed);

// Arrival policy for the door and portal seams. Returns the next screen:
// a vignette the first time a dungeon or the Riftwild is entered, else the
// existing stage card (dungeon from Riftwild) or SCREEN_SELF.
screen_id_t vignette_arrival(u8 from_world, u8 stage) BANKED;
// After a Worldglass shift: the first Hollow entry of a run gets its vignette.
screen_id_t vignette_after_shift(void) BANKED;

// CUTSCENES ONCE / OFF lives in the lifetime SRAM flags (survives runs).
u8 vignette_cutscenes_off(void) BANKED;
void vignette_toggle_cutscenes(void) BANKED;

#endif
