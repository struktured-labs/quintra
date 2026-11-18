#pragma bank 22

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

/* Aether Lattice call-and-response row. */

#define ECHO_IDLE 0
#define ECHO_REST 1
#define ECHO_PLAY 2

static const u8 row_x[4] = { 4, 8, 12, 16 };
static const u8 row_y[4] = { 7, 9, 7, 9 };

u8 room_row_len;
u8 room_row_phrase[5];
u8 room_row_progress;
u8 room_echo_mode;
static u8 echo_timer;
static u8 echo_step;
static u8 row_contact;
static u8 row_phase_bit;

static void row_set_tiles(u8 lit) {
    u8 i;
    room_rune_lit_mask = lit ? 0x0F : 0;
    for (i = 0; i < 4; ++i)
        room_tilemap[row_y[i]][row_x[i]] = lit ? RUNE_LIT_TILE(i)
                                               : RUNE_IDLE_TILE(i);
}

static void row_paint_solved(u8 lit) {
    row_set_tiles(lit);
    rune_paint_all();
}

static u8 phrase_illegal(u8 n) {
    if (room_row_phrase[0] == 0 && room_row_phrase[1] == 1
        && room_row_phrase[2] == 2) return 1;
    if (room_row_phrase[0] == 3 && room_row_phrase[1] == 2
        && room_row_phrase[2] == 1) return 1;
    if (n >= 4 && room_row_phrase[0] == 0 && room_row_phrase[1] == 1
        && room_row_phrase[2] == 2 && room_row_phrase[3] == 3) return 1;
    if (n >= 4 && room_row_phrase[0] == 3 && room_row_phrase[1] == 2
        && room_row_phrase[2] == 1 && room_row_phrase[3] == 0) return 1;
    (void)n;
    return 0;
}

static u8 phrase_has_consec_repeat(u8 n) {
    u8 i;
    for (i = 1; i < n; ++i)
        if (room_row_phrase[i] == room_row_phrase[(u8)(i - 1)]) return 1;
    return 0;
}

static u8 phrase_reuse_ok(u8 n) {
    u8 counts[4];
    u8 i, reused, seen;
    if (n < 5) return 1;
    counts[0] = counts[1] = counts[2] = counts[3] = 0;
    for (i = 0; i < n; ++i) counts[room_row_phrase[i] & 3]++;
    reused = 0;
    seen = 0;
    for (i = 0; i < 4; ++i) {
        if (counts[i]) seen++;
        if (counts[i] == 2) reused++;
        if (counts[i] > 2) return 0;
    }
    return (u8)(seen == 4 && reused == 1);
}

static void pick_row_phrase(u8 mix, u8 n) {
    u8 attempt, i, start, step, drop, insert_at, insert_plate;
    room_row_len = n;
    for (attempt = 0; attempt < 48; ++attempt) {
        u8 s = (u8)(mix + (u8)(attempt * 17u) + (u8)(attempt << 2));
        if (n <= 4) {
            drop = (n == 3) ? (u8)(s & 3) : 0xFF;
            start = (u8)((s >> 2) & 3);
            step = (u8)(1 + ((s >> 4) & 1) * 2);
            i = 0;
            {
                u8 at = start, seen = 0;
                while (seen < 4 && i < n) {
                    if (at != drop) {
                        room_row_phrase[i] = at;
                        i++;
                    }
                    at = (u8)((at + step) & 3);
                    seen++;
                }
            }
        } else {
            start = (u8)(s & 3);
            step = (u8)(1 + ((s >> 2) & 1) * 2);
            {
                u8 at = start;
                for (i = 0; i < 4; ++i) {
                    room_row_phrase[i] = at;
                    at = (u8)((at + step) & 3);
                }
            }
            insert_at = (u8)(1 + ((s >> 3) & 3));
            if (insert_at > 4) insert_at = 4;
            insert_plate = (u8)((s >> 5) & 3);
            for (i = 4; i > insert_at; --i)
                room_row_phrase[i] = room_row_phrase[(u8)(i - 1)];
            if (insert_plate == room_row_phrase[(u8)(insert_at - 1)])
                insert_plate = (u8)((insert_plate + 1) & 3);
            if (insert_at < 4
                && insert_plate == room_row_phrase[(u8)(insert_at + 1)])
                insert_plate = (u8)((insert_plate + 2) & 3);
            room_row_phrase[insert_at] = insert_plate;
        }
        if (!phrase_has_consec_repeat(n) && !phrase_illegal(n)
            && phrase_reuse_ok(n))
            return;
    }
    room_row_phrase[0] = 0;
    room_row_phrase[1] = 2;
    room_row_phrase[2] = 1;
    room_row_phrase[3] = 3;
    room_row_phrase[4] = 0;
    room_row_len = n;
}

