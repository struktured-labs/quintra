#pragma bank 255
// Sun Lattice generator and beam tracer. Plain C: also compiled on the host
// (SL_HOST) by scripts/test_sun_lattice_parity.py against the Rust
// reference in tools/crates/quintra-procgen/src/sun_lattice.rs. Every
// arithmetic step is written with explicit 8/16-bit casts so SDCC and a
// 32-bit host compiler agree bit for bit.

#include "game/sun_lattice.h"

#ifdef SL_HOST
#define BGT_FLOOR        1
#define BGT_FLOOR2      19
#define BGT_FLOOR3      20
#define BGT_SPIKES      31
#define BGT_SWITCH      33
#define BGT_WILD_WATER  97
#define BGT_GATE_WATER 101
#define BGT_GATE_VENT  104
#define BGT_WILD_HOLE  108
extern u8 room_tilemap[SL_MAP_H][SL_MAP_W];
#else
#include "render/tiles.h"
#include "game/room.h"
#endif

// Fixture cells stay 3+ tiles from the walls so a 5x5 floor apron fits
// inside the 18x15 interior and the champion can always walk around them.
#define SL_X0 3
#define SL_X1 16
#define SL_Y0 3
#define SL_Y1 13
#define SL_PATH_CAP 32   // tracer steps per queued branch
#define SL_QUEUE    5    // emitter + two Bifrost Wedges x two outputs
#define SL_TRIES    64

u8 sl_n;
u8 sl_x[SL_MAX_FIX];
u8 sl_y[SL_MAX_FIX];
u8 sl_kind[SL_MAX_FIX];
u8 sl_ang[SL_MAX_FIX];
u8 sl_solved_ang[SL_MAX_FIX];
u8 sl_lit[SL_MAX_FIX];
u8 sl_crystal_x, sl_crystal_y;
u8 sl_beam_h[SL_BITS];
u8 sl_beam_v[SL_BITS];
u8 sl_fixbits[SL_BITS];
u8 sl_attempts;

static u16 sl_rs;
static u8 sl_occ[SL_BITS];
static u8 sl_end_d;   // travel direction into the last placed terminator
// Pending branches: start fixture cell, direction, vanes, terminator.
static u8 pq_x[SL_QUEUE], pq_y[SL_QUEUE], pq_d[SL_QUEUE], pq_v[SL_QUEUE], pq_t[SL_QUEUE];
static u8 pq_n;

static const i8 sl_dx[4] = { 0, 1, 0, -1 };
static const i8 sl_dy[4] = { -1, 0, 1, 0 };

// Per-stage shape (index = min(stage, 8) - 2): main-branch vanes, Bifrost
// Wedges, vanes per wedge child, Fixed Vanes, decoy vanes.
static const u8 sl_main_v[7] = { 2, 2, 3, 3, 3, 3, 3 };
static const u8 sl_wedges[7] = { 0, 1, 1, 1, 1, 2, 2 };
static const u8 sl_sub_v[7]  = { 0, 1, 1, 1, 1, 0, 0 };
static const u8 sl_fixed[7]  = { 0, 0, 0, 1, 1, 2, 2 };
static const u8 sl_decoy[7]  = { 0, 0, 1, 1, 2, 2, 2 };

static u8 rnd(void) {
    sl_rs ^= (u16)(sl_rs << 7);
    sl_rs ^= (u16)(sl_rs >> 9);
    sl_rs ^= (u16)(sl_rs << 8);
    return (u8)sl_rs;
}

static u16 cell_of(u8 x, u8 y) {
    return (u16)((u16)((u16)y << 4) + (u16)((u16)y << 2) + x);
}

static u8 bit_get(const u8 *b, u8 x, u8 y) {
    u16 i = cell_of(x, y);
    return (u8)(b[(u8)(i >> 3)] & (u8)(1u << (u8)(i & 7)));
}

static void bit_set(u8 *b, u8 x, u8 y) {
    u16 i = cell_of(x, y);
    b[(u8)(i >> 3)] |= (u8)(1u << (u8)(i & 7));
}

static void bits_clear(u8 *b) {
    u8 i;
    for (i = 0; i < SL_BITS; ++i) b[i] = 0;
}

