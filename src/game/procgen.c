#pragma bank 4
#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "core/rng.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/spawn_reach.h"
#include "render/tiles.h"
#include "content.h"

u8 procgen_current_room_is_boss;

u32 procgen_room_seed(u32 run_seed, u8 biome_id, u8 room_counter) BANKED {
    return run_seed ^ ((u32)biome_id << 16) ^ ((u32)room_counter * 0x9E3779B9UL);
}

// All nine large bosses load their distinct 32x32 art into one shared VRAM
// slot, so the entity tile number is constant even though the silhouettes are
// not. This helper keeps that implementation detail out of spawn wiring.
u8 boss_sprite_for_stage(u8 stage) {
    stage;
    return SPR_BOSS_BIG;
}

// The boss always draws on OBJ palette slot 6; room_enter loads a stage-tinted
// palette into that slot so each stage's boss has its own colour.
u8 boss_palette_for_stage(u8 stage) {
    stage;
    return 0x06;
}

// Place player at the door opposite the one they entered from.
static void place_player_after_entry(void) {
    // Spawn just inside the door opposite the exit. The player's WALL box
    // is the feet half (x+2..x+13, y+8..y+15), so x=72 centers the body
    // on the 2-wide N/S doors (cols 9-10) and y=60 on the E/W pair
    // (rows 8-9).
    u8 dir = run_state.entered_from;
    if (dir == DIR_N)      { player.x = 72;  player.y = 112; }
    else if (dir == DIR_S) { player.x = 72;  player.y = 8;   }
    else if (dir == DIR_E) { player.x = 8;   player.y = 60;  }
    else if (dir == DIR_W) { player.x = 136; player.y = 60;  }
    else                   { player.x = 72;  player.y = 60;  }
}

// Weighted pick from this stage's roster (generated stage_pool tables;
// stage wraps with the endless theme cycle). One rng draw per pick.
static u8 pick_enemy_for_stage(u8 stage_raw) {
    u8 st = (u8)(stage_raw % N_STAGES);
    u8 r = rng_range(stage_pool_total[st]);
    u8 k, acc = 0;
    for (k = 0; k < stage_pool_n[st]; ++k) {
        acc = (u8)(acc + stage_pool_w[st][k]);
        if (r < acc) return stage_pool_ids[st][k];
    }
    return stage_pool_ids[st][0];
}

// One source for town and dungeon merchant entities. Prices differ by venue;
// visual and ware wiring do not.
static u8 spawn_shop_ware(u8 px, u8 py, u8 ware, u8 price) {
    u8 idx = pickup_spawn(PICKUP_SHOP, FIX8(px), FIX8(py));
    if (idx == 0xFF) return idx;
    entities[idx].ai_data[0] = PICKUP_SHOP;
    entities[idx].ai_data[1] = ware;
    entities[idx].ai_data[2] = price;
    entities[idx].sprite_tile = (ware == WARE_HEART) ? SPR_HEART
        : (ware == WARE_SURGE) ? SPR_SURGE_ORB : SPR_ITEM_ORB;
    entities[idx].palette = (ware == WARE_ITEM) ? 0x05
        : (ware == WARE_SURGE) ? 0x06 : 0x04;
    // Keep the stock's heart/relic sprite intact and put the dedicated gold
    // sale tag above it. This answers "can I pick this up?" before the player
    // has to walk into a ware or discover the bottom-HUD price convention.
    {
        u8 tag = pickup_spawn_shop_tag(FIX8(px), FIX8((i16)py - 12));
        if (tag != 0xFF) entities[tag].ai_data[1] = idx;
    }
    return idx;
}

// The dungeon's premium shelf is seed-stable without consuming RNG: some
// expeditions offer permanent vitality, others let a cash-rich player buy a
// short pre-boss damage/speed window. The player can read both the cyan orb
// and the dedicated lightning HUD glyph before touching either stock.
static u8 dungeon_premium_ware(void) {
    return (((u8)run_state.run_seed ^ run_state.bosses_beaten) & 1)
        ? WARE_SURGE : WARE_BIG;
}

static u8 dungeon_premium_price(u8 ware) {
    return (ware == WARE_SURGE) ? 20 : 40;
}

static void paint_shop_price(u8 tx, u8 price) {
    room_tilemap[10][tx]     = HUD_COIN;
    room_tilemap[10][tx + 1] = (price >= 10) ? (u8)(HUD_DIGIT_0 + price / 10) : HUD_BLANK;
    room_tilemap[10][tx + 2] = (u8)(HUD_DIGIT_0 + price % 10);
}

// Fixed mini-boss escorts are chosen after props have been placed. Their old
// hard-coded coordinates could land inside a seeded 2x2 crate, creating a
// sealed room with an unreachable live enemy. Pick the nearest champion-sized
// clear cell without consuming RNG, so procedural parity and room seeds stay
// stable.
static u8 escort_cell_open(u8 tx, u8 ty) {
    if (tx < 1 || ty < 1 || tx + 1 >= ROOM_W - 1 || ty + 1 >= ROOM_H - 1) return 0;
    return room_tile_walkable(room_tilemap[ty][tx])
        && room_tile_walkable(room_tilemap[ty][tx + 1])
        && room_tile_walkable(room_tilemap[ty + 1][tx])
        && room_tile_walkable(room_tilemap[ty + 1][tx + 1]);
}

// A rift is activated by the hero's feet center, but movement validates a
// 12x8px feet box.  Stamping only the glowing tile could leave its required
// 2x2 standing footprint half inside a procedurally placed pillar or crate.
// Carve a small deterministic apron so every nonlinear exit is physically
// reachable, not merely visible on the map.
static void stamp_rift_portal(u8 px, u8 py) {
    u8 x, y;
    for (y = (u8)(py - 2); y <= py; ++y)
        for (x = (u8)(px - 2); x <= px; ++x)
            room_tilemap[y][x] = BGT_FLOOR;
    room_tilemap[py][px] = BGT_PORTAL;
}

static u8 escort_cell_unoccupied(u8 tx, u8 ty) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        i16 ex, ey;
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_ENEMY) continue;
        ex = FIX8_TO_INT(entities[i].x);
        ey = FIX8_TO_INT(entities[i].y);
        if (ex < 0 || ey < 0) continue;
        {
            u8 etx = (u8)((ex + 4) >> 3);
            u8 ety = (u8)((ey + 4) >> 3);
            if (tx < (u8)(etx + 2) && (u8)(tx + 2) > etx
                && ty < (u8)(ety + 2) && (u8)(ty + 2) > ety) return 0;
        }
    }
    return 1;
}

