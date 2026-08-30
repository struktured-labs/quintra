#pragma bank 14

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/audio.h"
#include "audio/music.h"
#include "audio/sfx.h"
#include "core/types.h"
#include "game/dungeon_director.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/procgen_spawn.h"
#include "game/projectile.h"
#include "game/riftwild_phase.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/sram.h"
#include "game/status.h"
#include "game/waygear.h"
#include "render/hud.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

static const u16 waking_palettes[5][4] = {
    { BGR555(2,5,2), BGR555(6,15,6), BGR555(12,23,9), BGR555(22,29,16) },
    { BGR555(1,4,2), BGR555(4,10,4), BGR555(8,18,7), BGR555(18,25,11) },
    { BGR555(1,5,6), BGR555(4,14,18), BGR555(10,24,29), BGR555(27,31,31) },
    { BGR555(4,2,1), BGR555(11,6,2), BGR555(21,13,5), BGR555(31,24,12) },
    { BGR555(4,2,0), BGR555(14,7,1), BGR555(27,16,3), BGR555(31,29,14) },
};

// Hollow is absence, not a blue night filter: bruised soil, bone-white
// growth, poisonous magenta crystal and cold void-cyan landmarks make the
// counterpart readable even on a non-backlit original display.
static const u16 hollow_palettes[5][4] = {
    { BGR555(1,1,3), BGR555(5,4,9), BGR555(13,8,17), BGR555(23,18,25) },
    { BGR555(0,1,2), BGR555(3,3,6), BGR555(9,8,12), BGR555(21,20,19) },
    { BGR555(2,0,4), BGR555(10,2,14), BGR555(23,7,25), BGR555(31,23,31) },
    { BGR555(0,3,4), BGR555(1,11,14), BGR555(5,23,25), BGR555(22,31,31) },
    { BGR555(4,0,1), BGR555(13,1,4), BGR555(28,5,9), BGR555(31,22,19) },
};

static void load_palette_set(const u16 palettes[5][4], u8 dim) {
    u8 slot, color;
    u16 tmp[4];
    for (slot = 0; slot < 5; ++slot) {
        if (!dim) palette_bg_load(slot, palettes[slot]);
        else {
            for (color = 0; color < 4; ++color)
                tmp[color] = (u16)((palettes[slot][color] >> 1) & 0x3DEF);
            palette_bg_load(slot, tmp);
        }
    }
}

void riftwild_load_world_palettes(u8 dim) BANKED {
    load_palette_set(run_state.world_mode && RUN_RIFTWILD_IS_HOLLOW()
        ? hollow_palettes : waking_palettes, dim);
}

static void load_shear_palette(u8 phase) {
    static const u16 shear[4][4] = {
        { BGR555(1,2,4), BGR555(3,12,17), BGR555(11,28,29), BGR555(29,31,31) },
        { BGR555(3,0,5), BGR555(12,2,18), BGR555(27,7,29), BGR555(31,25,31) },
        { BGR555(5,1,2), BGR555(18,4,10), BGR555(31,11,19), BGR555(31,30,25) },
        { BGR555(2,2,2), BGR555(10,10,15), BGR555(25,25,29), BGR555(31,31,31) },
    };
    u8 slot;
    phase &= 3;
    for (slot = 0; slot < 5; ++slot) palette_bg_load(slot, shear[phase]);
}

static void draw_shift_hero(i8 echo) {
    u8 i;
    u8 class_id = player.class_id < 5 ? player.class_id : 0;
    u8 base = (u8)(room_player_pose_base
        + (u8)(class_id * SPR_CLASS_STRIDE));
    u8 sx = (u8)((i16)player.x - room_camera_x + 8);
    u8 sy = (u8)((i16)player.y - room_camera_y + 16);
    for (i = 0; i < 4; ++i) {
        u8 dx = (i & 1) ? 8 : 0;
        u8 dy = (i & 2) ? 8 : 0;
        set_sprite_tile(i, (u8)(base + i));
        set_sprite_prop(i, 0x01);
        move_sprite(i, (u8)(sx + dx), (u8)(sy + dy));
        set_sprite_tile((u8)(36 + i), (u8)(base + i));
        set_sprite_prop((u8)(36 + i), 0x06);
        move_sprite((u8)(36 + i), (u8)(sx + dx + echo),
            (u8)(sy + dy - echo));
    }
}

static void hide_shift_echo(void) {
    u8 i;
    for (i = 36; i < 40; ++i) move_sprite(i, 0, 0);
}

static void animate_shear(u8 opening, u8 base_x, u8 base_y) {
    u8 frame;
    for (frame = 0; frame < 28; ++frame) {
        u8 p = opening ? frame : (u8)(27 - frame);
        u8 tooth = (u8)(p & 7);
        i8 wave = (i8)(tooth < 4 ? tooth : (u8)(7 - tooth));
        i8 direction = (p & 8) ? -1 : 1;
        i8 reach = (i8)(1 + (p >> 3));
        wait_vbl_done();
        audio_tick();
        load_shear_palette((u8)((p >> 1) + (p >> 3)));
        SCX_REG = (u8)(base_x + direction * wave * reach);
        SCY_REG = (u8)(base_y + ((p & 4) ? reach : -reach));
        draw_shift_hero((i8)(direction * (2 + reach)));
    }
}

