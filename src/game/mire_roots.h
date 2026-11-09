#ifndef QUINTRA_MIRE_ROOTS_H
#define QUINTRA_MIRE_ROOTS_H

#include "game/entity.h"

// 1 while a cast is on the floor (windup through wither).
extern u8 mire_root_active;
// 1 during the 48-tick anchored windup. large_boss_draw pulses the lobes.
extern u8 mire_root_windup;
// 0..95 during a cast. Tests read this; it is not save data.
extern u8 mire_root_u;

// Advance the stage-4 cast. Returns 1 when the player should take hurt(2).
// Called only from boss_phase_tick, after the phase clock has stepped.
u8 mire_roots_service(entity_t *e) BANKED;
// Drop the overlay and the cast. Safe on a fresh room and on boss death.
void mire_roots_clear(void) BANKED;
// Pack-menu return redraws the arena from room_tilemap. Stamp the live cast
// back onto that clean floor.
void mire_roots_redraw(void) BANKED;

#endif
