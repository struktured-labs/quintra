#pragma bank 6

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/pickup.h"
#include "game/prism_toggle.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/rime_room.h"
#include "game/rewrite_room.h"
#include "game/kite_room.h"
#include "game/secret_merchant.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/sun_lattice.h"
#include "render/hud.h"
#include "render/tiles.h"

u8 room_puzzle_kind;
u8 room_puzzle_locked;
u8 room_puzzle_visual_y;
u8 room_puzzle_phase_bit;
u8 room_hidden_secret_kind;
u8 room_hidden_secret_x;
u8 room_hidden_secret_y;
u8 room_hidden_secret_x2;
u8 room_hidden_secret_y2;
u8 room_hidden_secret_bit;
u8 room_socket_x = 0xFF;
u8 room_socket_y = 0xFF;

static u8 puzzle_block_x;
static u8 puzzle_block_y;
static u8 puzzle_contact;
static u8 rune_progress;
static u8 rune_count;
static u8 rune_order[5];
static u8 rune_x[5];
static u8 rune_y[5];
static u8 rune_descending;
u8 room_rune_count;
u8 room_rune_x[5];
u8 room_rune_y[5];
u8 room_rune_pitch[5];
u8 room_rune_lit_mask;


static const u8 rune_orders[18] = {
    0,1,2, 0,2,1, 1,0,2, 1,2,0, 2,0,1, 2,1,0
};

static u8 rune_pitch(u8 order_rank) {
    u8 degree = rune_descending
        ? (u8)(rune_count - 1 - order_rank) : order_rank;
    return degree;
}

void puzzle_prepare_room_role(void) BANKED {
    u8 x, y;
    puzzle_prepare_room();
    // Reachability uses bit 7 as scratch metadata while procgen chooses legal
    // enemy cells. Puzzle preparation is the final tilemap authoring step
    // before every full draw or streamed slide, so sanitize here as a hard
    // rendering/collision boundary even if an earlier banked cleanup was
    // interrupted. Tile ids 128..255 are never legal room terrain.
    for (y = 0; y < ROOM_H; ++y)
        for (x = 0; x < ROOM_W; ++x)
            room_tilemap[y][x] &= 0x7F;
    room_combat_sealed = (room_puzzle_kind != PUZZLE_NONE)
        ? 0 : puzzle_combat_seal_policy();
}

u8 puzzle_combat_seal_policy(void) BANKED {
    u8 local;
    u8 chosen;
    if (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter)) return 0;
    local = run_state_dungeon_local();
    if (local == run_state_dungeon_entry_cell())
        return (run_state.bosses_beaten == 0
            && run_state.room_counter == local) ? 0 : 1;
    if (local == run_state.mission_warden_cell
        || local == run_state.mission_deep_warden_cell) return 1;
    if (local >= 4) return 0;
    chosen = (u8)(1 + ((run_state.run_seed
        ^ (u32)(run_state.bosses_beaten * 0x5D)) & 1));
    return (local == chosen) ? 1 : 0;
}

static u8 puzzle_solved(void) {
    u8 cell = run_state_dungeon_cell();
    u8 bit = (cell == run_state.mission_trial_cell) ? RUN_TRIAL_BIT
        : (cell == run_state.mission_waystone_cell) ? RUN_WAYSTONE_BIT : 0;
    return (bit && (run_state.dungeon_puzzles & bit)) ? 1 : 0;
}

static void mark_puzzle_solved(u8 delay_fanfare) {
    u8 cell = run_state_dungeon_cell();
    if (cell == run_state.mission_trial_cell)
        run_state.dungeon_puzzles |= RUN_TRIAL_BIT;
    else if (cell == run_state.mission_waystone_cell)
        run_state.dungeon_puzzles |= RUN_WAYSTONE_BIT;
    room_puzzle_locked = 0;
    if (delay_fanfare) sfx_play_puzzle_after_note();
    else sfx_play(SFX_PUZZLE);
    room_shake(1, 18);
    // Every mandatory puzzle pays one physical tool charge. The seed and
    // local cell choose the implement, so routing changes the tactical Pack
    // without turning tools into generic random enemy trash.
    pickup_spawn_item((u8)(22 + ((u8)run_state.run_seed
        + run_state_dungeon_cell()) % 3), player.x, player.y);
}

