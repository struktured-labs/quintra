#ifndef QUINTRA_GAME_COMPANION_H
#define QUINTRA_GAME_COMPANION_H

#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"

// A run receives one seed-selected Road Echo per dungeon. Their silhouettes
// are shared, while palette, firing rhythm, and ASK aid give each a role.
#define COMPANION_HEARTH 0
#define COMPANION_AETHER 1
#define COMPANION_WAY    2
#define COMPANION_COUNT  3

void companion_spawn_current(void) BANKED;
void companion_update(entity_t *e, u8 idx) BANKED;

// SELECT opens the Compass; A there invokes the active Echo's ASK aid.
// The public kind accessor lets that prompt carry the aid's semantic colour.
u8 companion_active_kind(void) BANKED;
u8 companion_ask_ready(void) BANKED;
u8 companion_ask(void) BANKED;

#endif
