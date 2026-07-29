#pragma bank 7
// Lifetime trophies live in SRAM bank 1. They are only read on title/results
// screens, so keeping this cold path in switchable ROM preserves scarce
// always-mapped bank-0 space for frame-critical runtime code.

#include <gb/gb.h>

#include "core/types.h"
#include "game/sram.h"

#define SRAM_BASE     ((volatile u8 *)0xA000)
#define META_VERSION  2
#define META_NO_TIME  0xFFFF

// Layout v2: 'Q' 'M' ver | best u16 | runs u16 | wins u16 |
//            best_win_time u16 (seconds; 0xFFFF = no win yet) | checksum.
// A version bump invalidates old meta (acceptable pre-1.0).
static void meta_open(void)  { ENABLE_RAM_MBC5; SWITCH_RAM_MBC5(1); }
static void meta_close(void) { DISABLE_RAM_MBC5; }

static u8 meta_sum(void) {
    u8 s = 0, i;
    for (i = 3; i < 11; ++i) s = (u8)(s + SRAM_BASE[i]);
    return s;
}

static u8 meta_valid(void) {
    return (SRAM_BASE[0] == 'Q' && SRAM_BASE[1] == 'M'
        && SRAM_BASE[2] == META_VERSION
        && SRAM_BASE[11] == meta_sum()) ? 1 : 0;
}

static void meta_reset(void) {
    u8 i;
    SRAM_BASE[0] = 'Q'; SRAM_BASE[1] = 'M'; SRAM_BASE[2] = META_VERSION;
    for (i = 3; i < 9; ++i) SRAM_BASE[i] = 0;
    SRAM_BASE[9] = 0xFF; SRAM_BASE[10] = 0xFF;
    SRAM_BASE[11] = meta_sum();
}

static u16 meta_get16(u8 off) {
    return (u16)(SRAM_BASE[off] | ((u16)SRAM_BASE[off + 1] << 8));
}

static void meta_put16(u8 off, u16 v) {
    SRAM_BASE[off]     = (u8)(v & 0xFF);
    SRAM_BASE[off + 1] = (u8)(v >> 8);
}

u16 sram_meta_best(void) BANKED {
    u16 v;
    meta_open();
    v = meta_valid() ? meta_get16(3) : 0;
    meta_close();
    return v;
}

u16 sram_meta_runs(void) BANKED {
    u16 v;
    meta_open();
    v = meta_valid() ? meta_get16(5) : 0;
    meta_close();
    return v;
}

u16 sram_meta_wins(void) BANKED {
    u16 v;
    meta_open();
    v = meta_valid() ? meta_get16(7) : 0;
    meta_close();
    return v;
}

u16 sram_meta_best_time(void) BANKED {
    u16 v;
    meta_open();
    v = meta_valid() ? meta_get16(9) : META_NO_TIME;
    meta_close();
    return v;
}

u8 sram_meta_record(u16 score, u8 won, u16 time_s) BANKED {
    u8 flags = 0;
    u16 count;
    meta_open();
    if (!meta_valid()) meta_reset();
    if (score > meta_get16(3)) { meta_put16(3, score); flags |= 1; }
    count = meta_get16(5);
    if (count != 0xFFFF) meta_put16(5, (u16)(count + 1));
    if (won) {
        count = meta_get16(7);
        if (count != 0xFFFF) meta_put16(7, (u16)(count + 1));
        if (time_s < meta_get16(9)) { meta_put16(9, time_s); flags |= 2; }
    }
    SRAM_BASE[11] = meta_sum();
    meta_close();
    return flags;
}