static void clear_all_cairns(void) {
    u8 x, y;
    for (y = 1; y < ROOM_H - 1; ++y) {
        for (x = 1; x < ROOM_W - 1; ++x) {
            u8 t = room_tilemap[y][x];
            if (t == BGT_BLOCK || t == BGT_BLOCK_TR
                || t == BGT_BLOCK_BL || t == BGT_BLOCK_BR)
                room_tilemap[y][x] = BGT_FLOOR;
        }
    }
}

static void floor_rect(u8 x0, u8 y0, u8 w, u8 h) {
    u8 x, y;
    for (y = y0; y < (u8)(y0 + h); ++y)
        for (x = x0; x < (u8)(x0 + w); ++x)
            room_tilemap[y][x] = BGT_FLOOR;
}

static void set_tile_live(u8 x, u8 y, u8 tile, u8 attr) {
    room_tilemap[y][x] = tile;
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &attr);
    VBK_REG = 0;
}

// Push Seal: the crate must be shoved onto a 2x2 gold socket along an
// L-shaped route (two legs of 2-3 shoves). The Rust mirror
// (quintra-procgen push_seal.rs) proves every variant solvable from any
// tile of the cleared apron under the push rules in room.c. A crate wedged
// off-route is reset by stepping out through the always-open return door.
static void prepare_push(u32 seed) {
    u8 sel = (u8)(seed >> 4) & 3;
    u8 sx = (sel & 1) ? 10 : 8;
    u8 sy = (sel & 2) ? 8 : 6;
    u8 hx = (u8)(2 + ((seed >> 2) & 1));
    u8 vy = (u8)(2 + ((seed >> 3) & 1));
    u8 x, y, x0, x1, y0, y1;
    if ((seed & 2) && sy == 6) vy = 2;
    x = (seed & 1) ? (u8)(sx - hx) : (u8)(sx + hx);
    y = (seed & 2) ? (u8)(sy - vy) : (u8)(sy + vy);
    x0 = (u8)(((x < sx) ? x : sx) - 3); if (x0 < 1) x0 = 1;
    x1 = (u8)(((x > sx) ? x : sx) + 4); if (x1 > 18) x1 = 18;
    y0 = (u8)(((y < sy) ? y : sy) - 3); if (y0 < 1 || y0 > 200) y0 = 1;
    y1 = (u8)(((y > sy) ? y : sy) + 4); if (y1 > 15) y1 = 15;
    clear_all_cairns();
    floor_rect(x0, y0, (u8)(x1 - x0 + 1), (u8)(y1 - y0 + 1));
    room_socket_x = sx;
    room_socket_y = sy;
    room_tilemap[sy][sx] = room_tilemap[sy][sx + 1] = BGT_FLOOR3;
    room_tilemap[sy + 1][sx] = room_tilemap[sy + 1][sx + 1] = BGT_FLOOR3;
    room_tilemap[y][x] = BGT_BLOCK;
    room_tilemap[y][x + 1] = BGT_BLOCK_TR;
    room_tilemap[y + 1][x] = BGT_BLOCK_BL;
    room_tilemap[y + 1][x + 1] = BGT_BLOCK_BR;
    puzzle_block_x = x;
    puzzle_block_y = y;
    room_puzzle_locked = 1;
}

