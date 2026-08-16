#pragma bank 6

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/pickup.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
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

static u8 puzzle_block_x;
static u8 puzzle_block_y;
static u8 puzzle_contact;
static u8 rune_progress;
static u8 rune_order[3];

static const u8 rune_x[3] = { 5, 10, 14 };
static const u8 rune_y[3] = { 8, 5, 10 };
static const u8 rune_orders[18] = {
    0,1,2, 0,2,1, 1,0,2, 1,2,0, 2,0,1, 2,1,0
};

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
    if (local == 0) return run_state.room_counter ? 1 : 0;
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

static void mark_puzzle_solved(void) {
    u8 cell = run_state_dungeon_cell();
    if (cell == run_state.mission_trial_cell)
        run_state.dungeon_puzzles |= RUN_TRIAL_BIT;
    else if (cell == run_state.mission_waystone_cell)
        run_state.dungeon_puzzles |= RUN_WAYSTONE_BIT;
    room_puzzle_locked = 0;
    sfx_play(SFX_PUZZLE);
    room_shake(1, 18);
    // Every mandatory puzzle pays one physical tool charge. The seed and
    // local cell choose the implement, so routing changes the tactical Pack
    // without turning tools into generic random enemy trash.
    pickup_spawn_item((u8)(22 + ((u8)run_state.run_seed
        + run_state_dungeon_cell()) % 3), player.x, player.y);
}

static void kill_puzzle_room_hostiles(void) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY)
            entity_kill(i);
    }
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

static void prepare_push(u32 seed) {
    u8 x = (seed & 1) ? 6 : 12;
    u8 y = (seed & 2) ? 5 : 10;
    clear_all_cairns();
    floor_rect((u8)(x - 3), (u8)(y - 2), 8, 6);
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
    order = (u8)(folded % 6);
    for (i = 0; i < 3; ++i) {
        floor_rect((u8)(rune_x[i] - 1), (u8)(rune_y[i] - 1), 3, 3);
        room_tilemap[rune_y[i]][rune_x[i]] = BGT_SWITCH;
        rune_order[i] = rune_orders[(u8)(order * 3 + i)];
    }
    rune_progress = 0;
    room_puzzle_locked = 1;
}

static void prepare_phase_switch(u8 bit) {
    // This room can own W/E/S graph exits. A stage archetype may leave its
    // central switch visible while a 12px hero still cannot reach the east
    // Sigil threshold through the surrounding pillars. Carve explicit
    // body-width cardinal lanes before placing the switch so every authored
    // graph edge remains physically usable, not merely present in the border.
    floor_rect(1, 7, ROOM_W - 2, 3);
    floor_rect(9, 1, 3, ROOM_H - 2);
    room_tilemap[8][10] = BGT_SWITCH;
    room_puzzle_visual_y = 8;
    room_puzzle_phase_bit = bit;
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

void puzzle_prepare_room(void) BANKED {
    u8 local;
    u8 family;
    u32 seed;
    room_puzzle_kind = PUZZLE_NONE;
    room_puzzle_locked = 0;
    room_puzzle_visual_y = 0xFF;
    room_puzzle_phase_bit = RUN_PHASE_OPEN_BIT;
    room_hidden_secret_kind = HIDDEN_SECRET_NONE;
    room_hidden_secret_bit = 0;
    puzzle_contact = 0;
    if (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter)
        || procgen_current_room_is_boss || run_state.secret_pending
        || run_state_is_shop() || run_state_is_sanctuary()) return;

    local = run_state_dungeon_local();
    family = (u8)(run_state.bosses_beaten % 3);
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
        // Roomier mid/late dungeons get a second mechanical beat before the
        // back half. Keep it within the persisted eight-bit puzzle mask and
        // alternate its vocabulary so it does not merely repeat room one.
        room_puzzle_kind = ((family + (u8)seed) & 1)
            ? PUZZLE_PUSH_SEAL : PUZZLE_RUNE_SEQUENCE;
    } else if (local == run_state.mission_trial_cell)
        room_puzzle_kind = (family & 1)
            ? PUZZLE_RUNE_SEQUENCE : PUZZLE_PUSH_SEAL;
    else {
        // These are the same stable spatial punctuation cells reserved by
        // the mission graph: nonlinear Rifts, named stage wings, witnesses,
        // and the optional third Warden. A disguised secret's clearing apron
        // must not erase a Mire pool, Frost vault, Temple colonnade, or other
        // lore fixture. Ordinary courts still provide ample fuzzy secrets.
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

    // Puzzle rooms are alternatives to extermination rooms. Enemies may be
    // rolled by the shared generator, but this authored room role removes
    // them while preserving Sigils, loot, and every other procgen fixture.
    kill_puzzle_room_hostiles();

    if (room_puzzle_kind == PUZZLE_PUSH_SEAL) {
        if (!puzzle_solved()) prepare_push(seed);
    } else if (room_puzzle_kind == PUZZLE_RUNE_SEQUENCE) {
        if (!puzzle_solved()) prepare_sequence(seed);
    } else if (room_puzzle_kind == PUZZLE_PHASE_SWITCH) {
        prepare_phase_switch(room_puzzle_phase_bit);
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
    mark_puzzle_solved();
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
    u8 i;
    for (i = 0; i < 3; ++i)
        set_tile_live(rune_x[i], rune_y[i], BGT_SWITCH, BGPAL_DOOR);
    rune_progress = 0;
}

static u8 update_sequence(u8 tx, u8 ty) {
    u8 i;
    u8 touched = 0xFF;
    for (i = 0; i < 3; ++i)
        if (tx == rune_x[i] && ty == rune_y[i]) touched = i;
    if (touched == 0xFF) {
        puzzle_contact = 0;
        return 0;
    }
    if (puzzle_contact) return 0;
    puzzle_contact = 1;
    if (touched != rune_order[rune_progress]) {
        reset_runes();
        sfx_play(SFX_HURT);
        room_shake(1, 6);
        return 0;
    }
    set_tile_live(tx, ty, BGT_FLOOR2, BGPAL_CRYSTAL);
    sfx_play_rune(rune_progress);
    rune_progress++;
    if (rune_progress < 3) return 0;
    mark_puzzle_solved();
    return 1;
}

static void update_phase_switch(u8 tx, u8 ty) {
    u8 attr;
    if (tx != 10 || ty != 8) {
        puzzle_contact = 0;
        return;
    }
    if (puzzle_contact) return;
    puzzle_contact = 1;
    run_state.dungeon_phase ^= room_puzzle_phase_bit;
    attr = (run_state.dungeon_phase & room_puzzle_phase_bit)
        ? BGPAL_CRYSTAL : BGPAL_CRACK;
    set_tile_live(10, 8, BGT_SWITCH, attr);
    sfx_play(SFX_PUZZLE);
    room_shake(1, 12);
}

u8 puzzle_update_player(void) BANKED {
    u8 tx = (u8)((player.x + 8) >> 3);
    u8 ty = (u8)((player.y + 12) >> 3);
    if (room_puzzle_kind == PUZZLE_RUNE_SEQUENCE && room_puzzle_locked)
        return update_sequence(tx, ty);
    if (room_puzzle_kind == PUZZLE_PHASE_SWITCH)
        update_phase_switch(tx, ty);
    return 0;
}
