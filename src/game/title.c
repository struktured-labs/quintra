#pragma bank 3
// TITLE screen — "QUINTRA" + "PRESS START". Pulses palette so the screen
// feels alive while waiting on player input.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <gbdk/font.h>

#include "audio/music.h"
#include "audio/sfx.h"
#include "core/types.h"
#include "game/loop.h"
#include "game/sram.h"
#include "game/title.h"
#include "game/version.h"
#include "render/class_palettes.h"
#include "render/palette.h"
#include "render/text.h"
#include "render/tiles.h"

BANKREF(title_enter)

// Cached at enter so tick doesn't hit SRAM every frame
static u8 has_save;

static u8  pulse_phase;
static u16 last_palette_color2;

// "Title vibe" palette: deep purple background, lilac highlight, white text.
// Color 0: background (deep indigo)
// Color 1: shadow / mid (purple)
// Color 2: pulsing accent (cycles between magenta/cyan)
// Color 3: text (near-white)
static const u16 title_palette_steady[4] = {
    BGR555( 1,  0,  5),    // 0: deep indigo
    BGR555( 6,  2, 14),    // 1: purple
    BGR555(20,  8, 26),    // 2: magenta-pink (starting)
    BGR555(30, 30, 31),    // 3: near-white
};

// 0 = main title, 1 = records page (SELECT toggles)
static u8 showing_records;
static u8 lore_beat;
static u8 lore_hold;

#define N_LORE_BEATS 7
#define TITLE_SPIRIT_COUNT 5
#define TITLE_SPIRIT_SPRITES 4

// A living lineup makes the opening myth about people rather than only text.
// Five complete 16x16 metasprites fit above the logo, reuse the in-game hero
// atlas, and are parked on every exit so no title OAM leaks into class select.
static const u8 title_spirit_x[TITLE_SPIRIT_COUNT] = { 24, 52, 80, 108, 136 };

static void title_hide_spirits(void) {
    u8 i;
    for (i = 0; i < (u8)(TITLE_SPIRIT_COUNT * TITLE_SPIRIT_SPRITES); ++i)
        move_sprite(i, 0, 0);
}

static void title_draw_spirits(void) {
    u8 spirit, part;
    // Staggered step poses and a one-pixel wave give the five champions a
    // quiet procession without consuming runtime entities or animation data.
    for (spirit = 0; spirit < TITLE_SPIRIT_COUNT; ++spirit) {
        u8 id = (u8)(spirit * TITLE_SPIRIT_SPRITES);
        u8 base = (u8)(((pulse_phase + spirit * 9u) & 0x10)
            ? SPR_CLASS_WALK_BASE : SPR_CLASS_BASE);
        u8 y = (u8)(31 + (((pulse_phase + spirit * 13u) & 0x18) == 0x18));
        base = (u8)(base + spirit * SPR_CLASS_STRIDE);
        for (part = 0; part < TITLE_SPIRIT_SPRITES; ++part) {
            set_sprite_tile((u8)(id + part), (u8)(base + part));
            move_sprite((u8)(id + part),
                (u8)(title_spirit_x[spirit] + ((part & 1) ? 8 : 0)),
                (u8)(y + ((part >= 2) ? 8 : 0)));
        }
    }
}

static void title_init_spirits(void) {
    u8 spirit, part;
    tiles_load_all_class_sprites();
    for (spirit = 0; spirit < TITLE_SPIRIT_COUNT; ++spirit) {
        u8 id = (u8)(spirit * TITLE_SPIRIT_SPRITES);
        palette_obj_load((u8)(spirit + 1), class_obj_palettes[spirit]);
        for (part = 0; part < TITLE_SPIRIT_SPRITES; ++part)
            set_sprite_prop((u8)(id + part), (u8)(spirit + 1));
    }
    title_draw_spirits();
}

static void render_lore_beat(void) {
    // The founding myth as a tiny, animated intro story. It lives on the title
    // so START can skip it immediately and repeat runs never inherit a cutscene.
    // Clear the complete rows. "FIVE SEAL THE RIFT" begins at x=2 and its
    // final T reaches column 19; the former x=1/18-cell erase left that T
    // attached to later beats (for example "ERE ALL NAMES FADET").
    gotoxy(0, 8); text_write("                    ");
    gotoxy(0, 9); text_write("                    ");
    switch (lore_beat) {
        case 0: gotoxy(2, 8); text_write("WHEN THE SKY TORE"); gotoxy(2, 9); text_write("FIVE SPIRITS WOKE"); break;
        // State the five spirits' charge before naming the catastrophe they
        // must stop.  This keeps the seven-beat procession readable even for
        // a player who skips it after a single pass.
        case 1: gotoxy(2, 8); text_write("FIVE ARE CHOSEN"); gotoxy(1, 9); text_write("TO BEAR THE SPARKS"); break;
        case 2: gotoxy(3, 8); text_write("BIND THE RIFT"); gotoxy(1, 9); text_write("ERE ALL NAMES FADE"); break;
        case 3: gotoxy(2, 8); text_write("FANG GUARDS FLAME"); gotoxy(2, 9); text_write("SCALE HOLDS STONE"); break;
        case 4: gotoxy(2, 8); text_write("WING READS SHADOW"); gotoxy(1, 9); text_write("FIN REMEMBERS TIDE"); break;
        case 5: gotoxy(2, 8); text_write("STING DEFIES ROT"); gotoxy(2, 9); text_write("FIVE SEAL THE RIFT"); break;
        default: gotoxy(1, 8); text_write("CHOOSE YOUR VESSEL"); gotoxy(2, 9); text_write("REKINDLE THE DAWN"); break;
    }
}

