#pragma bank 255
// ROOM — top-down gameplay scene. Phase 5: spawns N enemies, supports
// 4-dir movement, 8-dir B-button fire, wall collision, combat resolution.
// Phase 7 wires procgen to fill from biome.room_template_pool.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/music.h"
#include "audio/sfx.h"
#include "core/types.h"
#include "core/rng.h"
#include "game/combat.h"
#include "game/entity.h"
#include "game/entity.h"
#include "game/enemy_ai.h"
#include "game/loop.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/sram.h"
#include "render/class_palettes.h"
#include "render/hud.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

BANKREF(room_enter)

u8 room_tilemap[ROOM_H][ROOM_W];

static u8 room_paused;
static u8 room_resume_flag;   // set by room_request_resume: skip procgen next enter
// Secret door opened by shooting a cracked wall this room (0xFF = none)
static u8 secret_door_x = 0xFF;
static u8 secret_door_y = 0xFF;
static u8 secret_door_x2 = 0xFF;   // secret doors open as a 2-tile pair
static u8 secret_door_y2 = 0xFF;   // (the wide feet box needs 16px)
// Block-push state: current lean direction + how long it's been held.
static u8 push_dir = DIR_NONE;
static u8 push_timer;
// Stage-entry reveal: first room of each new stage fades in from dimmed
// palettes over ~half a second. stage_seen tracks the last stage revealed.
static u8 stage_seen = 0xFF;
static u8 stage_fade;

// Room-clear chime: hostiles seen alive this room (reset on every room
// generation so walking into an empty room never false-fires the chime).
static u8 hostiles_prev;

// Screen shake (BG scroll wiggle; the WINDOW HUD stays put). Set by
// combat via room_shake() on boss kills / player hits.
static u8 shake_timer;
static u8 shake_mag;

// Death sequence: frames left in the fall-down beat before GAMEOVER.
static u8 death_timer;

// Dodge dash (double-tap a direction): a fast i-frame lunge on a short
// cooldown. tap_dir/tap_age detect the double-tap; dash_timer runs the
// lunge; dash_cd gates re-use.
static u8 tap_dir;       // last freshly-pressed cardinal ('L'/'R'/'U'/'D')
static u8 tap_age;       // frames since that press
static u8 dash_timer;    // frames left in the current dash
static u8 dash_cd;       // cooldown before the next dash
static i8 dash_dx, dash_dy;

void room_shake(u8 mag, u8 frames) BANKED {
    shake_mag = mag;
    if (frames > shake_timer) shake_timer = frames;
}

void room_request_resume(void) BANKED { room_resume_flag = 1; }

// Stage themes now live in the Rust content layer (content/src/stages.rs)
// and arrive as generated BGR555 tables: stage_pal / boss_stage_pal /
// stage_pal_crack / stage_names (see src/generated/stages.h). Invalid
// colors or a wrong stage count fail at cargo build, never here.

static u8 room_stage(void) {
    // Endless descent (10th+ boss): the nine themes cycle again —
    // Crystal Caverns at double power, and on down. Stats stay maxed
    // (procgen clamps power separately); this drives look + music.
    u8 s = run_state.bosses_beaten;
    return (s < N_STAGES) ? s : (u8)(s % N_STAGES);
}

// Crawler (enemy) palette — blue, with one accent
static const u16 crawler_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555( 8, 12, 28),
    BGR555( 4,  6, 20),
    BGR555(20, 24, 31),
};

// Skeleton — bone white (OBJ palette 0)
static const u16 skeleton_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(28, 28, 26),
    BGR555(13, 13, 15),
    BGR555(30, 20, 18),
};

// Orc — moss green (OBJ palette 7)
static const u16 orc_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(12, 22,  8),
    BGR555( 5, 10,  4),
    BGR555(27, 13,  6),
};

// Stone Sentinel (mini-boss) palette — granite grey with bright accent
static const u16 sentinel_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(18, 18, 22),
    BGR555( 8,  8, 12),
    BGR555(28, 24, 14),
};

// (Per-stage large-boss palettes now come from the generated stage
// tables — boss_stage_pal in stages.h.)

// Bullet palette — bright gold
static const u16 bullet_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(31, 24,  0),
    BGR555(28, 16,  0),
    BGR555(31, 31,  4),
};

// Heart pickup palette (red). Color 3 is unused by the heart sprite —
// it doubles as the Bomber's lit fuse and the weapon orb's glow core.
static const u16 heart_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(31, 12, 12),
    BGR555(16,  4,  4),
    BGR555(31, 26,  6),
};

// Coin pickup palette (gold)
static const u16 coin_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(31, 24,  4),
    BGR555(18, 12,  0),
    BGR555(31, 31, 14),
};

u8 room_tile_at_px(i16 px, i16 py) BANKED {
    if (px < 0 || py < 0) return BGT_WALL;
    {
        u8 tx = (u8)(px >> 3);
        u8 ty = (u8)(py >> 3);
        if (tx >= ROOM_W || ty >= ROOM_H) return BGT_WALL;
        return room_tilemap[ty][tx];
    }
}

u8 room_tile_walkable(u8 t) BANKED {
    return (t == BGT_FLOOR || t == BGT_FLOOR2 || t == BGT_FLOOR3
         || t == BGT_RUBBLE || t == BGT_DOOR || t == BGT_SPIKES
         // Shop price tags are painted floor (coin glyph + digits)
         || t == HUD_COIN || (t >= HUD_DIGIT_0 && t <= HUD_DIGIT_0 + 9));
}

static u8 is_walkable_at(i16 px, i16 py) {
    return room_tile_walkable(room_tile_at_px(px, py));
}