static void prepare_sequence(u32 seed) {
    u8 i;
    u16 folded;
    u8 order;
    // Preserve (seed >> 8) % 6 without linking the generic 32-bit modulo
    // helper into fixed ROM. Because 256^n % 6 == 4 for every n >= 1,
    // folding the three significant bytes into a 16-bit value is exact.
    folded = (u8)(seed >> 8);
    folded += (u16)((u16)(u8)(seed >> 16) << 2);
    folded += (u16)((u16)(u8)(seed >> 24) << 2);
    // Stage one teaches a short three-tone phrase. Verdant expands it to
    // four far-apart corners; Ember and every later dungeon demand five,
    // including a center pivot that creates phone-unlock-like crossings.
    // The fixtures stay deterministic for a run seed while their growing
    // spatial span prevents three adjacent taps from solving every stage.
    rune_count = run_state.bosses_beaten == 0 ? 3
        : run_state.bosses_beaten == 1 ? 4 : 5;
    if (rune_count == 3) {
        rune_x[0] = 5;  rune_y[0] = 8;
        rune_x[1] = 10; rune_y[1] = 5;
        rune_x[2] = 14; rune_y[2] = 10;
        // The phrase is mandatory progression, so its three visible aprons
        // must be one physical circuit even when the generated court beneath
        // them is a narrow horizontal or vertical lane.  A three-tile road
        // admits the champion's full 12px body without revealing the order.
        floor_rect(4, 7, 8, 3);
        floor_rect(9, 4, 3, 8);
        floor_rect(10, 9, 6, 3);
    } else {
        rune_x[0] = 3;  rune_y[0] = 4;
        rune_x[1] = 16; rune_y[1] = 4;
        rune_x[2] = 4;  rune_y[2] = 12;
        rune_x[3] = 15; rune_y[3] = 12;
        rune_x[4] = 10; rune_y[4] = 8;
        // Four/five-note Waystones span the whole compact court. Connect the
        // upper and lower rune roads through the center pivot before laying
        // the switches; merely clearing five isolated 3x3 aprons can leave a
        // lower note marooned behind otherwise valid procedural cover.
        floor_rect(2, 3, 16, 3);
        floor_rect(3, 11, 14, 3);
        floor_rect(9, 3, 3, 11);
    }
    order = (u8)(folded % 6);
    // Each Waystone owns one coherent musical grammar for the whole attempt.
    // The physical plates keep their assigned pitch through resets; only the
    // required traversal direction changes between rising and falling.
    rune_descending = (u8)((seed >> 6) & 1);
    for (i = 0; i < rune_count; ++i) {
        floor_rect((u8)(rune_x[i] - 1), (u8)(rune_y[i] - 1), 3, 3);
    }
    if (rune_count == 3) {
        for (i = 0; i < 3; ++i)
            rune_order[i] = rune_orders[(u8)(order * 3 + i)];
    } else {
        u8 at = (u8)seed;
        u8 step = rune_count == 4
            ? ((seed & 0x100UL) ? 3 : 1)
            : (u8)(1 + ((u8)(seed >> 8) & 3));
        while (at >= rune_count) at = (u8)(at - rune_count);
        for (i = 0; i < rune_count; ++i) {
            rune_order[i] = at;
            at = (u8)(at + step);
            if (at >= rune_count) at = (u8)(at - rune_count);
        }
    }
    rune_progress = 0;
    room_rune_lit_mask = 0;
    room_rune_count = rune_count;
    for (i = 0; i < rune_count; ++i) {
        room_rune_x[i] = rune_x[i];
        room_rune_y[i] = rune_y[i];
        room_rune_pitch[rune_order[i]] = rune_pitch(i);
    }
    for (i = 0; i < rune_count; ++i)
        room_tilemap[rune_y[i]][rune_x[i]] = RUNE_IDLE_TILE(room_rune_pitch[i]);
    room_puzzle_locked = 1;
}

static void prepare_phase_switch(u8 bit, u32 seed) {
    // Body-width cardinal lanes so every authored graph edge stays usable.
    floor_rect(1, 7, ROOM_W - 2, 3);
    floor_rect(9, 1, 3, ROOM_H - 2);
    room_puzzle_visual_y = 8;
    room_puzzle_phase_bit = bit;
    /* Fold the 32-bit seed here so the banked prepare does not pay
       SDCC's expensive u32-argument trampoline. */
    {
        u8 mix = (u8)(seed ^ (seed >> 8) ^ (seed >> 16) ^ (seed >> 21));
        rune_row_prepare(bit, mix);
    }
}

static void prepare_phase_gate(u8 bit) {
    u8 x;
    // This is a remote wall, not a magical lock on every doorway. Procedural
    // fold edges can enter the gate chamber from either side before the hero
    // reaches its paired switch; globally sealing unexplored doors therefore
    // made some valid maze seeds strand the player. Keep a solid, conspicuous
    // center barrier but leave two-tile body-width detours at both ends. The
    // remote switch lowers the wall into the fast route, and the sanctuary's
    // objective check remains the hard progression gate.
    room_puzzle_visual_y = 11;
    room_puzzle_phase_bit = bit;
    for (x = 4; x < ROOM_W - 4; ++x)
        room_tilemap[11][x] = (run_state.dungeon_phase & bit)
            ? BGT_FLOOR2 : BGT_PILLAR;
    // A remote gate is the final graph node, not merely decoration. It counts
    // only when revisited after its distant switch has changed the dungeon.
    if (run_state.dungeon_phase & bit)
        run_state.dungeon_puzzles |= RUN_DEEP_GATE_BIT;
    room_puzzle_locked = 0;
}

