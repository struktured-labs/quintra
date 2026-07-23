#pragma bank 3
// VICTORY — boss-defeated screen, returns to TITLE.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <gbdk/font.h>

#include "audio/music.h"
#include "core/types.h"
#include "game/run_state.h"
#include "game/sram.h"
#include "game/victory.h"
#include "render/palette.h"
#include "render/text.h"

BANKREF(victory_enter)

static u8 pulse;
static u8 ending_beat;
static u8 spark_pose;
static u16 ending_frames;

static const u16 victory_palette[4] = {
    BGR555( 0,  4,  2),    // 0: deep emerald
    BGR555( 4, 16,  6),    // 1: forest green
    BGR555(24, 28,  6),    // 2: bright yellow-green
    BGR555(31, 31, 24),    // 3: cream-gold
};

static u8 new_best;

static void render_ending(void) {
    cls();
    gotoxy(2, 16); text_write("START SKIPS ENDING");

    if (ending_beat == 0) {
        gotoxy(3, 3);  text_write("THE RIFT IS BOUND");
        gotoxy(2, 8);  text_write("NINE COLOSSI FALL");
        gotoxy(2, 11); text_write("FIVE SPARKS RISE");
    } else if (ending_beat == 1) {
        gotoxy(3, 3);  text_write("THE SPIRITS WAKE");
        gotoxy(2, 8);  text_write("FANG SCALE WING");
        gotoxy(2, 10); text_write("FIN STING RETURN");
    } else if (ending_beat == 2) {
        gotoxy(2, 3);  text_write("THE ROADS REMEMBER");
        gotoxy(3, 8);  text_write("DAWN HAS A NAME");
        gotoxy(4, 11); text_write("QUINTRA ENDURES");
    } else {
        gotoxy(6, 2);  text_write("VICTORY!");
        gotoxy(2, 5);  text_write("9 depths freed");
        gotoxy(2, 8);  text_write("rooms   "); text_u16((u16)run_state.room_counter);
        gotoxy(2, 9);  text_write("kills   "); text_u16((u16)run_state.enemies_killed);
        gotoxy(2, 10); text_write("score   "); text_u16((u16)run_state.score);
        if (new_best & 1) text_write(" NEW!");
        gotoxy(2, 11); text_write("best    "); text_u16(sram_meta_best());
        gotoxy(2, 12); text_write("time    "); text_u16((u16)(run_state.run_timer / 60));
        text_write(":"); text_digit((u8)((run_state.run_timer % 60) / 10));
        text_digit((u8)(run_state.run_timer % 10));
        if (new_best & 2) text_write(" FAST!");
        gotoxy(0, 15); text_write("START=END A=DESCEND");
        gotoxy(2, 16); text_write("                  ");
    }
}

static void render_sparks(void) {
    if (ending_beat >= 3) return;
    // Draw in place: font_min's blank glyph does not share the console's CGB
    // backdrop colour, so clearing a moving row exposes ugly black bars.
    if (spark_pose) {
        gotoxy(4, 5); text_write("O + O + O + O");
    } else {
        gotoxy(4, 5); text_write("+ O + O + O +");
    }
}

void victory_enter(void) {
    sram_clear_run();   // run over -> suspend save dies with it
    // Record a WIN only on the true 9th boss. Endless-descent bosses
    // (10th, 11th, ...) reopen this screen but shouldn't inflate the
    // runs/wins counters — best score still updates via later deaths.
    new_best = 0;
    if (run_state.bosses_beaten == BOSSES_TO_WIN) {
        new_best = sram_meta_record(run_state.score, 1, run_state.run_timer);
    }
    DISPLAY_OFF;
    HIDE_SPRITES;
    HIDE_WIN;
    palette_bg_load(0, victory_palette);
    palette_bg_load(7, victory_palette);

    font_init();
    { font_t f = font_load(font_min); font_set(f); }
    cls();

    pulse = 0;
    // The founding epilogue belongs to the canonical ninth-boss clear. Later
    // optional endless-descent colossi go straight to their results page.
    ending_beat = (run_state.bosses_beaten == BOSSES_TO_WIN) ? 0 : 3;
    spark_pose = 0;
    ending_frames = 0;
    render_ending();
    render_sparks();
    music_play_victory();
    SHOW_BKG;
    DISPLAY_ON;
}

void victory_exit(void) {}

screen_id_t victory_tick(u8 keys, u8 pressed) {
    keys;
    if (pressed & J_START) {
        if (ending_beat < 3) {
            ending_beat = 3;
            ending_frames = 0;
            render_ending();
            return SCREEN_SELF;
        }
        return SCREEN_TITLE;
    }
    // Endless descent keeps the run but resumes in Riftwild. Explicit stage
    // topology clamps boss identity at stage nine, so regenerating room 118
    // would simply rebuild the sealed Void arena and trap the champion.
    if ((pressed & J_A) && ending_beat >= 3) {
        run_state.victory = 0;
        run_state_begin_world();
        return SCREEN_ROOM;
    }
    return SCREEN_SELF;
}

void victory_draw(void) {
    // Pulse color index 2 between green-yellow and pale-gold
    pulse = (u8)(pulse + 1);
    if (pulse >= 90) pulse = 0;

    // Three skippable three-second epilogue tableaux, then settle on results.
    // The five rising glyphs shift every half-second as a cheap, legible GBC
    // animation; START and A remain responsive throughout.
    if (ending_beat < 3) {
        ending_frames++;
        if ((ending_frames % 30) == 0) {
            spark_pose ^= 1;
            render_sparks();
        }
        if (ending_frames >= 180) {
            ending_frames = 0;
            ending_beat++;
            render_ending();
            render_sparks();
        }
    }
    {
        u8 phase = pulse < 45 ? pulse : (u8)(89 - pulse);
        u8 r     = (u8)(24 - (phase >> 1));
        u8 g     = (u8)(28 + (phase >> 3));
        u8 b     = (u8)(6  + (phase >> 1));
        u16 c2   = BGR555(r, g, b);
        u16 pal[4] = {
            victory_palette[0],
            victory_palette[1],
            c2,
            victory_palette[3],
        };
        palette_bg_load(0, pal);
        palette_bg_load(7, pal);
    }
}