static u8 in_box(u8 x, u8 y) {
    return (x >= SL_X0 && x <= SL_X1 && y >= SL_Y0 && y <= SL_Y1) ? 1 : 0;
}

static u8 far_from_fixtures(u8 x, u8 y) {
    u8 i, ax, ay;
    for (i = 0; i < sl_n; ++i) {
        ax = (x > sl_x[i]) ? (u8)(x - sl_x[i]) : (u8)(sl_x[i] - x);
        ay = (y > sl_y[i]) ? (u8)(y - sl_y[i]) : (u8)(sl_y[i] - y);
        if (ax < 3 && ay < 3) return 0;
    }
    return 1;
}

static void add_fixture(u8 x, u8 y, u8 kind, u8 ang) {
    sl_x[sl_n] = x;
    sl_y[sl_n] = y;
    sl_kind[sl_n] = kind;
    sl_ang[sl_n] = ang;
    sl_solved_ang[sl_n] = ang;
    sl_lit[sl_n] = 0;
    bit_set(sl_occ, x, y);
    bit_set(sl_fixbits, x, y);
    sl_n++;
}

static u8 room_ahead(u8 x, u8 y, u8 d) {
    return in_box((u8)(x + sl_dx[d] * 3), (u8)(y + sl_dy[d] * 3));
}

// A straight beam run of len cells from (x, y): every crossed cell is free
// and the far end is a legal, well-spaced fixture cell.
static u8 seg_ok(u8 x, u8 y, u8 d, u8 len) {
    u8 k, cx = x, cy = y;
    for (k = 0; k < len; ++k) {
        cx = (u8)(cx + sl_dx[d]);
        cy = (u8)(cy + sl_dy[d]);
        if (cx >= SL_MAP_W || cy >= SL_MAP_H) return 0;
        if (bit_get(sl_occ, cx, cy)) return 0;
    }
    return (in_box(cx, cy) && far_from_fixtures(cx, cy)) ? 1 : 0;
}

static void seg_mark(u8 x, u8 y, u8 d, u8 len) {
    u8 k;
    for (k = 0; k < len; ++k) {
        x = (u8)(x + sl_dx[d]);
        y = (u8)(y + sl_dy[d]);
        bit_set(sl_occ, x, y);
    }
}

// Lay `vanes` reflecting turns, then a terminator (Obelisk or Bifrost).
static u8 run_branch(u8 x, u8 y, u8 d, u8 vanes, u8 term) {
    u8 i, t, len, base, nd, used = 0;
    for (i = 0; i <= vanes; ++i) {
        base = (u8)(rnd() % 5);
        len = 0;
        for (t = 0; t < 5; ++t) {
            u8 cand = (u8)(3 + (u8)((u8)(base + t) % 5));
            if ((u8)(used + cand) <= SL_PATH_CAP && seg_ok(x, y, d, cand)) {
                len = cand;
                break;
            }
        }
        if (!len) return 0;
        seg_mark(x, y, d, len);
        used = (u8)(used + len);
        x = (u8)(x + sl_dx[d] * len);
        y = (u8)(y + sl_dy[d] * len);
        if (i == vanes) {
            if (term == SLK_BIFROST
                && !(room_ahead(x, y, (u8)((d + 1) & 3))
                     && room_ahead(x, y, (u8)((d + 3) & 3))))
                return 0;
            add_fixture(x, y, term, 0);
            sl_end_d = d;
            return 1;
        }
        nd = (u8)((d + ((rnd() & 1) ? 1 : 3)) & 3);
        if (!room_ahead(x, y, nd)) {
            nd = (u8)((nd + 2) & 3);
            if (!room_ahead(x, y, nd)) return 0;
        }
        // '/' maps N<->E and S<->W (d ^ 1); '\' maps N<->W and S<->E.
        add_fixture(x, y, SLK_VANE, ((u8)(d ^ 1) == nd) ? 0 : 1);
        d = nd;
    }
    return 0;
}

static void push_branch(u8 x, u8 y, u8 d, u8 v, u8 t) {
    pq_x[pq_n] = x; pq_y[pq_n] = y; pq_d[pq_n] = d;
    pq_v[pq_n] = v; pq_t[pq_n] = t;
    pq_n++;
}

