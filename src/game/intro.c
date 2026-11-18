#pragma bank 26
// Lore intro (spec 2026-11-16 §1) and title attract mode (2026-11-17
// addendum). Seven shots in the Ultima: Runes of Virtue grammar: panels that
// pan, a window text band, cell swaps, palette fades and small OBJ parades.
// Pictures, text and palettes are DATA from scripts/gen_intro.py
// (src/render/intro_*.c, banks 27+); this file owns the timeline.
//
// Each scene loads with the LCD on under black palettes (32 tiles or four
// map rows a frame), then fades in, so a load never shows. The window band
// (WY=112, rows 1-2) carries the lines over the panning panel.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/music.h"
#include "core/types.h"
#include "game/attract.h"
#include "game/class_select.h"
#include "game/loop.h"
#include "game/player.h"
#include "game/run_state.h"
#include "game/title.h"
#include "game/vignette.h"
#include "input/input.h"
#include "render/intro_data.h"
#include "render/palette.h"
#include "render/tiles.h"

BANKREF(intro_enter)

u16 intro_pal[32];
u8 attract_mute;
u8 attract_demo;

#define IN_BLACK BGR555(1, 0, 3)
#define IN_WHITE BGR555(31, 31, 31)
#define IN_LOADED 0xFF
#define IN_NONE 0xFF
#define IN_SHOTS 7
#define IN_SPARK_TILE 127   // exclusive OBJ range: BG 8800 mode never writes it
#define IN_SPARK_SPR 20
#define IN_BOOT_SETTLE 2

static u8 in_attract;       // 0 = power-on intro, 1 = attract replay
static u8 in_shot;
static u8 in_scene;
static u8 in_load;
static u8 in_settle;
static u8 in_t;
static u8 in_k, in_white, in_pal_set;
static u8 in_shown_k, in_shown_white, in_dirty;
static u8 in_scx, in_scy;
static u8 in_blk, in_blk_part;
static u8 in_blink;
static u16 in_cur[32];
static u8 attract_next_demo;  // the cycle alternates intro and demo
static u8 attract_demo_idx;

static const u8 shot_scene[IN_SHOTS] = {
    ISC_VALLEY, ISC_VALLEY, ISC_BUSTS, ISC_SHRINE, ISC_CHOSEN, ISC_CLIFF, ISC_TITLE
};
static const u8 shot_len[IN_SHOTS] = { 180, 240, 180, 180, 240, 180, 180 };
// bit 0 = fade in, bit 1 = fade out (shot 2 is a hard cut back to the sky;
// shot 7 hands straight to the title).
static const u8 shot_fade[IN_SHOTS] = { 1, 2, 3, 3, 3, 3, 1 };

static const i8 shake_x[4] = { 2, -2, 1, -1 };
static const i8 shake_y[4] = { 0, 1, -1, 0 };
static const u8 spark_x[5] = { 22, 50, 80, 110, 138 };

// 3x3 spark with a bright core (colour 3 core, colour 2 ring).
static const u8 spark_tile[16] = {
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x38,
    0x10, 0x38, 0x00, 0x38, 0x00, 0x00, 0x00, 0x00
};

static u8 io(u8 op, u8 a, u8 b) {
    return INTRO_IO(in_scene, op, a, b);
}

// k = 0..4 steps from c toward target (4 = target).
static u16 mix(u16 c, u16 target, u8 k) {
    u8 r, g, b;
    u8 inv = (u8)(4 - k);
    r = (u8)(((c & 31) * inv + (target & 31) * k) >> 2);
    g = (u8)((((c >> 5) & 31) * inv + ((target >> 5) & 31) * k) >> 2);
    b = (u8)((((c >> 10) & 31) * inv + ((target >> 10) & 31) * k) >> 2);
    return (u16)(r | ((u16)g << 5) | ((u16)b << 10));
}

static void compose(void) {
    u8 i;
    u16 target = in_white ? IN_WHITE : IN_BLACK;
    for (i = 0; i < 32; ++i)
        in_cur[i] = in_k ? mix(intro_pal[i], target, in_k) : intro_pal[i];
    in_shown_k = in_k;
    in_shown_white = in_white;
}

static void commit(void) {
    u8 i;
    // CRAM ignores writes in mode 3: commit at the top of a fresh VBlank.
    // (Already inside VBlank at LY 150+ would spill into line 0.) loop_run
    // then skips its own wait because the VBlank epoch moved.
    wait_vbl_done();
    BCPS_REG = 0x80;
    for (i = 0; i < 32; ++i) {
        BCPD_REG = (u8)in_cur[i];
        BCPD_REG = (u8)(in_cur[i] >> 8);
    }
    in_dirty = 0;
}

static void hide_all_sprites(void) {
    u8 i;
    for (i = 0; i < 40; ++i) move_sprite(i, 0, 0);
}

