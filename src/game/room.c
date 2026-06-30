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
#include "game/projectile.h"
#include "game/room.h"
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

// Bullet palette — bright gold
static const u16 bullet_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(31, 24,  0),
    BGR555(28, 16,  0),
    BGR555(31, 31,  4),
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
    // Sprite blink during iframes
    if (player.iframes > 0 && (player.iframes & 0x04)) {
        move_sprite(0, 0, 0);
    } else {
        move_sprite(0,
            (u8)(FIX8_TO_INT(player.x) + 8),
            (u8)(FIX8_TO_INT(player.y) + 16));
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

    tiles_load_room_bg();
    tiles_load_player_sprite();
    tiles_load_combat_sprites();

    build_default_room();
    draw_room_tilemap();

    // Player sprite
    set_sprite_tile(0, SPR_PLAYER);
    set_sprite_prop(0, 0x01);          // CGB OBJ palette 1

    // Player starts at center
    player.x = FIX8((ROOM_W / 2) * 8);
    player.y = FIX8((ROOM_H / 2) * 8);
    player.facing       = FACE_S;
    player.iframes      = 0;
    player.fire_cooldown = 0;
    place_player_sprite();

    // Spawn entities
    entity_init_all();

    // Phase 5: spawn 3 enemies at fixed positions. Phase 7 will use
    // room template's spawn_slots filtered by biome.enemy_pool.
    {
        const enemy_def_t *crawler = &enemies[0];
        // Re-palette: enemies[0] palette field references OBJ palette index
        // but we want crawler_palette → assign palette 3 dynamically.
        crawler;       // value not actually used; spawned via fixed crawler id
        enemy_spawn(0, 5,  4);
        enemy_spawn(0, 15, 5);
        enemy_spawn(0, 10, 13);
        // Re-tag entity palettes to point to OBJ palette 3 (CGB OBJ pal bits)
        {
            u8 i;
            for (i = 0; i < MAX_ENTITIES; ++i) {
                if ((entities[i].flags & EF_ACTIVE)
                    && entities[i].type == ENT_ENEMY) {
                    entities[i].palette = 0x03;
                }
            }
        }
    }

    SHOW_SPRITES;
    SHOW_BKG;
    DISPLAY_ON;
}

void room_exit(void) {
    HIDE_SPRITES;
    entity_init_all();
}

screen_id_t room_tick(u8 keys, u8 pressed) {
    // ---- Movement
    {
        fix8_t nx = player.x;
        fix8_t ny = player.y;
        fix8_t step = (fix8_t)((i16)player.spd * SPEED_SCALE);
        u8 moved = 0;

        if (keys & J_LEFT)  { nx -= step; player.facing = FACE_W; moved = 1; }
        if (keys & J_RIGHT) { nx += step; player.facing = FACE_E; moved = 1; }
        if (keys & J_UP)    { ny -= step; player.facing = FACE_N; moved = 1; }
        if (keys & J_DOWN)  { ny += step; player.facing = FACE_S; moved = 1; }

        // X axis
        {
            i16 px = FIX8_TO_INT(nx);
            i16 py = FIX8_TO_INT(player.y);
            if (is_walkable_at(px + 1, py + 1)
                && is_walkable_at(px + 6, py + 1)
                && is_walkable_at(px + 1, py + 6)
                && is_walkable_at(px + 6, py + 6)) {
                player.x = nx;
            }
        }
        // Y axis
        {
            i16 px = FIX8_TO_INT(player.x);
            i16 py = FIX8_TO_INT(ny);
            if (is_walkable_at(px + 1, py + 1)
                && is_walkable_at(px + 6, py + 1)
                && is_walkable_at(px + 1, py + 6)
                && is_walkable_at(px + 6, py + 6)) {
                player.y = ny;
            }
        }

        if (moved) {
            player.anim_frame = (u8)((player.anim_frame + 1) & 0x07);
        }
    }

    // ---- Fire (B press / hold)
    if ((keys & J_B) && player.fire_cooldown == 0) {
        u8 dir = input_to_dir8(keys);
        if (dir == 0xFF) dir = facing_to_dir8(player.facing);
        projectile_spawn_player(dir8_dx[dir], dir8_dy[dir]);
        player.fire_cooldown = 12;   // matches Wolfkin Claw Combo fire_rate
    }
    if (player.fire_cooldown > 0) player.fire_cooldown--;

    // ---- Entity updates
    entity_update_all(keys, pressed);

    // ---- Combat
    if (combat_resolve()) {
        // Player died — Phase 5: return to TITLE. Phase 9 = GAMEOVER.
        return SCREEN_TITLE;
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
