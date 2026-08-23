#ifndef QUINTRA_GAME_COMPANION_H
#define QUINTRA_GAME_COMPANION_H

#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"

// A run can discover one seed-selected Road Echo in an optional disguised
// cache. Its identity then remains stable for the rest of that expedition.
#define COMPANION_HEARTH 0
#define COMPANION_AETHER 1
#define COMPANION_WAY    2
#define COMPANION_COUNT  3

// The persisted companion byte reuses its spare high bits so this discovery
// does not shift the suspend ABI. ASK needs only 0..20 in the low six bits;
// PENDING places the newly found Echo inside its cache for one reveal beat.
#define COMPANION_COOLDOWN_MASK  0x3F
#define COMPANION_PENDING_BIT    0x40
#define COMPANION_DISCOVERED_BIT 0x80

void companion_spawn_current(void) BANKED;
void companion_update(entity_t *e, u8 idx) BANKED;
void companion_discover(void) BANKED;
u8 companion_discovered(void) BANKED;

// SELECT opens the Compass; A there invokes the active Echo's ASK aid.
// The public kind accessor lets that prompt carry the aid's semantic colour.
u8 companion_active_kind(void) BANKED;
u8 companion_ask_ready(void) BANKED;
u8 companion_ask(void) BANKED;

#endif
