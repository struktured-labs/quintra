#pragma bank 3
#include <gb/gb.h>
#include <gb/cgb.h>
#include "audio/sfx.h"
#include "game/map.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

BANKREF(map_enter)

static const u16 map_pal_base[4] = {
    BGR555(1,3,2), BGR555(7,16,10), BGR555(16,23,12), BGR555(30,31,24)
};

// The glyphs intentionally share one abstract tile language, so color must
// carry their semantic priority. The former loader assigned different palette
// slots but filled every slot with map_pal, making HERE/SIGIL/BOSS identical
// on real CGB output despite correct tile attributes.
static const u16 map_pal_sigil[4] = {
    BGR555(1,3,2), BGR555(8,4,14), BGR555(20,8,27), BGR555(31,14,31)
};
static const u16 map_pal_here[4] = {
    BGR555(1,3,2), BGR555(2,10,14), BGR555(5,23,25), BGR555(12,31,31)
};
static const u16 map_pal_boss[4] = {
    BGR555(1,3,2), BGR555(14,3,1), BGR555(27,7,1), BGR555(31,20,4)
};

static u8 map_attr(u8 tile) {
    if (tile >= BGT_MAP_NODE_HERE_BASE
        && tile < BGT_MAP_NODE_HERE_BASE + 4) return BGPAL_DOOR;
    if ((tile >= BGT_MAP_NODE_BOSS_BASE
            && tile < BGT_MAP_NODE_BOSS_BASE + 4)
        || (tile >= BGT_MAP_NODE_TRIAL_BASE
            && tile < BGT_MAP_NODE_TRIAL_BASE + 4)) return BGPAL_CRACK;
    if (tile >= BGT_MAP_NODE_SIGIL_BASE
        && tile < BGT_MAP_NODE_SIGIL_BASE + 4) return BGPAL_CRYSTAL;
    if (tile == BGT_WALL || tile == BGT_PILLAR || tile == BGT_ROOF
        || tile == BGT_FENCE || tile == BGT_TREE
        || tile == BGT_WILD_STONE) return BGPAL_WALL;
    if (tile == BGT_CRYSTAL || tile == BGT_PORTAL
        || tile == BGT_WILD_FLOWER || tile == BGT_WILD_WATER)
        return BGPAL_CRYSTAL;
    if (tile == BGT_MAP_SIGIL || tile == BGT_MAP_RIFT) return BGPAL_CRYSTAL;
    if (tile == BGT_MAP_HERE) return BGPAL_DOOR;
    if (tile == BGT_MAP_BOSS) return BGPAL_CRACK;
    if (tile == BGT_DOOR || tile == BGT_SWITCH || tile == BGT_WILD_STUMP)
        return BGPAL_DOOR;
    if (tile == BGT_WALL_CRACK || tile == BGT_SPIKES) return BGPAL_CRACK;
    return BGPAL_FLOOR;
}

static void map_put(u8 x, u8 y, u8 tile) {
    u8 attr = map_attr(tile);
    VBK_REG = 0; set_bkg_tiles(x, y, 1, 1, &tile);
    VBK_REG = 1; set_bkg_tiles(x, y, 1, 1, &attr);
    VBK_REG = 0;
}

static void map_clear_tiles(void) {
    u8 row[20];
    u8 attrs[20];
    u8 x, y;
    for (x = 0; x < 20; ++x) { row[x] = BGT_VOID; attrs[x] = BGPAL_FLOOR; }
    for (y = 0; y < 18; ++y) {
        VBK_REG = 0; set_bkg_tiles(0, y, 20, 1, row);
        VBK_REG = 1; set_bkg_tiles(0, y, 20, 1, attrs);
    }
    VBK_REG = 0;
}

// Keep the screen self-identifying at native 160x144 resolution. The former
// font-based Select page truncated; these three authored tiles preserve the
// compact graphical Compass while making the diagram immediately read as a
// map in dungeons, villages, and Riftwild alike.
static void draw_map_heading(void) {
    map_put(8, 0, BGT_AREA_M);
    map_put(9, 0, BGT_AREA_A);
    map_put(10, 0, BGT_MAP_LABEL_P);
}

