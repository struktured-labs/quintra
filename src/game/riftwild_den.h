// Riftwild hidden dens: optional three-per-region secrets beside the
// Warden -> Gate spine. See docs/superpowers/specs/2026-11-15-riftwild-hidden-dungeons.md.
#ifndef QUINTRA_GAME_RIFTWILD_DEN_H
#define QUINTRA_GAME_RIFTWILD_DEN_H

#include <gb/gb.h>
#include "core/types.h"

#define RIFT_DEN_COUNT 3
// Den kinds name the entrance verb.
#define RIFT_DEN_CAIRN   0   // sealed standing stone: Bombs, Morningstar, Rift Bomb, Glove/Sauran
#define RIFT_DEN_DROWNED 1   // pond island stair: Tide Raft / Picsean
#define RIFT_DEN_SCAR    2   // sinkhole-ringed island: Rift Hook / Corvin
// The tell sits in each den field's south-east sector, clear of the trail
// cross, the Waygear pockets (north), and every six-tile edge mouth.
#define RIFT_DEN_TELL_X 24
#define RIFT_DEN_TELL_Y 22

// Nonzero while the current field or den needs the per-frame den tick.
extern u8 riftwild_den_armed;

// Field currently represented on the Compass: the parent field inside a den.
u8 riftwild_field_screen(void) BANKED;
// Nonzero when the current Riftwild field hosts a den (its south-east
// clearing and approach are carved after the set-piece pass).
u8 riftwild_den_in_field(void) BANKED;
// Field terrain post-pass. Call after climate painting, before population.
void riftwild_den_stamp_field(void) BANKED;
// Complete den-room transaction (tiles, entities, player) for world_screen >= 36.
void riftwild_den_build_room(void) BANKED;
// Stair/portal under the feet at wide tile (tx, ty). Returns 1 after it has
// moved world_screen into or out of a den; the caller then regenerates.
u8 riftwild_den_portal(u8 tx, u8 ty) BANKED;
// The complete Riftwild portal transaction (den stairs, arches, vault,
// cave stairs). Moves world_screen; the caller regenerates the room.
void riftwild_take_portal(u8 tx, u8 ty) BANKED;
// Heavy impact (Bomb burst, Morningstar, Rift Bomb) on a wild stone tile.
u8 riftwild_den_strike(u8 tx, u8 ty) BANKED;
// Rift Bomb burst centred on the hero's feet tile.
void riftwild_den_burst(u8 tx, u8 ty) BANKED;
// Per-frame: Glove touch on a cairn, den seals, keeper defeat, rewards.
void riftwild_den_tick(void) BANKED;
// Echo Chime rung in a Riftwild field.
void riftwild_den_chime(void) BANKED;
// Compass icon for a Riftwild field node (opened, unclaimed den -> chest).
u8 riftwild_den_map_icon(u8 cell, u8 icon) BANKED;

#endif
