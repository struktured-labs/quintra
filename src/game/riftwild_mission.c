#pragma bank 17

#include <gb/gb.h>

#include "core/types.h"
#include "game/riftwild_mission.h"
#include "game/run_state.h"
#include "render/text.h"
#include "render/tiles.h"

// These two getters used to live in bank-10 regional_riftwild.c, but after
// later main landings (notably morningstar art) that bank sat on the
// 256-byte emergency floor. Keep the screen list in lockstep with
// regional_guard_screen there.
static u8 mission_region_step(void) {
    u8 cleared = run_state.bosses_beaten;
    if (!cleared) return 0;
    cleared--;
    while (cleared >= DUNGEONS_PER_REGION)
        cleared = (u8)(cleared - DUNGEONS_PER_REGION);
    return cleared;
}

u8 run_state_riftwild_guard_screen(void) BANKED {
    static const u8 screens[3] = { 3, 17, 29 };
    return screens[mission_region_step()];
}

u8 run_state_riftwild_guard_down(void) BANKED {
    return run_state_riftwild_gate_active(run_state_riftwild_gate_screen());
}

// Pack goal and Compass pull for the Riftwild. The old Pack line always read
// FIND DUNGEON while the arch was sealed and the real goal was the Warden;
// the Compass never showed where that Warden waited. Both now follow the
// same two-step spine: find and slay the Warden, then cross the gate.

u8 riftwild_mission_target(void) BANKED {
    return run_state_riftwild_guard_down()
        ? run_state_riftwild_gate_screen()
        : run_state_riftwild_guard_screen();
}

u8 riftwild_mission_dir(u8 target) BANKED {
    u8 here = run_state.world_screen;
    u8 r0 = (u8)(here / 6), c0 = (u8)(here % 6);
    u8 r1 = (u8)(target / 6), c1 = (u8)(target % 6);
    u8 dr = r1 > r0 ? (u8)(r1 - r0) : (u8)(r0 - r1);
    u8 dc = c1 > c0 ? (u8)(c1 - c0) : (u8)(c0 - c1);
    u8 ns = 0, ew = 0; // 1 = N/E, 2 = S/W
    if (!dr && !dc) return RIFT_DIR_HERE;
    // A field two rows away and one column over still reads as "north";
    // only a balanced offset earns a diagonal.
    if (dr && (u8)(dc << 1) > dr) ew = c1 > c0 ? 1 : 2;
    if (dc && (u8)(dr << 1) > dc) ns = r1 < r0 ? 1 : 2;
    if (!dc) ns = r1 < r0 ? 1 : 2;
    if (!dr) ew = c1 > c0 ? 1 : 2;
    if (ns == 1) return ew == 1 ? 1 : ew == 2 ? 7 : 0;
    if (ns == 2) return ew == 1 ? 3 : ew == 2 ? 5 : 4;
    return ew == 1 ? 2 : 6;
}

u8 riftwild_warden_known(void) BANKED {
    return ((run_state.world_seen_xxhi & RIFT_WARDEN_NAMED_BIT)
        || run_state_world_cell_seen(run_state_riftwild_guard_screen()))
        ? 1 : 0;
}

void riftwild_name_warden(void) BANKED {
    run_state.world_seen_xxhi |= RIFT_WARDEN_NAMED_BIT;
}

void riftwild_mission_write_goal(void) BANKED {
    static const char *const short_dir[8] = {
        "N", "NE", "E", "SE", "S", "SW", "W", "NW"
    };
    u8 down = run_state_riftwild_guard_down();
    u8 dir = riftwild_mission_dir(riftwild_mission_target());
    if (!down) {
        if (dir == RIFT_DIR_HERE) { text_write("SLAY THE WARDEN"); return; }
        if (!riftwild_warden_known()) { text_write("FIND THE WARDEN"); return; }
        text_write("WARDEN LIES ");
    } else {
        if (dir == RIFT_DIR_HERE) { text_write("ENTER THE GATE"); return; }
        text_write("GATE OPEN ");
    }
    text_write(short_dir[dir]);
}

// The Warden's red mark appears once a wayfarer has named it or the field
// has been entered (the same earned rule as the dungeon map), even across
// fog. Once it falls the woken gate is marked instead, so the Compass
// always shows the next step.
u8 riftwild_compass_goal_icon(u8 cell, u8 icon) BANKED {
    if (icon == BGT_MAP_HERE) return icon;
    if (!run_state_riftwild_guard_down()) {
        if (cell == run_state_riftwild_guard_screen()
            && riftwild_warden_known()) return BGT_MAP_BOSS;
    } else if (cell == run_state_riftwild_gate_screen()) return BGT_PORTAL;
    return icon;
}

static char seek_line[20];

const char *riftwild_seek_line(void) BANKED {
    static const char *const long_dir[8] = {
        "NORTH", "NORTHEAST", "EAST", "SOUTHEAST",
        "SOUTH", "SOUTHWEST", "WEST", "NORTHWEST"
    };
    const char *src;
    char *dst = seek_line;
    u8 dir = riftwild_mission_dir(riftwild_mission_target());
    src = (dir == RIFT_DIR_HERE) ? "IT IS ^3THIS FIELD" : "SEEK ^3";
    while (*src) *dst++ = *src++;
    if (dir != RIFT_DIR_HERE) {
        src = long_dir[dir];
        while (*src) *dst++ = *src++;
    }
    *dst = 0;
    return seek_line;
}