static void queue_block(u8 id) {
    // One pending block; a second request flushes the first immediately.
    while (in_blk != IN_NONE) {
        if (!io(IOP_BLOCK, in_blk, in_blk_part++)) in_blk = IN_NONE;
    }
    in_blk = id;
    in_blk_part = 0;
}

static void put_hero(u8 cls, i16 x, u8 y, u8 flip) {
    u8 part;
    u8 id = (u8)(cls << 2);
    u8 base = (u8)(SPR_CLASS_BASE + cls * SPR_CLASS_STRIDE);
    u8 prop = (u8)((cls + 1) | (flip ? S_FLIPX : 0));
    for (part = 0; part < 4; ++part) {
        i16 sx = x + ((part & 1) ? 16 : 8);
        set_sprite_tile((u8)(id + part), (u8)(base + (flip ? (part ^ 1) : part)));
        set_sprite_prop((u8)(id + part), prop);
        if (sx <= 0 || sx >= 168) move_sprite((u8)(id + part), 0, 0);
        else move_sprite((u8)(id + part), (u8)sx, (u8)(y + ((part >= 2) ? 24 : 16)));
    }
}

static void hide_hero(u8 cls) {
    u8 id = (u8)(cls << 2);
    move_sprite(id, 0, 0); move_sprite((u8)(id + 1), 0, 0);
    move_sprite((u8)(id + 2), 0, 0); move_sprite((u8)(id + 3), 0, 0);
}

// Smoothstep pan: 0 before t0, dist after t0 + dur.
static u8 pan(u8 t, u8 t0, u8 dur, u8 dist) {
    u16 p;
    u32 e;
    if (t <= t0) return 0;
    if ((u8)(t - t0) >= dur) return dist;
    p = (u16)(((u16)(t - t0) << 8) / dur);
    e = ((u32)p * p * (768u - 2u * p)) >> 16;
    return (u8)(((u16)dist * (u16)e) >> 8);
}

static void shot_setup(void) {
    in_t = 0;
    in_scx = in_scy = 0;
    in_blink = 0;
    hide_all_sprites();
    switch (in_shot) {
    case 0: queue_block(IB_VALLEY_ONCE); SHOW_WIN; break;
    case 1:
        io(IOP_PAL, 0, 0);
        queue_block(IB_VALLEY_TEAR0);
        queue_block(IB_VALLEY_TORE);
        SHOW_WIN;
        break;
    case 2: queue_block(IB_BUSTS_COLOSSI); SHOW_WIN; break;
    case 3:
        set_sprite_data(IN_SPARK_TILE, 1, spark_tile);
        queue_block(IB_SHRINE_SPIRITS);
        SHOW_WIN;
        break;
    case 5: in_scx = 32; queue_block(IB_CLIFF_WILD); SHOW_WIN; break;
    case 6: queue_block(IB_TITLE_VESSEL); HIDE_WIN; break;
    default: HIDE_WIN; break;
    }
    in_dirty = 1;
}

static void start_shot(u8 shot) {
    queue_block(IN_NONE);     // finish the old scene's pending cells first
    in_shot = shot;
    if (shot_scene[shot] != in_scene) {
        in_scene = shot_scene[shot];
        in_load = 0;
        in_k = 4;
        in_white = 0;
        compose();
        in_dirty = 1;
        hide_all_sprites();
        HIDE_WIN;
        in_scx = in_scy = 0;
        return;
    }
    shot_setup();
}

static screen_id_t intro_finish(void) {
    intro_exit();
    return SCREEN_TITLE;
}

static void begin_intro(void);

void intro_enter(void) {
    in_settle = 0;
    in_scene = IN_NONE;
    in_blk = IN_NONE;
    in_load = IN_LOADED;
    in_shot = 0;
    in_k = 4;
    in_white = 0;
    in_dirty = 0;
    {
        u8 i;
        for (i = 0; i < 32; ++i) intro_pal[i] = 0;
    }
    if (in_attract) {
        in_settle = IN_BOOT_SETTLE;
        begin_intro();
    }
}

void intro_exit(void) {
    HIDE_WIN;
    hide_all_sprites();
    SCX_REG = 0;
    SCY_REG = 0;
    VBK_REG = 0;
    palette_obj_pending_commit = 0;
    in_attract = 1;     // every later intro is an attract replay
}

static void begin_intro(void) {
    u8 i;
    palette_bg_pending_commit = 0;
    palette_bg_dirty = 0;
    for (i = 0; i < 32; ++i) intro_pal[i] = IN_BLACK;
    in_k = 4;
    compose();
    commit();
    LCDC_REG |= 0x40;                // window map 0x9C00, as the HUD sets it
    WX_REG = 7;
    WY_REG = 112;
    hide_all_sprites();
    tiles_load_all_class_sprites();
    palette_obj_cache_title();
    palette_obj_pending_commit = PALETTE_OBJ_COMMIT_PASSES;
    SHOW_BKG;
    SHOW_SPRITES;
    DISPLAY_ON;
    music_play_title();
    attract_next_demo = 1;       // the next attract item is the demo
    start_shot(0);
}

