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

static void write_results(void) {
    gotoxy(2, 2);  text_write("TIME ");
    text_u16((u16)(run_state.run_timer / 60));
    text_write(":");
    text_digit((u8)((run_state.run_timer % 60) / 10));
    text_digit((u8)(run_state.run_timer % 10));
    gotoxy(6, 3);  text_write("GAME  OVER");
    gotoxy(1, 13);
    text_write(RUN_IS_EASY() ? "TRY ANOTHER HERO" : "SELECT EASY AT HERO");
    /* Stay in columns 1..18 so 5-digit values cannot wrap or eat the frame. */
    gotoxy(1, 14); text_write("RM "); text_u16((u16)run_state.room_counter);
    text_write(" KILL "); text_u16(run_state_enemies_killed_total());
    gotoxy(2, 15); text_write("PRESS  START");
    gotoxy(1, 16); text_write("RUN "); text_u16((u16)run_state.score);
    if (new_best & 1) text_write(" NEW");
    else { text_write(" HI "); text_u16(sram_meta_best()); }
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
