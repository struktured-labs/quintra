#pragma bank 255
// TITLE screen — "QUINTRA" + "PRESS START". Pulses palette so the screen
// feels alive while waiting on player input.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <gbdk/font.h>
#include <stdio.h>

#include "audio/music.h"
#include "audio/sfx.h"
#include "core/types.h"
#include "game/loop.h"
#include "game/sram.h"
#include "game/title.h"
#include "render/palette.h"

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

static void render_lore_beat(void) {
    // The founding myth as a tiny, animated intro story. It lives on the title
    // so START can skip it immediately and repeat runs never inherit a cutscene.
    gotoxy(1, 8); printf("                  ");
    gotoxy(1, 9); printf("                  ");
    switch (lore_beat) {
        case 0: gotoxy(2, 8); printf("WHEN THE SKY TORE"); gotoxy(2, 9); printf("FIVE SPIRITS WOKE"); break;
        case 1: gotoxy(2, 8); printf("BEAR FIVE SPARKS"); gotoxy(1, 9); printf("TO THE WORLD BELOW"); break;
        case 2: gotoxy(3, 8); printf("BIND THE RIFT"); gotoxy(1, 9); printf("ERE ALL NAMES FADE"); break;
        case 3: gotoxy(2, 8); printf("FANG GUARDS FLAME"); gotoxy(2, 9); printf("SCALE HOLDS STONE"); break;
        case 4: gotoxy(2, 8); printf("WING READS SHADOW"); gotoxy(1, 9); printf("FIN REMEMBERS TIDE"); break;
        case 5: gotoxy(2, 8); printf("STING DEFIES ROT"); gotoxy(2, 9); printf("FIVE SEAL THE RIFT"); break;
        default: gotoxy(1, 8); printf("CHOOSE YOUR VESSEL"); gotoxy(2, 9); printf("REKINDLE THE DAWN"); break;
    }
}

static void render_title(void) {
    cls();
    // Layout: 20 cols × 18 rows. Center "QUINTRA" (7 chars) at col 6.
    gotoxy(6, 4);
    printf("QUINTRA");
    gotoxy(5, 6);
    printf("THE  ROGUELIKE");
    render_lore_beat();
    if (has_save) {
        gotoxy(4, 11);
        printf("A     CONTINUE");
        gotoxy(4, 13);
        printf("START NEW RUN");
    } else {
        gotoxy(4, 12);
        printf("PRESS  START");
    }
    // Leave a real gutter before the version. The old 14-column label ended
    // immediately beside it and rendered as the misleading "RECORDSv0.17".
    gotoxy(1, 17); printf("SEL RECORDS");
    gotoxy(15, 17); printf("v0.17");
    {
        u16 best = sram_meta_best();
        if (best > 0) {
            gotoxy(3, 15);
            printf("BEST %u", best);
            {
                u16 w = sram_meta_wins();
                if (w > 0) printf("  WINS %u", w);
            }
        }
    }
}

static void render_records(void) {
    u16 runs = sram_meta_runs();
    u16 wins = sram_meta_wins();
    cls();
    gotoxy(5, 2);  printf("- RECORDS -");
    gotoxy(2, 5);  printf("BEST SCORE %u", sram_meta_best());
    gotoxy(2, 7);  printf("RUNS       %u", runs);
    gotoxy(2, 9);  printf("WINS       %u", wins);
    gotoxy(2, 11); printf("FALLEN     %u", (u16)(runs - wins));
    {
        u16 bt = sram_meta_best_time();
        if (bt != 0xFFFF) {
            gotoxy(2, 13);
            printf("FAST WIN   %u:%u%u", (u16)(bt / 60),
                (u16)((bt % 60) / 10), (u16)(bt % 10));
        }
    }
    gotoxy(2, 14); printf("ONLY KNOWLEDGE");
    gotoxy(2, 15); printf("PERSISTS.");
    gotoxy(2, 17); printf("SELECT/B = BACK");
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

    music_play_title();
    SHOW_BKG;
    DISPLAY_ON;
}

void title_exit(void) {
    // No-op for now.
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
        }
        return SCREEN_SELF;
    }
    if (pressed & J_SELECT) {
        showing_records = 1;
        sfx_play(SFX_COIN);
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
