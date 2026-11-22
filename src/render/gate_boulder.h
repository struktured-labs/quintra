#ifndef QUINTRA_RENDER_GATE_BOULDER_H
#define QUINTRA_RENDER_GATE_BOULDER_H

#include <gb/gb.h>
#include "core/types.h"

extern const u8 bgt_gate_boulder_open[16];
extern u8 gate_boulder_attr;

void tiles_apply_passable_boulder(void) BANKED;
void gate_boulder_refresh_attrs(void) BANKED;
void gate_boulder_room_reset(void) BANKED;
void gate_boulder_tick(void) BANKED;

#endif