static void tick_shot(void) {
    u8 t = in_t;
    u8 len = shot_len[in_shot];
    u8 fade = shot_fade[in_shot];
    u8 i;
    in_k = 0;
    in_white = 0;
    switch (in_shot) {
    case 0:
        in_scy = pan(t, 20, 140, 128);
        break;
    case 1:
        if (t == 20) queue_block(IB_VALLEY_TEAR1);
        else if (t == 40) queue_block(IB_VALLEY_TEAR2);
        else if (t == 60) queue_block(IB_VALLEY_TEAR3);
        else if (t == 80) queue_block(IB_VALLEY_TEAR4);
        else if (t == 120) queue_block(IB_VALLEY_DEVOUR);
        if (t == 150) { io(IOP_PAL, 1, 0); in_dirty = 1; }
        if (t == 190) { io(IOP_PAL, 2, 0); in_dirty = 1; }
        in_scy = pan(t, 120, 110, 128);
        in_scx = 0;
        if (t >= 20 && t < 90) {
            u8 s = (u8)((t / 3) & 3);
            in_scx = (u8)shake_x[s];
            in_scy = (u8)(in_scy + (u8)shake_y[s]);
        }
        if (t >= 20 && t < 24) { in_k = 1; in_white = 1; }
        break;
    case 2:
        for (i = 0; i < 9; ++i) {
            u8 at = (u8)(12 + i * 12);
            if (t == at) queue_block((u8)(IB_BUSTS_BUST0 + i));
            if (t >= at && t < (u8)(at + 2)) { in_k = 2; in_white = 1; }
        }
        break;
    case 3:
        for (i = 0; i < 5; ++i) {
            u8 spr = (u8)(IN_SPARK_SPR + i);
            u8 y = (u8)(62 - (u8)(((u8)(t >> 1) + i * 23u) % 62u));
            if (t < 16 || t >= (u8)(len - 16)) { move_sprite(spr, 0, 0); continue; }
            set_sprite_tile(spr, IN_SPARK_TILE);
            set_sprite_prop(spr, (u8)(i + 1));
            move_sprite(spr, (u8)(spark_x[i] + 8 - 4), (u8)(y + 16 - 4));
        }
        break;
    case 4:
        for (i = 0; i < 5; ++i) {
            u8 at = (u8)(16 + i * 32);
            u8 left = (u8)((i & 1) == 0);
            u8 slide;
            i16 x;
            if (t < at || t >= (u8)(len - 16)) { hide_hero(i); continue; }
            if (t == at) queue_block((u8)(IB_CHOSEN_HERO0 + i));
            slide = (u8)(t - at);
            if (slide > 16) slide = 16;
            // Unsigned shifts only: signed division pulls a library
            // routine into the full home bank.
            if (left) x = (i16)((u16)(24u * slide) >> 4) - 16;
            else x = (i16)(160u - ((u16)(24u * slide) >> 4));
            put_hero(i, x, (u8)((3 + i * 3) * 8 - (((t >> 4) + i) & 1)),
                     slide < 16 ? (u8)((t >> 3) & 1) : 0);
        }
        break;
    case 5:
        in_scx = (u8)(32 - pan(t, 0, 170, 32));
        in_scy = pan(t, 0, 170, 16);
        if (t == 80) queue_block(IB_CLIFF_BIND);
        break;
    case 6:
        for (i = 0; i < 5; ++i) {
            i16 x;
            u8 walking = 1;
            u8 bob = 0;
            u8 dt = (u8)(t > (u8)(i * 8) ? t - i * 8 : 0);
            if (dt >= 90) { dt = 90; walking = 0; bob = (u8)(((t / 20) + i) & 1); }
            x = (i16)((u16)((u16)dt * (u16)(36u + 28u * i)) / 90u) - 20;
            put_hero(i, x, (u8)(47 - bob), walking ? (u8)(((t + i * 5) >> 3) & 1) : 0);
        }
        if (t == 100) queue_block(IB_TITLE_PRESS);
        if (t > 100) {
            u8 on = (u8)(((t / 30) & 1) == 0);
            if (on != in_blink) {
                in_blink = on;
                queue_block(on ? IB_TITLE_PRESS : IB_TITLE_CLEAR);
            }
        }
        break;
    }
    if ((fade & 1) && t < 16) in_k = (u8)(4 - (t >> 2));
    if ((fade & 2) && t >= (u8)(len - 16)) in_k = (u8)(((u8)(t - (u8)(len - 16)) >> 2) + 1);
    if (in_k != in_shown_k || in_white != in_shown_white || in_dirty) {
        compose();
        in_dirty = 1;
    }
}

