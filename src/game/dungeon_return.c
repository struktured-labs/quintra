#pragma bank 14
// Objective-leg return surprises are chosen only during room generation.
// The live wave/trap state machine remains in its tight director bank.

#include <gb/gb.h>

#include "core/types.h"
#include "game/dungeon_director.h"
#include "game/run_state.h"
#include "content.h"

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

static void choose_reaper_hunt(void) {
    run_state.return_echo_flags |= RUN_REAPER_HUNT_BIT;
    room_return_echo_kind = 5;
    room_encounter_kind = ENCOUNTER_HUNT;
    room_roster_kind = ROOM_ROSTER_MIXED;
}

void dungeon_director_choose_return(u8 eligible, u8 was_seen) BANKED {
    u8 phase;
    u8 variant;
    if (!eligible || (run_state.dungeon_puzzles & RUN_REAPER_CLEARED_BIT))
        return;
    phase = return_echo_phase();
    // A suspended hunt regenerates in the same visited room. Before it has
    // begun, the first eligible progressed return leg springs it; reaching
    // the deep court remains a guarantee for a route that never doubled back.
    // A named signature encounter should not be hidden behind a 25% miss that
    // can make an entire playthrough appear not to contain it.
    if (run_state.return_echo_flags & RUN_REAPER_HUNT_BIT) {
        if (was_seen) choose_reaper_hunt();
        return;
    }
    if ((was_seen && phase >= 0x02)
        || run_state_dungeon_local() == 15) {
        choose_reaper_hunt();
        return;
    }
    if (!was_seen) return;
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
        static const u8 echo_leader[3] = {
            ENEMY_ORC, ENEMY_BOMBER, ENEMY_WARLOCK
        };
        // A return miniboss must be physically larger than its escort. Cycle
        // the three champion-scale bruiser bodies rather than promoting an
        // arbitrary 8x8 roster creature and hoping a cyan tint sells it.
        room_encounter_kind = ENCOUNTER_ELITE;
        room_roster_kind = ROOM_ROSTER_COMMAND;
        room_roster_secondary = echo_leader[run_state.bosses_beaten % 3];
    }
}

u8 dungeon_director_adjust_initial_count(u8 proposed) BANKED {
    if (room_encounter_kind == ENCOUNTER_HUNT) return 0;
    // A first-visit trap starts with visible sentries; the later pack changes
    // pressure instead of presenting an apparently empty field. A warned
    // return ambush may retain its hush because it is explicitly a revisit.
    if (room_encounter_kind == ENCOUNTER_TRAP) {
        u8 cap;
        if (room_return_echo_kind == 3) return 0;
        cap = RUN_IS_EASY() ? 2 : 3;
        return proposed > cap ? cap : proposed;
    }
    // A changed roster was formerly only a seed-level distinction. Add a
    // compact reinforcement so this return variant is visible in play.
    if (room_return_echo_kind == 1)
        return (u8)(proposed + (RUN_IS_EASY() ? 1 : 2));
    if (room_return_echo_kind == 2) return proposed;
    if (room_encounter_kind == ENCOUNTER_WAVE)
        return (u8)((proposed + 1) >> 1);
    if (room_encounter_kind == ENCOUNTER_HOLD) {
        u8 cap = RUN_IS_EASY() ? 3 : 4;
        return proposed > cap ? cap : proposed;
    }
    return proposed;
}
