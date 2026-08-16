#ifndef QUINTRA_GAME_MISSION_GRAPH_H
#define QUINTRA_GAME_MISSION_GRAPH_H

#include <gb/gb.h>
#include "core/types.h"

// Build the stage's complete objective graph before room terrain or entities.
// Repeated calls are cheap once the appended run-state record is initialized.
void mission_graph_ensure(void) BANKED;
u8 mission_graph_valid(void) BANKED;
u8 mission_graph_cell_is_role(u8 cell) BANKED;

#endif