// Per-stage puzzle pool (spec 2.1 + batch-1 addendum). One dungeon-level
// mix picks the Trial (slot 0) and Waystone (slot 1) kinds; the two slots of
// one dungeon never repeat a kind in Stages 1-2. From Stage 3 the Trial stays
// a Sun Lattice, and through Stage 6 the Waystone may become a Prism Toggle.
// Mirrored by puzzle_slot_kinds() in scripts/quintra_topology.py.
static const u8 puzzle_early_pool[2][3] = {
    { PUZZLE_PUSH_SEAL, PUZZLE_RUNE_SEQUENCE, PUZZLE_PRISM_TOGGLE },
    { PUZZLE_RUNE_SEQUENCE, PUZZLE_PRISM_TOGGLE, PUZZLE_PUSH_SEAL },
};

u8 puzzle_slot_kind(u8 slot) BANKED {
    u8 bb = run_state.bosses_beaten;
    u8 mix = (u8)run_state.run_seed;
    u8 first;
    mix ^= (u8)(run_state.run_seed >> 8);
    mix ^= (u8)(run_state.run_seed >> 16);
    mix ^= (u8)(run_state.run_seed >> 24);
    mix = (u8)(mix + bb * 51);
    if (bb < 2) {
        first = (u8)(mix % 3);
        if (slot) first = (u8)((first + 1 + ((mix >> 2) & 1)) % 3);
        return puzzle_early_pool[bb][first];
    }
    if (slot && bb <= 5 && ((mix >> 3) & 1)) return PUZZLE_PRISM_TOGGLE;
    return PUZZLE_SUN_LATTICE;
}