static void map_room_box(u8 x, u8 y, u8 center) {
    u8 dx, dy;
    for (dy = 0; dy < 3; ++dy) {
        for (dx = 0; dx < 3; ++dx) {
            u8 edge = (dx == 0 || dx == 2 || dy == 0 || dy == 2);
            map_put((u8)(x + dx), (u8)(y + dy), edge ? BGT_WALL : BGT_FLOOR);
        }
    }
    map_put((u8)(x + 1), (u8)(y + 1), center);
}

// A dungeon room is one 16×16 self-bordered glyph. The earlier 8×8 cells
// technically described the graph but left most of the LCD empty and read
// like circuit pads. Four quadrants make each room unmistakably square while
// the one-tile gaps retain a compact 6×5 Zelda-style pocket map.
// knowledge: 0 hidden, 1 hollow frontier, 2 explored/objective.
static void map_dungeon_node(u8 x, u8 y, u8 icon, u8 knowledge) {
    u8 base = BGT_MAP_NODE_ROOM_BASE;
    if (!knowledge) return;
    if (knowledge == 1) base = BGT_MAP_NODE_UNKNOWN_BASE;
    else if (icon == BGT_MAP_HERE) base = BGT_MAP_NODE_HERE_BASE;
    else if (icon == BGT_MAP_BOSS) base = BGT_MAP_NODE_BOSS_BASE;
    else if (icon == BGT_MAP_SIGIL) base = BGT_MAP_NODE_SIGIL_BASE;
    else if (icon == BGT_SWITCH) base = BGT_MAP_NODE_TRIAL_BASE;
    map_put(x, y, base);
    map_put((u8)(x + 1), y, (u8)(base + 1));
    map_put(x, (u8)(y + 1), (u8)(base + 2));
    map_put((u8)(x + 1), (u8)(y + 1), (u8)(base + 3));
}

// A pocket map should grow from the route the player actually walked, not
// present the entire dungeon as a dim circuit diagram on the first screen.
// Keep one layer of adjacent exits visible as hollow frontier rooms. This
// communicates "you can go here next" without revealing the rest of the
// generated maze or making explored and unexplored paths compete visually.
static u8 dungeon_cell_frontier(u8 cell, u8 size) {
    // Frontier squares must reflect every real door. In particular, local
    // room one is now a legible junction: the objective wing continues east
    // while the deeper route branches south. Showing both hollow squares is
    // the visual proof that the pocket map describes space rather than a
    // disguised room counter.
    if (cell && run_state_dungeon_cell_seen((u8)(cell - 1))) return 1;
    if ((u8)(cell + 1) < size
        && run_state_dungeon_cell_seen((u8)(cell + 1))) return 1;
    if (cell == 1 && run_state_dungeon_cell_seen(10)) return 1;
    if (cell == 10 && run_state_dungeon_cell_seen(1)) return 1;
    return 0;
}

static void draw_dungeon_legend(void) {
    static const u8 you[3] = {
        BGT_MAP_LABEL_Y, BGT_MAP_LABEL_O, BGT_MAP_LABEL_U
    };
    static const u8 sigil[5] = {
        BGT_MAP_LABEL_S, BGT_MAP_LABEL_I, BGT_MAP_LABEL_G,
        BGT_MAP_LABEL_I, BGT_MAP_LABEL_L
    };
    static const u8 boss[4] = {
        BGT_MAP_LABEL_B, BGT_MAP_LABEL_O, BGT_MAP_LABEL_S, BGT_MAP_LABEL_S
    };
    u8 i;
    map_put(1, 16, BGT_MAP_HERE);
    for (i = 0; i < 3; ++i) map_put((u8)(2 + i), 16, you[i]);
    map_put(7, 16, BGT_MAP_SIGIL);
    for (i = 0; i < 5; ++i) map_put((u8)(8 + i), 16, sigil[i]);
    map_put(15, 16, BGT_MAP_BOSS);
    for (i = 0; i < 4; ++i) map_put((u8)(16 + i), 16, boss[i]);
    if (run_state.bosses_beaten > 0) {
        map_put(7, 17, BGT_MAP_RIFT);
        map_put(8, 17, BGT_MAP_LABEL_R);
        map_put(9, 17, BGT_MAP_LABEL_I);
        map_put(10, 17, BGT_MAP_LABEL_F);
        map_put(11, 17, BGT_MAP_LABEL_T);
    }
}