static void restore_nearest_position(i16 old_x, i16 old_y) {
    i8 radius, dx, dy;
    if (room_player_position_clear(old_x, old_y)) {
        player.x = old_x; player.y = old_y; return;
    }
    for (radius = 1; radius <= 8; ++radius) {
        for (dy = -radius; dy <= radius; ++dy) {
            for (dx = -radius; dx <= radius; ++dx) {
                i8 ax = dx < 0 ? -dx : dx;
                i8 ay = dy < 0 ? -dy : dy;
                i16 x, y;
                if ((i8)(ax + ay) != radius) continue;
                x = old_x + (i16)dx * 8;
                y = old_y + (i16)dy * 8;
                if (room_player_position_in_bounds(x, y)
                    && room_player_position_clear(x, y)) {
                    player.x = x; player.y = y; return;
                }
            }
        }
    }
    // Both realities retain the central path cross by construction.
    player.x = 72; player.y = 60;
}

u8 riftwild_shift_execute(u8 keys, u8 pressed) BANKED {
    i16 old_x, old_y;
    u8 camera_x, camera_y, scroll_x, scroll_y;
    if (!run_state.world_mode
        || !(player.waygear_owned & WAYGEAR_BIT(WAYGEAR_WORLDGLASS))
        || !((keys & J_SELECT) && (keys & J_B))
        || !(pressed & (J_SELECT | J_B))) return 0;

    old_x = player.x; old_y = player.y;
    camera_x = room_camera_x; camera_y = room_camera_y;
    scroll_x = (u8)((room_bg_origin_x << 3) + camera_x);
    scroll_y = (u8)((room_bg_origin_y << 3) + camera_y);
    HIDE_WIN;
    sfx_play_reward(SFX_REWARD_MAGIC);
    animate_shear(1, scroll_x, scroll_y);

    DISPLAY_OFF;
    run_state.riftwild_shadow ^= RIFT_SHADOW_HOLLOW_BIT;
    // Keep same cell/direction, but rebuild every terrain, encounter, and
    // reward fixture from the counterpart's deterministic contract.
    procgen_generate_current_room();
    room_apply_world_arena();
    restore_nearest_position(old_x, old_y);
    room_camera_x = camera_x;
    room_camera_y = camera_y;
    dungeon_director_activate();
    procgen_repair_enemy_spawns();
    room_draw_tilemap();
    riftwild_load_world_palettes(0);
    hud_redraw_all();
    entity_draw_all();
    status_player_refresh_visual();
    if (RUN_RIFTWILD_IS_HOLLOW()) music_play_hollow_riftwild();
    else music_play_riftwild();
    SHOW_SPRITES;
    SHOW_BKG;
    DISPLAY_ON;

    animate_shear(0, scroll_x, scroll_y);
    hide_shift_echo();
    SCX_REG = scroll_x;
    SCY_REG = scroll_y;
    SHOW_WIN;
    player.iframes = 90;
    sram_save_run();
    return 1;
}

static u8 hollow_step(void) {
    u8 cleared = run_state.bosses_beaten;
    if (cleared) cleared--;
    while (cleared >= DUNGEONS_PER_REGION)
        cleared = (u8)(cleared - DUNGEONS_PER_REGION);
    return cleared;
}

void riftwild_prepare_hollow_field(void) BANKED {
    static const u8 screen[3] = { 5, 22, 35 };
    static const u8 item[3] = {
        ITEM_ID_BLAST_SEED, ITEM_ID_RIFT_LENS, ITEM_ID_MIRROR_SHARD
    };
    static const u8 bit[3] = {
        RIFT_SHADOW_RELIC_1_BIT,
        RIFT_SHADOW_RELIC_2_BIT,
        RIFT_SHADOW_RELIC_3_BIT,
    };
    u8 step;
    u8 idx;
    if (!run_state.world_mode || !RUN_RIFTWILD_IS_HOLLOW()) return;
    step = hollow_step();
    if (run_state.world_screen != screen[step]
        || (run_state.riftwild_shadow & bit[step])) return;
    idx = pickup_spawn(PICKUP_HOLLOW_RELIC, FIX8(208), FIX8(200));
    if (idx == 0xFF) return;
    entities[idx].ai_data[1] = item[step];
    entities[idx].ai_data[2] = bit[step];
    entities[idx].sprite_tile = item[step] == ITEM_ID_BLAST_SEED
        ? SPR_ITEM_BLAST_SEED : item[step] == ITEM_ID_RIFT_LENS
        ? SPR_ITEM_RIFT_LENS : SPR_ITEM_MIRROR_SHARD;
    entities[idx].palette = 0x06;
    entities[idx].hitbox = 0x88;
    entities[idx].state_timer = 0;
}

void riftwild_harden_enemy(u8 idx, u8 spawn_ordinal) BANKED {
    u8 bonus;
    if (!run_state.world_mode || !RUN_RIFTWILD_IS_HOLLOW()
        || idx == 0xFF) return;
    // +50% HP and +1 contact makes the counterpart meaningfully later-game
    // without accelerating its readable slow-projectile vocabulary.
    bonus = (u8)((entities[idx].hp + 1) >> 1);
    entities[idx].hp = entities[idx].hp > (u8)(255 - bonus) ? 255
        : (u8)(entities[idx].hp + bonus);
    entities[idx].damage++;
    if (spawn_ordinal & 1) entities[idx].palette = 0x06;
}

u8 riftwild_claim_hollow_relic(u8 item_id, u8 claim_bit) BANKED {
    u8 i;
    u8 free = 0xFF;
    if (run_state.riftwild_shadow & claim_bit) return 0;
    for (i = 0; i < INVENTORY_SLOTS; ++i) {
        if (player.inventory[i] == item_id
            && item_id != ITEM_ID_MIRROR_SHARD) {
            run_state.riftwild_shadow |= claim_bit;
            return 1;
        }
        if (free == 0xFF && player.inventory[i] == 0xFF) free = i;
    }
    if (free == 0xFF) return 0;
    player.inventory[free] = item_id;
    run_state.riftwild_shadow |= claim_bit;
    projectile_sync_player_relics();
    room_refresh_player_appearance(1);
    return 1;
}
