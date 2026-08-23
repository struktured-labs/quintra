#pragma bank 11

#include <gb/gb.h>

#include "core/types.h"
#include "game/companion.h"
#include "game/run_state.h"

// Discovery is room-transition/cold Compass state, not per-frame following.
// Keep these tiny persisted-state helpers with the spacious specialist bank
// so the companion movement/procgen bank retains its emergency ROM floor.
u8 companion_discovered(void) BANKED {
    return (run_state.companion_cooldown & COMPANION_DISCOVERED_BIT) ? 1 : 0;
}

void companion_discover(void) BANKED {
    if (run_state.companion_cooldown & COMPANION_DISCOVERED_BIT) return;
    run_state.companion_cooldown =
        COMPANION_DISCOVERED_BIT | COMPANION_PENDING_BIT;
}

u8 companion_ask_ready(void) BANKED {
    return (run_state.companion_cooldown & COMPANION_DISCOVERED_BIT)
        && !(run_state.companion_cooldown & COMPANION_COOLDOWN_MASK);
}
