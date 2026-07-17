#pragma bank 3
#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <gbdk/font.h>
#include <stdio.h>
#include "audio/sfx.h"
#include "game/map.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

BANKREF(map_enter)

static const u16 map_pal[4] = {
    BGR555(1,3,2), BGR555(4,12,8), BGR555(16,23,12), BGR555(30,31,24)
};

// Town names are lore fixtures; the whispered line is seed-fuzzy. A region
// remains memorable across runs without turning the roguelike into one fixed
// account of what happened there.
static const char *const town_names[3] = {
    "EMBERFORD", "GLOAMHARBOR", "DAWN'S VERGE"
};
static const char *const town_rumors[4] = {
    "THE WELL DREAMS", "BELLS FEAR DEPTH",
    "FIVE SHADOWS WALK", "THE RIFT KNOWS YOU"
};

static u8 map_attr(u8 tile) {
    if (tile == BGT_WALL || tile == BGT_PILLAR || tile == BGT_ROOF
        || tile == BGT_FENCE || tile == BGT_TREE) return BGPAL_WALL;
    if (tile == BGT_CRYSTAL || tile == BGT_PORTAL) return BGPAL_CRYSTAL;
    if (tile == BGT_DOOR || tile == BGT_SWITCH) return BGPAL_DOOR;
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

static void map_room_box(u8 x, u8 y, u8 center, u8 seen) {
    u8 dx, dy;
    if (!seen) return; // the tile-built graph literally fills as explored
    for (dy = 0; dy < 3; ++dy) {
        for (dx = 0; dx < 3; ++dx) {
            u8 edge = (dx == 0 || dx == 2 || dy == 0 || dy == 2);
            map_put((u8)(x + dx), (u8)(y + dy), edge ? BGT_WALL : BGT_FLOOR);
        }
    }
    map_put((u8)(x + 1), (u8)(y + 1), center);
}

static void draw_world_grid(void) {
    u8 r, c;
    for (r = 0; r < 4; ++r) {
        for (c = 0; c < 4; ++c) {
            u8 cell = (u8)(r * 4 + c);
            u8 x = (u8)(1 + c * 4);
            u8 y = (u8)(1 + r * 4);
            u8 seen = (run_state.world_seen & (u16)(1u << cell)) ? 1 : 0;
            u8 icon = BGT_FLOOR3;
            const zelda_screen_t *z = &zelda_overworlds[0].screen_grid[cell];
            if (cell == (run_state.world_screen & 15)) icon = BGT_SWITCH;
            else if (z->kind == ZELDA_CELL_DUNGEON_ENTRANCE) icon = BGT_PORTAL;
            else if (z->kind == ZELDA_CELL_VAULT) icon = BGT_CRYSTAL;
            else if (z->kind == ZELDA_CELL_BOSS) icon = BGT_SPIKES;
            else if (z->kind == ZELDA_CELL_CAVE_ENTRANCE) icon = BGT_DOOR;
            map_room_box(x, y, icon, seen);
            if (c < 3 && (run_state.world_seen & (u16)(1u << cell))
                && (run_state.world_seen & (u16)(1u << (cell + 1)))
                && (zelda_overworlds[0].screen_grid[cell].edges & 2)) {
                map_put((u8)(x + 3), (u8)(y + 1), BGT_FLOOR2);
            }
            if (r < 3 && (run_state.world_seen & (u16)(1u << cell))
                && (run_state.world_seen & (u16)(1u << (cell + 4)))
                && (zelda_overworlds[0].screen_grid[cell].edges & 4)) {
                map_put((u8)(x + 1), (u8)(y + 3), BGT_FLOOR2);
            }
        }
    }
}

static void draw_dungeon_grid(void) {
    static const u8 gx[6] = { 1, 7, 13, 13, 7, 1 };
    static const u8 gy[6] = { 3, 3, 3, 10, 10, 10 };
    u8 i;
    u8 local = (u8)(run_state.room_counter % ROOMS_PER_STAGE);
    // The opening dungeon includes its entry room in the diagram. Later
    // dungeons begin after an overworld gate, so their local rooms are
    // shifted left by one (the same mapping used by dungeon_seen below).
    u8 sigil_cell = run_state.bosses_beaten ? 1 : 2;
    u8 sigil_found = (run_state.rift_sigils
        & RUN_STAGE_SIGIL_BIT(run_state.bosses_beaten)) ? 1 : 0;
    u8 here = (local == 0 && run_state.room_counter > 0) ? 5
        : ((run_state.bosses_beaten > 0 && local > 0)
            ? (u8)(local - 1) : local);
    for (i = 0; i < 6; ++i) {
        u8 seen = (run_state.dungeon_seen & (u8)(1u << i)) ? 1 : 0;
        u8 icon = (i == here) ? BGT_SWITCH : (i == 5 ? BGT_SPIKES : BGT_FLOOR3);
        // Put the objective in the room that actually owns it. The older
        // free-floating center marker looked like decoration, so players
        // could reach the sanctuary without realizing which room held the
        // required Rift Sigil.
        if (i == sigil_cell && i != here)
            icon = sigil_found ? BGT_CRYSTAL : BGT_WALL_CRACK;
        map_room_box(gx[i], gy[i], icon, seen);
        if (i < 2 && (run_state.dungeon_seen & (u8)(3u << i)) == (u8)(3u << i)) {
            map_put((u8)(gx[i] + 3), (u8)(gy[i] + 1), BGT_FLOOR2);
            map_put((u8)(gx[i] + 4), (u8)(gy[i] + 1), BGT_FLOOR2);
            map_put((u8)(gx[i] + 5), (u8)(gy[i] + 1), BGT_FLOOR2);
        }
        if (i == 2 && (run_state.dungeon_seen & 0x0C) == 0x0C) {
            map_put(14,6,BGT_FLOOR2); map_put(14,7,BGT_FLOOR2);
            map_put(14,8,BGT_FLOOR2); map_put(14,9,BGT_FLOOR2);
        }
        if (i >= 3 && i < 5
            && (run_state.dungeon_seen & (u8)((1u << i) | (1u << (i + 1))))
                == (u8)((1u << i) | (1u << (i + 1)))) {
            map_put((u8)(gx[i + 1] + 3), (u8)(gy[i] + 1), BGT_FLOOR2);
            map_put((u8)(gx[i + 1] + 4), (u8)(gy[i] + 1), BGT_FLOOR2);
            map_put((u8)(gx[i + 1] + 5), (u8)(gy[i] + 1), BGT_FLOOR2);
        }
    }
}

void map_enter(void) {
    u8 in_region = (u8)(run_state.room_counter % ROOMS_PER_REGION);
    u8 is_town = (run_state.room_counter > ROOMS_PER_REGION && in_region == 1);
    DISPLAY_OFF; HIDE_SPRITES; HIDE_WIN;
    palette_bg_load(0, map_pal); palette_bg_load(1, map_pal);
    palette_bg_load(2, map_pal); palette_bg_load(3, map_pal);
    palette_bg_load(4, map_pal); palette_bg_load(7, map_pal);
    if (run_state.world_mode) {
        tiles_load_dungeon_bg(); map_clear_tiles();
        draw_world_grid();
        SHOW_BKG; DISPLAY_ON;
        return;
    }
    if (is_town) {
        u8 completed = (u8)((run_state.room_counter - 1) / ROOMS_PER_REGION);
        u8 town = (completed > 0 && completed <= 3) ? (u8)(completed - 1) : 0;
        u8 rumor = (u8)(run_state.run_seed ^ (run_state.run_seed >> 8)
            ^ (run_state.run_seed >> 16) ^ completed) & 3;
        font_init(); { font_t f = font_load(font_ibm); font_set(f); }
        cls();
        gotoxy(1,0); printf("- SPIRIT COMPASS -");
        gotoxy(1,2);  printf("REGION %u COMPLETE", (u16)completed);
        gotoxy(1,4);  printf("%s", town_names[town]);
        gotoxy(1,6);  printf("SANCTUARY & MARKET");
        gotoxy(1,8);  printf("NEXT REGION %u", (u16)(completed + 1));
        gotoxy(1,10); printf("ELDER RESTORES ALL");
        gotoxy(1,11); printf("CHARTWRIGHT MARKS PATH");
        gotoxy(1,13); printf("%s", town_rumors[rumor]);
        gotoxy(1,15); printf("LORE SHIFTS BY SEED");
        gotoxy(2,17); printf("SELECT/B = RETURN");
        palette_bg_fill_attrs(0);
        SHOW_BKG; DISPLAY_ON;
        return;
    }
    tiles_load_dungeon_bg(); map_clear_tiles();
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
