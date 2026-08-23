#include "core/types.h"
#include "game/player.h"
#include "game/room.h"
#include "game/status.h"
#include "content.h"

// These routines only write fields and globals; keeping them as banked leaves
// saves scarce ROM0 without nesting another bank switch under gameplay code.
void player_clear_fields(void) BANKED;
void player_apply_class(u8 class_id) BANKED;

player_state_t player;

void player_clear(void) {
    // Passive clocks are gameplay progress within one run, never hidden
    // carryover from the previous champion/death screen.
    room_reset_passive_timers();
    status_reset_all();
    player_clear_fields();
}

void player_init_from_class(u8 class_id) {
    player_clear();
    if (class_id >= N_CLASSES) return;
    player_apply_class(class_id);
}
