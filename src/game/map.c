#pragma bank 255
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

BANKREF(map_enter)

static const u16 map_pal[4] = {
    BGR555(1,3,2), BGR555(4,12,8), BGR555(16,23,12), BGR555(30,31,24)
};

void map_enter(void) {
    u8 in_region = (u8)(run_state.room_counter % ROOMS_PER_REGION);
    u8 dungeon = (u8)(in_region / ROOMS_PER_STAGE);
    u8 room = (u8)(in_region % ROOMS_PER_STAGE);
    u8 to_town = (in_region <= 1) ? 0 : (u8)(ROOMS_PER_REGION + 1 - in_region);
    DISPLAY_OFF; HIDE_SPRITES; HIDE_WIN;
    palette_bg_load(0, map_pal); palette_bg_load(7, map_pal);
    font_init(); { font_t f = font_load(font_min); font_set(f); }
    cls();
    gotoxy(3,0); printf("- SPIRIT COMPASS -");
    gotoxy(1,2); printf("REGION %u", (u16)(run_state.bosses_beaten / 3 + 1));
    gotoxy(1,4); printf("DUNGEON %u OF 3", (u16)(dungeon + 1));
    gotoxy(1,5); printf("DEPTH   %u OF 6", (u16)(room + 1));
    gotoxy(1,7); printf("PATH  o-o-o-B");
    gotoxy(1,9); printf("TOWN ");
    if (in_region == 1) printf("YOU ARE HERE");
    else printf("IN %u ROOMS", (u16)to_town);
    gotoxy(1,11); printf("SEED %u:%u", (u16)(run_state.run_seed >> 16), (u16)run_state.run_seed);
    gotoxy(1,13); printf("THE ROAD REMEMBERS");
    gotoxy(1,14); printf("DIFFERENTLY EACH RUN");
    gotoxy(2,17); printf("SELECT/B = RETURN");
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
