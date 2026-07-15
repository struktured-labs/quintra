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

static char world_cell_glyph(u8 cell) {
    const zelda_screen_t *z = &zelda_overworlds[0].screen_grid[cell];
    if (cell == (run_state.world_screen & 15)) return '@';
    if (!(run_state.world_seen & (u16)(1u << cell))) return '?';
    if (z->kind == ZELDA_CELL_DUNGEON_ENTRANCE) return 'D';
    if (z->kind == ZELDA_CELL_VAULT) return 'V';
    if (z->kind == ZELDA_CELL_BOSS) return 'C';
    if (z->kind == ZELDA_CELL_CAVE_ENTRANCE) return 'A';
    return 'O';
}

static void draw_world_grid(void) {
    u8 r, c;
    gotoxy(1, 1); printf("RIFTWILD 4x4 MAP");
    for (r = 0; r < 4; ++r) {
        for (c = 0; c < 4; ++c) {
            u8 cell = (u8)(r * 4 + c);
            u8 x = (u8)(1 + c * 5);
            u8 y = (u8)(3 + r * 3);
            gotoxy(x, y); printf("[%c]", world_cell_glyph(cell));
            if (c < 3 && (run_state.world_seen & (u16)(1u << cell))
                && (run_state.world_seen & (u16)(1u << (cell + 1)))
                && (zelda_overworlds[0].screen_grid[cell].edges & 2)) {
                gotoxy((u8)(x + 3), y); printf("==");
            }
            if (r < 3 && (run_state.world_seen & (u16)(1u << cell))
                && (run_state.world_seen & (u16)(1u << (cell + 4)))
                && (zelda_overworlds[0].screen_grid[cell].edges & 4)) {
                gotoxy((u8)(x + 1), (u8)(y + 1)); printf("I");
                gotoxy((u8)(x + 1), (u8)(y + 2)); printf("I");
            }
        }
    }
    gotoxy(1,15); printf("@YOU D:GATE ?:HIDDEN");
}

static void draw_dungeon_grid(void) {
    static const u8 gx[6] = { 2, 8, 14, 14, 8, 2 };
    static const u8 gy[6] = { 4, 4, 4, 9, 9, 9 };
    u8 i;
    u8 local = (u8)(run_state.room_counter % ROOMS_PER_STAGE);
    u8 here = (local == 0 && run_state.room_counter > 0) ? 5
        : ((run_state.bosses_beaten > 0 && local > 0)
            ? (u8)(local - 1) : local);
    gotoxy(1,1); printf("DUNGEON %u  VISITED", (u16)(run_state.bosses_beaten + 1));
    for (i = 0; i < 6; ++i) {
        char g = (i == here) ? '@'
            : ((run_state.dungeon_seen & (u8)(1u << i)) ? 'O' : '?');
        gotoxy(gx[i], gy[i]); printf("[%c]", g);
        if (i < 2 && (run_state.dungeon_seen & (u8)(3u << i)) == (u8)(3u << i)) {
            gotoxy((u8)(gx[i] + 3), gy[i]); printf("===");
        }
        if (i == 2 && (run_state.dungeon_seen & 0x0C) == 0x0C) {
            gotoxy(15,5); printf("I"); gotoxy(15,6); printf("I");
            gotoxy(15,7); printf("I"); gotoxy(15,8); printf("I");
        }
        if (i >= 3 && i < 5
            && (run_state.dungeon_seen & (u8)((1u << i) | (1u << (i + 1))))
                == (u8)((1u << i) | (1u << (i + 1)))) {
            gotoxy((u8)(gx[i + 1] + 3), gy[i]); printf("===");
        }
    }
    gotoxy(1,12); printf("@ YOU   ? UNSEEN");
    gotoxy(1,14); printf("BOSS AT FINAL CELL");
}

void map_enter(void) {
    u8 in_region = (u8)(run_state.room_counter % ROOMS_PER_REGION);
    u8 is_town = (run_state.room_counter > ROOMS_PER_REGION && in_region == 1);
    DISPLAY_OFF; HIDE_SPRITES; HIDE_WIN;
    palette_bg_load(0, map_pal); palette_bg_load(7, map_pal);
    // The Compass needs brackets and line glyphs for its actual room grid;
    // font_min silently drops them and turns the map into scattered letters.
    font_init(); { font_t f = font_load(font_ibm); font_set(f); }
    cls();
    gotoxy(1,0); printf("- SPIRIT COMPASS -");
    if (run_state.world_mode) {
        draw_world_grid();
        gotoxy(2,17); printf("SELECT/B = RETURN");
        palette_bg_fill_attrs(0);
        SHOW_BKG; DISPLAY_ON;
        return;
    }
    if (is_town) {
        u8 completed = (u8)((run_state.room_counter - 1) / ROOMS_PER_REGION);
        u8 town = (completed > 0 && completed <= 3) ? (u8)(completed - 1) : 0;
        u8 rumor = (u8)(run_state.run_seed ^ (run_state.run_seed >> 8)
            ^ (run_state.run_seed >> 16) ^ completed) & 3;
        gotoxy(1,2);  printf("REGION %u COMPLETE", (u16)completed);
        gotoxy(1,4);  printf("%s", town_names[town]);
        gotoxy(1,6);  printf("SANCTUARY & MARKET");
        gotoxy(1,8);  printf("NEXT REGION %u", (u16)(completed + 1));
        gotoxy(1,10); printf("ELDER RESTORES ALL");
        gotoxy(1,12); printf("%s", town_rumors[rumor]);
        gotoxy(1,14); printf("LORE SHIFTS BY SEED");
        gotoxy(2,17); printf("SELECT/B = RETURN");
        palette_bg_fill_attrs(0);
        SHOW_BKG; DISPLAY_ON;
        return;
    }
    draw_dungeon_grid();
    gotoxy(2,17); printf("SELECT/B = RETURN");
    palette_bg_fill_attrs(0);
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