static u8 spawn_escort_safely(u8 eid, u8 preferred_x, u8 preferred_y) {
    u8 tx, ty, best_x = 0, best_y = 0, found = 0, best_distance = 0xFF;
    for (ty = 1; ty < ROOM_H - 2; ++ty) {
        for (tx = 1; tx < ROOM_W - 2; ++tx) {
            u8 dx, dy, distance;
            if (!escort_cell_open(tx, ty) || !escort_cell_unoccupied(tx, ty)) continue;
            dx = tx > preferred_x ? (u8)(tx - preferred_x) : (u8)(preferred_x - tx);
            dy = ty > preferred_y ? (u8)(ty - preferred_y) : (u8)(preferred_y - ty);
            distance = (u8)(dx + dy);
            if (!found || distance < best_distance) {
                best_x = tx; best_y = ty; best_distance = distance; found = 1;
            }
        }
    }
    return found ? enemy_spawn(eid, best_x, best_y) : 0xFF;
}

// Layer stage-authored traversal identity over the shared reachable room
// skeleton. No RNG is consumed: the same seed remains stable when content is
// added, and door lanes remain clear. Only the first two combat rooms of each
// stage receive these stronger silhouettes, keeping shops/rest rooms safe.
static void apply_stage_archetype(u8 stage, u32 seed) {
    u8 archetype = stage_room_archetype[stage % N_STAGES];
    u8 i;
    if (archetype == STAGE_ARCH_GROVE) {
        // Grove: paired crystal thickets form four cover islands. Stage
        // palettes turn the common crystal art into luminous vegetation.
        static const u8 gx[8] = { 4, 5, 14, 15, 4, 5, 14, 15 };
        static const u8 gy[8] = { 4, 4, 4, 4, 12, 12, 12, 12 };
        for (i = 0; i < 8; ++i) {
            room_tilemap[gy[i]][gx[i]] = BGT_CRYSTAL;
        }
    } else if (archetype == STAGE_ARCH_GAUNTLET) {
        // Gauntlet: two broken magma/spike seams make lateral positioning
        // matter without blocking any route. Three-tile gaps alternate per
        // seed, and spike iframes make crossing costly rather than fatal.
        u8 gap_a = (seed & 1) ? 5 : 11;
        u8 gap_b = (gap_a == 5) ? 11 : 5;
        for (i = 3; i <= 14; ++i) {
            if (i < gap_a || i > (u8)(gap_a + 2)) {
                if (room_tile_walkable(room_tilemap[i][5]))
                    room_tilemap[i][5] = BGT_SPIKES;
            }
            if (i < gap_b || i > (u8)(gap_b + 2)) {
                if (room_tile_walkable(room_tilemap[i][14]))
                    room_tilemap[i][14] = BGT_SPIKES;
            }
        }
    } else if (archetype == STAGE_ARCH_VAULT) {
        // Vault: a broken octagonal crystal ring creates an icy central
        // arena with four broad entrances. The ring provides cover without
        // sealing the centre or any door lane; the shared seeded room shape
        // underneath still varies the space outside this authored ring.
        static const u8 vx[16] = {
            7, 8, 11, 12, 7, 8, 11, 12,
            5, 5, 5, 5, 14, 14, 14, 14
        };
        static const u8 vy[16] = {
            5, 5, 5, 5, 12, 12, 12, 12,
            6, 7, 10, 11, 6, 7, 10, 11
        };
        // This ring is the stage's authored identity, not optional
        // decoration. Shared procgen may already have a pillar at a ring
        // coordinate; overwrite it just as Mire overwrites its pool sites,
        // while the eight axial breaks retain every cardinal route.
        for (i = 0; i < 16; ++i)
            room_tilemap[vy[i]][vx[i]] = BGT_CRYSTAL;
    } else if (archetype == STAGE_ARCH_MIRE) {
        // Mire: four irregular toxic pools create island-to-island movement
        // instead of Ember's continuous seams. Their inner-corner breaks face
        // the safe central cross, so every door remains connected without
        // forcing damage. Seeded base geometry and props vary their shores.
        static const u8 mx[28] = {
            4,5,6, 4,5, 4,5,
            13,14,15, 14,15, 14,15,
            4,5, 4,5, 4,5,6,
            14,15, 14,15, 13,14,15
        };
        static const u8 my[28] = {
            4,4,4, 5,5, 6,6,
            4,4,4, 5,5, 6,6,
            11,11, 12,12, 13,13,13,
            11,11, 12,12, 13,13,13
        };
        for (i = 0; i < 28; ++i) {
            // Pools supersede the shared room skeleton at these safe sites;
            // otherwise pillar-heavy shapes can erase most of the mire.
            room_tilemap[my[i]][mx[i]] = BGT_SPIKES;
        }
    } else if (archetype == STAGE_ARCH_KEEP) {
        // Keep: two broken portcullis rows split the room into three courts.
        // Their four-tile gates sit on opposite sides, creating a readable
        // zig-zag through hard cover. Seed mirroring swaps the route without
        // changing its length or sealing any of the four door approaches.
        u8 upper_gate = (seed & 1) ? 5 : 11;
        u8 lower_gate = (u8)(16 - upper_gate);
        for (i = 4; i <= 15; ++i) {
            if (i < upper_gate || i > (u8)(upper_gate + 3))
                room_tilemap[6][i] = BGT_PILLAR;
            else
                room_tilemap[6][i] = BGT_FLOOR;
            if (i < lower_gate || i > (u8)(lower_gate + 3))
                room_tilemap[11][i] = BGT_PILLAR;
            else
                room_tilemap[11][i] = BGT_FLOOR;
        }
    } else if (archetype == STAGE_ARCH_TEMPLE) {
        // Temple: paired colonnades frame a broad north/south processional
        // aisle, while the east/west transept stays completely open. Four
        // gold-tinted crystals mark the inner court; their seeded inset gives
        // the arcade two silhouettes without changing combat clearance.
        u8 inner_l = (seed & 1) ? 7 : 6;
        // Clear the authored circulation cross before adding the arcade so a
        // shared random room shape can never contradict the temple fixture.
        for (i = 3; i <= 14; ++i) {
            room_tilemap[i][9] = BGT_FLOOR;
            room_tilemap[i][10] = BGT_FLOOR;
            if ((i > 3 && i < 7) || (i > 10 && i < 14)) {
                room_tilemap[i][5] = BGT_PILLAR;
                room_tilemap[i][14] = BGT_PILLAR;
            }
        }
        for (i = 3; i <= 16; ++i) {
            room_tilemap[8][i] = BGT_FLOOR;
            room_tilemap[9][i] = BGT_FLOOR;
        }
        room_tilemap[5][inner_l] = BGT_CRYSTAL;
        room_tilemap[5][19 - inner_l] = BGT_CRYSTAL;
        room_tilemap[12][inner_l] = BGT_CRYSTAL;
        room_tilemap[12][19 - inner_l] = BGT_CRYSTAL;
    } else if (archetype == STAGE_ARCH_BLOODMOON) {
        // Bloodmoon: four diagonal ritual cuts advance from the corners but
        // stop before the broad central cross. They read as one crimson sigil
        // while leaving every cardinal route damage-free.
        for (i = 4; i <= 6; i += 2) {
            room_tilemap[i][i] = BGT_SPIKES;
            room_tilemap[i][19 - i] = BGT_SPIKES;
            room_tilemap[17 - i][i] = BGT_SPIKES;
            room_tilemap[17 - i][19 - i] = BGT_SPIKES;
        }
    } else if (archetype == STAGE_ARCH_VOID) {
        // Void: mirrored broken arcs close around an open event horizon.
        // Alternating hard silhouettes reverse with the seed, while the
        // cardinal cross guarantees that its apparent trap always has exits.
        for (i = 4; i <= 5; ++i) {
            u8 t = ((u8)seed + i) & 1 ? BGT_PILLAR : BGT_CRYSTAL;
            room_tilemap[i - 1][i] = t;
            room_tilemap[i - 1][19 - i] = t;
            room_tilemap[17 - i][i] = t;
            room_tilemap[17 - i][19 - i] = t;
        }
        for (i = 3; i <= 16; ++i) {
            room_tilemap[8][i] = BGT_FLOOR;
            room_tilemap[9][i] = BGT_FLOOR;
            if (i <= 14) {
                room_tilemap[i][9] = BGT_FLOOR;
                room_tilemap[i][10] = BGT_FLOOR;
            }
        }
    }
}

