#pragma bank 15
// Lifetime trophies live in SRAM bank 1. They are only read on title/results
// screens, so keeping this cold path in switchable ROM preserves scarce
// always-mapped bank-0 space for frame-critical runtime code.

#include <gb/gb.h>

#include "core/types.h"
#include "game/run_state.h"
#include "game/sram.h"
#include "game/attract.h"

#define SRAM_BASE     ((volatile u8 *)0xA000)
#define META_VERSION  2
#define META_NO_TIME  0xFFFF

// Layout v2, extended in place (version stays 2 so old carts migrate):
// 'Q' 'M' ver | best u16 | runs u16 | wins u16 |
// best_win_time u16 (seconds; 0xFFFF = no win yet) |
// meta_flags | checksum over bytes [0..11].
// Legacy v2 stored sum([3..10]) at [11]. That shape is rewritten on read.
//
// Hero-crown extension (#243), appended so a missing block is not corruption:
// [13] 'C' | [14] ext ver 1 | [15..19] wins[5] |
// [20..21] 2-bit tiers packed | [22] sum([13..21]).
#define META_EXT_MAGIC_OFF 13
#define META_EXT_VER_OFF   14
#define META_EXT_WINS_OFF  15
#define META_EXT_TIER_OFF  20
#define META_EXT_SUM_OFF   22
#define META_EXT_VERSION   1

static void meta_open(void)  {
    /* Pair with sram_write_open: keep VBlank off while cart RAM is unlocked. */
    disable_interrupts();
    ENABLE_RAM_MBC5;
    SWITCH_RAM_MBC5(1);
}
static void meta_close(void) {
    DISABLE_RAM_MBC5;
    enable_interrupts();
}

static u8 meta_sum_range(u8 from, u8 to) {
    u8 s = 0, i;
    for (i = from; i < to; ++i) s = (u8)(s + SRAM_BASE[i]);
    return s;
}

static void meta_seal(void) {
    SRAM_BASE[12] = meta_sum_range(0, 12);
}

static void ext_seal(void) {
    SRAM_BASE[META_EXT_SUM_OFF] = meta_sum_range(META_EXT_MAGIC_OFF,
                                                META_EXT_SUM_OFF);
}

static u8 ext_valid(void) {
    return (SRAM_BASE[META_EXT_MAGIC_OFF] == 'C'
        && SRAM_BASE[META_EXT_VER_OFF] == META_EXT_VERSION
        && SRAM_BASE[META_EXT_SUM_OFF]
            == meta_sum_range(META_EXT_MAGIC_OFF, META_EXT_SUM_OFF)) ? 1 : 0;
}

static void ext_reset(void) {
    u8 i;
    SRAM_BASE[META_EXT_MAGIC_OFF] = 'C';
    SRAM_BASE[META_EXT_VER_OFF] = META_EXT_VERSION;
    for (i = META_EXT_WINS_OFF; i < META_EXT_SUM_OFF; ++i) SRAM_BASE[i] = 0;
    ext_seal();
}

static u8 meta_header(void) {
    return (SRAM_BASE[0] == 'Q' && SRAM_BASE[1] == 'M'
        && SRAM_BASE[2] == META_VERSION) ? 1 : 0;
}

static void meta_migrate_legacy(void) {
    u16 wins = (u16)(SRAM_BASE[7] | ((u16)SRAM_BASE[8] << 8));
    SRAM_BASE[11] = wins ? META_FLAG_VOID_LORD_CLEARED : 0;
    meta_seal();
}

static u8 meta_valid(void) {
    if (!meta_header()) return 0;
    if (SRAM_BASE[12] == meta_sum_range(0, 12)) return 1;
    // Old 12-byte record: checksum of [3..10] lives at [11].
    if (SRAM_BASE[11] == meta_sum_range(3, 11)) {
        if (!attract_demo) meta_migrate_legacy();
        return 1;
    }
    return 0;
}

static void meta_reset(void) {
    u8 i;
    SRAM_BASE[0] = 'Q'; SRAM_BASE[1] = 'M'; SRAM_BASE[2] = META_VERSION;
    for (i = 3; i < 9; ++i) SRAM_BASE[i] = 0;
    SRAM_BASE[9] = 0xFF; SRAM_BASE[10] = 0xFF;
    SRAM_BASE[11] = 0;
    meta_seal();
    ext_reset();
}