screen_id_t intro_tick(u8 keys, u8 pressed) {
    keys;
    if (in_dirty) commit();
    SCX_REG = in_scx;
    SCY_REG = in_scy;

    if (in_settle < IN_BOOT_SETTLE) {
        // Power-on: two blank frames so a headless harness can set
        // attract_mute before the first picture; then CUTSCENES OFF and the
        // mute go straight to the title.
        if (++in_settle < IN_BOOT_SETTLE) return SCREEN_SELF;
        if (!in_attract && (attract_mute || vignette_cutscenes_off()))
            return intro_finish();
        begin_intro();
        return SCREEN_SELF;
    }
    // Boot intro: A, B or START skip. Attract replay: any button.
    if (pressed & (in_attract ? 0xFF : (J_A | J_B | J_START)))
        return intro_finish();

    if (in_blk != IN_NONE) {
        if (!io(IOP_BLOCK, in_blk, in_blk_part++)) in_blk = IN_NONE;
    }
    if (in_load != IN_LOADED) {
        if (!io(IOP_LOAD, in_load++, 0)) {
            in_load = IN_LOADED;
            shot_setup();
        }
        return SCREEN_SELF;
    }
    tick_shot();
    if (++in_t >= shot_len[in_shot]) {
        if (in_shot + 1 >= IN_SHOTS) return intro_finish();
        start_shot((u8)(in_shot + 1));
    }
    return SCREEN_SELF;
}

// ---------------------------------------------------------------- attract

#include "game/attract_demo_data.h"

static u8 demo_saved_easy;
static u16 demo_saved_frame;
static u16 demo_frames;
static u16 demo_i;
static u8 demo_left, demo_keys, demo_prev;

screen_id_t attract_begin(void) BANKED {
    const u8 *d;
    if (!attract_next_demo) {
        attract_next_demo = 1;
        in_attract = 1;
        return SCREEN_INTRO;
    }
    attract_next_demo = 0;
    d = attract_demos[attract_demo_idx];
    attract_demo = 1;
    demo_frames = 0;
    demo_i = 0;
    demo_left = 0;
    demo_keys = 0;
    demo_prev = 0;
    demo_saved_easy = class_select_easy_mode;
    demo_saved_frame = loop_frame_counter;
    class_select_easy_mode = 0;
    player_init_from_class(d[0]);
    title_stage_warp = d[1];
    // run_init_enter seeds the run from loop_frame_counter.
    loop_frame_counter = (u16)(d[2] | ((u16)d[3] << 8));
    music_stop();
    return SCREEN_RUN_INIT;
}

static screen_id_t attract_demo_end(u8 raw) {
    attract_demo = 0;
    class_select_easy_mode = demo_saved_easy;
    loop_frame_counter = (u16)(demo_saved_frame + demo_frames);
    title_stage_warp = 0xFF;
    // Keep the real buttons as the previous state: a button held through the
    // hand-back is not a fresh press on the title.
    input_keys = raw;
    input_pressed = input_released = 0;
    if (++attract_demo_idx >= ATTRACT_DEMO_COUNT) attract_demo_idx = 0;
    return SCREEN_TITLE;
}

screen_id_t attract_demo_frame(void) BANKED {
    const u8 *d = attract_demos[attract_demo_idx];
    u8 scr = loop_current_screen;
    u8 keys = 0;
    // input_keys is still the real joypad here. Any held button ends the demo
    // (attract only starts with none held). input_pressed is not used: its
    // previous state is the demo's keys, so it misses a key the demo holds.
    if (input_keys || ++demo_frames >= ATTRACT_DEMO_FRAMES
        || (scr != SCREEN_RUN_INIT && scr != SCREEN_ROOM && scr != SCREEN_DIALOG))
        return attract_demo_end(input_keys);
    if (scr == SCREEN_RUN_INIT) {
        // Demo runs skip the foyer vignette: the intro already shows the art.
        run_state.vignette_seen = 0xFFFF;
        room_start_vignette = 0;
    } else {
        // ROOM and DIALOG follow the recording (A dismisses a stage card).
        if (!demo_left) {
            u16 off = (u16)(4u + demo_i * 2u);
            if (d[off + 1] == 0) {
                demo_keys = 0;
                demo_left = 0xFF;
            } else {
                demo_keys = d[off];
                demo_left = d[off + 1];
                demo_i++;
            }
        }
        if (demo_left != 0xFF) demo_left--;
        keys = demo_keys;
    }
    input_keys = keys;
    input_pressed = (u8)(keys & ~demo_prev);
    input_released = (u8)(demo_prev & ~keys);
    demo_prev = keys;
    return SCREEN_SELF;
}