void puzzle_prepare_room(void) BANKED {
    u8 local;
    u32 seed;
    room_puzzle_kind = PUZZLE_NONE;
    room_puzzle_locked = 0;
    room_puzzle_visual_y = 0xFF;
    room_puzzle_phase_bit = RUN_PHASE_OPEN_BIT;
    room_hidden_secret_kind = HIDDEN_SECRET_NONE;
    room_hidden_secret_bit = 0;
    room_socket_x = room_socket_y = 0xFF;
    room_rune_count = 0;
    room_rune_lit_mask = 0;
    rune_cancel_flash();
    puzzle_contact = 0;
    secret_merchant_room_ready();
    rime_live = 0;
    rw_live = 0;
    kt_live = 0;
    puzzle_keep_on = 0;
    puzzle_pack_n = 0;
    room_freeze_beats = 0;
    rime_cell = 0xFF;
    if (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter)
        || procgen_current_room_is_boss || run_state.secret_pending
        || run_state_is_shop() || run_state_is_sanctuary()) return;

    local = run_state_dungeon_local();
    rime_cell = rime_pick_cell();
    seed = procgen_room_seed(run_state.run_seed, run_state.biome_id,
                            run_state.room_counter);

    if (local == run_state.mission_deep_switch_cell) {
        // The deep switch controls a gate in the following graph cell. It is
        // deliberately present in every full-size dungeon, giving the long
        // route one dependable multi-room state change amid fuzzy procgen.
        room_puzzle_kind = PUZZLE_PHASE_SWITCH;
        room_puzzle_phase_bit = RUN_DEEP_PHASE_OPEN_BIT;
    } else if (local == run_state.mission_deep_gate_cell) {
        room_puzzle_kind = PUZZLE_PHASE_GATE;
        room_puzzle_phase_bit = RUN_DEEP_PHASE_OPEN_BIT;
    } else if (local == run_state.mission_waystone_cell) {
        room_puzzle_kind = puzzle_slot_kind(1);
    } else if (local == run_state.mission_trial_cell)
        room_puzzle_kind = puzzle_slot_kind(0);
    else {
        // These are the same stable spatial punctuation cells reserved by
        // the mission graph: nonlinear Rifts, named stage wings, witnesses,
        // and the optional third Warden. A disguised secret's clearing apron
        // must not erase a Mire pool, Frost vault, Temple colonnade, or other
        // lore fixture. Ordinary courts still provide ample fuzzy secrets.
        // M1 Rime chamber (Verdant Hollow) / M2 Cairn Ford (Ember Depths) /
        // M3 Kite Kennel (Frost Vault).
        if (local == rime_cell) {
            if (run_state.bosses_beaten == KT_STAGE) {
                if (kt_prepare()) {
                    room_puzzle_kind = PUZZLE_KITE_ROOM;
                    return;
                }
            } else if (run_state.bosses_beaten == RW_STAGE) {
                if (rw_prepare()) {
                    room_puzzle_kind = PUZZLE_REWRITE_ROOM;
                    return;
                }
            } else if (rime_prepare()) {
                room_puzzle_kind = PUZZLE_RIME_ROOM;
                return;
            }
        }
        if (secret_merchant_prepare_host()) return;
        if (local == 2 || local == 5 || local == 8 || local == 11
            || local == 15 || local == 17 || local == 23) return;
        // Roughly three rooms in 32 contain a true optional secret. Unlike
        // amber cracks, these use the exact ordinary wall/cairn art: only
        // experimentation reveals whether this seed wants a shot, a walk
        // through stone, or a shove. No objective or boss route uses them.
        u8 roll = (u8)(seed >> 16) & 31;
        if (roll > 2) return;
        // Four otherwise-unused dungeon-phase bits remember discoveries for
        // the current stage. Seed collisions simply make a later optional
        // cache decline to appear; they can never recreate an already-looted
        // vault for farming after backtracking.
        room_hidden_secret_bit = RUN_HIDDEN_SECRET_BIT((u8)(seed >> 24));
        if (run_state.dungeon_phase & room_hidden_secret_bit) return;
        room_hidden_secret_kind = (u8)(roll + 1);
        if (room_hidden_secret_kind == HIDDEN_SECRET_PUSH) {
            u8 i;
            floor_rect(4, 4, 6, 6);
            // Entities were selected before the puzzle pass. Do not silently
            // entomb a living enemy in the disguised 2x2 cairn; when this
            // particular procedural room already owns its center, keep the
            // newly cleared floor but decline the optional secret.
            for (i = 0; i < MAX_ENTITIES; ++i) {
                if ((entities[i].flags & EF_ACTIVE)
                    && entities[i].type == ENT_ENEMY) {
                    u8 ex = (u8)((FIX8_TO_INT(entities[i].x) + 8) >> 3);
                    u8 ey = (u8)((FIX8_TO_INT(entities[i].y) + 8) >> 3);
                    if (ex >= 5 && ex <= 8 && ey >= 5 && ey <= 8) {
                        room_hidden_secret_kind = HIDDEN_SECRET_NONE;
                        return;
                    }
                }
            }
            room_hidden_secret_x = 6; room_hidden_secret_y = 6;
            room_hidden_secret_x2 = 7; room_hidden_secret_y2 = 7;
            room_tilemap[6][6] = BGT_BLOCK;
            room_tilemap[6][7] = BGT_BLOCK_TR;
            room_tilemap[7][6] = BGT_BLOCK_BL;
            room_tilemap[7][7] = BGT_BLOCK_BR;
        } else if (seed & 0x200000UL) {
            u8 pos = (u8)(2 + ((u8)(seed >> 24) % 5));
            if (seed & 0x100000UL) pos = (u8)(pos + 9);
            room_hidden_secret_x = room_hidden_secret_x2 = 0;
            room_hidden_secret_y = pos;
            room_hidden_secret_y2 = (u8)(pos + 1);
            room_tilemap[pos][0] = room_tilemap[pos + 1][0] = BGT_WALL;
        } else {
            u8 pos = (u8)(2 + ((u8)(seed >> 24) % 6));
            if (seed & 0x100000UL) pos = (u8)(pos + 10);
            room_hidden_secret_x = pos;
            room_hidden_secret_x2 = (u8)(pos + 1);
            room_hidden_secret_y = room_hidden_secret_y2 = 0;
            room_tilemap[0][pos] = room_tilemap[0][pos + 1] = BGT_WALL;
        }
        return;
    }

    // Puzzle rooms are traversal objectives rather than extermination locks,
    // but their smaller procgen guard pack remains alive around the fixture.

    if (room_puzzle_kind == PUZZLE_PUSH_SEAL) {
        if (!puzzle_solved()) prepare_push(seed);
    } else if (room_puzzle_kind == PUZZLE_RUNE_SEQUENCE) {
        if (!puzzle_solved()) prepare_sequence(seed);
    } else if (room_puzzle_kind == PUZZLE_PRISM_TOGGLE) {
        u8 solved = puzzle_solved();
        clear_all_cairns();
        prism_prepare(seed, run_state.bosses_beaten, solved);
        room_puzzle_locked = solved ? 0 : 1;
    } else if (room_puzzle_kind == PUZZLE_SUN_LATTICE) {
        u8 solved = puzzle_solved();
        clear_all_cairns();
        sun_lattice_prepare(seed, local == run_state.mission_waystone_cell,
            solved);
        room_puzzle_locked = solved ? 0 : 1;
    } else if (room_puzzle_kind == PUZZLE_PHASE_SWITCH) {
        prepare_phase_switch(room_puzzle_phase_bit, seed);
    } else {
        prepare_phase_gate(room_puzzle_phase_bit);
    }
}