static u16 meta_get16(u8 off) {
    return (u16)(SRAM_BASE[off] | ((u16)SRAM_BASE[off + 1] << 8));
}

static void meta_put16(u8 off, u16 v) {
    SRAM_BASE[off]     = (u8)(v & 0xFF);
    SRAM_BASE[off + 1] = (u8)(v >> 8);
}

static void ext_ensure(void) {
    if (!ext_valid()) ext_reset();
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
    if (attract_demo) return 0;   // demo runs record nothing
    meta_open();
    if (!meta_valid()) meta_reset();
    if (score > meta_get16(3)) { meta_put16(3, score); flags |= 1; }
    count = meta_get16(5);
    if (count != 0xFFFF) meta_put16(5, (u16)(count + 1));
    if (won) {
        count = meta_get16(7);
        if (count != 0xFFFF) meta_put16(7, (u16)(count + 1));
        if (time_s < meta_get16(9)) { meta_put16(9, time_s); flags |= 2; }
        SRAM_BASE[11] |= META_FLAG_VOID_LORD_CLEARED;
    }
    meta_seal();
    meta_close();
    return flags;
}

u8 sram_meta_flags(void) BANKED {
    u8 v;
    meta_open();
    v = meta_valid() ? SRAM_BASE[11] : 0;
    meta_close();
    return v;
}

u8 sram_meta_note_hexa(u16 score) BANKED {
    u8 flags = 0;
    if (attract_demo) return 0;
    meta_open();
    if (!meta_valid()) meta_reset();
    if (score > meta_get16(3)) { meta_put16(3, score); flags |= 1; }
    SRAM_BASE[11] |= META_FLAG_HEXA_BEATEN;
    meta_seal();
    meta_close();
    return flags;
}

void sram_meta_set_flag(u8 bit, u8 on) BANKED {
    if (attract_demo) return;
    meta_open();
    if (!meta_valid()) meta_reset();
    if (on) SRAM_BASE[11] |= bit;
    else SRAM_BASE[11] &= (u8)~bit;
    meta_seal();
    meta_close();
}

u8 sram_meta_hero_wins(u8 class_id) BANKED {
    u8 v = 0;
    if (class_id >= HERO_TROPHY_SLOTS) return 0;
    meta_open();
    if (meta_valid() && ext_valid())
        v = SRAM_BASE[META_EXT_WINS_OFF + class_id];
    meta_close();
    return v;
}

u8 sram_meta_hero_tier(u8 class_id) BANKED {
    u8 v = 0;
    if (class_id >= HERO_TROPHY_SLOTS) return 0;
    meta_open();
    if (meta_valid() && ext_valid())
        v = (u8)((meta_get16(META_EXT_TIER_OFF) >> (class_id * 2)) & 3);
    meta_close();
    return v;
}

void sram_meta_hero_trophies(u8 *wins, u8 *tiers) BANKED {
    u8 i, ok;
    u16 bits = 0;
    meta_open();
    ok = (u8)(meta_valid() && ext_valid());
    if (ok) bits = meta_get16(META_EXT_TIER_OFF);
    for (i = 0; i < HERO_TROPHY_SLOTS; ++i) {
        wins[i] = ok ? SRAM_BASE[META_EXT_WINS_OFF + i] : 0;
        tiers[i] = ok ? (u8)((bits >> (i * 2)) & 3) : 0;
    }
    meta_close();
}

void sram_meta_record_hero_win(u8 class_id, u8 difficulty) BANKED {
    u8 tier, cur, shift;
    u16 bits;
    if (attract_demo) return;
    if (class_id >= HERO_TROPHY_SLOTS) return;
    // Easy stays simple; Normal and any future harder mode are majestic.
    tier = (difficulty == DIFFICULTY_EASY) ? CROWN_TIER_EASY : CROWN_TIER_NORMAL;
    meta_open();
    if (!meta_valid()) meta_reset();
    ext_ensure();
    if (SRAM_BASE[META_EXT_WINS_OFF + class_id] != 0xFF)
        SRAM_BASE[META_EXT_WINS_OFF + class_id]++;
    bits = meta_get16(META_EXT_TIER_OFF);
    shift = (u8)(class_id * 2);
    cur = (u8)((bits >> shift) & 3);
    if (tier > cur) {
        bits &= (u16)~((u16)3 << shift);
        bits |= (u16)tier << shift;
        meta_put16(META_EXT_TIER_OFF, bits);
    }
    ext_seal();
    meta_close();
}
