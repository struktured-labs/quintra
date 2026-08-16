#pragma bank 8
// Suspend-save in battery SRAM bank 0 (cart 0x1B = MBC5+RAM+BAT, 32KB).
// Layout: magic "QS" | version | 2 payload lengths | run_state bytes |
// player bytes | 8-bit checksum. RAM is enabled only around accesses —
// leaving it disabled write-protects the battery SRAM between saves.
//
// Home code: touched from title (banked) and room (banked); SRAM at
// 0xA000 is reachable regardless of the current ROM bank.

#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/run_state.h"
#include "game/sram.h"

#define SRAM_BASE     ((volatile u8 *)0xA000)
#define SAVE_VERSION  1
#define HDR_SIZE      5   // 'Q' 'S' version len_rs len_pl
#define LEGACY_RS_SIZE 20 // v0.17.47 and earlier, before visited-map fields
#define PRE_SIGIL_RS_SIZE 23 // v0.17.48-v0.17.51
#define PRE_DIFFICULTY_RS_SIZE 26 // v0.18.42 and earlier: implicit Normal
#define PRE_PUZZLE_RS_SIZE 27 // v0.18.52 and earlier: no dungeon puzzle state
#define PRE_WIDE_MAP_RS_SIZE 29 // v0.18.54 and earlier: six-cell topology
#define PRE_DEEP_MAP_RS_SIZE 31 // v0.18.58: 10..16-cell topology
#define PRE_MAZE_MAP_RS_SIZE 33 // v0.18.60-v0.18.61: 14..20-cell 5x4 topology
#define PRE_WIDE_KILLS_RS_SIZE 35 // v0.18.62-v0.18.91: 8-bit kill total
#define PRE_DUNGEON_LAW_RS_SIZE 36 // before seeded dungeon-wide state
#define PRE_MISSION_RS_SIZE 37 // before generated dungeon mission roles
#define PRE_REGIONAL_RIFT_RS_SIZE 46 // before shared three-dungeon Riftwild
#define PRE_WILL_PL_SIZE 42 // player layout before the appended Will meter
#define PRE_OATH_PL_SIZE 43 // Will-era player layout before Oath selection

void sram_migrate_run(u8 saved_rs) BANKED;

static void sram_open(void)  { ENABLE_RAM_MBC5; SWITCH_RAM_MBC5(0); }
static void sram_close(void) { DISABLE_RAM_MBC5; }

u8 sram_run_valid(void) BANKED {
    u8 ok = 0;
    sram_open();
    if (SRAM_BASE[0] == 'Q' && SRAM_BASE[1] == 'S'
        && SRAM_BASE[2] == SAVE_VERSION
        && (SRAM_BASE[3] == (u8)sizeof(run_state_t)
            || SRAM_BASE[3] == PRE_REGIONAL_RIFT_RS_SIZE
            || SRAM_BASE[3] == PRE_MISSION_RS_SIZE
            || SRAM_BASE[3] == PRE_DUNGEON_LAW_RS_SIZE
            || SRAM_BASE[3] == PRE_WIDE_KILLS_RS_SIZE
            || SRAM_BASE[3] == PRE_MAZE_MAP_RS_SIZE
            || SRAM_BASE[3] == PRE_DEEP_MAP_RS_SIZE
            || SRAM_BASE[3] == PRE_WIDE_MAP_RS_SIZE
            || SRAM_BASE[3] == PRE_PUZZLE_RS_SIZE
            || SRAM_BASE[3] == PRE_DIFFICULTY_RS_SIZE
            || SRAM_BASE[3] == PRE_SIGIL_RS_SIZE
            || SRAM_BASE[3] == LEGACY_RS_SIZE)
        && (SRAM_BASE[4] == (u8)sizeof(player_state_t)
            || SRAM_BASE[4] == PRE_OATH_PL_SIZE
            || SRAM_BASE[4] == PRE_WILL_PL_SIZE)) {
        u8 n = (u8)(SRAM_BASE[3] + SRAM_BASE[4]);
        u8 sum = 0, i;
        for (i = 0; i < n; ++i) sum = (u8)(sum + SRAM_BASE[HDR_SIZE + i]);
        ok = (sum == SRAM_BASE[HDR_SIZE + n]) ? 1 : 0;
    }
    sram_close();
    return ok;
}

