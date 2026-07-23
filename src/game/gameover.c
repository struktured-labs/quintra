#pragma bank 3
// GAMEOVER — death stats screen, returns to TITLE.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <gbdk/font.h>

#include "audio/music.h"
#include "core/types.h"
#include "game/gameover.h"
#include "game/sram.h"
#include "game/run_state.h"
#include "render/palette.h"
#include "render/text.h"

BANKREF(gameover_enter)

static const u16 gameover_palette[4] = {
    BGR555( 4,  0,  2),    // 0: deep red-black
    BGR555(12,  2,  4),    // 1: dark crimson
    BGR555(28,  8,  8),    // 2: bright red
    BGR555(31, 28, 28),    // 3: pale pink-white
};

static u8 new_best;

void gameover_enter(void) {
    sram_clear_run();   // run over -> suspend save dies with it
    new_best = sram_meta_record(run_state.score, 0, run_state.run_timer);
    DISPLAY_OFF;
    HIDE_SPRITES;
    HIDE_WIN;
    palette_bg_load(0, gameover_palette);
    palette_bg_load(7, gameover_palette);

    font_init();
    { font_t f = font_load(font_min); font_set(f); }
    cls();

    gotoxy(6, 3);  text_write("GAME  OVER");
    gotoxy(2, 7);  text_write("rooms   "); text_u16((u16)run_state.room_counter);
    gotoxy(2, 8);  text_write("kills   "); text_u16((u16)run_state.enemies_killed);
    // These are deliberately distinct values. A plain "score" / "best"
    // pair made the two adjacent numbers read like a duplicated score during
    // a fast post-death glance, especially when a new-record tag followed.
    gotoxy(2, 9);  text_write("run     "); text_u16((u16)run_state.score);
    if (new_best & 1) text_write(" NEW!");
    gotoxy(2, 10); text_write("record  "); text_u16(sram_meta_best());
    gotoxy(2, 11); text_write("time    "); text_u16((u16)(run_state.run_timer / 60));
    text_write(":"); text_digit((u8)((run_state.run_timer % 60) / 10));
    text_digit((u8)(run_state.run_timer % 10));
    gotoxy(2, 14); text_write("PRESS  START");

    // Console glyph writes touch tile ids only; stale CGB attribute bytes from
    // gameplay otherwise color arbitrary digits differently.
    palette_bg_fill_attrs(0);

    music_play_gameover();
    SHOW_BKG;
    DISPLAY_ON;
}

void gameover_exit(void) {}

screen_id_t gameover_tick(u8 keys, u8 pressed) {
    keys;
    if (pressed & (J_START | J_A)) return SCREEN_TITLE;
    return SCREEN_SELF;
}

void gameover_draw(void) {}