static void draw_world_grid(void) {
    static const u8 wx[4] = { 1, 4, 7, 10 };
    static const u8 wy[4] = { 4, 7, 10, 13 };
    u8 r, c;
    for (r = 0; r < 4; ++r) {
        for (c = 0; c < 4; ++c) {
            u8 cell = (u8)(r * 4 + c);
            u8 x = wx[c];
            u8 y = wy[r];
            u8 seen = (run_state.world_seen & (u16)(1u << cell)) ? 1 : 0;
            u8 icon = BGT_MAP_ROOM;
            const zelda_screen_t *z = &zelda_overworlds[0].screen_grid[cell];
            // Use the dungeon Compass's single-glyph language here too. The
            // former 3x3 terrain thumbnails filled nearly the whole LCD yet
            // still left a new player guessing which colored square was the
            // onward gate. This compact field reads as an actual 4x4 graph
            // and leaves room for an in-cartridge legend.
            if (cell == (run_state.world_screen & 15)) icon = BGT_MAP_HERE;
            else if (cell == RIFTWELL_WORLD_SCREEN)
                icon = BGT_MAP_RIFT;
            else if (z->kind == ZELDA_CELL_DUNGEON_ENTRANCE)
                icon = BGT_PORTAL;
            else if (z->kind == ZELDA_CELL_VAULT)
                icon = BGT_MAP_SIGIL;
            else if (z->kind == ZELDA_CELL_BOSS)
                icon = BGT_MAP_BOSS;
            else if (z->kind == ZELDA_CELL_CAVE_ENTRANCE)
                icon = BGT_MAP_RIFT;
            // The fixed 4x4 lattice is safe knowledge; show unseen positions
            // as dim hollow cells so a partial route reads as a square grid.
            // Identity and connectivity remain fogged until actually visited.
            map_put(x, y, seen ? icon : BGT_MAP_UNKNOWN);
            if (c < 3 && (run_state.world_seen & (u16)(1u << cell))
                && (run_state.world_seen & (u16)(1u << (cell + 1)))
                && (zelda_overworlds[0].screen_grid[cell].edges & 2)) {
                map_put((u8)(x + 1), y, BGT_MAP_PATH_H);
                map_put((u8)(x + 2), y, BGT_MAP_PATH_H);
            }
            if (r < 3 && (run_state.world_seen & (u16)(1u << cell))
                && (run_state.world_seen & (u16)(1u << (cell + 4)))
                && (zelda_overworlds[0].screen_grid[cell].edges & 4)) {
                map_put(x, (u8)(y + 1), BGT_MAP_PATH_V);
                map_put(x, (u8)(y + 2), BGT_MAP_PATH_V);
            }
        }
    }
}

