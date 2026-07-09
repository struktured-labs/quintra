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
#include "game/run_state.h"
#include "game/sram.h"

#define SRAM_BASE     ((volatile u8 *)0xA000)
#define SAVE_VERSION  1
#define HDR_SIZE      5   // 'Q' 'S' version len_rs len_pl

static void sram_open(void)  { ENABLE_RAM_MBC5; SWITCH_RAM_MBC5(0); }
static void sram_close(void) { DISABLE_RAM_MBC5; }

u8 sram_run_valid(void) {
    u8 ok = 0;
    sram_open();
    if (SRAM_BASE[0] == 'Q' && SRAM_BASE[1] == 'S'
        && SRAM_BASE[2] == SAVE_VERSION
        && SRAM_BASE[3] == (u8)sizeof(run_state_t)
        && SRAM_BASE[4] == (u8)sizeof(player_state_t)) {
        u8 n = (u8)(sizeof(run_state_t) + sizeof(player_state_t));
        u8 sum = 0, i;
        for (i = 0; i < n; ++i) sum = (u8)(sum + SRAM_BASE[HDR_SIZE + i]);
        ok = (sum == SRAM_BASE[HDR_SIZE + n]) ? 1 : 0;
    }
    sram_close();
    return ok;
}

void sram_save_run(void) {
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

u8 sram_load_run(void) {
    u8 *rs = (u8 *)&run_state;
    u8 *pl = (u8 *)&player;
    u8 i;
    u16 off = HDR_SIZE;
    if (!sram_run_valid()) return 0;
    sram_open();
    for (i = 0; i < (u8)sizeof(run_state_t); ++i, ++off) rs[i] = SRAM_BASE[off];
    for (i = 0; i < (u8)sizeof(player_state_t); ++i, ++off) pl[i] = SRAM_BASE[off];
    sram_close();
    // A mid-fight suspend must not resume inside a half-resolved boss kill
    run_state.pending_unseal = 0;
    run_state.victory = 0;
    return 1;
}

void sram_clear_run(void) {
    sram_open();
    SRAM_BASE[0] = 0x00;   // kill the magic — everything else is inert
    sram_close();
}

// ---- Meta-progress: SRAM bank 1 (per the engine design's bank plan).
// Layout: 'Q' 'M' version | best u16 | runs u16 | wins u16 | checksum.

#define META_VERSION 1

static void meta_open(void)  { ENABLE_RAM_MBC5; SWITCH_RAM_MBC5(1); }

static u8 meta_sum(void) {
    u8 s = 0, i;
    for (i = 3; i < 9; ++i) s = (u8)(s + SRAM_BASE[i]);
    return s;
}

static u8 meta_valid(void) {
    return (SRAM_BASE[0] == 'Q' && SRAM_BASE[1] == 'M'
        && SRAM_BASE[2] == META_VERSION
        && SRAM_BASE[9] == meta_sum()) ? 1 : 0;
}

static void meta_reset(void) {
    u8 i;
    SRAM_BASE[0] = 'Q'; SRAM_BASE[1] = 'M'; SRAM_BASE[2] = META_VERSION;
    for (i = 3; i < 9; ++i) SRAM_BASE[i] = 0;
    SRAM_BASE[9] = meta_sum();
}

static u16 meta_get16(u8 off) {
    return (u16)(SRAM_BASE[off] | ((u16)SRAM_BASE[off + 1] << 8));
}

static void meta_put16(u8 off, u16 v) {
    SRAM_BASE[off]     = (u8)(v & 0xFF);
    SRAM_BASE[off + 1] = (u8)(v >> 8);
}

u16 sram_meta_best(void) {
    u16 v;
    meta_open();
    v = meta_valid() ? meta_get16(3) : 0;
    sram_close();
    return v;
}

u16 sram_meta_runs(void) {
    u16 v;
    meta_open();
    v = meta_valid() ? meta_get16(5) : 0;
    sram_close();
    return v;
}

u16 sram_meta_wins(void) {
    u16 v;
    meta_open();
    v = meta_valid() ? meta_get16(7) : 0;
    sram_close();
    return v;
}

u8 sram_meta_record(u16 score, u8 won) {
    u8 is_best = 0;
    meta_open();
    if (!meta_valid()) meta_reset();
    if (score > meta_get16(3)) { meta_put16(3, score); is_best = 1; }
    meta_put16(5, (u16)(meta_get16(5) + 1));
    if (won) meta_put16(7, (u16)(meta_get16(7) + 1));
    SRAM_BASE[9] = meta_sum();
    sram_close();
    return is_best;
}
