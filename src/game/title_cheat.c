#pragma bank 12
// Cold presentation for the hidden title-screen stage selector. Input stays
// in title.c so an idle title never pays a far call merely to track a code.

#include <gb/gb.h>
#include <gbdk/console.h>

#include "audio/music.h"
#include "audio/sfx.h"
#include "core/types.h"
#include "game/title.h"
#include "render/text.h"
#include "content.h"

static u8 stage_cursor;
static u8 code_pos;

// Trace a crooked loop in both directions before sealing it with B, A. It is
// a Quintra-specific "rift spiral", memorable without borrowing another
// game's famous sequence or appearing during ordinary menu use.
static const u8 code[10] = {
    J_UP, J_RIGHT, J_DOWN, J_LEFT, J_RIGHT,
    J_UP, J_LEFT, J_DOWN, J_B, J_A,
};

static void render(void) {
    cls();
    gotoxy(3, 1);  text_write("- RIFT INDEX -");
    gotoxy(2, 3);  text_write("A FORBIDDEN PATH");

    gotoxy(5, 6);  text_write("STAGE ");
    text_digit((u8)(stage_cursor + 1));
    text_write(" OF 9");
    gotoxy(2, 8);  text_write(stage_names[stage_cursor]);

    gotoxy(3, 11); text_write("STAGE-READY BUILD");
    gotoxy(3, 13); text_write("UP/DOWN    ONE");
    gotoxy(3, 14); text_write("LEFT/RIGHT THREE");
    gotoxy(2, 16); text_write("A CHOOSE  B CLOSE");
}

void title_cheat_reset(void) BANKED {
    code_pos = 0;
    stage_cursor = 0;
}

u8 title_cheat_code_input(u8 key) BANKED {
    if (key == code[code_pos]) code_pos++;
    else code_pos = (key == J_UP) ? 1 : 0;
    if (code_pos < (u8)sizeof(code)) return 0;
    code_pos = 0;
    return 1;
}

void title_cheat_begin(void) BANKED {
    stage_cursor = 0;
    render();
}

screen_id_t title_cheat_tick(u8 pressed) BANKED {
    if (pressed & J_UP) {
        stage_cursor = stage_cursor ? (u8)(stage_cursor - 1) : 8;
    } else if (pressed & J_DOWN) {
        stage_cursor++;
        if (stage_cursor >= 9) stage_cursor = 0;
    } else if (pressed & J_LEFT) {
        stage_cursor = (stage_cursor >= 3)
            ? (u8)(stage_cursor - 3) : (u8)(stage_cursor + 6);
    } else if (pressed & J_RIGHT) {
        stage_cursor = (u8)(stage_cursor + 3);
        if (stage_cursor >= 9) stage_cursor -= 9;
    } else if (pressed & J_B) {
        sfx_play(SFX_HURT);
        return SCREEN_TITLE;
    } else if (pressed & (J_A | J_START)) {
        title_stage_warp = stage_cursor;
        sfx_play(SFX_HEART);
        music_stop();
        return SCREEN_CLASS_SELECT;
    } else return SCREEN_SELF;
    sfx_play(SFX_HIT);
    render();
    return SCREEN_SELF;
}