static void render_title(void) {
    cls();
    // Layout: 20 cols × 18 rows. Center "QUINTRA" (7 chars) at col 6.
    gotoxy(6, 4);
    text_write("QUINTRA");
    gotoxy(5, 6);
    text_write("THE  ROGUELIKE");
    render_lore_beat();
    if (has_save) {
        gotoxy(4, 11);
        text_write("A     CONTINUE");
        gotoxy(4, 13);
        text_write("START NEW RUN");
    } else {
        gotoxy(4, 12);
        text_write("PRESS  START");
    }
    // Keep the records affordance and version on separate centred rows.  The
    // old packed "SEL RECORD v0..." footer read as broken leftover text and
    // was easily mistaken for the stray glyph reported at the right edge.
    // Neither line touches column 19: the GBDK console would wrap/scroll if
    // the bottom-right cell were written.
    gotoxy(3, 16); text_write("SELECT RECORDS");
    gotoxy(6, 17); text_write(QUINTRA_VERSION);
    // Personal score belongs on SELECT → Records. Keeping it off the title
    // preserves the lore tableau instead of leaving a bare persistent number
    // stranded in the lower middle of the screen.
}

static void render_records(void) {
    u16 runs = sram_meta_runs();
    u16 wins = sram_meta_wins();
    cls();
    gotoxy(5, 2);  text_write("- RECORDS -");
    gotoxy(2, 5);  text_write("BEST SCORE "); text_u16(sram_meta_best());
    gotoxy(2, 7);  text_write("RUNS       "); text_u16(runs);
    gotoxy(2, 9);  text_write("WINS       "); text_u16(wins);
    gotoxy(2, 11); text_write("FALLEN     "); text_u16((u16)(runs - wins));
    {
        u16 bt = sram_meta_best_time();
        if (bt != 0xFFFF) {
            gotoxy(2, 13);
            text_write("FAST WIN   "); text_u16((u16)(bt / 60)); text_write(":");
            text_digit((u8)((bt % 60) / 10)); text_digit((u8)(bt % 10));
        }
    }
    gotoxy(2, 14); text_write("ONLY KNOWLEDGE");
    gotoxy(2, 15); text_write("PERSISTS.");
    gotoxy(2, 17); text_write("SELECT/B = BACK");
}

void title_enter(void) {
    DISPLAY_OFF;

    palette_bg_load(0, title_palette_steady);
    // Mirror to palette 7 so font_init's choice of palette doesn't surprise us
    palette_bg_load(7, title_palette_steady);

    font_init();
    {
        font_t f = font_load(font_min);   // tiny font into VRAM
        font_set(f);
    }

    has_save = sram_run_valid();
    showing_records = 0;
    lore_beat = 0;
    lore_hold = 0;
    render_title();

    pulse_phase         = 0;
    last_palette_color2 = title_palette_steady[2];
    title_hide_spirits();
    title_init_spirits();

    music_play_title();
    SHOW_SPRITES;
    SHOW_BKG;
    DISPLAY_ON;
}

void title_exit(void) {
    title_hide_spirits();
}

screen_id_t title_tick(u8 keys, u8 pressed) {
    keys;
    // Records page: SELECT toggles, B backs out. Blocks run-start inputs
    // so a stray START on the stats page doesn't launch a game.
    if (showing_records) {
        if (pressed & (J_SELECT | J_B | J_START)) {
            showing_records = 0;
            sfx_play(SFX_COIN);
            render_title();
            title_draw_spirits();
        }
        return SCREEN_SELF;
    }
    if (pressed & J_SELECT) {
        showing_records = 1;
        sfx_play(SFX_COIN);
        // The records page owns the whole text field. Park the title tableau
        // instead of letting the five heroes float over personal statistics.
        title_hide_spirits();
        render_records();
        return SCREEN_SELF;
    }
    // Resume the suspended run (room regenerates from the saved seed +
    // counter; hud_init runs in room_enter, so RUN_INIT is skippable).
    if ((pressed & J_A) && has_save && sram_load_run()) {
        sfx_play(SFX_HEART);
        music_stop();
        return SCREEN_ROOM;
    }
    if (pressed & J_START) { sfx_play(SFX_COIN); music_stop(); return SCREEN_CLASS_SELECT; }
    return SCREEN_SELF;
}

void title_draw(void) {
    // Pulse color index 2 — cycles through a magenta/cyan ramp every ~90 frames.
    // Triangle wave: 0..45 magenta-ish, 45..89 cyan-ish.
    pulse_phase = (u8)(pulse_phase + 1);
    if (pulse_phase >= 90) pulse_phase = 0;

    // OAM updates are deliberately coarse: the tableau reads as a living
    // procession at 7.5 Hz while leaving nearly all title frames untouched.
    if (!showing_records && (pulse_phase & 7) == 0) title_draw_spirits();

    // Change the vow every three pulse cycles. The palette continues moving
    // between beats, giving the lore tableau a simple hardware-cheap animation.
    if (pulse_phase == 0 && !showing_records) {
        if (++lore_hold >= 3) {
            lore_hold = 0;
            lore_beat = (u8)((lore_beat + 1) % N_LORE_BEATS);
            render_lore_beat();
        }
    }

    {
        u8  phase    = pulse_phase < 45 ? pulse_phase : (u8)(89 - pulse_phase);
        u8  r        = (u8)(20 - (phase >> 1));     // 20 → ~0
        u8  g        = (u8)(4  + (phase >> 1));     // 4 → ~26
        u8  b        = (u8)(26 - (phase >> 2));     // 26 → 15
        u16 c2       = BGR555(r, g, b);
        u16 pal[4] = {
            title_palette_steady[0],
            title_palette_steady[1],
            c2,
            title_palette_steady[3],
        };
        palette_bg_load(0, pal);
        palette_bg_load(7, pal);
        last_palette_color2 = c2;
    }
}