void sram_save_run(void) BANKED {
    const u8 *rs = (const u8 *)&run_state;
    const u8 *pl = (const u8 *)&player;
    u8 sum = 0, i;
    u16 off = HDR_SIZE;
    sram_open();
    SRAM_BASE[0] = 'Q';
    SRAM_BASE[1] = 'S';
    SRAM_BASE[2] = SAVE_VERSION;
    SRAM_BASE[3] = (u8)sizeof(run_state_t);
    SRAM_BASE[4] = (u8)sizeof(player_state_t);
    for (i = 0; i < (u8)sizeof(run_state_t); ++i, ++off) {
        SRAM_BASE[off] = rs[i];
        sum = (u8)(sum + rs[i]);
    }
    for (i = 0; i < (u8)sizeof(player_state_t); ++i, ++off) {
        SRAM_BASE[off] = pl[i];
        sum = (u8)(sum + pl[i]);
    }
    SRAM_BASE[off] = sum;
    sram_close();
}

u8 sram_load_run(void) BANKED {
    u8 *rs = (u8 *)&run_state;
    u8 *pl = (u8 *)&player;
    u8 i, saved_rs, saved_pl;
    u16 off = HDR_SIZE;
    if (!sram_run_valid()) return 0;
    sram_open();
    saved_rs = SRAM_BASE[3];
    saved_pl = SRAM_BASE[4];
    for (i = 0; i < (u8)sizeof(run_state_t); ++i) rs[i] = 0;
    for (i = 0; i < saved_rs; ++i, ++off) rs[i] = SRAM_BASE[off];
    // Appended fields make suspend records forward-migratable without
    // shifting any historical player/debug offsets.
    for (i = 0; i < (u8)sizeof(player_state_t); ++i) pl[i] = 0;
    for (i = 0; i < saved_pl; ++i, ++off) pl[i] = SRAM_BASE[off];
    sram_close();
    if (saved_rs == LEGACY_RS_SIZE) {
        run_state.dungeon_seen = 0;
        run_state.world_seen = 0;
        run_state_mark_visited();
    }
    if ((saved_rs == LEGACY_RS_SIZE
            || saved_rs == PRE_SIGIL_RS_SIZE
            || saved_rs == PRE_DIFFICULTY_RS_SIZE
            || saved_rs == PRE_PUZZLE_RS_SIZE
            || saved_rs == PRE_WIDE_MAP_RS_SIZE
            || saved_rs == PRE_MAZE_MAP_RS_SIZE
            || saved_rs == PRE_DEEP_MAP_RS_SIZE)
        && run_state.bosses_beaten < BOSSES_TO_WIN)
        sram_migrate_run(saved_rs);
    // A mid-fight suspend must not resume inside a half-resolved boss kill
    run_state.pending_unseal = 0;
    run_state.victory = 0;
    if (saved_rs == PRE_MISSION_RS_SIZE) {
        // The former fixed room-one Trial occupied puzzle bit one. Preserve
        // its completion while moving the generated Trial to a stable bit.
        if (run_state.dungeon_puzzles & (u8)(1u << 1))
            run_state.dungeon_puzzles |= RUN_TRIAL_BIT;
        run_state.mission_ready = 0;
    }
    run_state_ensure_dungeon_law();
    if (player.active_oath >= BOSSES_TO_WIN
        || player.active_oath >= run_state.bosses_beaten)
        player.active_oath = 0;
    projectile_sync_player_relics();
    return 1;
}

void sram_clear_run(void) BANKED {
    sram_open();
    SRAM_BASE[0] = 0x00;   // kill the magic — everything else is inert
    sram_close();
}
