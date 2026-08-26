#pragma bank 14
// Objective-leg return surprises are chosen only during room generation.
// The live wave/trap state machine remains in its tight director bank.

#include <gb/gb.h>

#include "core/types.h"
#include "game/dungeon_director.h"
#include "game/run_state.h"

static u8 return_echo_phase(void) {
    if (run_state.dungeon_puzzles & RUN_DEEP_GATE_BIT) return 0x40;
    if (run_state.dungeon_phase & RUN_DEEP_PHASE_OPEN_BIT) return 0x20;
    if (run_state.dungeon_phase & RUN_DEEP_WARDEN_BIT) return 0x10;
    if (run_state.dungeon_puzzles & RUN_WAYSTONE_BIT) return 0x08;
    if (run_state.dungeon_puzzles & RUN_WARDEN_BOON_BIT) return 0x04;
    if (run_state.rift_sigils
        & RUN_STAGE_SIGIL_BIT(run_state.bosses_beaten)) return 0x02;
    if (run_state.dungeon_puzzles & RUN_TRIAL_BIT) return 0x01;
    return 0;
}

void dungeon_director_choose_return(u8 eligible, u8 was_seen) BANKED {
    u8 phase;
    u8 variant;
    if (!eligible || !was_seen) return;
    phase = return_echo_phase();
    if (!phase || (run_state.return_echo_flags & phase)) return;
    run_state.return_echo_flags |= phase;
    variant = (u8)(((u8)(run_state.run_seed >> 8)
        + run_state.room_counter + run_state.bosses_beaten + phase) & 3);
    room_return_echo_kind = (u8)(variant + 1);
    if (variant == 0) {
        if (room_roster_kind == ROOM_ROSTER_BROOD)
            room_roster_kind = ROOM_ROSTER_MIXED;
        else if (room_roster_kind == ROOM_ROSTER_MIXED)
            room_roster_kind = ROOM_ROSTER_PAIR;
        else {
            room_roster_kind = ROOM_ROSTER_BROOD;
            if (room_roster_secondary != 0xFF)
                room_roster_primary = room_roster_secondary;
        }
    } else if (variant == 1) {
        room_encounter_kind = ENCOUNTER_WAVE;
    } else if (variant == 2) {
        room_encounter_kind = ENCOUNTER_TRAP;
        room_encounter_timer = 50;
    } else {
        // One glowing leader plus a compact escort reads as a miniboss echo
        // without importing a Colossus into ordinary procedural geometry.
        room_encounter_kind = ENCOUNTER_ELITE;
        room_roster_kind = ROOM_ROSTER_COMMAND;
    }
}
