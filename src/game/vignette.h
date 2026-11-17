// Stage-transition vignettes (spec 2026-11-16 §2): a framed 3 s picture with
// the place name, motto, the champion walking in, and one cheap effect.
// The screen loads its art under black palettes (no LCD-off), plays once per
// run per vignette, and returns through the room resume path like PACK.
#ifndef QUINTRA_GAME_VIGNETTE_H
#define QUINTRA_GAME_VIGNETTE_H

#include <gb/gb.h>
#include "core/types.h"
#include "game/screen.h"

// Per-run seen bits live in run_state.vignette_seen (saved with the run).

void vignette_enter(void);
screen_id_t vignette_tick(u8 keys, u8 pressed);

// Arrival policy for the door, portal, and new-run foyer seams.
// from_world is 1 when the previous place was the Riftwild. Town-to-dungeon
// sets vig_from_town before the room counter changes. Returns SCREEN_VIGNETTE
// the first time, else the existing stage card (Riftwild-to-dungeon only)
// or SCREEN_SELF.
screen_id_t vignette_arrival(u8 from_world, u8 stage) BANKED;
extern u8 vig_from_town;
// After a Worldglass shift: the first Hollow entry of a run gets its vignette.
screen_id_t vignette_after_shift(void) BANKED;
// New-run foyer: consume the queued start flag and try the stage vignette.
// Does not fall back to the stage card (the foyer already has its dim fade).
screen_id_t vignette_on_run_start(u8 stage) BANKED;

// Set by room_enter on a fresh-run foyer. Tests clear it through
// mute_vignettes() (symbol _room_start_vignette) so other contracts keep
// their post-class-select timing.
extern u8 room_start_vignette;

// CUTSCENES ONCE / OFF lives in the lifetime SRAM flags (survives runs).
u8 vignette_cutscenes_off(void) BANKED;
void vignette_toggle_cutscenes(void) BANKED;

#endif