static void row_echo_start(u8 rest) {
    room_echo_mode = ECHO_REST;
    echo_timer = rest;
    echo_step = 0;
    sfx_lock_secret((u8)(rest + (u8)(room_row_len * 24u) + 8u));
}

void rune_echo_cancel(void) BANKED {
    room_echo_mode = ECHO_IDLE;
    echo_timer = 0;
}

static u8 row_standing_on_plate(u8 tx, u8 ty, u8 *out) {
    u8 i;
    for (i = 0; i < 4; ++i)
        if (tx == row_x[i] && ty == row_y[i]) {
            if (out) *out = i;
            return 1;
        }
    return 0;
}

void rune_echo_tick(void) BANKED {
    if (room_echo_mode == ECHO_IDLE) return;
    if (echo_timer) {
        echo_timer--;
        return;
    }
    if (room_echo_mode == ECHO_REST) {
        room_echo_mode = ECHO_PLAY;
        echo_step = 0;
    }
    if (room_echo_mode == ECHO_PLAY) {
        if (echo_step >= room_row_len) {
            room_echo_mode = ECHO_IDLE;
            return;
        }
        sfx_play_rune_echo(room_rune_pitch[room_row_phrase[echo_step]]);
        rune_start_flash(room_row_phrase[echo_step]);
        echo_step++;
        echo_timer = 24;
    }
}

void rune_row_prepare(u8 bit, u8 mix) BANKED {
    u8 i, n, solved;
    row_phase_bit = bit;
    row_contact = 0;
    room_row_progress = 0;
    n = run_state.bosses_beaten == 0 ? 3
        : run_state.bosses_beaten == 1 ? 4 : 5;
    pick_row_phrase(mix, n);
    room_rune_count = 4;
    for (i = 0; i < 4; ++i) {
        room_rune_x[i] = row_x[i];
        room_rune_y[i] = row_y[i];
        room_rune_pitch[i] = i;
    }
    solved = (run_state.dungeon_phase & bit) ? 1 : 0;
    row_set_tiles(solved);
    if (solved) {
        room_row_progress = room_row_len;
        rune_echo_cancel();
    } else {
        row_echo_start(20);
    }
}

void rune_row_tick(u8 tx, u8 ty) BANKED {
    u8 touched = 0xFF;
    u8 on = row_standing_on_plate(tx, ty, &touched);
    if (room_echo_mode != ECHO_IDLE) {
        if (on) row_contact = 1;
        return;
    }
    if (!on) {
        row_contact = 0;
        return;
    }
    if (row_contact) return;
    row_contact = 1;
    if (run_state.dungeon_phase & row_phase_bit) return;
    if (touched != room_row_phrase[room_row_progress]) {
        room_row_progress = 0;
        row_paint_solved(0);
        voice_plate(touched);
        sfx_play(SFX_HIT);
        room_shake(1, 6);
        row_echo_start(40);
        return;
    }
    room_row_progress++;
    if (room_row_progress < room_row_len) {
        voice_plate(touched);
        return;
    }
    run_state.dungeon_phase |= row_phase_bit;
    row_paint_solved(1);
    voice_plate_final(touched);
    room_shake(1, 12);
}

void puzzle_phase_switch_zap(void) BANKED {
    rune_echo_cancel();
    run_state.dungeon_phase ^= row_phase_bit;
    if (run_state.dungeon_phase & row_phase_bit) {
        room_row_progress = room_row_len;
        row_paint_solved(1);
    } else {
        room_row_progress = 0;
        row_paint_solved(0);
        row_echo_start(20);
    }
}