// The right-hand legend is deliberately part of the cartridge rendering,
// not README lore. It explains the four symbols that affect a Riftwild route;
// treasure vaults retain the already-familiar violet Sigil diamond.
static void draw_world_legend(void) {
    static const u8 you[3] = {
        BGT_MAP_LABEL_Y, BGT_MAP_LABEL_O, BGT_MAP_LABEL_U
    };
    static const u8 gate[4] = {
        BGT_AREA_G, BGT_AREA_A, BGT_MAP_LABEL_T, BGT_AREA_E
    };
    static const u8 rift[4] = {
        BGT_MAP_LABEL_R, BGT_MAP_LABEL_I,
        BGT_MAP_LABEL_F, BGT_MAP_LABEL_T
    };
    static const u8 boss[4] = {
        BGT_MAP_LABEL_B, BGT_MAP_LABEL_O,
        BGT_MAP_LABEL_S, BGT_MAP_LABEL_S
    };
    u8 i;
    map_put(13, 4, BGT_MAP_HERE);
    for (i = 0; i < 3; ++i) map_put((u8)(14 + i), 4, you[i]);
    map_put(13, 7, BGT_PORTAL);
    for (i = 0; i < 4; ++i) map_put((u8)(14 + i), 7, gate[i]);
    map_put(13, 10, BGT_MAP_RIFT);
    for (i = 0; i < 4; ++i) map_put((u8)(14 + i), 10, rift[i]);
    map_put(13, 13, BGT_MAP_BOSS);
    for (i = 0; i < 4; ++i) map_put((u8)(14 + i), 13, boss[i]);
}