u8 puzzle_on_block_moved(u8 old_x, u8 old_y) BANKED {
    if (room_hidden_secret_kind == HIDDEN_SECRET_PUSH
        && old_x == room_hidden_secret_x && old_y == room_hidden_secret_y) {
        room_hidden_secret_kind = HIDDEN_SECRET_NONE;
        run_state.dungeon_phase |= room_hidden_secret_bit;
        room_open_secret(6, 0);
        sfx_play(SFX_PUZZLE);
        return 0; // optional discovery never clears a live combat seal
    }
    if (room_puzzle_kind != PUZZLE_PUSH_SEAL || !room_puzzle_locked) return 0;
    if (old_x != puzzle_block_x || old_y != puzzle_block_y) return 0;
    {
        // Follow the crate one tile, then repaint any socket quadrant the
        // shove floored. Only a crate seated exactly on the socket solves.
        u8 nx = old_x, ny = old_y, i, j;
        if (old_x + 1 < ROOM_W && room_tilemap[old_y][old_x + 1] == BGT_BLOCK)
            nx = (u8)(old_x + 1);
        else if (old_x && room_tilemap[old_y][old_x - 1] == BGT_BLOCK)
            nx = (u8)(old_x - 1);
        else if (old_y + 1 < ROOM_H && room_tilemap[old_y + 1][old_x] == BGT_BLOCK)
            ny = (u8)(old_y + 1);
        else if (old_y && room_tilemap[old_y - 1][old_x] == BGT_BLOCK)
            ny = (u8)(old_y - 1);
        puzzle_block_x = nx;
        puzzle_block_y = ny;
        for (j = 0; j < 2; ++j)
            for (i = 0; i < 2; ++i) {
                u8 tx = (u8)(room_socket_x + i), ty = (u8)(room_socket_y + j);
                // The shove redraw used plain terrain colours; restore the
                // gold socket on every quadrant the crate does not cover.
                if (room_tilemap[ty][tx] == BGT_FLOOR
                    || room_tilemap[ty][tx] == BGT_FLOOR3)
                    set_tile_live(tx, ty, BGT_FLOOR3, BGPAL_DOOR);
            }
        if (nx != room_socket_x || ny != room_socket_y) {
            sfx_play_rune((u8)((nx + ny) & 3));
            return 0;
        }
    }
    mark_puzzle_solved(0);
    return 1;
}

u8 puzzle_try_hidden_shot(u8 tx, u8 ty) BANKED {
    if (room_hidden_secret_kind != HIDDEN_SECRET_SHOT) return 0;
    if (!((tx == room_hidden_secret_x && ty == room_hidden_secret_y)
        || (tx == room_hidden_secret_x2 && ty == room_hidden_secret_y2)))
        return 0;
    room_hidden_secret_kind = HIDDEN_SECRET_NONE;
    run_state.dungeon_phase |= room_hidden_secret_bit;
    room_open_secret(room_hidden_secret_x, room_hidden_secret_y);
    sfx_play(SFX_PUZZLE);
    return 1;
}