// Halve each 5-bit channel: pause-dim without storing dim palettes.
static void palette_bg_load_dimmed(u8 slot, const u16 *pal) {
    u16 tmp[4];
    u8 i;
    for (i = 0; i < 4; ++i) tmp[i] = (u16)((pal[i] >> 1) & 0x3DEF);
    palette_bg_load(slot, tmp);
}

static void room_apply_pause_palettes(u8 dim) {
    const u16 (*sp)[4] = stage_pal[room_stage()];
    if (dim) {
        palette_bg_load_dimmed(BGPAL_FLOOR,   sp[0]);
        palette_bg_load_dimmed(BGPAL_WALL,    sp[1]);
        palette_bg_load_dimmed(BGPAL_CRYSTAL, sp[2]);
        palette_bg_load_dimmed(BGPAL_DOOR,    sp[3]);
    } else {
        palette_bg_load(BGPAL_FLOOR,   sp[0]);
        palette_bg_load(BGPAL_WALL,    sp[1]);
        palette_bg_load(BGPAL_CRYSTAL, sp[2]);
        palette_bg_load(BGPAL_DOOR,    sp[3]);
    }
}

// Rewrite the 4 cardinal door tiles after a boss seal is lifted.
// Called at the top of vblank so the handful of VRAM writes land safely.
static void room_unseal_doors(void) {
    static const u8 dxs[8] = { 9, 10, 9, 10, 0, 0, ROOM_W - 1, ROOM_W - 1 };
    static const u8 dys[8] = { 0, 0, ROOM_H - 1, ROOM_H - 1, 8, 9, 8, 9 };
    u8 i;
    for (i = 0; i < 8; ++i) room_tilemap[dys[i]][dxs[i]] = BGT_DOOR;
    wait_vbl_done();
    {
        u8 door = BGT_DOOR, attr = BGPAL_DOOR;
        VBK_REG = 0;
        for (i = 0; i < 8; ++i) set_bkg_tiles(dxs[i], dys[i], 1, 1, &door);
        VBK_REG = 1;
        for (i = 0; i < 8; ++i) set_bkg_tiles(dxs[i], dys[i], 1, 1, &attr);
        VBK_REG = 0;
    }
}

// Single-tile rewrite (tile + attr) at the top of vblank.
static void room_set_tile_vbl(u8 tx, u8 ty, u8 t, u8 attr) {
    room_tilemap[ty][tx] = t;
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(tx, ty, 1, 1, &t);
    VBK_REG = 1;
    set_bkg_tiles(tx, ty, 1, 1, &attr);
    VBK_REG = 0;
}

void room_break_crystal(u8 tx, u8 ty) BANKED {
    // Shatter a crystal tile: floor it, ~25% of shards hold a +1 MP wisp
    // (crystals are the world's mana nodes).
    if (tx >= ROOM_W || ty >= ROOM_H) return;
    if (room_tilemap[ty][tx] != BGT_CRYSTAL) return;
    room_set_tile_vbl(tx, ty, BGT_FLOOR, BGPAL_FLOOR);
    sfx_play(SFX_HIT);
    if (rng_next_u8() < 64) {
        pickup_spawn_mp(FIX8((i16)tx * 8), FIX8((i16)ty * 8));
    }
}

void room_open_secret(u8 tx, u8 ty) BANKED {
    u8 tx2 = tx, ty2 = ty;
    if (tx >= ROOM_W || ty >= ROOM_H) return;
    // Open a second tile along the wall so the doorway is 16px wide
    // (cracks spawn at 2..N-3, so the +1 neighbor is never a corner).
    if (ty == 0 || ty == ROOM_H - 1) tx2 = (u8)(tx + 1);
    else                             ty2 = (u8)(ty + 1);
    room_set_tile_vbl(tx, ty, BGT_DOOR, BGPAL_DOOR);
    room_set_tile_vbl(tx2, ty2, BGT_DOOR, BGPAL_DOOR);
    secret_door_x = tx;   secret_door_y = ty;
    secret_door_x2 = tx2; secret_door_y2 = ty2;
    sfx_play(SFX_DOOR);
}

// CGB palette attribute per tile id
static u8 attr_for_tile(u8 t) {
    switch (t) {
        case BGT_WALL:
        case BGT_PILLAR:  return BGPAL_WALL;
        case BGT_WALL_CRACK:
        case BGT_SPIKES:  return BGPAL_CRACK;   // amber danger signal
        case BGT_BLOCK:
        case BGT_BLOCK_TR:
        case BGT_BLOCK_BL:
        case BGT_BLOCK_BR: return BGPAL_DOOR;      // gold-ish, reads as interactive
        case BGT_CRYSTAL: return BGPAL_CRYSTAL;
        case BGT_DOOR:    return BGPAL_DOOR;
        default:
            // Shop price tags glow amber (crack palette) for readability
            if (t == HUD_COIN || (t >= HUD_DIGIT_0 && t <= HUD_DIGIT_0 + 9)) {
                return BGPAL_CRACK;
            }
            return BGPAL_FLOOR;
    }
}

static void draw_room_tilemap(void) {
    u8 x, y;
    u8 attr_row[ROOM_W];
    for (y = 0; y < ROOM_H; ++y) {
        // Tile indices (VRAM bank 0)
        VBK_REG = 0;
        set_bkg_tiles(0, y, ROOM_W, 1, room_tilemap[y]);
        // Palette attributes (VRAM bank 1)
        for (x = 0; x < ROOM_W; ++x) attr_row[x] = attr_for_tile(room_tilemap[y][x]);
        VBK_REG = 1;
        set_bkg_tiles(0, y, ROOM_W, 1, attr_row);
    }
    VBK_REG = 0;
}

