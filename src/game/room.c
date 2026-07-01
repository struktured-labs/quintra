// ROOM — top-down gameplay scene. Phase 5: spawns N enemies, supports
// 4-dir movement, 8-dir B-button fire, wall collision, combat resolution.
// Phase 7 wires procgen to fill from biome.room_template_pool.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "core/types.h"
#include "core/rng.h"
#include "game/combat.h"
#include "game/entity.h"
#include "game/enemy_ai.h"
#include "game/loop.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

u8 room_tilemap[ROOM_H][ROOM_W];

#define SPEED_SCALE 32   // each spd unit = 32/256 px = 0.125 px/tick

// Biome palette for room — cave-y blue-grey
static const u16 room_bg_palette[4] = {
    BGR555( 0,  0,  4),
    BGR555( 5,  6, 12),
    BGR555(12, 14, 22),
    BGR555(22, 24, 28),
};

// Player (Wolfkin) palette
static const u16 player_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(28, 22, 14),
    BGR555(16,  8,  4),
    BGR555( 0,  0,  0),
};

// Crawler (enemy) palette — blue, with one accent
static const u16 crawler_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555( 8, 12, 28),
    BGR555( 4,  6, 20),
    BGR555( 0,  0,  0),
};

// Stone Sentinel (boss) palette — granite grey with bright accent
static const u16 sentinel_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(18, 18, 22),
    BGR555( 8,  8, 12),
    BGR555(28, 24, 14),
};

// Bullet palette — bright gold
static const u16 bullet_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(31, 24,  0),
    BGR555(28, 16,  0),
    BGR555(31, 31,  4),
};

// Heart pickup palette (red)
static const u16 heart_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(31, 12, 12),
    BGR555(16,  4,  4),
    BGR555( 0,  0,  0),
};

// Coin pickup palette (gold)
static const u16 coin_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(31, 24,  4),
    BGR555(18, 12,  0),
    BGR555(31, 31, 14),
};

static void build_default_room(void) {
    u8 x, y;
    for (y = 0; y < ROOM_H; ++y) {
        for (x = 0; x < ROOM_W; ++x) {
            if (y == 0 || y == ROOM_H - 1 || x == 0 || x == ROOM_W - 1) {
                room_tilemap[y][x] = BGT_WALL;
            } else {
                room_tilemap[y][x] = BGT_FLOOR;
            }
        }
    }
    room_tilemap[0][ROOM_W / 2]            = BGT_DOOR;
    room_tilemap[ROOM_H - 1][ROOM_W / 2]   = BGT_DOOR;
    room_tilemap[ROOM_H / 2][0]            = BGT_DOOR;
    room_tilemap[ROOM_H / 2][ROOM_W - 1]   = BGT_DOOR;
}

static u8 tile_at(i16 px, i16 py) {
    if (px < 0 || py < 0) return BGT_WALL;
    {
        u8 tx = (u8)(px >> 3);
        u8 ty = (u8)(py >> 3);
        if (tx >= ROOM_W || ty >= ROOM_H) return BGT_WALL;
        return room_tilemap[ty][tx];
    }
}

static u8 is_walkable_at(i16 px, i16 py) {
    u8 t = tile_at(px, py);
    return (t == BGT_FLOOR || t == BGT_DOOR);
}

