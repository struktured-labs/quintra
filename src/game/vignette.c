#pragma bank 21
// Pinned: autobank (255) packed these into nearly-full banks 2/17/19.
// Banks 20+ were empty; one bank keeps the player and its art together.
// Stage-transition vignettes. Data-driven: every picture, text line, effect
// state, palette and timing comes from scripts/gen_vignettes.py output
// (src/render/vignette_*.c). This file is the one generic player.
//
// Timeline (60 fps): black load (~10 frames, art copied with the LCD on
// while every palette is black) -> 4-step fade in over 16 frames -> walk and
// effect -> exit fade to black, or a white lift for the Riftwild. A, B or
// START skips from frame 8. The room returns through room_request_resume(),
// which reloads every BG tile range the vignette borrowed.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <string.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/dialog.h"
#include "game/loop.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/sram.h"
#include "game/vignette.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "render/vignette_data.h"

BANKREF(vignette_enter)

void room_prepare_stage_arrival(u8 stage) BANKED;

static u8 vig_id;
static u8 vig_file;
static u8 vig_meta[VIG_META_SIZE];
static u16 vig_pal[32];
static u16 vig_hero_base[4];
static u16 vig_hero_pal[4];
static u8 vig_load;      // load step; VIG_LOADED once playing
static u8 vig_t;         // frame since fade-in start
static u8 vig_exit_k;    // exit fade progress (0 = not exiting)
static u8 vig_cyc_phase;
static u8 vig_hero_k;    // hero fade step, 4 = hidden

#define VIG_LOADED 0xFF
#define VIG_ROW_STEPS 3
#define VIG_BLACK BGR555(1, 0, 3)
#define VIG_WHITE BGR555(31, 31, 31)
// Leaves borrow an exclusive-OBJ tile (0x8000-0x87FF). BG 8800 mode does
// not use that range, and room_enter reloads every OBJ tile on resume.
#define VIG_LEAF_TILE 32
#define VIG_LEAF_SPR  4
#define VIG_FX_LEAVES 1

u8 room_start_vignette;
u8 vig_from_town;
extern u8 stage_fade;

// 8x8 leaf, colours 1=dark, 2=mid, 3=light rim.
static const u8 vig_leaf_tile[16] = {
    0x18, 0x00,
    0x3C, 0x08,
    0x7E, 0x1C,
    0x7C, 0x38,
    0x3C, 0x18,
    0x18, 0x08,
    0x08, 0x00,
    0x00, 0x00
};

static const u8 vig_table[VIG_COUNT] = VIG_TABLE;
static const u8 vig_stage_table[9] = VIG_STAGE_TABLE;
static const u8 vig_zero[16] = { 0 };
// BG slots inside the borrowed ranges that the room resume path leaves
// as-is (measured blank in dungeon, Riftwild and stage-3 rooms): blank them
// again on exit so no vignette art can leak into a later room.
static const u8 vig_blank_slots[] = { 0xC8, 0xC9, 0xCA, 0xCB, 0xFF,
                                      0x44, 0x45, 0x46, 0x47 };

static void vig_io(u8 op, u8 arg, u8 *dst) {
    VIG_DISPATCH(vig_file, op, arg, dst);
}

