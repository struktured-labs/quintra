#pragma bank 10
// GAMEOVER — Nameless Visor death motif, then coloured stats, back to TITLE.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <gbdk/font.h>

#include "audio/music.h"
#include "core/types.h"
#include "game/gameover.h"
#include "game/sram.h"
#include "game/run_state.h"
#include "render/gameover_art.h"
#include "render/palette.h"
#include "render/text.h"

BANKREF(gameover_enter)

#define GO_LOCK      20
#define GO_RISE_END  80
#define GO_TEXT      130
#define GO_SHARD_N    3

static u8 new_best;
static u8 anim;
static u8 shown;
static u8 rise_rows;
static u8 pulse;
static u16 pals[6][4];

typedef struct {
    u8 x, y, dy, tile;
} shard_t;

static shard_t shards[GO_SHARD_N];

static void load_faded(u8 slot, const u16 *src, u8 level) {
    u16 pal[4];
    u8 i;
    if (level > 8) level = 8;
    for (i = 0; i < 4; i++) {
        u16 c = src[i];
        u8 r = (u8)((c & 0x1F) * level / 8);
        u8 g = (u8)(((c >> 5) & 0x1F) * level / 8);
        u8 b = (u8)(((c >> 10) & 0x1F) * level / 8);
        pal[i] = BGR555(r, g, b);
    }
    palette_bg_load(slot, pal);
}

static void apply_fade(u8 level) {
    load_faded(GOART_PAL_BACKDROP, pals[0], level);
    load_faded(GOART_PAL_STONE, pals[1], level);
    load_faded(GOART_PAL_EMBER, pals[2], level);
    load_faded(GOART_PAL_TITLE, pals[3], level);
    load_faded(GOART_PAL_GOLD, pals[4], level);
}

static void pulse_ember(void) {
    u16 pal[4];
    u8 i;
    u8 phase = pulse < 45 ? pulse : (u8)(89 - pulse);
    /* Lift colour 2 (the crack/ember mid) by up to 6 steps of red/gold. */
    for (i = 0; i < 4; i++) pal[i] = pals[2][i];
    {
        u16 c = pals[2][2];
        u8 r = (u8)(c & 0x1F);
        u8 g = (u8)((c >> 5) & 0x1F);
        u8 b = (u8)((c >> 10) & 0x1F);
        u8 lift = (u8)(phase / 8);
        if ((u8)(r + lift) < 32) r = (u8)(r + lift);
        else r = 31;
        if ((u8)(g + (lift / 2)) < 32) g = (u8)(g + (lift / 2));
        pal[2] = BGR555(r, g, b);
    }
    palette_bg_load(GOART_PAL_EMBER, pal);
}

/* Text lives in columns 1..18 (one-column margin on each side). */
#define GO_MARGIN 1
#define GO_TEXT_COLS 18

static u8 prompt_on;

static u8 str_len(const char *s) {
    u8 n = 0;
    while (s[n]) n++;
    return n;
}

static u8 u16_len(u16 v) {
    u8 n = 1;
    while (v > 9) { v /= 10; n++; }
    return n;
}

static char *put_u16(char *p, u16 v) {
    char d[5];
    u8 n = 0;
    do {
        d[n++] = (char)('0' + (v % 10));
        v /= 10;
    } while (v);
    while (n) *p++ = d[--n];
    return p;
}

static void write_centered(u8 y, const char *s) {
    u8 n = str_len(s);
    u8 x, i;
    char tmp[19];
    if (n > GO_TEXT_COLS) n = GO_TEXT_COLS;
    x = (u8)((20 - n) / 2);
    if (x < GO_MARGIN) x = GO_MARGIN;
    if ((u8)(x + n) > 19) x = (u8)(19 - n);
    for (i = 0; i < n; i++) tmp[i] = s[i];
    tmp[n] = 0;
    gotoxy(x, y);
    text_write(tmp);
}

