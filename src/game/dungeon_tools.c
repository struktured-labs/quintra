#pragma bank 8

#include <gb/gb.h>
#include <gbdk/console.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/dungeon_tools.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/pickup.h"
#include "game/projectile.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/text.h"
#include "render/tiles.h"
#include "content.h"

#define TOOL_COUNT 3

static const u8 tool_ids[TOOL_COUNT] = {
    ITEM_ID_RIFT_BOMB, ITEM_ID_ECHO_CHIME, ITEM_ID_MIRROR_SHARD
};
static const char *const tool_names[TOOL_COUNT] = {
    "BOMB", "CHIME", "MIRROR"
};
static u8 selected_tool;
// Queued across the Pack-screen bank transition. The room-resume path
// consumes it once after DISPLAY_ON; ordinary gameplay pays no polling call.
static u8 pending_tool = 0xFF;

static u8 tool_count(u8 id) {
    u8 i, n = 0;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == id) n++;
    return n;
}

void dungeon_tools_draw_pack(void) BANKED {
    static const u8 icons[TOOL_COUNT] = {
        SPR_ITEM_RIFT_BOMB, SPR_ITEM_ECHO_CHIME, SPR_ITEM_MIRROR_SHARD
    };
    gotoxy(3, 15); text_write("                ");
    gotoxy(3, 15);
    text_write("<>");
    text_write(tool_names[selected_tool]);
    text_write(" x");
    text_u16(tool_count(tool_ids[selected_tool]));
    text_write(" A");
    set_sprite_tile(8, icons[selected_tool]);
    set_sprite_prop(8, 3);
    // The tool and Oath glyphs occupy consecutive PACK rows. Keep the tool
    // one scanline high so silhouettes such as Echo Chime (which use their
    // bottom tile row) do not touch the Oath flare's top row below.
    move_sprite(8, 16, 135);
}

u8 dungeon_tools_pack_input(u8 pressed) BANKED {
    u8 i;
    if (pressed & J_LEFT) {
        selected_tool = selected_tool ? (u8)(selected_tool - 1) : TOOL_COUNT - 1;
        dungeon_tools_draw_pack();
        sfx_play(SFX_DOOR);
        return 1;
    }
    if (pressed & J_RIGHT) {
        selected_tool++;
        if (selected_tool == TOOL_COUNT) selected_tool = 0;
        dungeon_tools_draw_pack();
        sfx_play(SFX_DOOR);
        return 1;
    }
    if (!(pressed & J_A)) return 0;
    for (i = 0; i < INVENTORY_SLOTS; ++i) {
        if (player.inventory[i] == tool_ids[selected_tool]) {
            pending_tool = selected_tool;
            player.inventory[i] = 0xFF;
            sfx_play(SFX_CLEAR);
            return 2;
        }
    }
    sfx_play(SFX_HURT);
    return 1;
}

static void tool_bomb(void) {
    u8 d;
    u8 tx = (u8)((player.x + 8) >> 3);
    u8 ty = (u8)((player.y + 12) >> 3);
    u8 x0 = (tx > 3) ? (u8)(tx - 3) : 0;
    u8 y0 = (ty > 3) ? (u8)(ty - 3) : 0;
    u8 x1 = (u8)(tx + 3);
    u8 y1 = (u8)(ty + 3);
    u8 x, y;
    if (x1 >= ROOM_W) x1 = ROOM_W - 1;
    if (y1 >= ROOM_H) y1 = ROOM_H - 1;
    for (y = y0; y <= y1; ++y) {
        for (x = x0; x <= x1; ++x) {
            u8 t = room_tilemap[y][x];
            if (t == BGT_CRYSTAL) room_break_crystal(x, y);
            else if (t == BGT_POT) room_break_pot(x, y);
            else if (t == BGT_WALL_CRACK) room_open_secret(x, y);
            else if (t == BGT_WALL) puzzle_try_hidden_shot(x, y);
        }
    }
    for (d = 0; d < 8; ++d) {
        u8 shot = projectile_spawn_player(dir8_dx[d], dir8_dy[d],
            (u8)(player.atk + 4), PROJ_BOMB);
        if (shot != 0xFF) {
            entities[shot].state_timer = 20;
            entities[shot].hitbox = 0xAA;
            entities[shot].hp = 3;
            entities[shot].ai_data[3] |= PROJ_FLAG_CONVERGENCE;
        }
    }
    room_shake(2, 20);
    sfx_play(SFX_ROAR);
}

static void tool_chime(void) {
    u8 i, dir;
    // Silence the current bullet pattern without deleting bodies or loot.
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE)
            && entities[i].type == ENT_PROJECTILE
            && !(entities[i].flags & EF_PLAYER_PROJ))
            entity_kill(i);
    }
    if (!run_state.world_mode) {
        u8 here = run_state_dungeon_cell();
        for (dir = DIR_N; dir <= DIR_W; ++dir) {
            u8 next = run_state_dungeon_cell_neighbor(here, dir);
            if (next != 0xFF) run_state_reveal_dungeon_cell(next);
        }
        puzzle_chime_reveal();
    }
    room_shake(1, 12);
    sfx_play(SFX_PUZZLE);
}

static void tool_mirror(void) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_PROJECTILE
            || (e->flags & EF_PLAYER_PROJ)) continue;
        e->flags |= EF_PLAYER_PROJ;
        e->vx = (i8)-e->vx;
        e->vy = (i8)-e->vy;
        e->damage = (u8)(player.atk + 3);
        e->hp = 2;
        e->palette = 6;
        e->ai_data[1] = 8; // shadow element
        e->ai_data[3] |= PROJ_FLAG_CONVERGENCE;
    }
    if (player.iframes < 24) player.iframes = 24;
    room_shake(1, 10);
    sfx_play(SFX_ROAR);
}

void dungeon_tools_apply_pending(void) BANKED {
    u8 tool = pending_tool;
    if (tool == 0xFF) return;
    pending_tool = 0xFF;
    if (tool == 0) tool_bomb();
    else if (tool == 1) tool_chime();
    else tool_mirror();
}