static void place_player_sprite(void) {
    // 16x16 player metasprite — 4 OAM slots, anchored at (x+8, y+16) per GBDK
    if (player.iframes > 0 && (player.iframes & 0x04)) {
        move_sprite(0, 0, 0);
        move_sprite(1, 0, 0);
        move_sprite(2, 0, 0);
        move_sprite(3, 0, 0);
    } else {
        u8 sx = (u8)(player.x + 8);
        u8 sy = (u8)(player.y + 16);
        u8 base = (u8)(SPR_CLASS_BASE
                       + (u8)(((player.class_id < 5) ? player.class_id : 0) * SPR_CLASS_STRIDE));
        // Walk cycle without extra tile art: for half of the anim counter,
        // swap the two leg tiles left<->right and X-flip them (OAM attr bit 5)
        // so the legs step. anim_frame only advances while moving, so a still
        // hero holds the neutral pose. Top row (head/torso) never changes.
        u8 step = (player.anim_frame & 0x04) ? 1 : 0;
        set_sprite_tile(0, (u8)(base + 0));
        set_sprite_tile(1, (u8)(base + 1));
        set_sprite_prop(0, 0x01);
        set_sprite_prop(1, 0x01);
        move_sprite(0, sx,         sy);
        move_sprite(1, (u8)(sx+8), sy);
        if (step) {
            set_sprite_tile(2, (u8)(base + 3));   // BR art on the left, flipped
            set_sprite_tile(3, (u8)(base + 2));   // BL art on the right, flipped
            set_sprite_prop(2, 0x01 | S_FLIPX);
            set_sprite_prop(3, 0x01 | S_FLIPX);
        } else {
            set_sprite_tile(2, (u8)(base + 2));
            set_sprite_tile(3, (u8)(base + 3));
            set_sprite_prop(2, 0x01);
            set_sprite_prop(3, 0x01);
        }
        move_sprite(2, sx,         (u8)(sy+8));
        move_sprite(3, (u8)(sx+8), (u8)(sy+8));
    }
}

// Get the 8-dir index from current/pressed input. Returns 0..7 or 0xFF if none.
static u8 input_to_dir8(u8 keys) {
    u8 d = 0xFF;
    if (keys & J_UP) {
        if      (keys & J_RIGHT) d = 1;   // NE
        else if (keys & J_LEFT)  d = 7;   // NW
        else                     d = 0;   // N
    } else if (keys & J_DOWN) {
        if      (keys & J_RIGHT) d = 3;   // SE
        else if (keys & J_LEFT)  d = 5;   // SW
        else                     d = 4;   // S
    } else if (keys & J_RIGHT) {
        d = 2;
    } else if (keys & J_LEFT) {
        d = 6;
    }
    return d;
}

// Map 4-dir facing to 8-dir for fallback when no D-pad pressed at fire time
static u8 facing_to_dir8(u8 facing) {
    switch (facing) {
        case FACE_N: return 0;
        case FACE_E: return 2;
        case FACE_S: return 4;
        case FACE_W: return 6;
        default:     return 4;
    }
}

void room_enter(void) {
    g_vbl_ticks = 0;   // run clock: don't count time spent off-room
    DISPLAY_OFF;

    {
        const u16 (*sp)[4] = stage_pal[room_stage()];
        palette_bg_load(BGPAL_FLOOR,   sp[0]);
        palette_bg_load(BGPAL_WALL,    sp[1]);
        palette_bg_load(BGPAL_CRYSTAL, sp[2]);
        palette_bg_load(BGPAL_DOOR,    sp[3]);
    }
    palette_bg_load(BGPAL_CRACK,   stage_pal_crack);
    palette_obj_load(0, skeleton_palette);
    palette_obj_load(1, class_obj_palettes[player.class_id < 5 ? player.class_id : 0]);
    palette_obj_load(2, bullet_palette);
    palette_obj_load(3, crawler_palette);
    palette_obj_load(4, heart_palette);
    palette_obj_load(5, coin_palette);
    palette_obj_load(6, boss_stage_pal[room_stage()]);   // stage-tinted large boss
    palette_obj_load(7, orc_palette);

    tiles_load_dungeon_bg();              // authored dungeon tileset (slot 0 = void)
    tiles_load_pickup_sprites();
    tiles_load_all_class_sprites();       // 5 × 16x16 player metasprites (slots 0..19)
    tiles_load_all_enemy_sprites();       // 4 enemy tiles (slots 20..23)
    tiles_load_miniboss(room_stage());    // this stage's distinct 16x16 mini-boss (slots 24..27)
    tiles_load_boss_big(room_stage());    // this stage's 32x32 boss (slots 40..55)
    tiles_load_fx_sprites();              // bullet A/B, muzzle, impact

    hud_init();
    hud_show();

    // Player metasprite — 4 tiles starting at class-specific base
    {
        u8 base = (u8)(SPR_CLASS_BASE + (u8)(player.class_id * SPR_CLASS_STRIDE));
        set_sprite_tile(0, (u8)(base + 0));    // TL
        set_sprite_tile(1, (u8)(base + 1));    // TR
        set_sprite_tile(2, (u8)(base + 2));    // BL
        set_sprite_tile(3, (u8)(base + 3));    // BR
        set_sprite_prop(0, 0x01);
        set_sprite_prop(1, 0x01);
        set_sprite_prop(2, 0x01);
        set_sprite_prop(3, 0x01);
    }
    player.facing        = FACE_S;
    player.fire_cooldown = 0;
    room_paused          = 0;

    if (room_resume_flag) {
        // Returning from the pack screen: keep the existing tilemap, entities
        // and player position — just redraw. Do NOT regenerate or restart music.
        room_resume_flag = 0;
        draw_room_tilemap();
        entity_draw_all();
        place_player_sprite();
        // Music kept running through the pack screen (room_exit no longer stops
        // it), so there's nothing to restart here — resume is seamless.
        SHOW_SPRITES;
        SHOW_BKG;
        DISPLAY_ON;
        return;
    }

    player.iframes       = 0;

    // Procgen builds the tilemap + spawns enemies + positions player
    procgen_generate_current_room();
    draw_room_tilemap();
    place_player_sprite();

    secret_door_x = secret_door_y = 0xFF;
    secret_door_x2 = secret_door_y2 = 0xFF;
    player.active_charge = 0;
    if (*(volatile u8*)0xFFFC == 0xBB) {
        music_play_boss(room_stage());
        sfx_play(SFX_ROAR);
        // Entry drama: the arena starts dark and trembling, then the
        // light pops as the fight begins.
        room_apply_pause_palettes(1);
        stage_fade = 30;
        room_shake(1, 24);
    } else {
        music_play_stage(room_stage());
    }

    hostiles_prev = 0;   // fresh room: re-arm the clear chime

    // Stage-entry reveal: first room of a new stage (or of a fresh run)
    // starts with dimmed palettes and pops to full ~0.4s in.
    if (run_state.room_counter == 0) stage_seen = 0xFF;
    if (room_stage() != stage_seen) {
        stage_seen = room_stage();
        stage_fade = 26;
        room_apply_pause_palettes(1);   // start dimmed
    }

    // Suspend save: every room entry snapshots the run (battery SRAM).
    sram_save_run();

    SHOW_SPRITES;
    SHOW_BKG;
    DISPLAY_ON;
}