static u16 meta16(u8 off) {
    return (u16)(vig_meta[off] | ((u16)vig_meta[off + 1] << 8));
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

static void write_bg_palettes(void) {
    u8 i;
    // loop.c skips its VBlank wait after an overrun frame (the chunked art
    // load can overrun). CRAM ignores writes in mode 3, so only write in VBlank.
    if (LY_REG < 144) wait_vbl_done();
    BCPS_REG = 0x80;
    for (i = 0; i < 32; ++i) {
        BCPD_REG = (u8)vig_pal[i];
        BCPD_REG = (u8)(vig_pal[i] >> 8);
    }
    OCPS_REG = 0x88;     // OBJ palette 1 = the champion
    for (i = 0; i < 4; ++i) {
        OCPD_REG = (u8)vig_hero_pal[i];
        OCPD_REG = (u8)(vig_hero_pal[i] >> 8);
    }
}

static void black_palettes(void) {
    u8 i;
    for (i = 0; i < 32; ++i) vig_pal[i] = VIG_BLACK;
    for (i = 0; i < 4; ++i) vig_hero_pal[i] = VIG_BLACK;
}

// Rebuild this frame's 32 BG colours: base palette, lava-style colour
// cycle, then the global fade (k toward black, or white when lifting).
static void compose_palettes(u8 k, u8 white) {
    u8 i, n, len;
    for (i = 0; i < 32; ++i)
        vig_pal[i] = meta16((u8)(VM_PAL + (i << 1)));
    n = vig_meta[VM_CYC_SLOTS];
    len = vig_meta[VM_CYC_LEN];
    for (i = 0; i < n; ++i) {
        u8 s = vig_meta[(u8)(VM_CYC + (i << 1))];
        u8 c = (u8)(vig_meta[(u8)(VM_CYC + (i << 1) + 1)] + vig_cyc_phase);
        while (c >= len) c = (u8)(c - len);
        vig_pal[s] = meta16((u8)(VM_CYC_COL + (c << 1)));
    }
    if (k) {
        u16 target = white ? VIG_WHITE : VIG_BLACK;
        for (i = 0; i < 32; ++i) vig_pal[i] = mix(vig_pal[i], target, k);
    }
    for (i = 0; i < 4; ++i) {
        u16 c = vig_hero_k >= 4 ? VIG_BLACK
            : mix(vig_hero_base[i], VIG_BLACK, vig_hero_k);
        vig_hero_pal[i] = k ? mix(c, white ? VIG_WHITE : VIG_BLACK, k) : c;
    }
}

static void hide_hero(void) {
    u8 i;
    for (i = 0; i < 4; ++i) move_sprite(i, 0, 0);
}

static void hide_leaves(void) {
    u8 i;
    for (i = 0; i < 4; ++i) move_sprite((u8)(VIG_LEAF_SPR + i), 0, 0);
}

static void load_leaf_obj(void) {
    static const u16 leaf_pal[4] = {
        VIG_BLACK,
        BGR555(8, 14, 3),
        BGR555(16, 22, 4),
        BGR555(22, 26, 8)
    };
    u8 i;
    set_sprite_data(VIG_LEAF_TILE, 1, vig_leaf_tile);
    if (LY_REG < 144) wait_vbl_done();
    OCPS_REG = 0x90;     // OBJ palette 2
    for (i = 0; i < 4; ++i) {
        OCPD_REG = (u8)leaf_pal[i];
        OCPD_REG = (u8)(leaf_pal[i] >> 8);
    }
    hide_leaves();
}

static void place_leaves(void) {
    static const u8 lx[4] = { 36, 56, 104, 124 };
    static const u8 lphase[4] = { 0, 37, 74, 111 };
    static const u8 lspd[4] = { 1, 2, 1, 2 };
    u8 i;
    if (vig_meta[VM_FX] != VIG_FX_LEAVES) return;
    for (i = 0; i < 4; ++i) {
        u8 t = (u8)(vig_t + lphase[i]);
        u8 y = (u8)(12 + (u8)((u16)t * lspd[i] % 100));
        u8 x = (u8)(lx[i] + ((t >> 3) & 2) - 1);
        u8 spr = (u8)(VIG_LEAF_SPR + i);
        if (y >= 112) { move_sprite(spr, 0, 0); continue; }
        set_sprite_tile(spr, VIG_LEAF_TILE);
        set_sprite_prop(spr, (u8)(0x02
            | ((t >> 4) & 1 ? S_FLIPX : 0)
            | ((t >> 5) & 1 ? S_FLIPY : 0)));
        move_sprite(spr, (u8)(x + 8), (u8)(y + 16));
    }
}

static void place_hero(void) {
    u8 t0 = vig_meta[VM_WALK_T0];
    u8 t1 = vig_meta[VM_WALK_T1];
    u8 y0 = vig_meta[VM_HERO_Y0];
    u8 y1 = vig_meta[VM_HERO_Y1];
    u8 x = vig_meta[VM_HERO_X];
    u8 y;
    u8 base = (u8)(SPR_CLASS_BASE + (u8)(player.class_id * SPR_CLASS_STRIDE));
    u8 flip = (vig_t >> 3) & 1;
    if (vig_hero_k >= 4) { hide_hero(); return; }
    if (vig_t <= t0) y = y0;
    else if (vig_t >= t1) y = y1;
    else {
        // smoothstep(p) with p in 0..255
        u16 p = (u16)(((u16)(vig_t - t0) << 8) / (u8)(t1 - t0));
        u32 e = ((u32)p * p * (768u - 2u * p)) >> 16;
        y = (u8)(y0 - (u8)(((u16)(y0 - y1) * (u16)e) >> 8));
    }
    // Walk cycle: H-flip the 16x16 champion every 8 frames.
    set_sprite_tile(0, (u8)(base + (flip ? 1 : 0)));
    set_sprite_tile(1, (u8)(base + (flip ? 0 : 1)));
    set_sprite_tile(2, (u8)(base + (flip ? 3 : 2)));
    set_sprite_tile(3, (u8)(base + (flip ? 2 : 3)));
    {
        u8 prop = (u8)(0x01 | (flip ? S_FLIPX : 0));
        set_sprite_prop(0, prop); set_sprite_prop(1, prop);
        set_sprite_prop(2, prop); set_sprite_prop(3, prop);
    }
    move_sprite(0, (u8)(x + 8), (u8)(y + 16));
    move_sprite(1, (u8)(x + 16), (u8)(y + 16));
    move_sprite(2, (u8)(x + 8), (u8)(y + 24));
    move_sprite(3, (u8)(x + 16), (u8)(y + 24));
}

static void apply_events(void) {
    u8 i, n = vig_meta[VM_EVENTS];
    for (i = 0; i < n; ++i) {
        if (vig_meta[(u8)(VM_EV + (i << 1))] == vig_t)
            vig_io(VIG_OP_STATE, vig_meta[(u8)(VM_EV + (i << 1) + 1)], 0);
    }
}

// vignette_enter/vignette_tick are reached only through the screens[] table
// in loop.c, which switches to BANK(vignette_enter) before the call.
void vignette_enter(void) {
    u8 i;
    u8 entry = vig_table[vig_id];
    vig_file = (u8)(entry >> 4);
    vig_io(VIG_OP_META, (u8)(entry & 0x0F), vig_meta);
    // The door path may have queued room palette heals; they must not
    // repaint the vignette mid-play.
    palette_bg_pending_commit = 0;
    palette_bg_dirty = 0;
    palette_obj_pending_commit = 0;
    HIDE_WIN;
    SCX_REG = 0;
    SCY_REG = 0;
    VBK_REG = 0;
    for (i = 0; i < 40; ++i) move_sprite(i, 0, 0);
    wait_vbl_done();
    // Capture the champion's OBJ palette before blacking everything out.
    for (i = 0; i < 4; ++i) {
        OCPS_REG = (u8)(0x08 + (i << 1));
        vig_hero_base[i] = OCPD_REG;
        OCPS_REG = (u8)(0x08 + (i << 1) + 1);
        vig_hero_base[i] |= (u16)OCPD_REG << 8;
    }
    black_palettes();
    write_bg_palettes();
    SHOW_SPRITES;
    vig_load = 0;
    vig_t = 0;
    vig_exit_k = 0;
    vig_cyc_phase = 0;
    vig_hero_k = 0;
    if (vig_meta[VM_SFX]) sfx_play_reward(SFX_REWARD_MAGIC);
    if (vig_meta[VM_FX] == VIG_FX_LEAVES) load_leaf_obj();
    else hide_leaves();
}

static screen_id_t vignette_finish(void) {
    u8 i;
    hide_hero();
    hide_leaves();
    HIDE_SPRITES;
    OCPS_REG = 0x88;
    for (i = 0; i < 4; ++i) {
        OCPD_REG = (u8)vig_hero_base[i];
        OCPD_REG = (u8)(vig_hero_base[i] >> 8);
    }
    for (i = 0; i < sizeof(vig_blank_slots); ++i)
        set_bkg_data(vig_blank_slots[i], 1, vig_zero);
    // Presentation time is not run time (same rule as the reward tableau).
    g_vbl_ticks = 0;
    room_request_resume();
    return SCREEN_ROOM;
}

screen_id_t vignette_tick(u8 keys, u8 pressed) {
    u8 tiles_steps;
    keys;
    // Top of VBlank: commit last frame's colours first. 72 CRAM bytes, well
    // inside mode 1 when the loop dispatches right after wait_vbl_done().
    write_bg_palettes();
    if (vig_load != VIG_LOADED) {
        tiles_steps = (u8)((vig_meta[VM_TILES] + 31) >> 5);
        if (vig_load < tiles_steps) {
            vig_io(VIG_OP_TILES, vig_load, 0);
        } else if (vig_load < (u8)(tiles_steps + VIG_ROW_STEPS)) {
            vig_io(VIG_OP_ROWS, (u8)(vig_load - tiles_steps), 0);
        } else {
            vig_io(VIG_OP_TEXT, vig_meta[VM_VARIANT], 0);
            apply_events();
            vig_load = VIG_LOADED;
            compose_palettes(4, 0);
            return SCREEN_SELF;
        }
        vig_load++;
        return SCREEN_SELF;
    }

    if (vig_t >= 8 && !vig_exit_k && vig_t < vig_meta[VM_EXIT_T]
        && (pressed & (J_A | J_B | J_START))) {
        vig_t = vig_meta[VM_EXIT_T];
    }
    if (vig_t >= vig_meta[VM_EXIT_T]) {
        // 4 exit steps, 4 frames each (skip and natural end share it).
        u8 k = (u8)(((u8)(vig_t - vig_meta[VM_EXIT_T]) >> 2) + 1);
        if (k > 4) return vignette_finish();
        vig_exit_k = k;
    }
    if (vig_t) apply_events();
    if (vig_meta[VM_CYC_SLOTS]
        && vig_t % vig_meta[VM_CYC_PERIOD] == 0) vig_cyc_phase++;
    if (vig_t >= vig_meta[VM_FADE_T0]) {
        u8 k = (u8)((u8)(vig_t - vig_meta[VM_FADE_T0]) / vig_meta[VM_FADE_STEP]);
        vig_hero_k = k > 4 ? 4 : k;
    }
    place_hero();
    place_leaves();
    {
        u8 k = 0, white = 0;
        u8 flash = vig_meta[VM_FLASH_T];
        if (vig_t < 16) k = (u8)(4 - (vig_t >> 2));
        if (flash && vig_t >= flash && vig_t < (u8)(flash + 8)) {
            k = vig_t < (u8)(flash + 4) ? 3 : 2;
            white = 1;
        }
        if (vig_exit_k) {
            k = vig_exit_k;
            white = vig_meta[VM_EXIT_WHITE];
        }
        compose_palettes(k, white);
    }
    vig_t++;
    return SCREEN_SELF;
}

static u8 vig_arm(u8 id) {
    u16 bit;
    if (id >= VIG_COUNT) return 0;
    bit = (u16)1 << id;
    if (run_state.vignette_seen & bit) return 0;
    if (vignette_cutscenes_off()) return 0;
    run_state.vignette_seen |= bit;
    vig_id = id;
    // The seam already saved the suspend; save again so a save-and-quit or
    // power cycle mid-run cannot replay this vignette.
    sram_save_run();
    return 1;
}

static screen_id_t vig_try_stage(u8 stage, u8 use_card) {
    u8 slot = stage;
    while (slot >= 9) slot = (u8)(slot - 9);
    if (vig_arm(vig_stage_table[slot])) return SCREEN_VIGNETTE;
    if (!use_card) return SCREEN_SELF;
    room_prepare_stage_arrival(stage);
    return SCREEN_DIALOG;
}

screen_id_t vignette_arrival(u8 from_world, u8 stage) BANKED {
    u8 from_town = vig_from_town;
    vig_from_town = 0;
    if (!run_state.world_mode) {
        if (RUN_ROOM_IS_TOWN(run_state.room_counter))
            return SCREEN_SELF;
        if (!from_world && !from_town)
            return SCREEN_SELF;
        // Riftwild-to-dungeon falls back to the classic stage card.
        // Town and new-run foyer keep the existing dim fade instead.
        return vig_try_stage(stage, from_world);
    }
    if (!from_world
        && vig_arm(RUN_RIFTWILD_IS_HOLLOW() ? VIG_RIFT_HOLLOW : VIG_RIFT_WAKING))
        return SCREEN_VIGNETTE;
    return SCREEN_SELF;
}

screen_id_t vignette_on_run_start(u8 stage) BANKED {
    // Stay on RUN_INIT for one tick so a test harness can mark vignettes
    // seen after run_state_init clears the bits and before this arms.
    static u8 delay;
    room_start_vignette = 0;
    if (!delay) {
        delay = 1;
        return SCREEN_SELF;
    }
    delay = 0;
    if (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter))
        return SCREEN_ROOM;
    {
        screen_id_t next = vig_try_stage(stage, 0);
        if (next == SCREEN_VIGNETTE) {
            stage_fade = 0;
            return SCREEN_VIGNETTE;
        }
        return SCREEN_ROOM;
    }
}

screen_id_t vignette_after_shift(void) BANKED {
    if (RUN_RIFTWILD_IS_HOLLOW() && vig_arm(VIG_RIFT_HOLLOW))
        return SCREEN_VIGNETTE;
    return SCREEN_SELF;
}

u8 vignette_cutscenes_off(void) BANKED {
    return (sram_meta_flags() & META_FLAG_CUTSCENES_OFF) ? 1 : 0;
}

void vignette_toggle_cutscenes(void) BANKED {
    sram_meta_set_flag(META_FLAG_CUTSCENES_OFF, !vignette_cutscenes_off());
}
