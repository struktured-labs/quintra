#pragma bank 7
#include <gb/gb.h>
#include <gb/cgb.h>
#include "audio/sfx.h"
#include "game/companion.h"
#include "game/dungeon_director.h"
#include "game/map.h"
#include "game/law_lock.h"
#include "game/mission_graph.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/secret_merchant.h"
#include "game/powerup.h"
#include "game/riftwild_den.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"
#include "game/map_marks.h"
#include "game/riftwild_mission.h"

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
// Doors and caches keep the cool landmark color. The player marker owns a
// separate lime/white palette below: sharing cyan made the old arrow look
// like another route instruction instead of an unmistakable "you are here."
static const u16 map_pal_landmark[4] = {
    BGR555(1,3,2), BGR555(2,10,14), BGR555(5,23,25), BGR555(12,31,31)
};
static const u16 map_pal_player[4] = {
    BGR555(1,3,2), BGR555(2,10,4), BGR555(8,27,8), BGR555(29,31,24)
};
static const u16 map_pal_boss[4] = {
    BGR555(1,3,2), BGR555(14,3,1), BGR555(27,7,1), BGR555(31,20,4)
};
static u8 map_attr(u8 tile) {
    if (tile == BGT_WALL || tile == BGT_PILLAR || tile == BGT_ROOF
        || tile == BGT_FENCE || tile == BGT_TREE
        || tile == BGT_WILD_STONE) return BGPAL_WALL;
    if (tile == BGT_CRYSTAL || tile == BGT_PORTAL
        || tile == BGT_WILD_FLOWER || tile == BGT_WILD_WATER)
        return BGPAL_CRYSTAL;
    if (tile == BGT_MAP_SIGIL || tile == BGT_MAP_RIFT
        || (tile >= BGT_MAP_BIG_GOAL
            && tile < BGT_MAP_BIG_GOAL + 4)) return BGPAL_CRYSTAL;
    if (tile == BGT_MAP_CACHE
        || (tile >= BGT_MAP_BIG_CACHE
            && tile < BGT_MAP_BIG_CACHE + 4)) return BGPAL_DOOR;
    if (tile == BGT_MAP_SHOP
        || (tile >= BGT_MAP_BIG_SHOP
            && tile < BGT_MAP_BIG_SHOP + 4)) return 5;
    if (tile == BGT_MAP_HERE
        || (tile >= BGT_MAP_BIG_HERE
            && tile < BGT_MAP_BIG_HERE + 4)) return 7;
    if (tile == BGT_MAP_BOSS
        || (tile >= BGT_MAP_BIG_BOSS
            && tile < BGT_MAP_BIG_BOSS + 4)) return BGPAL_CRACK;
    if (tile == BGT_DOOR || tile == BGT_SWITCH || tile == BGT_WILD_STUMP)
        return BGPAL_DOOR;
    if (tile == BGT_WALL_CRACK || tile == BGT_SPIKES) return BGPAL_CRACK;
    return BGPAL_FLOOR;
}

static void map_put_attr(u8 x, u8 y, u8 tile, u8 attr) {
    VBK_REG = 0; set_bkg_tiles(x, y, 1, 1, &tile);
    VBK_REG = 1; set_bkg_tiles(x, y, 1, 1, &attr);
    VBK_REG = 0;
}

static void map_put(u8 x, u8 y, u8 tile) {
    map_put_attr(x, y, tile, map_attr(tile));
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
    if (run_state.world_mode)
        map_put_attr(5, 0, RUN_RIFTWILD_IS_HOLLOW()
            ? BGT_AREA_H : BGT_AREA_W,
            RUN_RIFTWILD_IS_HOLLOW() ? BGPAL_CRACK : BGPAL_DOOR);
    map_put(8, 0, BGT_AREA_M);
    map_put(9, 0, BGT_AREA_A);
    map_put(10, 0, BGT_MAP_LABEL_P);
}

static void draw_ask_prompt(void) {
    u8 kind;
    u8 pal;
    if (!companion_discovered()) return;
    kind = companion_active_kind();
    pal = companion_ask_ready() ? (kind == COMPANION_HEARTH ? BGPAL_CRACK
        : kind == COMPANION_AETHER ? BGPAL_CRYSTAL : BGPAL_DOOR) : BGPAL_WALL;
    // Red ASK restores health, violet restores magic, and cyan scouts the
    // adjacent route. The word dims while its twenty-second cooldown runs.
    map_put_attr(14, 0, BGT_AREA_A, pal);
    map_put_attr(16, 0, BGT_AREA_A, pal);
    map_put_attr(17, 0, BGT_MAP_LABEL_S, pal);
    map_put_attr(18, 0, BGT_AREA_K, pal);
}

