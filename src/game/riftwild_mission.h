#ifndef QUINTRA_GAME_RIFTWILD_MISSION_H
#define QUINTRA_GAME_RIFTWILD_MISSION_H
#include "core/types.h"

// Riftwild expedition pull: the Warden first, then the woken gate.
// world_seen_xxhi bit 7 records that a wayfarer named this region's Warden
// (bits 0..3 are cells 32..35, bits 4..6 belong to the hidden dens). It is
// cleared with the rest of the regional chart on a region change.
#define RIFT_WARDEN_NAMED_BIT 0x80
#define RIFT_DIR_HERE 8

u8   riftwild_mission_target(void) BANKED;   // Warden field, then gate field
u8   riftwild_mission_dir(u8 target) BANKED;  // 0=N..7=NW, RIFT_DIR_HERE
u8   riftwild_warden_known(void) BANKED;
void riftwild_name_warden(void) BANKED;
void riftwild_mission_write_goal(void) BANKED;
u8   riftwild_compass_goal_icon(u8 cell, u8 icon) BANKED;
// "SEEK ^3NORTHEAST" for the current target, in a WRAM buffer so the
// dialog bank can read it with its own bank mapped.
const char *riftwild_seek_line(void) BANKED;

#endif