static void write_prompt(u8 on) {
    if (on) write_centered(16, "PRESS START");
    else {
        gotoxy(GO_MARGIN, 16);
        text_write("                  ");
    }
    prompt_on = on;
}

static void write_stats_row(void) {
    char buf[19];
    char *p = buf;
    u16 rooms = (u16)run_state.room_counter;
    u16 kills = run_state_enemies_killed_total();
    u16 mins = (u16)(run_state.run_timer / 60);
    u8 secs = (u8)(run_state.run_timer % 60);
    /* "RM n K n T m ss" when it fits in 18 columns; otherwise tighten. */
    u8 wide = (u8)(12 + u16_len(rooms) + u16_len(kills) + u16_len(mins));
    u8 tight = (u8)(8 + u16_len(rooms) + u16_len(kills) + u16_len(mins));
    if (wide <= GO_TEXT_COLS) {
        *p++ = 'R'; *p++ = 'M'; *p++ = ' ';
        p = put_u16(p, rooms);
        *p++ = ' '; *p++ = 'K'; *p++ = ' ';
        p = put_u16(p, kills);
        *p++ = ' '; *p++ = 'T'; *p++ = ' ';
        p = put_u16(p, mins);
        *p++ = ' ';
        *p++ = (char)('0' + (u8)(secs / 10));
        *p++ = (char)('0' + (u8)(secs % 10));
    } else if (tight <= GO_TEXT_COLS) {
        *p++ = 'R';
        p = put_u16(p, rooms);
        *p++ = ' '; *p++ = 'K';
        p = put_u16(p, kills);
        *p++ = ' '; *p++ = 'T';
        p = put_u16(p, mins);
        *p++ = ' ';
        *p++ = (char)('0' + (u8)(secs / 10));
        *p++ = (char)('0' + (u8)(secs % 10));
    } else {
        /* Rare long times: drop the seconds rather than clip the row. */
        *p++ = 'R';
        p = put_u16(p, rooms);
        *p++ = ' '; *p++ = 'K';
        p = put_u16(p, kills);
        *p++ = ' '; *p++ = 'T';
        p = put_u16(p, mins);
    }
    *p = 0;
    write_centered(14, buf);
}

static void write_run_row(void) {
    char buf[19];
    char *p = buf;
    *p++ = 'R'; *p++ = 'U'; *p++ = 'N'; *p++ = ' ';
    p = put_u16(p, (u16)run_state.score);
    if (new_best & 1) {
        *p++ = ' '; *p++ = 'N'; *p++ = 'E'; *p++ = 'W';
    } else {
        *p++ = ' '; *p++ = 'H'; *p++ = 'I'; *p++ = ' ';
        p = put_u16(p, sram_meta_best());
    }
    *p = 0;
    write_centered(15, buf);
}

static void write_results(void) {
    write_centered(2, "GAME OVER");
    /* Row 3 stays blank so the title sits above the visor with a gap. */
    if (!RUN_IS_EASY()) write_centered(13, "TRY EASY MODE");
    write_stats_row();
    write_run_row();
    write_prompt(1);
}

static void place_shards(void) {
    /* Birth near the visor rim, falling through the lower well. */
    shards[0].x = 56;  shards[0].y = 56; shards[0].dy = 1; shards[0].tile = 0;
    shards[1].x = 104; shards[1].y = 48; shards[1].dy = 1; shards[1].tile = 1;
    shards[2].x = 80;  shards[2].y = 40; shards[2].dy = 2; shards[2].tile = 2;
}

static void tick_shards(void) {
    u8 i;
    for (i = 0; i < GO_SHARD_N; i++) {
        if (shards[i].y == 0) continue;
        shards[i].y = (u8)(shards[i].y + shards[i].dy);
        /* Expire at the well floor so shards never sit on the gold text. */
        if (shards[i].y > 116) {
            move_sprite(i, 0, 0);
            shards[i].y = 0;
            continue;
        }
        set_sprite_tile(i, (u8)(shards[i].tile ^ ((anim >> 3) & 1)));
        set_sprite_prop(i, S_PRIORITY);
        move_sprite(i, shards[i].x, shards[i].y);
    }
}