void room_exit(void) {
    HIDE_SPRITES;
    hud_hide();
    // Settle any in-flight shake so the next screen isn't skewed
    shake_timer = 0;
    SCX_REG = 0;
    SCY_REG = 0;
    // NOTE: do NOT wipe entities or stop music here. Opening the pack screen
    // (START) exits the room and returns via the resume path, which expects
    // the room's entities/player/music to be intact. Real room changes
    // re-init entities in procgen_generate_current_room(). Leaving music
    // running also avoids a restart blip every time the pack is toggled.
}

screen_id_t room_tick(u8 keys, u8 pressed) {
    // ---- START opens the PACK (stats + items); SELECT quick-pauses (dim).
    if (pressed & J_START) {
        return SCREEN_INVENTORY;
    }
    if (pressed & J_SELECT) {
        room_paused ^= 1;
        room_apply_pause_palettes(room_paused);
    }
    if (room_paused) { g_vbl_ticks = 0; return SCREEN_SELF; }   // clock holds

    // ---- Death beat: the world keeps animating (bullets fly, bursts
    // pop, screen shakes) but the hero is done — then GAMEOVER.
    if (death_timer) {
        if (--death_timer == 0) return SCREEN_GAMEOVER;
        if (player.iframes) player.iframes--;   // drives the flicker
        entity_update_all(0, 0);
        place_player_sprite();
        entity_draw_all();
        return SCREEN_SELF;
    }

    // ---- Stage-entry reveal: hold dimmed palettes briefly, then pop to
    // full brightness — a beat of "emerging into somewhere new".
    if (stage_fade) {
        if (--stage_fade == 0) room_apply_pause_palettes(0);
    }

    // ---- Run clock: counts REAL seconds of active room play via the
    // VBL ISR tick (the room loop overruns vblanks under load, so loop
    // iterations are not wall time). Pause/pack drain the ticks instead.
    while (g_vbl_ticks >= 60) {
        g_vbl_ticks = (u8)(g_vbl_ticks - 60);
        if (run_state.run_timer < 65535) run_state.run_timer++;
    }

    // ---- Low-HP danger: at one heart the HUD hearts pulse white-hot
    // and a soft heartbeat blip sounds in the quiet between shots.
    {
        static u8 lowhp_t;
        if (player.hp <= 2 && player.hp > 0) {
            lowhp_t++;
            hud_low_hp_pulse((u8)((lowhp_t & 0x10) ? 1 : 0));
            if (lowhp_t >= 96) { lowhp_t = 0; sfx_play(SFX_LOWHP); }
        } else if (lowhp_t) {
            lowhp_t = 0;
            hud_low_hp_pulse(0);
        }
    }

    // ---- Hit-stop: freeze the world a few frames on impact for weight,
    // but keep drawing so the flash/knockback is visible.
    if (g_hitstop) {
        g_hitstop--;
        place_player_sprite();
        entity_draw_all();
        return SCREEN_SELF;
    }

    // ---- Movement: SPD-scaled sub-pixel accumulator.
    // acc += spd; each 5 accumulated = 1 px step. spd 5 = 1.0 px/f,
    // Sauran 4 = 0.8, Wolfkin 6 = 1.2, Vespine 7 = 1.4.
    {
        u8 moved = 0;
        i8 dx = 0, dy = 0;
        u8 steps;

        if (keys & J_LEFT)  { dx = -1; player.facing = FACE_W; moved = 1; }
        if (keys & J_RIGHT) { dx = +1; player.facing = FACE_E; moved = 1; }
        if (keys & J_UP)    { dy = -1; player.facing = FACE_N; moved = 1; }
        if (keys & J_DOWN)  { dy = +1; player.facing = FACE_S; moved = 1; }

        if (moved) {
            player.move_acc = (u8)(player.move_acc + player.spd);
        }

        // ---- Dodge dash: double-tap a cardinal within ~12 frames to lunge
        // fast in that direction with brief i-frames, then a short cooldown.
        {
            u8 td = (pressed & J_LEFT)  ? (u8)'L'
                  : (pressed & J_RIGHT) ? (u8)'R'
                  : (pressed & J_UP)    ? (u8)'U'
                  : (pressed & J_DOWN)  ? (u8)'D' : 0;
            if (td) {
                if (td == tap_dir && tap_age <= 12
                    && dash_cd == 0 && dash_timer == 0) {
                    dash_timer = 7;
                    dash_cd    = 30;
                    if (player.iframes < 14) player.iframes = 14;
                    dash_dx = (td == 'L') ? -1 : (td == 'R') ? 1 : 0;
                    dash_dy = (td == 'U') ? -1 : (td == 'D') ? 1 : 0;
                    sfx_play(SFX_DOOR);   // whoosh
                    tap_dir = 0;
                } else {
                    tap_dir = td;
                    tap_age = 0;
                }
            }
            if (tap_age < 255) tap_age++;
            if (dash_cd) dash_cd--;
        }

        // While dashing, override player control with a fast wall-checked
        // lunge (3 px/frame). The rest of room_tick still runs — enemies
        // and bullets keep moving so the dash actually dodges them; the
        // dash's i-frames keep you safe. Normal movement + block-push are
        // neutralized below via moved/move_acc = 0.
        if (dash_timer) {
            u8 s;
            dash_timer--;
            for (s = 0; s < 3; ++s) {
                if (dash_dx) {
                    ppos_t nx = (ppos_t)(player.x + dash_dx);
                    if (is_walkable_at(nx + 2,  player.y + 8)
                        && is_walkable_at(nx + 13, player.y + 8)
                        && is_walkable_at(nx + 2,  player.y + 15)
                        && is_walkable_at(nx + 13, player.y + 15))
                        player.x = nx;
                }
                if (dash_dy) {
                    ppos_t ny = (ppos_t)(player.y + dash_dy);
                    if (is_walkable_at(player.x + 2,  ny + 8)
                        && is_walkable_at(player.x + 13, ny + 8)
                        && is_walkable_at(player.x + 2,  ny + 15)
                        && is_walkable_at(player.x + 13, ny + 15))
                        player.y = ny;
                }
            }
            dx = 0; dy = 0; moved = 0; player.move_acc = 0;
        }

        // --- Pushable blocks: press against a block (cardinal move) and,
        //     if the tile behind it is open floor, it slides one tile.
        //     Detection probes the player's LEADING EDGE corners (not the
        //     center tile), so contact counts whenever you're actually
        //     grinding on the block, at any off-axis alignment. Input
        //     noise (a 1-frame diagonal brush) DECAYS the hold instead of
        //     restarting it — d-pads are messy. ---
        {
            u8 qualified = 0;
            u8 fx = 0, fy = 0, cur = 0;
            if (moved && ((dx != 0) != (dy != 0))) {
                // Leading-edge probes: 1px beyond the 1..6 collision box
                // on the facing side, at both cross-axis corners. When
                // flush against a block, these land inside its tile.
                i16 p1x, p1y, p2x, p2y;
                if (dx) {
                    i16 ex = (i16)(player.x + ((dx > 0) ? 14 : 1));
                    p1x = ex; p1y = (i16)(player.y + 9);
                    p2x = ex; p2y = (i16)(player.y + 14);
                } else {
                    i16 ey = (i16)(player.y + ((dy > 0) ? 16 : 7));
                    p1x = (i16)(player.x + 3); p1y = ey;
                    p2x = (i16)(player.x + 12); p2y = ey;
                }
                cur = (u8)((dy != 0) ? ((dy < 0) ? DIR_N : DIR_S)
                                     : ((dx < 0) ? DIR_W : DIR_E));
                {
                    u8 q1 = room_tile_at_px(p1x, p1y);
                    u8 q2 = room_tile_at_px(p2x, p2y);
                    if (q1 == BGT_BLOCK || q1 == BGT_BLOCK_TR
                        || q1 == BGT_BLOCK_BL || q1 == BGT_BLOCK_BR) {
                        fx = (u8)(p1x >> 3); fy = (u8)(p1y >> 3); qualified = 1;
                    } else if (q2 == BGT_BLOCK || q2 == BGT_BLOCK_TR
                        || q2 == BGT_BLOCK_BL || q2 == BGT_BLOCK_BR) {
                        fx = (u8)(p2x >> 3); fy = (u8)(p2y >> 3); qualified = 1;
                    }
                }
            }
            if (qualified) {
                // Resolve the crate's ORIGIN (top-left) from whichever
                // quadrant the probe touched.
                u8 ox = fx, oy = fy;
                {
                    u8 q = room_tilemap[fy][fx];
                    if (q == BGT_BLOCK_TR)      { ox = (u8)(fx - 1); }
                    else if (q == BGT_BLOCK_BL) { oy = (u8)(fy - 1); }
                    else if (q == BGT_BLOCK_BR) { ox = (u8)(fx - 1); oy = (u8)(fy - 1); }
                }
                {
                // Leading edge after an 8px slide: two cells to check
                u8 t1x, t1y, t2x, t2y;
                u8 open;
                if (dx > 0)      { t1x = (u8)(ox + 2); t1y = oy; t2x = t1x; t2y = (u8)(oy + 1); }
                else if (dx < 0) { t1x = (u8)(ox - 1); t1y = oy; t2x = t1x; t2y = (u8)(oy + 1); }
                else if (dy > 0) { t1x = ox; t1y = (u8)(oy + 2); t2x = (u8)(ox + 1); t2y = t1y; }
                else             { t1x = ox; t1y = (u8)(oy - 1); t2x = (u8)(ox + 1); t2y = t1y; }
                open = (t1x < ROOM_W && t1y < ROOM_H && t2x < ROOM_W && t2y < ROOM_H);
                if (open) {
                    u8 a = room_tilemap[t1y][t1x], b = room_tilemap[t2y][t2x];
                    open = (a == BGT_FLOOR || a == BGT_FLOOR2 || a == BGT_FLOOR3)
                        && (b == BGT_FLOOR || b == BGT_FLOOR2 || b == BGT_FLOOR3);
                }
                // Never entomb a live enemy under the sliding crate
                if (open) {
                    u8 k;
                    for (k = 0; k < MAX_ENTITIES; ++k) {
                        u8 etx, ety;
                        if (!(entities[k].flags & EF_ACTIVE)
                            || entities[k].type != ENT_ENEMY) continue;
                        etx = (u8)((FIX8_TO_INT(entities[k].x) + 4) >> 3);
                        ety = (u8)((FIX8_TO_INT(entities[k].y) + 4) >> 3);
                        if ((etx == t1x && ety == t1y) || (etx == t2x && ety == t2y)) {
                            open = 0;
                            break;
                        }
                    }
                }
                if (open) {
                    if (push_dir == cur) push_timer++;
                    else { push_dir = cur; push_timer = 1; }
                    if (push_timer >= 10) {
                        u8 nox = (u8)(ox + dx), noy = (u8)(oy + dy);
                        // One vblank, eight tile writes: clear the old
                        // 2x2, draw the crate at its new origin.
                        room_tilemap[oy][ox]         = BGT_FLOOR;
                        room_tilemap[oy][ox + 1]     = BGT_FLOOR;
                        room_tilemap[oy + 1][ox]     = BGT_FLOOR;
                        room_tilemap[oy + 1][ox + 1] = BGT_FLOOR;
                        room_tilemap[noy][nox]         = BGT_BLOCK;
                        room_tilemap[noy][nox + 1]     = BGT_BLOCK_TR;
                        room_tilemap[noy + 1][nox]     = BGT_BLOCK_BL;
                        room_tilemap[noy + 1][nox + 1] = BGT_BLOCK_BR;
                        wait_vbl_done();
                        {
                            u8 yy, xx;
                            u8 x0 = (dx < 0) ? nox : ox;
                            u8 y0 = (dy < 0) ? noy : oy;
                            VBK_REG = 0;
                            for (yy = 0; yy < 3; ++yy)
                                for (xx = 0; xx < 3; ++xx)
                                    set_bkg_tiles((u8)(x0 + xx), (u8)(y0 + yy),
                                        1, 1, &room_tilemap[y0 + yy][x0 + xx]);
                            VBK_REG = 1;
                            for (yy = 0; yy < 3; ++yy)
                                for (xx = 0; xx < 3; ++xx) {
                                    u8 at = attr_for_tile(room_tilemap[y0 + yy][x0 + xx]);
                                    set_bkg_tiles((u8)(x0 + xx), (u8)(y0 + yy),
                                        1, 1, &at);
                                }
                            VBK_REG = 0;
                        }
                        sfx_play(SFX_DOOR);
                        push_timer = 0;
                    }
                } else if (push_timer) {
                    push_timer--;
                }
                }
            } else if (push_timer) {
                push_timer--;              // noise decays, never hard-resets
                if (push_timer == 0) push_dir = DIR_NONE;
            }
        }

        steps = 0;
        while (player.move_acc >= 5) { player.move_acc -= 5; steps++; }

        while (steps--) {
            // Feet-anchored wall box (Zelda convention): x+2..x+13 wide,
            // y+8..y+15 — the bottom half of the 16x16 body. The head
            // overhangs walls above; the body never buries into terrain.
            if (dx) {
                ppos_t nx = (ppos_t)(player.x + dx);
                if (is_walkable_at(nx + 2,  player.y + 8)
                    && is_walkable_at(nx + 13, player.y + 8)
                    && is_walkable_at(nx + 2,  player.y + 15)
                    && is_walkable_at(nx + 13, player.y + 15)) {
                    player.x = nx;
                }
            }
            if (dy) {
                ppos_t ny = (ppos_t)(player.y + dy);
                if (is_walkable_at(player.x + 2,  ny + 8)
                    && is_walkable_at(player.x + 13, ny + 8)
                    && is_walkable_at(player.x + 2,  ny + 15)
                    && is_walkable_at(player.x + 13, ny + 15)) {
                    player.y = ny;
                }
            }
        }

        if (moved) {
            player.anim_frame = (u8)((player.anim_frame + 1) & 0x07);
        }
    }

    // ---- Weapons. Starter comes from the generated items[] entry
    // (p0=fire_rate, p1=damage, p2=projectile kind). Starter ids 0-4 map
    // to array indices 0-4 by content authoring; guarded by N_ITEMS.
    // Per-class elemental identity: Wolfkin fire, Sauran lightning,
    // Corvin shadow, Picsean ice, Vespine poison (1/4/8/2/16).
    {
        static const u8 class_element[5] = { 1, 4, 8, 2, 16 };
        const item_def_t *w =
            &items[player.starter_weapon < N_ITEMS ? player.starter_weapon : 0];
        g_shot_element = class_element[player.class_id < 5 ? player.class_id : 0];

        if ((keys & J_A) && player.fire_cooldown == 0) {
            u8 dir = input_to_dir8(keys);
            u8 dmg = (u8)(w->p1 + player.atk);   // ATK adds linearly
            if (dir == 0xFF) dir = facing_to_dir8(player.facing);
            projectile_spawn_player(dir8_dx[dir], dir8_dy[dir], dmg, w->p2);
            player.fire_cooldown = (u8)(w->p0 >> 1);
        }
        if (player.fire_cooldown > 0) player.fire_cooldown--;

        // ---- Weapon 2 (B, edge): class signature move. Costs MP_COST_B
        // magic on top of the ~2.3s cooldown; no MP -> error beep.
        #define MP_COST_B 2
        if ((pressed & J_B) && player.active_charge == 0
            && player.mp < MP_COST_B) {
            sfx_play(SFX_HURT);   // out of magic
        }
        if ((pressed & J_B) && player.active_charge == 0
            && player.mp >= MP_COST_B) {
            u8 dir = input_to_dir8(keys);
            u8 dmg = (u8)(w->p1 + 1 + player.atk);
            u8 d;
            if (dir == 0xFF) dir = facing_to_dir8(player.facing);
            switch (player.class_id) {
                case 0:   // Wolfkin HOWL: 8-way spike ring
                    for (d = 0; d < 8; ++d) {
                        projectile_spawn_player(dir8_dx[d], dir8_dy[d], dmg, PROJ_SPIKE);
                    }
                    break;
                case 1:   // Sauran STONESKIN: 1.5s of iframes
                    player.iframes = 90;
                    break;
                case 2:   // Corvin MURDER: 3-way shuriken spread
                    projectile_spawn_player(dir8_dx[dir], dir8_dy[dir], dmg, PROJ_SHURIKEN);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 1) & 7)],
                        dir8_dy[(u8)((dir + 1) & 7)], dmg, PROJ_SHURIKEN);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 7) & 7)],
                        dir8_dy[(u8)((dir + 7) & 7)], dmg, PROJ_SHURIKEN);
                    break;
                case 3:   // Picsean TIDAL WAVE: 3-lane bubble wall
                    projectile_spawn_player(dir8_dx[dir], dir8_dy[dir], dmg, PROJ_BUBBLE);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 2) & 7)],
                        dir8_dy[(u8)((dir + 2) & 7)], dmg, PROJ_BUBBLE);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 6) & 7)],
                        dir8_dy[(u8)((dir + 6) & 7)], dmg, PROJ_BUBBLE);
                    break;
                default:  // Vespine SWARM: 4-stinger fan burst
                    projectile_spawn_player(dir8_dx[dir], dir8_dy[dir], dmg, PROJ_SPIKE);
                    projectile_spawn_player(dir8_dx[dir], dir8_dy[dir], dmg, PROJ_BULLET);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 1) & 7)],
                        dir8_dy[(u8)((dir + 1) & 7)], dmg, PROJ_BULLET);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 7) & 7)],
                        dir8_dy[(u8)((dir + 7) & 7)], dmg, PROJ_BULLET);
                    break;
            }
            sfx_play(SFX_ROAR);
            player.active_charge = 140;
            player.mp = (u8)(player.mp - MP_COST_B);
            hud_redraw_mp();
        }
        if (player.active_charge > 0) player.active_charge--;

        // MP trickle: +1 every ~3.2s while below max — Picsean's
        // MP-attuned passive (perk 4) regenerates twice as fast.
        if (player.mp < player.mp_max) {
            static u8 mp_regen;
            u8 thresh = (player.class_id == 3) ? 96 : 192;
            if (++mp_regen >= thresh) {
                mp_regen = 0;
                player.mp++;
                hud_redraw_mp();
            }
        }

        // Sauran's scaled hide (perk 2): slow HP regen, one half-heart
        // per ~40s of active play.
        if (player.class_id == 1 && player.hp < player.hp_max) {
            static u16 hp_regen;
            if (++hp_regen >= 1350) {
                hp_regen = 0;
                player.hp++;
                hud_redraw_hp();
                sfx_play(SFX_HEART);
            }
        }
    }

    // ---- Entity updates
    entity_update_all(keys, pressed);

    // ---- Combat
    if (combat_resolve()) {
        // Player died: don't hard-cut — a beat of shake, bursts, and a
        // flickering hero falling before the GAMEOVER screen takes over.
        death_timer = 50;
        player.iframes = 50;             // reuse the iframe flicker
        sfx_play(SFX_DEATH);
        music_stop();
        room_shake(2, 30);
        fx_spawn(SPR_FX_IMPACT, 2, (i16)player.x,     (i16)player.y,     16);
        fx_spawn(SPR_FX_IMPACT, 2, (i16)player.x - 8, (i16)player.y - 8, 24);
        fx_spawn(SPR_FX_IMPACT, 2, (i16)player.x + 8, (i16)player.y + 8, 32);
        hud_redraw_hp();                 // show the empty hearts
        return SCREEN_SELF;
    }

    // ---- Boss HP bar + room-clear detection in one entity sweep.
    // HUD helper caches segments so polling only writes VRAM on change.
    {
        u8 i, found = 0, alive = 0, corvin_i = 0xFF;
        for (i = 0; i < MAX_ENTITIES; ++i) {
            if (!(entities[i].flags & EF_ACTIVE)) continue;
            if (entities[i].type != ENT_ENEMY)    continue;
            alive++;
            if (corvin_i == 0xFF) corvin_i = i;
            if (!found && entities[i].ai_data[0] == 1) {
                // ai_data[6] = remembered max HP (set on first boss tick);
                // fall back to current hp for the very first frame.
                u8 max = entities[i].ai_data[6];
                if (max == 0) max = entities[i].hp;
                hud_redraw_boss(entities[i].hp, max);
                found = 1;
            }
        }
        // Corvin's raven sight (perk 3): with no boss around, the bar
        // reads a regular enemy's HP instead (max from the content table).
        if (!found && player.class_id == 2 && corvin_i != 0xFF) {
            u8 eid = entities[corvin_i].ai_data[0];
            u8 max = (eid < N_ENEMIES) ? enemies[eid].stats.hp : 0;
            if (max) {
                // Elites carry doubled HP — double the reference too
                if (entities[corvin_i].flags & EF_ELITE) max = (u8)(max << 1);
                hud_redraw_boss(entities[corvin_i].hp, max);
                found = 1;
            }
        }
        if (!found) hud_redraw_boss(0, 0);

        // Last hostile down → rising chime + 1 MP back. Boss kills keep
        // their own fanfare (roar/explosion), so skip when one just landed.
        if (alive == 0 && hostiles_prev != 0
            && !run_state.pending_unseal && !run_state.victory) {
            sfx_play(SFX_CLEAR);
            if (player.mp < player.mp_max) {
                player.mp++;
                hud_redraw_mp();
            }
        }
        hostiles_prev = alive;
    }

    // ---- Boss beaten (non-final): lift the door seal, run continues,
    // and the fight music yields back to the exploration theme.
    if (run_state.pending_unseal) {
        run_state.pending_unseal = 0;
        room_unseal_doors();
        music_play_stage(room_stage());
    }

    // ---- Final victory: all bosses down
    if (run_state.victory) {
        return SCREEN_VICTORY;
    }

    // ---- Rubble poking: walking over rubble kicks it apart (Zelda bush-cut)
    {
        u8 rtx = (u8)((player.x + 8) >> 3);
        u8 rty = (u8)((player.y + 12) >> 3);
        if (rtx < ROOM_W && rty < ROOM_H
            && room_tilemap[rty][rtx] == BGT_RUBBLE) {
            room_set_tile_vbl(rtx, rty, BGT_FLOOR, BGPAL_FLOOR);
            sfx_play(SFX_HIT);
            if (rng_next_u8() < 100) {   // ~40%: hidden coin
                pickup_spawn(PICKUP_COIN_1,
                    FIX8((i16)rtx * 8), FIX8((i16)rty * 8));
            }
        }
        // ---- Spike floor: walkable but bites when the feet-box center
        // rests on it. DEF soaks it (min 1), then iframes + a jolt so you
        // can cross but pay for lingering.
        else if (rtx < ROOM_W && rty < ROOM_H
            && room_tilemap[rty][rtx] == BGT_SPIKES
            && player.iframes == 0) {
            u8 taken = (player.def < 1) ? 1 : 1;   // spikes always sting 1
            if (player.hp > taken) {
                player.hp = (u8)(player.hp - taken);
                player.iframes = 40;
                g_hitstop = 2;
                room_shake(1, 6);
                sfx_play(SFX_HURT);
                hud_redraw_hp();
            } else {
                player.hp = 0;
                return SCREEN_GAMEOVER;
            }
        }
    }

    // ---- Door detection: if the feet-box center stands on a door,
    // advance to the next room
    {
        i16 px = player.x + 8;
        i16 py = player.y + 12;
        u8 tx = (u8)(px >> 3);
        u8 ty = (u8)(py >> 3);

        if (tx < ROOM_W && ty < ROOM_H && room_tilemap[ty][tx] == BGT_DOOR) {
            // Determine which door
            u8 dir = DIR_NONE;
            if      (ty == 0)              dir = DIR_N;
            else if (ty == ROOM_H - 1)     dir = DIR_S;
            else if (tx == 0)              dir = DIR_W;
            else if (tx == ROOM_W - 1)     dir = DIR_E;

            if (dir != DIR_NONE) {
                // Leaving through a shot-open secret door → treasure room
                if ((tx == secret_door_x && ty == secret_door_y)
                    || (tx == secret_door_x2 && ty == secret_door_y2)) {
                    run_state.secret_pending = 1;
                }
                secret_door_x = secret_door_y = 0xFF;
                secret_door_x2 = secret_door_y2 = 0xFF;
                // Sticky dungeon: room layout is a pure function of room_counter,
                // so treat the counter as a position on a corridor. Leaving
                // through the door we came in (opposite of entered_from) walks
                // BACK to the previous room — regenerating its identical layout;
                // any other door advances. entered_from = exit dir works for
                // both (the player spawns at the opposite door either way).
                {
                    u8 back_dir = (u8)((run_state.entered_from + 2) & 3);
                    if (run_state.entered_from != DIR_NONE
                        && dir == back_dir
                        && run_state.room_counter > 0) {
                        run_state.room_counter--;
                    } else {
                        run_state.room_counter++;
                    }
                }
                run_state.entered_from = dir;
                sfx_play(SFX_DOOR);
                // Regenerate room in-place (skip full screen exit/enter)
                DISPLAY_OFF;
                procgen_generate_current_room();
                draw_room_tilemap();
                place_player_sprite();
                hud_redraw_all();
                DISPLAY_ON;
                if (*(volatile u8*)0xFFFC == 0xBB) {
                    music_play_boss(room_stage());
                    sfx_play(SFX_ROAR);
                    // Entry drama: dark, trembling, then the light pops
                    room_apply_pause_palettes(1);
                    stage_fade = 30;
                    room_shake(1, 24);
                } else {
                    music_play_stage(room_stage());
                }
                hostiles_prev = 0;   // fresh room: re-arm the clear chime
                // Stage-entry reveal (door path — stage changes land here
                // after a boss kill, not via room_enter)
                if (room_stage() != stage_seen) {
                    stage_seen = room_stage();
                    stage_fade = 26;
                    room_apply_pause_palettes(1);
                }
                sram_save_run();   // suspend save on every room entry
                return SCREEN_SELF;
            }
        }
    }

    return SCREEN_SELF;
}

void room_draw(void) {
    place_player_sprite();
    entity_draw_all();

    // Impact shake: alternate the BG scroll a few px, settle back to 0.
    if (shake_timer) {
        shake_timer--;
        if (shake_timer == 0) {
            SCX_REG = 0;
            SCY_REG = 0;
        } else {
            SCX_REG = (shake_timer & 2) ? shake_mag : (u8)(256 - shake_mag);
            SCY_REG = (shake_timer & 4) ? 1 : 0xFF;
        }
    }
}