static void reset_layout(void) {
    sl_n = 0;
    pq_n = 0;
    sl_crystal_x = sl_crystal_y = 0xFF;
    bits_clear(sl_occ);
    bits_clear(sl_fixbits);
}

static u8 build_tree(u8 s) {
    u8 ex, ey, ed, k, qi, wedges_left;
    ex = (u8)(SL_X0 + rnd() % 14);
    ey = (u8)(SL_Y0 + rnd() % 11);
    ed = (u8)(rnd() & 3);
    for (k = 0; k < 4 && !room_ahead(ex, ey, ed); ++k)
        ed = (u8)((ed + 1) & 3);
    if (k == 4) return 0;
    add_fixture(ex, ey, SLK_EMITTER, ed);
    wedges_left = sl_wedges[s];
    push_branch(ex, ey, ed, sl_main_v[s], wedges_left ? SLK_BIFROST : SLK_OBELISK);
    if (wedges_left) wedges_left--;
    for (qi = 0; qi < pq_n; ++qi) {
        if (!run_branch(pq_x[qi], pq_y[qi], pq_d[qi], pq_v[qi], pq_t[qi]))
            return 0;
        if (pq_t[qi] == SLK_BIFROST) {
            u8 wx = sl_x[(u8)(sl_n - 1)], wy = sl_y[(u8)(sl_n - 1)];
            u8 d = sl_end_d;
            push_branch(wx, wy, (u8)((d + 1) & 3), sl_sub_v[s],
                wedges_left ? SLK_BIFROST : SLK_OBELISK);
            if (wedges_left) wedges_left--;
            push_branch(wx, wy, (u8)((d + 3) & 3), sl_sub_v[s], SLK_OBELISK);
        }
    }
    return 1;
}

// Hand-checked fallback (spec Layout 1, reconciled): Brazier fires East
// into '\', South into '/', West into the Obelisk.
static void fallback_tree(void) {
    reset_layout();
    add_fixture(3, 4, SLK_EMITTER, 1);
    add_fixture(14, 4, SLK_VANE, 1);
    add_fixture(14, 12, SLK_VANE, 0);
    add_fixture(4, 12, SLK_OBELISK, 0);
    sl_attempts = 0xFF;
}

void sl_generate(u32 seed, u8 stage, u8 role) SL_BANKED {
    u8 s, i, k, want, flipped, rot, fixed_left;
    s = (u8)((stage > 8 ? 8 : stage < 2 ? 2 : stage) - 2);
    sl_rs = (u16)((u16)seed ^ (u16)(seed >> 16));
    if (role) sl_rs ^= 0x5A5A;
    if (!sl_rs) sl_rs = 0xACE1;
    sl_attempts = 0;
    for (;;) {
        reset_layout();
        if (build_tree(s)) break;
        if (++sl_attempts >= SL_TRIES) {
            fallback_tree();
            break;
        }
    }

    // Late stages harden some reflectors into Fixed Vanes. Keep at least
    // two rotatable vanes so the room is still a puzzle.
    rot = 0;
    for (i = 0; i < sl_n; ++i) if (sl_kind[i] == SLK_VANE) rot++;
    fixed_left = sl_fixed[s];
    for (i = 0; i < sl_n && fixed_left && rot > 2; ++i) {
        if (sl_kind[i] == SLK_VANE && (rnd() & 1)) {
            sl_kind[i] = SLK_FIXED;
            fixed_left--;
            rot--;
        }
    }

    // Decoy vanes sit off the solved light path. They never block the
    // solution but catch a mis-turned beam.
    want = (u8)(sl_decoy[s] + (role ? 1 : 0));
    for (i = 0; i < want && sl_n < SL_MAX_FIX; ++i) {
        for (k = 0; k < 8; ++k) {
            u8 x = (u8)(SL_X0 + rnd() % 14);
            u8 y = (u8)(SL_Y0 + rnd() % 11);
            u8 a = (u8)(rnd() & 1);
            if (!bit_get(sl_occ, x, y) && far_from_fixtures(x, y)) {
                add_fixture(x, y, SLK_VANE, a);
                sl_solved_ang[(u8)(sl_n - 1)] = a;
                break;
            }
        }
    }

    // Stage 3 teaches the shatterable Crystal blocking the first run.
    if ((s == 0 && role == 0) || (s >= 3 && (rnd() & 3) == 0)) {
        u8 d = sl_ang[0];
        sl_crystal_x = (u8)(sl_x[0] + sl_dx[d] * 2);
        sl_crystal_y = (u8)(sl_y[0] + sl_dy[d] * 2);
    }

    // Scramble backwards from the solved tree: flip vanes until at least
    // half of the rotatable path vanes' worth are wrong (rounded up) and the
    // room is provably not already lit.
    flipped = 0;
    want = (u8)((rot + 1) >> 1);
    for (i = 0; i < sl_n; ++i) {
        if (sl_kind[i] == SLK_VANE && sl_ang[i] == sl_solved_ang[i]
            && (rnd() & 1)) {
            sl_ang[i] ^= 1;
            flipped++;
        }
    }
    for (i = 0; i < sl_n && (flipped < want || sl_trace(0)); ++i) {
        if (sl_kind[i] == SLK_VANE && sl_ang[i] == sl_solved_ang[i]) {
            sl_ang[i] ^= 1;
            flipped++;
        }
    }
    // A mis-turned beam can, very rarely, reach every Obelisk by another
    // route. Never publish a room that is lit on arrival.
    if (sl_trace(0)) {
        fallback_tree();
        sl_ang[1] = 0;
    }
}