static void draw_dungeon_grid(void) {
    //  0 - 1 - 2 - 3 - 4 - 5
    //                      |
    // 11 -10 - 9 - 8 - 7 - 6
    // |
    // 12 -13 -14 -15 -16 -17
    //                      |
    // 23 -22 -21 -20 -19 -18
    // |
    // 24 -25 -26 -27 -28 -29
    // The fixed 6×5 abstract lattice exposes the stage's eventual footprint.
    // Every row owns the guaranteed winding spine. The opening objective wing
    // creates one large readable loop, and only real connections appear here.
    static const u8 gx[MAX_DUNGEON_CELLS] = {
        1, 4, 7, 10, 13, 16,
        16, 13, 10, 7, 4, 1,
        1, 4, 7, 10, 13, 16,
        16, 13, 10, 7, 4, 1,
        1, 4, 7, 10, 13, 16
    };
    static const u8 gy[MAX_DUNGEON_CELLS] = {
        1, 1, 1, 1, 1, 1,
        4, 4, 4, 4, 4, 4,
        7, 7, 7, 7, 7, 7,
        10, 10, 10, 10, 10, 10,
        13, 13, 13, 13, 13, 13
    };
    u8 i, j;
    u8 size = run_state_dungeon_size();
    u8 here = run_state_dungeon_cell();
    u8 warden_done = (run_state.dungeon_puzzles
        & RUN_WARDEN_BOON_BIT) ? 1 : 0;
    u8 waystone_done = (run_state.dungeon_puzzles
        & RUN_WAYSTONE_BIT) ? 1 : 0;
    u8 deep_warden_done = (run_state.dungeon_phase
        & RUN_DEEP_WARDEN_BIT) ? 1 : 0;
    u8 sigil_done = (run_state.rift_sigils
        & RUN_STAGE_SIGIL_BIT(run_state.bosses_beaten)) ? 1 : 0;
    u8 next_trial = 0xFF;
    if (sigil_done && !warden_done) next_trial = 3;
    else if (warden_done && size >= 12 && !waystone_done) {
        next_trial = 7;
    } else if (warden_done && waystone_done
        && size >= 14 && !deep_warden_done) next_trial = 9;
    for (i = 0; i < size; ++i) {
        u8 seen = run_state_dungeon_cell_seen(i);
        u8 knowledge = seen ? 2 : dungeon_cell_frontier(i, size);
        u8 icon = (i == here) ? BGT_MAP_HERE
            : (i == (u8)(size - 1) ? BGT_MAP_BOSS : BGT_MAP_ROOM);
        // Reaching the sanctuary reveals the adjacent boss threshold even
        // before it is crossed. The amber danger node is the map equivalent
        // of Zelda's compass hint and matches the marked in-room boss doors.
        if (i == (u8)(size - 1)
            && run_state_dungeon_cell_seen((u8)(size - 2))) {
            knowledge = 2;
        }
        // Put the objective in the room that actually owns it. The older
        // free-floating center marker looked like decoration, so players
        // could reach the sanctuary without realizing which room held the
        // required Rift Sigil.
        if (i == 2 && i != here)
            icon = BGT_MAP_SIGIL;
        // Each completed fixture reveals exactly one next trial. The switch
        // glyph distinguishes the Waystone puzzle from amber Warden fights;
        // late maps therefore teach the route without exposing unrelated
        // procedural rooms or returning to a truncated text page.
        if (i == next_trial && i != here) {
            icon = BGT_SWITCH;
            knowledge = 2;
        }
        map_dungeon_node(gx[i], gy[i], icon, knowledge);
    }
    // Draw only real reciprocal maze edges that touch explored knowledge.
    // A bright segment joins two known rooms; a subdued segment points from
    // the walked route to its one-room frontier. Deeper links remain blank,
    // so each SELECT press shows travel history instead of a solved circuit.
    // The boss threshold remains the one deliberate adjacent reveal.
    for (i = 0; i < size; ++i) {
        u8 a_seen = run_state_dungeon_cell_seen(i);
        for (j = (u8)(i + 1); j < size; ++j) {
            u8 b_seen = run_state_dungeon_cell_seen(j);
            u8 adjacent = (gy[i] == gy[j]
                    && (gx[i] + 3 == gx[j] || gx[j] + 3 == gx[i]))
                || (gx[i] == gx[j]
                    && (gy[i] + 3 == gy[j] || gy[j] + 3 == gy[i]));
            if (i == (u8)(size - 1)
                && run_state_dungeon_cell_seen((u8)(size - 2))) {
                a_seen = 1;
            }
            if (j == (u8)(size - 1)
                && run_state_dungeon_cell_seen((u8)(size - 2))) {
                b_seen = 1;
            }
            if (next_trial != 0xFF) {
                if (i == next_trial) a_seen = 1;
                if (j == next_trial) b_seen = 1;
            }
            if (!adjacent || !run_state_dungeon_cells_connected(i, j))
                continue;
            if (!a_seen && !b_seen) continue;
            if (gy[i] == gy[j]) {
                u8 left = gx[i] < gx[j] ? gx[i] : gx[j];
                u8 right = gx[i] > gx[j] ? gx[i] : gx[j];
                u8 tile = (a_seen && b_seen)
                    ? BGT_MAP_PATH_H : BGT_MAP_PATH_H_DIM;
                u8 p;
                for (p = (u8)(left + 2); p < right; ++p)
                    map_put(p, (u8)(gy[i] + 1), tile);
            } else {
                u8 top = gy[i] < gy[j] ? gy[i] : gy[j];
                u8 bottom = gy[i] > gy[j] ? gy[i] : gy[j];
                u8 tile = (a_seen && b_seen)
                    ? BGT_MAP_PATH_V : BGT_MAP_PATH_V_DIM;
                u8 p;
                for (p = (u8)(top + 2); p < bottom; ++p)
                    map_put((u8)(gx[i] + 1), p, tile);
            }
        }
    }
    // After the tutorial dungeon, local rooms 2 and 8 own a reversible rift
    // well. Explicit stage starts make those the same Compass cells in every
    // dungeon. Reveal one violet end-cap when its room is known;
    // once both are seen, the completed diagonal makes the nonlinear shortcut
    // explicit without pretending it is a cardinal hallway.
    if (run_state.bosses_beaten > 0) {
        if (run_state_dungeon_cell_seen(2)) map_put(9, 3, BGT_MAP_RIFT);
        if (run_state_dungeon_cell_seen(8)) map_put(9, 4, BGT_MAP_RIFT);
    }
    draw_dungeon_legend();
}

