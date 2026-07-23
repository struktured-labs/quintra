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
#define LEGACY_RS_SIZE 20 // v0.17.47 and earlier, before visited-map fields
#define PRE_SIGIL_RS_SIZE 23 // v0.17.48-v0.17.51
#define PRE_DIFFICULTY_RS_SIZE 26 // v0.18.42 and earlier: implicit Normal
#define PRE_PUZZLE_RS_SIZE 27 // v0.18.52 and earlier: no dungeon puzzle state
#define PRE_WIDE_MAP_RS_SIZE 29 // v0.18.54 and earlier: six-cell topology

static void sram_open(void)  { ENABLE_RAM_MBC5; SWITCH_RAM_MBC5(0); }
static void sram_close(void) { DISABLE_RAM_MBC5; }

u8 sram_run_valid(void) {
    u8 ok = 0;
    sram_open();
    if (SRAM_BASE[0] == 'Q' && SRAM_BASE[1] == 'S'
        && SRAM_BASE[2] == SAVE_VERSION
        && (SRAM_BASE[3] == (u8)sizeof(run_state_t)
            || SRAM_BASE[3] == PRE_WIDE_MAP_RS_SIZE
            || SRAM_BASE[3] == PRE_PUZZLE_RS_SIZE
            || SRAM_BASE[3] == PRE_DIFFICULTY_RS_SIZE
            || SRAM_BASE[3] == PRE_SIGIL_RS_SIZE
            || SRAM_BASE[3] == LEGACY_RS_SIZE)
        && SRAM_BASE[4] == (u8)sizeof(player_state_t)) {
        u8 n = (u8)(SRAM_BASE[3] + SRAM_BASE[4]);
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
    u8 i, saved_rs;
    u16 off = HDR_SIZE;
    if (!sram_run_valid()) return 0;
    sram_open();
    saved_rs = SRAM_BASE[3];
    for (i = 0; i < (u8)sizeof(run_state_t); ++i) rs[i] = 0;
    for (i = 0; i < saved_rs; ++i, ++off) rs[i] = SRAM_BASE[off];
    for (i = 0; i < (u8)sizeof(player_state_t); ++i, ++off) pl[i] = SRAM_BASE[off];
    sram_close();
    if (saved_rs == LEGACY_RS_SIZE) {
        run_state.dungeon_seen = 0;
        run_state.world_seen = 0;
        run_state_mark_visited();
    }
    if (saved_rs == PRE_WIDE_MAP_RS_SIZE && run_state.bosses_beaten < BOSSES_TO_WIN) {
        // Preserve the player's approximate place inside an old six-room
        // dungeon while migrating its absolute counter to the expanded table.
        // World/town checkpoints map to their exact new campaign landmarks.
        u8 stage = run_state.bosses_beaten;
        if (run_state.world_mode && stage)
            run_state.room_counter = run_state_boss_room((u8)(stage - 1));
        else if (stage == 3 && run_state.room_counter == 19)
            run_state.room_counter = 33;
        else if (stage == 6 && run_state.room_counter == 37)
            run_state.room_counter = 73;
        else {
            u8 old_start = stage ? (u8)(stage * 6 + 1) : 0;
            u8 old_local = (run_state.room_counter > old_start)
                ? (u8)(run_state.room_counter - old_start) : 0;
            u8 new_last = (u8)(run_state_dungeon_size() - 1);
            if (old_local > new_last) old_local = new_last;
            run_state.room_counter =
                (u8)(run_state_stage_start(stage) + old_local);
        }
    }
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
// Layout v2: 'Q' 'M' ver | best u16 | runs u16 | wins u16 |
//            best_win_time u16 (seconds; 0xFFFF = no win yet) | checksum.
// A version bump invalidates old meta (acceptable pre-1.0).

#define META_VERSION 2
#define META_NO_TIME 0xFFFF

static void meta_open(void)  { ENABLE_RAM_MBC5; SWITCH_RAM_MBC5(1); }

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
    SRAM_BASE[9] = 0xFF; SRAM_BASE[10] = 0xFF;   // no win time yet
    SRAM_BASE[11] = meta_sum();
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

u16 sram_meta_best_time(void) {
    u16 v;
    meta_open();
    v = meta_valid() ? meta_get16(9) : META_NO_TIME;
    sram_close();
    return v;
}

u8 sram_meta_record(u16 score, u8 won, u16 time_s) {
    u8 flags = 0;
    meta_open();
    if (!meta_valid()) meta_reset();
    if (score > meta_get16(3)) { meta_put16(3, score); flags |= 1; }
    meta_put16(5, (u16)(meta_get16(5) + 1));
    if (won) {
        meta_put16(7, (u16)(meta_get16(7) + 1));
        if (time_s < meta_get16(9)) { meta_put16(9, time_s); flags |= 2; }
    }
    SRAM_BASE[11] = meta_sum();
    sram_close();
    return flags;
}