static void finish_layout(void) {
    DISPLAY_OFF;
    apply_fade(8);
    gameover_art_draw_full();
    gameover_art_draw_frame();
    write_results();
    gameover_art_paint_attrs(1);
    shown = 1;
    anim = GO_TEXT;
    rise_rows = GOART_MASK_H;
    gameover_art_hide_shards();
    DISPLAY_ON;
}

void gameover_enter(void) {
    u8 i;
    sram_clear_run();   // run over -> suspend save dies with it
    new_best = sram_meta_record(run_state.score, 0, run_state.run_timer);
    DISPLAY_OFF;
    VBK_REG = 0;
    HIDE_WIN;
    SCX_REG = 0;
    SCY_REG = 0;
    WX_REG = 7;
    WY_REG = 144;
    LCDC_REG &= (u8)~LCDCF_BG9C00;

    font_init();
    { font_t f = font_load(font_min); font_set(f); }
    cls();

    gameover_art_load();
    gameover_art_copy_pals(&pals[0][0]);
    gameover_art_load_shards();
    gameover_art_paint_attrs(0);
    gameover_art_draw_frame();
    apply_fade(0);

    anim = 0;
    shown = 0;
    rise_rows = 0;
    pulse = 0;
    prompt_on = 0;
    place_shards();
    for (i = 0; i < 40; i++) move_sprite(i, 0, 0);

    music_play_gameover();
    SHOW_SPRITES;
    SHOW_BKG;
    DISPLAY_ON;
}

void gameover_exit(void) {
    u8 i;
    HIDE_SPRITES;
    HIDE_WIN;
    for (i = 0; i < 40; i++) move_sprite(i, 0, 0);
    SCX_REG = 0;
    SCY_REG = 0;
    WX_REG = 7;
    WY_REG = 144;
    VBK_REG = 0;
}

screen_id_t gameover_tick(u8 keys, u8 pressed) {
    u8 want;
    keys;
    if (anim >= GO_LOCK && (pressed & (J_START | J_A))) {
        if (!shown) {
            finish_layout();
            return SCREEN_SELF;
        }
        return SCREEN_TITLE;
    }
    if (anim < 255 && !shown) anim++;

    want = 0;
    if (anim >= GO_LOCK) {
        want = (u8)((u16)(anim - GO_LOCK) * GOART_MASK_H / (GO_RISE_END - GO_LOCK));
        if (want > GOART_MASK_H) want = GOART_MASK_H;
    }
    if (want > rise_rows) {
        /* Wait once on the 9 reveal frames so the well rewrite stays in
           VBlank. Turning the LCD off here flashed white in the preview. */
        wait_vbl_done();
        rise_rows = want;
        gameover_art_draw_rise(rise_rows);
    }

    if (anim >= 80) tick_shards();

    if (anim >= GO_TEXT && !shown) {
        DISPLAY_OFF;
        write_results();
        gameover_art_paint_attrs(1);
        apply_fade(8);
        shown = 1;
        gameover_art_hide_shards();
        DISPLAY_ON;
    }

    if (shown || anim >= GO_RISE_END) {
        pulse = (u8)(pulse + 1);
        if (pulse >= 90) pulse = 0;
    }
    /* 32 frames on, 16 off. Cheap: rewrite the one row only on a toggle. */
    if (shown) {
        u8 on = (u8)((pulse % 48) < 32);
        if (on != prompt_on) {
            wait_vbl_done();
            write_prompt(on);
        }
    }
    return SCREEN_SELF;
}

void gameover_draw(void) {
    /* Palette heals for slots 0-4 land in the loop's VBlank commit. */
    if (!shown && anim <= GO_RISE_END) {
        u8 level = (u8)((u16)anim * 8 / GO_RISE_END);
        apply_fade(level);
    }
    if (shown || anim >= GO_RISE_END) pulse_ember();
}