static void draw_room_tilemap(void) {
    u8 y;
    for (y = 0; y < ROOM_H; ++y) {
        set_bkg_tiles(0, y, ROOM_W, 1, room_tilemap[y]);
    }
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
        move_sprite(0, sx,         sy);
        move_sprite(1, (u8)(sx+8), sy);
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
    DISPLAY_OFF;

    palette_bg_load(0, room_bg_palette);
    palette_obj_load(1, player_palette);
    palette_obj_load(2, bullet_palette);
    palette_obj_load(3, crawler_palette);
    palette_obj_load(4, heart_palette);
    palette_obj_load(5, coin_palette);
    palette_obj_load(6, sentinel_palette);

    tiles_load_room_bg();
    tiles_load_player_sprite();           // legacy single-tile fallback
    tiles_load_combat_sprites();
    tiles_load_pickup_sprites();
    tiles_load_boss_sprite();
    tiles_load_all_class_sprites();       // 5 × 16x16 player metasprites (slots 0..19)
    tiles_load_all_enemy_sprites();       // 4 enemy tiles (slots 20..23)
    tiles_load_boss_metasprite();         // 16x16 boss (slots 24..27)
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
    player.iframes       = 0;
    player.fire_cooldown = 0;

    // Procgen builds the tilemap + spawns enemies + positions player
    procgen_generate_current_room();
    draw_room_tilemap();
    place_player_sprite();

    SHOW_SPRITES;
    SHOW_BKG;
    DISPLAY_ON;
}

void room_exit(void) {
    HIDE_SPRITES;
    hud_hide();
    entity_init_all();
}

screen_id_t room_tick(u8 keys, u8 pressed) {
    // ---- Movement: 1 px/frame, i16 positions
    {
        ppos_t nx = player.x;
        ppos_t ny = player.y;
        u8 moved = 0;

        if (keys & J_LEFT)  { nx -= 1; player.facing = FACE_W; moved = 1; }
        if (keys & J_RIGHT) { nx += 1; player.facing = FACE_E; moved = 1; }
        if (keys & J_UP)    { ny -= 1; player.facing = FACE_N; moved = 1; }
        if (keys & J_DOWN)  { ny += 1; player.facing = FACE_S; moved = 1; }

        // X axis
        if (is_walkable_at(nx + 1, player.y + 1)
            && is_walkable_at(nx + 6, player.y + 1)
            && is_walkable_at(nx + 1, player.y + 6)
            && is_walkable_at(nx + 6, player.y + 6)) {
            player.x = nx;
        }
        // Y axis
        if (is_walkable_at(player.x + 1, ny + 1)
            && is_walkable_at(player.x + 6, ny + 1)
            && is_walkable_at(player.x + 1, ny + 6)
            && is_walkable_at(player.x + 6, ny + 6)) {
            player.y = ny;
        }

        if (moved) {
            player.anim_frame = (u8)((player.anim_frame + 1) & 0x07);
        }
    }

    // ---- Fire (B press / hold) — rapid Penta-style auto-fire
    if ((keys & J_B) && player.fire_cooldown == 0) {
        u8 dir = input_to_dir8(keys);
        if (dir == 0xFF) dir = facing_to_dir8(player.facing);
        projectile_spawn_player(dir8_dx[dir], dir8_dy[dir]);
        player.fire_cooldown = 6;    // 10 shots/sec — rapid
    }
    if (player.fire_cooldown > 0) player.fire_cooldown--;

    // ---- Entity updates
    entity_update_all(keys, pressed);

    // ---- Combat
    if (combat_resolve()) {
        // Player died → GAMEOVER
        return SCREEN_GAMEOVER;
    }

    // ---- Victory check: boss defeated this run
    if (run_state.victory) {
        return SCREEN_VICTORY;
    }

    // ---- Door detection: if player stands on a door, advance to next room
    {
        i16 px = player.x + 4;
        i16 py = player.y + 4;
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
                run_state.room_counter++;
                run_state.entered_from = dir;
                // Regenerate room in-place (skip full screen exit/enter)
                DISPLAY_OFF;
                procgen_generate_current_room();
                draw_room_tilemap();
                place_player_sprite();
                hud_redraw_all();
                DISPLAY_ON;
                return SCREEN_SELF;
            }
        }
    }

    // ---- START returns to TITLE (Phase 5 testing)
    if (pressed & J_START) {
        return SCREEN_TITLE;
    }

    return SCREEN_SELF;
}

void room_draw(void) {
    place_player_sprite();
    entity_draw_all();
}
