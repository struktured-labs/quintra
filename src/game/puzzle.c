#pragma bank 6

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"

u8 room_puzzle_kind;
u8 room_puzzle_locked;
u8 room_puzzle_visual_y;

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
    if (local == 3) return 1;
    if (local >= 4) return 0;
    chosen = (u8)(1 + ((run_state.run_seed
        ^ (u32)(run_state.bosses_beaten * 0x5D)) & 1));
    return (local == chosen) ? 1 : 0;
}

static u8 puzzle_solved(void) {
    return (run_state.dungeon_puzzles
        & (u8)(1u << run_state_dungeon_cell())) ? 1 : 0;
}

static void mark_puzzle_solved(void) {
    run_state.dungeon_puzzles |= (u8)(1u << run_state_dungeon_cell());
    room_puzzle_locked = 0;
    sfx_play(SFX_PUZZLE);
    room_shake(1, 18);
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
    set_bkg_tiles(x, y, 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(x, y, 1, 1, &attr);
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

static void prepare_phase_switch(void) {
    // This room can own W/E/S graph exits. A stage archetype may leave its
    // central switch visible while a 12px hero still cannot reach the east
    // Sigil threshold through the surrounding pillars. Carve explicit
    // body-width cardinal lanes before placing the switch so every authored
    // graph edge remains physically usable, not merely present in the border.
    floor_rect(1, 7, ROOM_W - 2, 3);
    floor_rect(9, 1, 3, ROOM_H - 2);
    room_tilemap[8][10] = BGT_SWITCH;
    room_puzzle_visual_y = 8;
}

static void prepare_phase_gate(void) {
    u8 x;
    // The reciprocal graph enters local room 2 through its west/east lane.
    // Keep that body-width arrival and the mandatory Sigil north of the
    // barrier; the paired switch controls the south branch instead.
    room_puzzle_visual_y = 11;
    for (x = 2; x < ROOM_W - 2; ++x)
        room_tilemap[11][x] = (run_state.dungeon_phase & RUN_PHASE_OPEN_BIT)
            ? BGT_FLOOR2 : BGT_PILLAR;
    room_puzzle_locked = (run_state.dungeon_phase & RUN_PHASE_OPEN_BIT) ? 0 : 1;
}

void puzzle_prepare_room(void) BANKED {
    u8 local;
    u8 family;
    u32 seed;
    room_puzzle_kind = PUZZLE_NONE;
    room_puzzle_locked = 0;
    room_puzzle_visual_y = 0xFF;
    puzzle_contact = 0;
    if (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter)
        || procgen_current_room_is_boss) return;

    local = run_state_dungeon_local();
    family = (u8)(run_state.bosses_beaten % 3);
    seed = procgen_room_seed(run_state.run_seed, run_state.biome_id,
                            run_state.room_counter);

    if (local == 7 && run_state_dungeon_size() >= 12) {
        // Roomier mid/late dungeons get a second mechanical beat before the
        // back half. Keep it within the persisted eight-bit puzzle mask and
        // alternate its vocabulary so it does not merely repeat room one.
        room_puzzle_kind = ((family + (u8)seed) & 1)
            ? PUZZLE_PUSH_SEAL : PUZZLE_RUNE_SEQUENCE;
    } else if (local == 1 && family == 0) room_puzzle_kind = PUZZLE_PUSH_SEAL;
    else if (local == 1 && family == 1) room_puzzle_kind = PUZZLE_RUNE_SEQUENCE;
    else if (local == 1 && family == 2) room_puzzle_kind = PUZZLE_PHASE_SWITCH;
    else if (local == 2 && family == 2) room_puzzle_kind = PUZZLE_PHASE_GATE;
    else return;

    // Puzzle rooms are alternatives to extermination rooms. Enemies may be
    // rolled by the shared generator, but this authored room role removes
    // them while preserving Sigils, loot, and every other procgen fixture.
    kill_puzzle_room_hostiles();

    if (room_puzzle_kind == PUZZLE_PUSH_SEAL) {
        if (!puzzle_solved()) prepare_push(seed);
    } else if (room_puzzle_kind == PUZZLE_RUNE_SEQUENCE) {
        if (!puzzle_solved()) prepare_sequence(seed);
    } else if (room_puzzle_kind == PUZZLE_PHASE_SWITCH) {
        prepare_phase_switch();
    } else {
        prepare_phase_gate();
    }
}

u8 puzzle_on_block_moved(u8 old_x, u8 old_y) BANKED {
    if (room_puzzle_kind != PUZZLE_PUSH_SEAL || !room_puzzle_locked) return 0;
    if (old_x != puzzle_block_x || old_y != puzzle_block_y) return 0;
    mark_puzzle_solved();
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
    run_state.dungeon_phase ^= RUN_PHASE_OPEN_BIT;
    attr = (run_state.dungeon_phase & RUN_PHASE_OPEN_BIT)
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
