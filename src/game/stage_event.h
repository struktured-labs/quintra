#ifndef QUINTRA_GAME_STAGE_EVENT_H
#define QUINTRA_GAME_STAGE_EVENT_H

#include <gb/gb.h>
#include "core/types.h"

#define STAGE_EVENT_NONE     0
#define STAGE_EVENT_ROOTS    1
#define STAGE_EVENT_FURNACE  2
#define STAGE_EVENT_ARROW_TRAPS 3
#define STAGE_EVENT_FADING_FLOOR 4

// Visible runtime state doubles as an emulator/playtest contract. The event
// is procgen-first: its presence and exact room are seed/local-cell stable.
extern u8 room_stage_event_kind;
extern u8 room_stage_event_phase;
extern u8 room_stage_event_remaining;

void stage_event_prepare_room(void) BANKED;
void stage_event_tick(void) BANKED;
void stage_event_on_crystal_break(u8 tx, u8 ty) BANKED;
// Cold animated hazards live in the roomy content bank; the public room
// event dispatcher remains the single caller from the combat loop.
void stage_event_prepare_arrows(void) BANKED;
void stage_event_prepare_fading(void) BANKED;
void stage_event_tick_hazard(void) BANKED;

#endif