// Dungeon screenshots and deep-test states need immediate campaign context.
// Keep the heading tile-native and compact: "S7 MAP" identifies the current
// procedural stage without taking any room away from the 6x5 graph or
// returning to the old truncated prose page.
static void draw_dungeon_heading(void) {
    u8 stage = (u8)(run_state.bosses_beaten + 1);
    if (stage > 9) stage = 9;
    map_put(6, 0, BGT_MAP_LABEL_S);
    map_put(7, 0, (u8)(HUD_DIGIT_0 + stage));
    map_put(9, 0, BGT_AREA_M);
    map_put(10, 0, BGT_AREA_A);
    map_put(11, 0, BGT_MAP_LABEL_P);
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

static void map_big_node(u8 x, u8 y, u8 base) {
    map_put(x, y, base);
    map_put((u8)(x + 1), y, (u8)(base + 1));
    map_put(x, (u8)(y + 1), (u8)(base + 2));
    map_put((u8)(x + 1), (u8)(y + 1), (u8)(base + 3));
}

static void draw_world_grid(void) {
    static const u8 wx[6] = { 1, 3, 5, 7, 9, 11 };
    static const u8 wy[6] = { 2, 4, 6, 8, 10, 12 };
    u8 r, c;
    u8 active_gate = run_state_riftwild_gate_screen();
    u8 here = riftwild_field_screen();
    for (r = 0; r < ZELDA_WORLD_H; ++r) {
        for (c = 0; c < ZELDA_WORLD_W; ++c) {
            u8 cell = (u8)(r * ZELDA_WORLD_W + c);
            u8 x = wx[c];
            u8 y = wy[r];
            u8 seen = run_state_world_cell_seen(cell);
            u8 icon = BGT_MAP_ROOM;
            const zelda_screen_t *z = &zelda_overworlds[0].screen_grid[cell];
            // Thirty-six nodes fit because each one is already a complete
            // scrolling field. The graph therefore communicates geographic
            // scale without returning to tiny terrain screenshots or text.
            if (cell == here) icon = BGT_MAP_HERE;
            else if (cell == RIFTWELL_WORLD_SCREEN)
                icon = BGT_MAP_RIFT;
            else if (z->kind == ZELDA_CELL_DUNGEON_ENTRANCE)
                icon = (cell == active_gate) ? BGT_PORTAL : BGT_MAP_ROOM;
            else if (z->kind == ZELDA_CELL_VAULT)
                icon = BGT_MAP_SIGIL;
            else if (z->kind == ZELDA_CELL_BOSS)
                icon = BGT_MAP_BOSS;
            else if (z->kind == ZELDA_CELL_CAVE_ENTRANCE)
                icon = BGT_MAP_RIFT;
            // The fixed 6x6 lattice is safe knowledge; show unseen positions
            // as dim hollow cells so a partial route reads as a square grid.
            // Identity and connectivity remain fogged until actually visited.
            if (seen) icon = riftwild_den_map_icon(cell,
                map_world_shop_icon(cell, icon));
            // The Warden (then the woken gate) is marked once earned, even
            // through fog, so the Compass always shows the next step.
            icon = riftwild_compass_goal_icon(cell,
                seen ? icon : BGT_MAP_UNKNOWN);
            // A Chime-heard den is a dim chest until it is actually found.
            if (icon & 0x80) map_put_attr(x, y, (u8)(icon & 0x7F), BGPAL_WALL);
            else map_put(x, y, icon);
            if (c + 1 < ZELDA_WORLD_W && seen
                && run_state_world_cell_seen((u8)(cell + 1))
                && (zelda_overworlds[0].screen_grid[cell].edges & 2)) {
                map_put((u8)(x + 1), y, BGT_MAP_PATH_H);
            }
            if (r + 1 < ZELDA_WORLD_H && seen
                && run_state_world_cell_seen((u8)(cell + ZELDA_WORLD_W))
                && (zelda_overworlds[0].screen_grid[cell].edges & 4)) {
                map_put(x, (u8)(y + 1), BGT_MAP_PATH_V);
            }
        }
    }
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
    // Two tiles per room plus one tile per link fills a 17x14 region: nearly
    // the complete LCD instead of a miniature left-hand diagram. The same
    // 6x5 topology stays compressed and abstract, but a room is now a
    // glance-readable 16x16 node with a large YOU, GOAL, or BOSS mark.
    static const u8 gx[MAX_DUNGEON_CELLS] = {
        1, 4, 7, 10, 13, 16,
        16, 13, 10, 7, 4, 1,
        1, 4, 7, 10, 13, 16,
        16, 13, 10, 7, 4, 1,
        1, 4, 7, 10, 13, 16
    };
    static const u8 gy[MAX_DUNGEON_CELLS] = {
        2, 2, 2, 2, 2, 2,
        5, 5, 5, 5, 5, 5,
        8, 8, 8, 8, 8, 8,
        11, 11, 11, 11, 11, 11,
        14, 14, 14, 14, 14, 14
    };
    u8 i, j;
    u8 size = run_state_dungeon_size();
    u8 here = run_state_dungeon_cell();
    u8 next_trial = dungeon_director_goal_cell();
    u8 route_dir = dungeon_director_direction_from(here);
    u8 route_next = (route_dir == DIR_NONE) ? 0xFF
        : run_state_dungeon_cell_neighbor(here, route_dir);
    u8 law = law_lock_active();
    u8 cache_cell = run_state_dungeon_cache_cell();
    u8 cache_done = (run_state.dungeon_phase
        & RUN_FARFOLD_CACHE_BIT) ? 1 : 0;
    // When the route must flip the Law first, its altar is the next GOAL.
    if (law && law_lock_waypoint != 0xFF) next_trial = law_lock_waypoint;
    for (i = 0; i < size; ++i) {
        u8 seen = run_state_dungeon_cell_seen(i);
        // The boss node appears once you are in the room that holds its
        // door. The corridor to it still waits until that room is entered.
        u8 boss_hint = (i == (u8)(size - 1)
            && run_state_dungeon_cell_seen((u8)(size - 2)));
        u8 icon = BGT_MAP_BIG_ROOM;
        u8 draw = (i == here || seen || (i == next_trial)
            || boss_hint) ? 1 : 0;
        if (!draw) continue;
        if (i == here) icon = BGT_MAP_BIG_HERE;
        // Each completed fixture reveals exactly one next GOAL, without
        // drawing the unwalked doors that lead there.
        if (i == next_trial && i != here) icon = BGT_MAP_BIG_GOAL;
        if (boss_hint && i != here) icon = BGT_MAP_BIG_BOSS;
        // The cache appears only after that room is visited or charted.
        if (seen && i == cache_cell && !cache_done && i != here)
            icon = BGT_MAP_BIG_CACHE;
        // Unclaimed shrine: gold mark on the earned compass after a visit.
        if (seen && i != here && powerup_shrine_map_mark(i))
            icon = BGT_MAP_BIG_SHOP;
        icon = map_dungeon_shop_icon(i, here, icon);
        map_big_node(gx[i], gy[i], icon);
        // A charted altar wears the current Law colour in its lower half.
        if (law && seen && icon == BGT_MAP_BIG_ROOM)
            law_lock_map_altar(gx[i], gy[i], i);
    }
    // The found Veil host wears the small coin in its node's corner (the
    // public merchant keeps the big coin); a Chime-heard host is dim.
    {
        u8 v = secret_merchant_map_cell();
        u8 c = (u8)(v & 0x7F);
        if (v != 0xFF && c < size) {
            if (v & 0x80)
                map_put_attr((u8)(gx[c] + 1), (u8)(gy[c] + 1), BGT_MAP_SHOP,
                    BGPAL_WALL);
            else map_put((u8)(gx[c] + 1), (u8)(gy[c] + 1), BGT_MAP_SHOP);
        }
    }
    // Depth numbers appear only for rows that contain a room you have
    // actually entered.
    for (i = 0; i < DUNGEON_GRID_H; ++i) {
        u8 base = (u8)(i * DUNGEON_GRID_W);
        u8 n, show = 0;
        if (base >= size) break;
        for (n = 0; n < DUNGEON_GRID_W && (u8)(base + n) < size; ++n) {
            u8 cell = (u8)(base + n);
            if (cell == here || run_state_dungeon_cell_seen(cell)) show = 1;
        }
        if (show)
            map_put(19, gy[base], (u8)(HUD_DIGIT_0 + i + 1));
    }
    // A corridor exists on the compass only after both rooms it joins have
    // been entered or charted. The goal marker does not leak the path.
    for (i = 0; i < size; ++i) {
        u8 a_seen = run_state_dungeon_cell_seen(i);
        for (j = (u8)(i + 1); j < size; ++j) {
            u8 b_seen = run_state_dungeon_cell_seen(j);
            u8 gate;
            u8 adjacent = (gy[i] == gy[j]
                    && (gx[i] + 3 == gx[j] || gx[j] + 3 == gx[i]))
                || (gx[i] == gx[j]
                    && (gy[i] + 3 == gy[j] || gy[j] + 3 == gy[i]));
            if (!a_seen || !b_seen) continue;
            if (!adjacent || !run_state_dungeon_cells_connected(i, j))
                continue;
            gate = law ? law_lock_edge_attr(i, j) : 0xFF;
            {
                u8 x0, y0, x1, y1, t, pal;
                u8 route_edge = ((i == here && j == route_next)
                    || (j == here && i == route_next));
                // Route edge glows cyan; a Law Lock corridor wears the
                // colour of the state that opens it; others stay plain.
                pal = route_edge ? BGPAL_CRYSTAL
                    : gate;
                if (gy[i] == gy[j]) {
                    x0 = x1 = (u8)((gx[i] < gx[j] ? gx[i] : gx[j]) + 2);
                    y0 = gy[i];
                    y1 = (u8)(y0 + 1);
                    t = BGT_MAP_PATH_H;
                } else {
                    x0 = gx[i];
                    x1 = (u8)(x0 + 1);
                    y0 = y1 = (u8)((gy[i] < gy[j] ? gy[i] : gy[j]) + 2);
                    t = BGT_MAP_PATH_V;
                }
                if (pal == 0xFF) {
                    map_put(x0, y0, t);
                    map_put(x1, y1, t);
                } else {
                    map_put_attr(x0, y0, t, pal);
                    map_put_attr(x1, y1, t, pal);
                }
            }
        }
    }
    // The rift-well link between local rooms 2 and 8 (map_marks.c).
    if (run_state.bosses_beaten > 0 && size > 8) map_draw_rift_link(here);
    map_draw_dungeon_legend();
    // "LAW" in the colour of the active state: corridors of the same colour
    // are open now, the others wait for an altar.
    if (law) law_lock_map_legend();
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
        map_room_box(tx[i], ty[i],
            map_town_shop_center(i, here, icon[i]));
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
    // Room rendering commonly leaves VBK on the attribute plane. Tile-data
    // uploads obey VBK too: without this reset the Compass atlas lands in
    // VRAM bank 1 while its nodes select bank 0, exposing stale champion art
    // as the notorious blue "arrow" and other garbage-shaped map glyphs.
    VBK_REG = 0;
    palette_bg_load(BGPAL_FLOOR, map_pal_base);
    palette_bg_load(BGPAL_WALL, map_pal_base);
    palette_bg_load(BGPAL_CRYSTAL, map_pal_sigil);
    palette_bg_load(BGPAL_DOOR, map_pal_landmark);
    palette_bg_load(BGPAL_CRACK, map_pal_boss);
    map_load_shop_palette();
    palette_bg_load(7, map_pal_player);
    if (run_state.world_mode) {
        // The area alphabet supplies G/A/E for GATE, then the Compass atlas
        // must win shared slots 90..92 so RIFT cannot render as "PNIHT".
        tiles_load_area_labels(); tiles_load_map_bg(); map_clear_tiles();
        draw_map_heading();
        draw_world_grid();
        map_draw_world_legend();
        draw_ask_prompt();
        SHOW_BKG; DISPLAY_ON;
        return;
    }
    if (is_town) {
        tiles_load_area_labels(); tiles_load_map_bg(); map_clear_tiles();
        draw_map_heading();
        draw_town_grid();
        draw_ask_prompt();
        SHOW_BKG; DISPLAY_ON;
        return;
    }
    mission_graph_ensure();
    tiles_load_area_labels(); tiles_load_map_bg(); tiles_load_hud();
    dungeon_director_refresh_route();
    map_clear_tiles();
    draw_dungeon_heading();
    draw_dungeon_grid();
    draw_ask_prompt();
    SHOW_BKG; DISPLAY_ON;
}
void map_exit(void) {}
screen_id_t map_tick(u8 keys, u8 pressed) {
    keys;
    if ((pressed & J_A) && companion_ask()) {
        room_request_resume();
        return SCREEN_ROOM;
    }
    if (pressed & (J_SELECT | J_B | J_START)) {
        sfx_play(SFX_COIN); room_request_resume(); return SCREEN_ROOM;
    }
    return SCREEN_SELF;
}
void map_draw(void) {}
