#pragma bank 10

// Cold battery writes live with other utility transactions so the validator
// and migration reader retain emergency room in the dedicated SRAM bank.

#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/run_state.h"
#include "game/sram.h"

#define SRAM_BASE    ((volatile u8 *)0xA000)
#define SAVE_VERSION 1
#define HDR_SIZE     5
#define LEGACY_RS_SIZE 20
#define PRE_SIGIL_RS_SIZE 23
#define PRE_DIFFICULTY_RS_SIZE 26
#define PRE_PUZZLE_RS_SIZE 27
#define PRE_WIDE_MAP_RS_SIZE 29
#define PRE_DEEP_MAP_RS_SIZE 31
#define PRE_MAZE_MAP_RS_SIZE 33
#define PRE_WIDE_KILLS_RS_SIZE 35
#define PRE_DUNGEON_LAW_RS_SIZE 36
#define PRE_MISSION_RS_SIZE 37
#define PRE_REGIONAL_RIFT_RS_SIZE 46
#define PRE_EXPANDED_RIFT_RS_SIZE 48
#define PRE_COMPANION_RS_SIZE 51
#define PRE_WILL_PL_SIZE 42
#define PRE_OATH_PL_SIZE 43
#define PRE_WAYGEAR_PL_SIZE 44

static void sram_write_open(void) {
    ENABLE_RAM_MBC5;
    SWITCH_RAM_MBC5(0);
}

static void sram_write_close(void) {
    DISABLE_RAM_MBC5;
}

u8 sram_run_valid(void) BANKED {
    u8 ok = 0;
    sram_write_open();
    if (SRAM_BASE[0] == 'Q' && SRAM_BASE[1] == 'S'
        && SRAM_BASE[2] == SAVE_VERSION
        && (SRAM_BASE[3] == (u8)sizeof(run_state_t)
            || SRAM_BASE[3] == PRE_COMPANION_RS_SIZE
            || SRAM_BASE[3] == PRE_EXPANDED_RIFT_RS_SIZE
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
            || SRAM_BASE[4] == PRE_WAYGEAR_PL_SIZE
            || SRAM_BASE[4] == PRE_OATH_PL_SIZE
            || SRAM_BASE[4] == PRE_WILL_PL_SIZE)) {
        u8 n = (u8)(SRAM_BASE[3] + SRAM_BASE[4]);
        u8 sum = 0, i;
        for (i = 0; i < n; ++i) sum = (u8)(sum + SRAM_BASE[HDR_SIZE + i]);
        ok = (sum == SRAM_BASE[HDR_SIZE + n]) ? 1 : 0;
    }
    sram_write_close();
    return ok;
}

void sram_save_run(void) BANKED {
    const u8 *rs = (const u8 *)&run_state;
    const u8 *pl = (const u8 *)&player;
    u8 sum = 0, i;
    u16 off = HDR_SIZE;
    sram_write_open();
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
    sram_write_close();
}

void sram_clear_run(void) BANKED {
    sram_write_open();
    SRAM_BASE[0] = 0x00;
    sram_write_close();
}