u8 puzzle_chime_reveal(void) BANKED {
    u8 kind;
    if (room_hidden_secret_kind == HIDDEN_SECRET_NONE) return 0;
    kind = room_hidden_secret_kind;
    room_hidden_secret_kind = HIDDEN_SECRET_NONE;
    run_state.dungeon_phase |= room_hidden_secret_bit;
    // The disguised cairn's reward threshold is the north wall; replacing
    // its middle 2x2 body with two door tiles recreates the old confusing
    // "holes in the floor" visual. Wall secrets open where they were found.
    if (kind == HIDDEN_SECRET_PUSH) room_open_secret(6, 0);
    else room_open_secret(room_hidden_secret_x, room_hidden_secret_y);
    sfx_play(SFX_PUZZLE);
    return 1;
}

static void reset_runes(void) {
    rune_progress = 0;
    room_rune_lit_mask = 0;
    rune_paint_all();
}

static u8 update_sequence(u8 tx, u8 ty) {
    u8 i;
    u8 touched = 0xFF;
    for (i = 0; i < rune_count; ++i)
        if (tx == rune_x[i] && ty == rune_y[i]) touched = i;
    if (touched == 0xFF) {
        puzzle_contact = 0;
        return 0;
    }
    if (puzzle_contact) return 0;
    puzzle_contact = 1;
    // A confirmed note remains safe for the rest of this attempt. It still
    // voices its own stable pitch: walking over any musical plate must teach
    // the scale, even when a route naturally crosses an earlier lit note.
    for (i = 0; i < rune_progress; ++i) {
        if (touched == rune_order[i]) {
            voice_plate(touched);
            return 0;
        }
    }
    if (touched != rune_order[rune_progress]) {
        // Preserve the pressed plate's place in the ascending phrase before
        // reset_runes clears progress. Its pitch is a genuine routing hint:
        // a low note belongs earlier, while a high note belongs later.
        for (i = 0; i < rune_count; ++i)
            if (touched == rune_order[i]) break;
        reset_runes();
        // A false note is a magical trap, not merely a UI reset. Charge one
        // half-heart on every distinct wrong press—even during the recovery
        // flash—so rapid brute force cannot become free. The contact latch
        // still guarantees that standing on one rune costs exactly once.
        if (player.hp) player.hp--;
        if (player.iframes < 30) player.iframes = 30;
        hud_redraw_hp();
        // Noise carries the hit while CH1 remains free to voice the wrong
        // plate. Muting that note removed the puzzle's best learnable clue.
        sfx_play(SFX_HIT);
        voice_plate(touched);
        room_shake(1, 6);
        return 0;
    }
    rune_progress++;
    room_rune_lit_mask |= (u8)(1u << touched);
    if (rune_progress < rune_count) {
        voice_plate(touched);
        return 0;
    }
    // Atomic final note + ducked delayed fanfare. mark() re-arms the delay
    // without starting the jingle immediately.
    voice_plate_final(touched);
    mark_puzzle_solved(1);
    return 1;
}

u8 puzzle_update_player(void) BANKED {
    u8 tx = (u8)((player.x + 8) >> 3);
    u8 ty = (u8)((player.y + 12) >> 3);
    tick_rune_flash();
    rune_echo_tick();
    if (room_puzzle_kind == PUZZLE_RIME_ROOM) {
        rime_tick();
        return 0;
    }
    if (room_puzzle_kind == PUZZLE_REWRITE_ROOM) {
        rw_tick();
        return 0;
    }
    if (room_puzzle_kind == PUZZLE_KITE_ROOM) {
        kt_tick();
        return 0;
    }
    if (room_puzzle_kind == PUZZLE_RUNE_SEQUENCE && room_puzzle_locked)
        return update_sequence(tx, ty);
    if (room_puzzle_kind == PUZZLE_PHASE_SWITCH)
        rune_row_tick(tx, ty);
    if (room_puzzle_kind == PUZZLE_PRISM_TOGGLE && prism_tick()) {
        mark_puzzle_solved(0);
        return 1;
    }
    if (room_puzzle_kind == PUZZLE_SUN_LATTICE && sun_lattice_tick()) {
        mark_puzzle_solved(0);
        return 1;
    }
    return 0;
}