static u8 sl_passable(u8 t) {
    return (t == BGT_FLOOR || t == BGT_FLOOR2 || t == BGT_FLOOR3
        || t == BGT_SPIKES || t == BGT_SWITCH || t == BGT_WILD_WATER
        || (t >= BGT_GATE_WATER && t <= BGT_GATE_VENT)
        || t == BGT_WILD_HOLE) ? 1 : 0;
}

u8 sl_trace(u8 use_map) SL_BANKED {
    u8 qx[SL_QUEUE], qy[SL_QUEUE], qd[SL_QUEUE];
    u8 qn = 0, qi, i, x, y, d, steps, all, any;
    bits_clear(sl_beam_h);
    bits_clear(sl_beam_v);
    for (i = 0; i < sl_n; ++i) {
        sl_lit[i] = 0;
        if (sl_kind[i] == SLK_EMITTER && qn < SL_QUEUE) {
            qx[qn] = sl_x[i]; qy[qn] = sl_y[i]; qd[qn] = sl_ang[i]; qn++;
        }
    }
    for (qi = 0; qi < qn; ++qi) {
        x = qx[qi]; y = qy[qi]; d = qd[qi];
        for (steps = 0; steps < SL_PATH_CAP; ++steps) {
            x = (u8)(x + sl_dx[d]);
            y = (u8)(y + sl_dy[d]);
            if (x >= SL_MAP_W || y >= SL_MAP_H) break;
            if (bit_get(sl_fixbits, x, y)) {
                u8 k;
                for (i = 0; i < sl_n; ++i)
                    if (sl_x[i] == x && sl_y[i] == y) break;
                k = sl_kind[i];
                if (k == SLK_VANE || k == SLK_FIXED) {
                    d = sl_ang[i] ? (u8)(3 - d) : (u8)(d ^ 1);
                    continue;
                }
                if (k == SLK_BIFROST) {
                    if (qn < SL_QUEUE) {
                        qx[qn] = x; qy[qn] = y; qd[qn] = (u8)((d + 1) & 3); qn++;
                    }
                    if (qn < SL_QUEUE) {
                        qx[qn] = x; qy[qn] = y; qd[qn] = (u8)((d + 3) & 3); qn++;
                    }
                } else if (k == SLK_OBELISK) sl_lit[i] = 1;
                break;
            }
            if (use_map && !sl_passable(room_tilemap[y][x])) break;
            bit_set((d & 1) ? sl_beam_h : sl_beam_v, x, y);
        }
    }
    all = 1; any = 0;
    for (i = 0; i < sl_n; ++i) {
        if (sl_kind[i] == SLK_OBELISK) {
            any = 1;
            if (!sl_lit[i]) all = 0;
        }
    }
    return (u8)(all & any);
}