void procgen_generate_current_room(void) BANKED {
    const biome_def_t *bio = &biomes[run_state.biome_id];
    u8 world_kind = run_state.world_mode
        ? zelda_overworlds[0].screen_grid[run_state.world_screen & 15].kind
        : ZELDA_CELL_OVERWORLD;
    u8 seed_room = run_state.world_mode
        ? (u8)(0x80 | (run_state.world_screen & 15))
        : run_state.room_counter;
    u32 seed = procgen_room_seed(run_state.run_seed, run_state.biome_id, seed_room);
    // A boss guards every Nth room until BOSSES_TO_WIN are down. Computed
    // once at function scope so door-drawing, the secret-room guard, and
    // enemy spawning all agree (a mismatch here soft-locked boss rooms).
    u8 is_boss_room = (!run_state.world_mode && run_state.room_counter > 0
        && (run_state.room_counter % BOSS_EVERY_N_ROOMS) == 0
        && (u8)(run_state.room_counter / BOSS_EVERY_N_ROOMS) > run_state.bosses_beaten) ? 1 : 0;
    procgen_current_room_is_boss = is_boss_room;
    // A village clearing follows every third dungeon: rooms 19, 37, 55...
    // It remains a pure function of room_counter, so suspend/resume and
    // backtracking regenerate the same world landmark.
    u8 is_town = (!run_state.world_mode && RUN_ROOM_IS_TOWN(run_state.room_counter)) ? 1 : 0;
    run_state_mark_visited();
    rng_seed(seed);

    bio;
    {
        u8 x, y;

        // Base: border walls + textured floor (plain / cracked / pebbled mix)
        for (y = 0; y < ROOM_H; ++y) {
            for (x = 0; x < ROOM_W; ++x) {
                if (y == 0 || y == ROOM_H - 1 || x == 0 || x == ROOM_W - 1) {
                    room_tilemap[y][x] = BGT_WALL;
                } else {
                    u8 r = rng_next_u8();
                    room_tilemap[y][x] =
                        (r < 38) ? BGT_FLOOR2 :        // ~15% cracked
                        (r < 64) ? BGT_FLOOR3 :        // ~10% pebbled
                                   BGT_FLOOR;
                }
            }
        }

        if (!is_boss_room) {
            // Doors are 2 tiles (16px) wide — hero-sized, and wide
            // enough for the feet-anchored 12px collision box.
            room_tilemap[0][9]            = BGT_DOOR;
            room_tilemap[0][10]           = BGT_DOOR;
            room_tilemap[ROOM_H - 1][9]   = BGT_DOOR;
            room_tilemap[ROOM_H - 1][10]  = BGT_DOOR;
            room_tilemap[8][0]            = BGT_DOOR;
            room_tilemap[9][0]            = BGT_DOOR;
            room_tilemap[8][ROOM_W - 1]   = BGT_DOOR;
            room_tilemap[9][ROOM_W - 1]   = BGT_DOOR;

            // Overworld screens expose only authored reciprocal graph edges.
            if (run_state.world_mode) {
                u8 edges = zelda_overworlds[0].screen_grid[run_state.world_screen & 15].edges;
                if (!(edges & 0x01)) { room_tilemap[0][9] = BGT_WALL; room_tilemap[0][10] = BGT_WALL; }
                if (!(edges & 0x02)) { room_tilemap[8][ROOM_W - 1] = BGT_WALL; room_tilemap[9][ROOM_W - 1] = BGT_WALL; }
                if (!(edges & 0x04)) { room_tilemap[ROOM_H - 1][9] = BGT_WALL; room_tilemap[ROOM_H - 1][10] = BGT_WALL; }
                if (!(edges & 0x08)) { room_tilemap[8][0] = BGT_WALL; room_tilemap[9][0] = BGT_WALL; }
            }

            // Interior obstacles. Door lanes stay clear (cols 9-11 for the
            // N/S door at col 10; rows 7-9 for the E/W door at row 8) so
            // every door remains reachable regardless of pattern.
            {
                u8 shape = (u8)rng_range(11);   // 11 interior layouts
                if (shape == 1) {
                    // Four pillars at quarter points
                    room_tilemap[4][4]   = BGT_PILLAR;
                    room_tilemap[4][15]  = BGT_PILLAR;
                    room_tilemap[13][4]  = BGT_PILLAR;
                    room_tilemap[13][15] = BGT_PILLAR;
                } else if (shape == 2) {
                    // Crystal clusters — up to 4, lanes + border excluded
                    u8 placed = 0, tries = 12;
                    while (placed < 4 && tries--) {
                        u8 cx = (u8)(2 + rng_range(ROOM_W - 4));
                        u8 cy = (u8)(2 + rng_range(ROOM_H - 4));
                        if (cx >= 9 && cx <= 11) continue;
                        if (cy >= 7 && cy <= 9)  continue;
                        room_tilemap[cy][cx] = BGT_CRYSTAL;
                        placed++;
                    }
                } else if (shape == 3) {
                    // Chunky pillar pairs in the corners
                    room_tilemap[4][4]   = BGT_PILLAR; room_tilemap[4][5]   = BGT_PILLAR;
                    room_tilemap[4][14]  = BGT_PILLAR; room_tilemap[4][15]  = BGT_PILLAR;
                    room_tilemap[13][4]  = BGT_PILLAR; room_tilemap[13][5]  = BGT_PILLAR;
                    room_tilemap[13][14] = BGT_PILLAR; room_tilemap[13][15] = BGT_PILLAR;
                } else if (shape == 4) {
                    // Inner vault: pillar ring at x 4-15 / y 4-12, with
                    // lane-wide gaps where the door lanes cross it.
                    u8 i;
                    for (i = 4; i <= 15; ++i) {
                        if (i >= 9 && i <= 11) continue;      // N/S lane gap
                        room_tilemap[4][i]  = BGT_PILLAR;
                        room_tilemap[12][i] = BGT_PILLAR;
                    }
                    for (i = 4; i <= 12; ++i) {
                        if (i >= 7 && i <= 9) continue;       // E/W lane gap
                        room_tilemap[i][4]  = BGT_PILLAR;
                        room_tilemap[i][15] = BGT_PILLAR;
                    }
                } else if (shape == 5) {
                    // Twin walls: vertical pillar runs at x=5 and x=14,
                    // broken at the E/W lane — three linked chambers.
                    u8 i;
                    for (i = 2; i <= 14; ++i) {
                        if (i >= 7 && i <= 9) continue;
                        room_tilemap[i][5]  = BGT_PILLAR;
                        room_tilemap[i][14] = BGT_PILLAR;
                    }
                } else if (shape == 6) {
                    // Diagonal crystal spurs from each corner (shootable)
                    room_tilemap[3][3]   = BGT_CRYSTAL; room_tilemap[4][4]   = BGT_CRYSTAL;
                    room_tilemap[5][5]   = BGT_CRYSTAL;
                    room_tilemap[3][16]  = BGT_CRYSTAL; room_tilemap[4][15]  = BGT_CRYSTAL;
                    room_tilemap[5][14]  = BGT_CRYSTAL;
                    room_tilemap[13][3]  = BGT_CRYSTAL; room_tilemap[12][4]  = BGT_CRYSTAL;
                    room_tilemap[11][5]  = BGT_CRYSTAL;
                    room_tilemap[13][16] = BGT_CRYSTAL; room_tilemap[12][15] = BGT_CRYSTAL;
                    room_tilemap[11][14] = BGT_CRYSTAL;
                } else if (shape == 7) {
                    // Colonnade: two pillar rows flanking the E/W lane —
                    // a great hall with cover to duck behind.
                    static const u8 col_x[6] = { 3, 5, 7, 13, 15, 17 };
                    u8 i;
                    for (i = 0; i < 6; ++i) {
                        room_tilemap[5][col_x[i]]  = BGT_PILLAR;
                        room_tilemap[11][col_x[i]] = BGT_PILLAR;
                    }
                } else if (shape == 8) {
                    // Serpentine: two staggered half-walls, N/S lane (cols
                    // 9-11) kept clear — weave an S around them.
                    u8 i;
                    for (i = 2; i <= 12; ++i)
                        if (i < 9 || i > 11) room_tilemap[5][i]  = BGT_PILLAR;
                    for (i = 7; i <= 17; ++i)
                        if (i < 9 || i > 11) room_tilemap[11][i] = BGT_PILLAR;
                } else if (shape == 9) {
                    // Pillar grid: a regular hall of columns (lanes clear).
                    static const u8 gx[4] = { 4, 8, 12, 16 };
                    u8 i;
                    for (i = 0; i < 4; ++i) {
                        room_tilemap[4][gx[i]]  = BGT_PILLAR;
                        room_tilemap[12][gx[i]] = BGT_PILLAR;
                    }
                } else if (shape == 10) {
                    // Central chamber: a pillar ring around the middle with
                    // openings at every door lane (cols 9-11, rows 7-9).
                    u8 i;
                    for (i = 6; i <= 13; ++i)
                        if (i < 9 || i > 11) {
                            room_tilemap[6][i]  = BGT_PILLAR;
                            room_tilemap[10][i] = BGT_PILLAR;
                        }
                    for (i = 6; i <= 10; ++i)
                        if (i < 7 || i > 9) {
                            room_tilemap[i][6]  = BGT_PILLAR;
                            room_tilemap[i][13] = BGT_PILLAR;
                        }
                }
                // shape 0: open room (1-in-11 — variety rules)
            }

            // Stage architecture is laid down before loose props so crates,
            // pots, and rubble respect its silhouette instead of erasing it.
            if (!is_town && !run_state.world_mode
                && ((run_state.room_counter % ROOMS_PER_STAGE) == 1
                    || (run_state.room_counter % ROOMS_PER_STAGE) == 2)) {
                apply_stage_archetype(run_state.bosses_beaten, seed);
            }

            // Rubble decoration (walkable) — 3 scatter spots
            {
                u8 i;
                for (i = 0; i < 3; ++i) {
                    u8 rx = (u8)(2 + rng_range(ROOM_W - 4));
                    u8 ry = (u8)(2 + rng_range(ROOM_H - 4));
                    if (room_tilemap[ry][rx] == BGT_FLOOR) {
                        room_tilemap[ry][rx] = BGT_RUBBLE;
                    }
                }
            }

            // Pushable crates — 0-2 per room, hero-sized (2x2 tiles),
            // kept clear of the door lanes so they never wall a door.
            {
                u8 nb = (u8)(rng_next_u8() % 3);
                u8 i;
                for (i = 0; i < nb; ++i) {
                    u8 bx = (u8)(3 + rng_range(ROOM_W - 6));
                    u8 by = (u8)(3 + rng_range(ROOM_H - 6));
                    if (bx >= 8 && bx <= 11) continue;   // cols bx..bx+1 vs lane 9-11
                    if (by >= 6 && by <= 9)  continue;   // rows by..by+1 vs lane 7-9
                    if (bx + 1 >= ROOM_W - 1 || by + 1 >= ROOM_H - 1) continue;
                    if (room_tilemap[by][bx] == BGT_FLOOR
                        && room_tilemap[by][bx + 1] == BGT_FLOOR
                        && room_tilemap[by + 1][bx] == BGT_FLOOR
                        && room_tilemap[by + 1][bx + 1] == BGT_FLOOR) {
                        room_tilemap[by][bx]         = BGT_BLOCK;
                        room_tilemap[by][bx + 1]     = BGT_BLOCK_TR;
                        room_tilemap[by + 1][bx]     = BGT_BLOCK_BL;
                        room_tilemap[by + 1][bx + 1] = BGT_BLOCK_BR;
                    }
                }
            }

            // Pressure-plate puzzle. A deterministic subset of ordinary
            // rooms gets a visible plate and a nearby crate. Either the hero
            // or the crate can press it; room.c consumes it and pays a cache.
            // Towns are redrawn below and never inherit dungeon puzzles.
            if (!is_town && run_state.room_counter > 0
                && !run_state.world_mode
                && (run_state.room_counter % 7) == 0) {
                // Coordinate comes from the already-derived room seed rather
                // than consuming RNG draws; adding puzzle content must not
                // reshuffle every later decoration/enemy in the same seed.
                u8 sx = (seed & 1) ? 7 : 12;
                u8 sy = (seed & 2) ? 5 : 11;
                if (room_tile_walkable(room_tilemap[sy][sx])) {
                    room_tilemap[sy][sx] = BGT_SWITCH;
                    // Guarantee one pushable block in the same local puzzle
                    // when the 2x2 footprint is clear.
                    if (room_tile_walkable(room_tilemap[sy][sx - 2])
                        && room_tile_walkable(room_tilemap[sy][sx - 1])
                        && room_tile_walkable(room_tilemap[sy + 1][sx - 2])
                        && room_tile_walkable(room_tilemap[sy + 1][sx - 1])) {
                        room_tilemap[sy][sx - 2] = BGT_BLOCK;
                        room_tilemap[sy][sx - 1] = BGT_BLOCK_TR;
                        room_tilemap[sy + 1][sx - 2] = BGT_BLOCK_BL;
                        room_tilemap[sy + 1][sx - 1] = BGT_BLOCK_BR;
                    }
                }
            }

            // A seed-stable nonlinear pair inside this stage. It starts after
            // the tutorial stage and can never target a boss, town, or region.
            if (!is_town && run_state.room_counter > 6
                && !run_state.world_mode
                && ((run_state.room_counter % ROOMS_PER_STAGE) == 2
                    || (run_state.room_counter % ROOMS_PER_STAGE) == 4)) {
                u8 px = (seed & 4) ? 5 : 14;
                u8 py = (seed & 8) ? 4 : 12;
                stamp_rift_portal(px, py);
            }

            // Entrances and vault staircases are explicit graph fixtures.
            if (run_state.world_mode
                && (world_kind == ZELDA_CELL_DUNGEON_ENTRANCE
                    || world_kind == ZELDA_CELL_VAULT
                    || zelda_overworlds[0].screen_grid[run_state.world_screen & 15].stairs != ID_NONE_U8)) {
                room_tilemap[8][10] = BGT_PORTAL;
            }


            // Secret cracked wall — ~half of rooms hide one on a border
            // (never on a door or the E/W door row). Rendered on its own
            // glowing palette so it's obviously shootable.
            if ((rng_next_u8() & 0x01) == 0) {
                u8 side = (u8)(rng_next_u8() & 0x03);
                u8 pos;
                if (side == 0) {          // north wall
                    pos = (u8)(2 + rng_range(ROOM_W - 4));
                    if (pos != 9 && pos != 10) room_tilemap[0][pos] = BGT_WALL_CRACK;
                } else if (side == 1) {   // south wall
                    pos = (u8)(2 + rng_range(ROOM_W - 4));
                    if (pos != 9 && pos != 10) room_tilemap[ROOM_H - 1][pos] = BGT_WALL_CRACK;
                } else if (side == 2) {   // west wall
                    pos = (u8)(2 + rng_range(ROOM_H - 4));
                    if (pos != 8 && pos != 9) room_tilemap[pos][0] = BGT_WALL_CRACK;
                } else {                  // east wall
                    pos = (u8)(2 + rng_range(ROOM_H - 4));
                    if (pos != 8 && pos != 9) room_tilemap[pos][ROOM_W - 1] = BGT_WALL_CRACK;
                }
            }

            // Spike patch — ~1/4 of rooms grow a 2x2 hazard cluster in the
            // interior, clear of the door lanes. One roll + two position
            // draws (mirror this exactly in the Rust procgen reference).
            if ((rng_next_u8() & 0x03) == 0) {
                u8 spx = (u8)(3 + rng_range(ROOM_W - 7));
                u8 spy = (u8)(3 + rng_range(ROOM_H - 7));
                if (!(spx >= 8 && spx <= 11) && !(spy >= 6 && spy <= 9)) {
                    u8 sdx, sdy;
                    for (sdy = 0; sdy < 2; ++sdy)
                        for (sdx = 0; sdx < 2; ++sdx) {
                            u8 ft = room_tilemap[spy + sdy][spx + sdx];
                            if (ft == BGT_FLOOR || ft == BGT_FLOOR2 || ft == BGT_FLOOR3)
                                room_tilemap[spy + sdy][spx + sdx] = BGT_SPIKES;
                        }
                }
            }

            // Breakable pots — 0-2 clay pots on interior floor, clear of
            // door lanes. Shoot them for loot. One count draw + 2 per pot
            // (mirror exactly in the Rust procgen reference).
            {
                u8 np = (u8)(rng_next_u8() % 3);
                u8 i;
                for (i = 0; i < np; ++i) {
                    u8 ptx = (u8)(2 + rng_range(ROOM_W - 4));
                    u8 pty = (u8)(2 + rng_range(ROOM_H - 4));
                    if (ptx >= 9 && ptx <= 11) continue;
                    if (pty >= 7 && pty <= 9)  continue;
                    {
                        u8 ft = room_tilemap[pty][ptx];
                        if (ft == BGT_FLOOR || ft == BGT_FLOOR2 || ft == BGT_FLOOR3)
                            room_tilemap[pty][ptx] = BGT_POT;
                    }
                }
            }

        }
    }

    // Riftwild is genuinely outdoors, not a dungeon graph with a different
    // name: tree line, grass, worn trails, and landmark wells replace every
    // inherited brick/prop tile while preserving authored reciprocal edges.
    if (run_state.world_mode) {
        u8 x, y;
        u8 edges = zelda_overworlds[0].screen_grid[run_state.world_screen & 15].edges;
        for (y = 0; y < ROOM_H; ++y)
            for (x = 0; x < ROOM_W; ++x)
                room_tilemap[y][x] = (y == 0 || y == ROOM_H - 1
                    || x == 0 || x == ROOM_W - 1) ? BGT_TREE : BGT_GRASS;
        // Trails reach only real graph exits, meeting at the clearing center.
        if (edges & 0x01) for (y = 0; y <= 8; ++y)
            room_tilemap[y][9] = room_tilemap[y][10] = BGT_PATH;
        if (edges & 0x04) for (y = 8; y < ROOM_H; ++y)
            room_tilemap[y][9] = room_tilemap[y][10] = BGT_PATH;
        if (edges & 0x08) for (x = 0; x <= 10; ++x)
            room_tilemap[8][x] = room_tilemap[9][x] = BGT_PATH;
        if (edges & 0x02) for (x = 9; x < ROOM_W; ++x)
            room_tilemap[8][x] = room_tilemap[9][x] = BGT_PATH;
        if (edges & 0x01) room_tilemap[0][9] = room_tilemap[0][10] = BGT_DOOR;
        if (edges & 0x04) room_tilemap[ROOM_H-1][9] = room_tilemap[ROOM_H-1][10] = BGT_DOOR;
        if (edges & 0x08) room_tilemap[8][0] = room_tilemap[9][0] = BGT_DOOR;
        if (edges & 0x02) room_tilemap[8][ROOM_W-1] = room_tilemap[9][ROOM_W-1] = BGT_DOOR;
        // Seed-stable groves provide outdoor cover without consuming RNG.
        room_tilemap[3 + (seed & 3)][3] = BGT_TREE;
        room_tilemap[11 + ((seed >> 2) & 1)][16] = BGT_TREE;
        room_tilemap[3][6] = BGT_TREE;
        room_tilemap[4][16] = BGT_TREE;
        room_tilemap[12][4] = BGT_TREE;
        room_tilemap[13][13] = BGT_TREE;
        if (world_kind == ZELDA_CELL_DUNGEON_ENTRANCE
            || world_kind == ZELDA_CELL_VAULT
            || zelda_overworlds[0].screen_grid[run_state.world_screen & 15].stairs != ID_NONE_U8)
            room_tilemap[8][10] = BGT_PORTAL;
    }

    // Three-screen village: arrival square branches west to the elder/forge
    // quarter and east to the market; only its north gate continues the run.
    if (is_town) {
        u8 x, y;
        for (y = 0; y < ROOM_H; ++y)
            for (x = 0; x < ROOM_W; ++x)
                room_tilemap[y][x] = (y == 0 || y == ROOM_H - 1
                    || x == 0 || x == ROOM_W - 1) ? BGT_FENCE : BGT_GRASS;
        // Close the generic four exits, then expose only authored town edges.
        if (run_state.world_return_screen == TOWN_ARRIVAL) {
            room_tilemap[0][9] = room_tilemap[0][10] = BGT_DOOR;
            room_tilemap[8][0] = room_tilemap[9][0] = BGT_DOOR;
            room_tilemap[8][ROOM_W - 1] = room_tilemap[9][ROOM_W - 1] = BGT_DOOR;
            // Fountain and processional road make arrival unmistakably civic.
            for (y = 1; y < ROOM_H - 1; ++y)
                room_tilemap[y][9] = room_tilemap[y][10] = BGT_PATH;
            for (x = 1; x < ROOM_W - 1; ++x)
                room_tilemap[8][x] = room_tilemap[9][x] = BGT_PATH;
            room_tilemap[7][8] = room_tilemap[7][11] = BGT_CRYSTAL;
            room_tilemap[10][8] = room_tilemap[10][11] = BGT_CRYSTAL;
            room_tilemap[3][3] = room_tilemap[3][16] = BGT_TREE;
            room_tilemap[13][3] = room_tilemap[13][16] = BGT_TREE;
        } else if (run_state.world_return_screen == TOWN_MARKET) {
            room_tilemap[8][0] = room_tilemap[9][0] = BGT_DOOR;
            // Two roofed stall rows around an open shopping lane.
            for (x = 3; x <= 16; ++x) {
                if (x == 6 || x == 10 || x == 14) continue;
                room_tilemap[4][x] = BGT_ROOF;
                room_tilemap[12][x] = BGT_ROOF;
            }
            for (x = 1; x <= 10; ++x)
                room_tilemap[8][x] = room_tilemap[9][x] = BGT_PATH;
        } else {
            room_tilemap[8][ROOM_W - 1] = room_tilemap[9][ROOM_W - 1] = BGT_DOOR;
            // Forge and apothecary houses face a small shared courtyard.
            for (x = 2; x <= 7; ++x) {
                room_tilemap[3][x] = room_tilemap[4][x] = BGT_ROOF;
                room_tilemap[11][x + 10] = room_tilemap[12][x + 10] = BGT_ROOF;
            }
            room_tilemap[5][4] = room_tilemap[5][5] = BGT_DOOR;
            room_tilemap[10][14] = room_tilemap[10][15] = BGT_DOOR;
            for (x = 9; x < ROOM_W - 1; ++x)
                room_tilemap[8][x] = room_tilemap[9][x] = BGT_PATH;
        }
    }

    // Clear entity table — fresh enemies per room
    entity_init_all();

    // Player position FIRST so spawn-avoidance checks the real tile
    place_player_after_entry();

    // The stage objective is progression-critical. Reserve its real pickup
    // before this room's optional enemy, shop, and decoration spawns can fill
    // the 32-slot table; later room orchestration calls are idempotent.
    room_spawn_progression_fixture();

    // Secret treasure room: no enemies, loot piled in the middle. Always
    // clear the flag (else it leaks into every future room). Only take the
    // early-return when this is NOT also a boss room — otherwise the sealed,
    // door-less boss layout would have no boss to spawn = unrecoverable.
    if (run_state.secret_pending) {
        run_state.secret_pending = 0;
        if (!is_boss_room) {
            u8 i;
            // The vault: a shootable crystal ring guards the hoard —
            // crack it open or slip around the corner gaps.
            for (i = 7; i <= 12; ++i) {
                room_tilemap[5][i]  = BGT_CRYSTAL;
                room_tilemap[11][i] = BGT_CRYSTAL;
            }
            room_tilemap[7][6]  = BGT_CRYSTAL; room_tilemap[9][6]  = BGT_CRYSTAL;
            room_tilemap[7][13] = BGT_CRYSTAL; room_tilemap[9][13] = BGT_CRYSTAL;
            // The hoard: hearts, a stat item, a coin shower, and a
            // 50% chance of a weapon orb to reroute the build.
            pickup_spawn(PICKUP_HEART_HALF, FIX8(72), FIX8(56));
            pickup_spawn(PICKUP_HEART_HALF, FIX8(88), FIX8(56));
            pickup_spawn(PICKUP_COIN_5,     FIX8(72), FIX8(72));
            pickup_spawn(PICKUP_COIN_5,     FIX8(88), FIX8(72));
            pickup_spawn(PICKUP_COIN_1,     FIX8(64), FIX8(64));
            pickup_spawn(PICKUP_COIN_1,     FIX8(96), FIX8(64));
            pickup_spawn(PICKUP_COIN_1,     FIX8(80), FIX8(48));
            pickup_spawn_item((u8)(10 + rng_range(10)), FIX8(80), FIX8(64));
            if (rng_next_u8() & 1) {
                u8 w = pickup_weapon_from_roll(rng_range(pickup_weapon_count()));
                if (w == player.starter_weapon) w = pickup_next_weapon(w);
                pickup_spawn_weapon(w, FIX8(80), FIX8(80));
            }
            sfx_play(SFX_CLEAR);   // secret-found fanfare
            player.iframes = 60;
            return;
        }
        // Boss room: fall through to spawn the boss below.
    }

    {
        u8 is_miniboss = run_state.world_mode
            ? (world_kind == ZELDA_CELL_BOSS)
            : ((!is_boss_room && (run_state.room_counter % ROOMS_PER_STAGE) == 3) ? 1 : 0);
        u8 is_shop     = (!is_boss_room && !is_miniboss
                          && (run_state.room_counter % ROOMS_PER_STAGE) == 4) ? 1 : 0;
        // Sanctuary: the room right before every stage boss. No enemies and
        // a guaranteed full blessing, so each escalating colossus tests the
        // build rather than leftover attrition from the preceding rooms.
        u8 is_rest     = (!is_boss_room
                          && !run_state.world_mode
                          && (run_state.room_counter % ROOMS_PER_STAGE) == 5) ? 1 : 0;

        if (is_town) {
            if (run_state.world_return_screen == TOWN_ARRIVAL) {
                pickup_spawn_villager(FIX8(80), FIX8(64));
                pickup_spawn_cartographer(FIX8(48), FIX8(64));
                pickup_spawn_waykeeper(FIX8(80), FIX8(24));
            } else if (run_state.world_return_screen == TOWN_MARKET) {
                pickup_spawn_merchant(FIX8(80), FIX8(40));
                spawn_shop_ware(48, 72, WARE_HEART, 5);
                spawn_shop_ware(80, 72, WARE_ITEM, 20);
                spawn_shop_ware(112, 72, WARE_BIG, 35);
                // A village stop is an intentional build choice, not just a
                // refill. The far shelf makes the temporary attack-speed and
                // damage burst reliably purchasable before the next dungeon.
                spawn_shop_ware(144, 72, WARE_SURGE, 20);
                paint_shop_price(16, 20);
            } else {
                pickup_spawn_smith(FIX8(40), FIX8(48));
                pickup_spawn_apothecary(FIX8(120), FIX8(96));
                spawn_shop_ware(40, 80, WARE_FORGE, 30);
                spawn_shop_ware(120, 64, WARE_RUNE, 30);
            }
            player.iframes = 60;
            return;
        }

        if (run_state.world_mode
            && world_kind == ZELDA_CELL_DUNGEON_ENTRANCE) {
            player.iframes = 60;
            return;
        }

        if (run_state.world_mode && world_kind == ZELDA_CELL_VAULT) {
            pickup_spawn_item((u8)(10 + rng_range(10)), FIX8(80), FIX8(64));
            pickup_spawn(PICKUP_COIN_5, FIX8(64), FIX8(72));
            pickup_spawn(PICKUP_COIN_5, FIX8(96), FIX8(72));
            player.iframes = 60;
            return;
        }

        if (is_rest) {
            // Crystal shrine: four pylons around the room's heart, all
            // outside the door lanes (cols 9-11 / rows 7-9 stay clear)
            room_tilemap[6][7]   = BGT_CRYSTAL; room_tilemap[6][12]  = BGT_CRYSTAL;
            room_tilemap[10][7]  = BGT_CRYSTAL; room_tilemap[10][12] = BGT_CRYSTAL;
            player.hp = player.hp_max;
            player.mp = player.mp_max;
            player.iframes = 60;
            return;
        }

        if (is_boss_room) {
            // EVERY stage ends with a LARGE (32x32) boss. Power clamps at
            // stage 8 (40 + 9*22 would overflow u8 -> a 4 HP boss); the
            // SKIN cycles all nine colossi forever in endless descent.
            u8 stage = run_state.bosses_beaten;
            u8 pow  = (stage < 9) ? stage : 8;
            u8 skin = (u8)(stage % 9);
            {
                u8 idx = enemy_spawn(ENEMY_STONE_SENTINEL, (ROOM_W / 2) - 2, (ROOM_H / 2) - 2);
                if (idx != 0xFF) {
                    entities[idx].sprite_tile = boss_sprite_for_stage(skin);
                    entities[idx].palette     = boss_palette_for_stage(skin);
                    entities[idx].hitbox      = (u8)0xFF;
                    entities[idx].ai_data[3]  = 1;              // giant flag
                    entities[idx].ai_data[2]  = skin;          // boss attack pattern
                    // A stage transition must never resolve into an instant
                    // ring on the hero's arrival tile. The boss still closes
                    // and keeps its full HP/damage/pattern, but this 0.8s
                    // opening telegraph gives the player one readable beat
                    // to choose a lane before the first bullet wall.
                    entities[idx].ai_data[1]  = 48;
                    // HP is one byte. The final 216 bonus plus the 50 HP
                    // base used to wrap to 10, making the finale trivial.
                    if (stage_boss_hp[pow] > (u8)(255 - entities[idx].hp))
                        entities[idx].hp = 255;
                    else
                        entities[idx].hp = (u8)(entities[idx].hp
                            + stage_boss_hp[pow]);
                    entities[idx].damage = (u8)(entities[idx].damage
                        + stage_boss_dmg[pow]);
                }
            }
        } else if (is_miniboss) {
            // MINI-BOSS: a beefed 16x16 Sentinel + a small escort. Tougher than
            // a normal room, a step below the stage boss.
            u8 stage = run_state.bosses_beaten;
            {
                u8 idx = enemy_spawn(ENEMY_STONE_SENTINEL, (ROOM_W / 2) - 1, 3);
                if (idx != 0xFF) {
                    // Silhouette comes from the generated stage table —
                    // ONE source shared with tiles_load_miniboss, so art and
                    // palette can't drift apart. HP power clamps (u8 overflow).
                    static const u8 mb_pal[5] = { 0x06, 0x07, 0x00, 0x04, 0x03 };
                    u8 mb_pow = (stage < 9) ? stage : 8;
                    u8 mb_var = stage_mb_variant[stage % 9];
                    entities[idx].sprite_tile = SPR_BOSS;
                    entities[idx].palette     = mb_pal[mb_var];
                    entities[idx].hitbox      = (u8)0xEE;
                    // ai_data[2] = variant → boss_tick picks the matching
                    // attack archetype (0 Sentinel / 1 Orc / 2 Skeleton).
                    entities[idx].ai_data[2]  = mb_var;
                    entities[idx].hp = (u8)(entities[idx].hp + (u8)(mb_pow * 12));
                }
            }
            // two escorts drawn from the stage roster
            {
                u8 e;
                for (e = 0; e < 2; ++e) {
                    u8 eid = pick_enemy_for_stage(stage);
                    spawn_escort_safely(eid, (u8)(4 + e * 11), (u8)(ROOM_H - 4));
                }
            }
        } else if (is_shop) {
            // MERCHANT room: three wares, no enemies. The premium shelf is
            // seed-stable: a permanent Iron Heart or a cheap, temporary Surge.
            {
                u8 premium = dungeon_premium_ware();
                pickup_spawn_merchant(FIX8(80), FIX8(40));
                spawn_shop_ware(56, 64, WARE_HEART, 10);
                spawn_shop_ware(80, 64, WARE_ITEM, 25);
                spawn_shop_ware(104, 64, premium, dungeon_premium_price(premium));
                // Price tags painted on the floor under each ware:
                // [coin][d][d], amber, walkable. Wares sit at tile y=8;
                // tags at y=10 leave a step of space.
                paint_shop_price(6, 10);
                paint_shop_price(9, 25);
                paint_shop_price(12, dungeon_premium_price(premium));
            }
        } else {
            // Enemy count scales with depth. One lone crawler made too many
            // early rooms read as a target practice hall; start at two bodies
            // so positioning and the champion's B kit matter immediately.
            // Keep the existing shallow ramp rather than raising every HP
            // value into a sponge fight.
            u8 depth_bonus = (u8)(run_state.room_counter / 6);
            u8 enemy_count = (u8)(2 + rng_range(4) + (depth_bonus > 2 ? 2 : depth_bonus));
            u8 ptx = (u8)(player.x >> 3);
            u8 pty = (u8)(player.y >> 3);
            u8 spawned = 0;
            u8 attempts = 0;
            mark_spawn_reachable();
            // `enemy_count` used to mean attempts, not bodies: a pillar or
            // entrance-safety rejection could quietly turn the intended
            // two-enemy floor back into one crawler. Retry a bounded four
            // sites per desired body; this remains deterministic and never
            // risks an unbounded procgen loop in a dense room archetype.
            while (spawned < enemy_count && attempts < (u8)(enemy_count << 2)) {
                u8 tx = (u8)(2 + rng_range(ROOM_W - 4));
                u8 ty = (u8)(2 + rng_range(ROOM_H - 4));
                attempts++;
                if (!(room_tilemap[ty][tx] & 0x80)) continue;
                {
                    u8 dx = (tx > ptx) ? (u8)(tx - ptx) : (u8)(ptx - tx);
                    u8 dy = (ty > pty) ? (u8)(ty - pty) : (u8)(pty - ty);
                    if (dx < 3 && dy < 3) continue;
                }
                {
                    // Roster comes from the generated per-stage pool —
                    // designed in content/src/stages.rs, not hard-coded here.
                    u8 eid = pick_enemy_for_stage(run_state.bosses_beaten);
                    {
                        u8 idx = enemy_spawn(eid, tx, ty);
                        // Every regular foe survives one more starter hit;
                        // deeper stages then gain another HP per two bosses.
                        // This makes enemy AI matter without turning the run
                        // into a sponge fight. It consumes NO RNG, so procgen
                        // C<->Rust parity (draw order) is untouched.
                        if (idx != 0xFF) {
                            u8 st = run_state.bosses_beaten;
                            if (st > 24) st = 24;
                            entities[idx].hp =
                                (u8)(entities[idx].hp + 1 + (u8)(st >> 1));
                        }
                        // ~12% spawn ELITE: boss-palette glow, double HP,
                        // +1 damage, EF_ELITE flag (combat pays the bonus).
                        if (idx != 0xFF && rng_next_u8() < 31) {
                            entities[idx].flags  |= EF_ELITE;
                            entities[idx].palette = 0x06;
                            entities[idx].hp      = (u8)(entities[idx].hp << 1);
                            entities[idx].damage  = (u8)(entities[idx].damage + 1);
                        }
                        if (idx != 0xFF) spawned++;
                    }
                }
            }
            clear_spawn_reachable();
        }
    }

    player.iframes = 60;    // brief invuln on room entry
}