// Towns are a fixed, legible respite between procedural regions. Unlike a
// dungeon's fogged graph, show all three civic nodes at once: their routes
// are safe information, and the player should never mistake a village for a
// single merchant room.  The centre icon moves with the hero; roof, crystal,
// and door respectively mean craft quarter, market, and onward gate.
static void draw_town_grid(void) {
    static const u8 tx[3] = { 2, 8, 14 };
    static const u8 ty[3] = { 8, 8, 8 };
    static const u8 icon[3] = { BGT_ROOF, BGT_FLOOR3, BGT_CRYSTAL };
    static const u8 forge[5] = {
        BGT_AREA_F, BGT_AREA_O, BGT_AREA_R, BGT_AREA_G, BGT_AREA_E
    };
    static const u8 village[7] = {
        BGT_AREA_V, BGT_AREA_I, BGT_AREA_L, BGT_AREA_L,
        BGT_AREA_A, BGT_AREA_G, BGT_AREA_E
    };
    static const u8 market[6] = {
        BGT_AREA_M, BGT_AREA_A, BGT_AREA_R,
        BGT_AREA_K, BGT_AREA_E, BGT_AREA_T
    };
    // Local IDs follow travel dispatch (arrival=0, market=1, quarter=2),
    // whereas the visual order is quarter, arrival, market.
    static const u8 plaza_node[3] = { 1, 2, 0 };
    u8 plaza = run_state.world_return_screen;
    u8 here;
    u8 i;
    if (plaza > TOWN_QUARTER) plaza = TOWN_ARRIVAL;
    here = plaza_node[plaza];
    for (i = 0; i < 3; ++i) {
        map_room_box(tx[i], ty[i], i == here ? BGT_SWITCH : icon[i]);
    }
    // East/west civic lanes and the north route back into the next dungeon.
    for (i = 0; i < 3; ++i) {
        map_put((u8)(5 + i), 9, BGT_FLOOR2);
        map_put((u8)(11 + i), 9, BGT_FLOOR2);
    }
    map_put(9, 4, BGT_DOOR);
    map_put(9, 5, BGT_FLOOR2);
    map_put(9, 6, BGT_FLOOR2);
    map_put(9, 7, BGT_FLOOR2);
    // The former roof/crystal shorthand still asked a new player to guess
    // which civic branch was the Forge or Market. Reuse the already-loaded
    // in-play landmark alphabet beneath the compact graph; the centre label
    // sits one row lower so all three words remain visually separated.
    for (i = 0; i < 5; ++i) map_put((u8)(1 + i), 13, forge[i]);
    for (i = 0; i < 7; ++i) map_put((u8)(7 + i), 15, village[i]);
    for (i = 0; i < 6; ++i) map_put((u8)(14 + i), 13, market[i]);
}

void map_enter(void) {
    u8 is_town = RUN_ROOM_IS_TOWN(run_state.room_counter) ? 1 : 0;
    DISPLAY_OFF; HIDE_SPRITES; HIDE_WIN;
    palette_bg_load(BGPAL_FLOOR, map_pal_base);
    palette_bg_load(BGPAL_WALL, map_pal_base);
    palette_bg_load(BGPAL_CRYSTAL, map_pal_sigil);
    palette_bg_load(BGPAL_DOOR, map_pal_here);
    palette_bg_load(BGPAL_CRACK, map_pal_boss);
    palette_bg_load(7, map_pal_base);
    if (run_state.world_mode) {
        tiles_load_map_bg(); tiles_load_area_labels(); map_clear_tiles();
        draw_map_heading();
        draw_world_grid();
        draw_world_legend();
        SHOW_BKG; DISPLAY_ON;
        return;
    }
    if (is_town) {
        tiles_load_map_bg(); tiles_load_area_labels(); map_clear_tiles();
        draw_map_heading();
        draw_town_grid();
        SHOW_BKG; DISPLAY_ON;
        return;
    }
    tiles_load_map_bg(); tiles_load_area_labels(); map_clear_tiles();
    draw_map_heading();
    draw_dungeon_grid();
    SHOW_BKG; DISPLAY_ON;
}
void map_exit(void) {}
screen_id_t map_tick(u8 keys, u8 pressed) {
    keys;
    if (pressed & (J_SELECT | J_B | J_START)) {
        sfx_play(SFX_COIN); room_request_resume(); return SCREEN_ROOM;
    }
    return SCREEN_SELF;
}
void map_draw(void) {}
