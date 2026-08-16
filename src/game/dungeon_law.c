#pragma bank 8

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/dungeon_law.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/sram.h"
#include "render/text.h"
#include "render/tiles.h"

#define LAW_SWITCH_X 3
#define LAW_SWITCH_Y 8

static const char *const law_names[3] = {
    "PRISM", "THORN", "STONE",
};

static u8 law_room_active(void) {
    return (!run_state.world_mode
        && !RUN_ROOM_IS_TOWN(run_state.room_counter)
        && procgen_current_room_is_large
        // The generated Trial, Waystone, and phase circuit are authored
        // after terrain. Ambient Law architecture must never overwrite a
        // cairn, rune, remote switch, or gate and leave a mandatory chamber
        // visibly locked but mechanically unsolvable.
        && room_puzzle_kind == PUZZLE_NONE) ? 1 : 0;
}

static u8 law_room_has_switch(void) {
    // Every Compass row begins with an altar. The state therefore remains
    // revisable throughout a 20..30-cell expedition without scattering an
    // interactive plate into every combat formation.
    return (law_room_active() && (run_state_dungeon_local() % 6) == 0) ? 1 : 0;
}

static void law_set_raw(u8 x, u8 y, u8 tile) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = tile;
        else room_world_extension[y][x - ROOM_W] = tile;
    } else room_world_bottom[y - ROOM_H][x] = tile;
}

static u8 law_attr(u8 tile) {
    if (tile == BGT_CRYSTAL) return BGPAL_CRYSTAL;
    if (tile == BGT_SPIKES) return BGPAL_CRACK;
    if (tile == BGT_SWITCH) return BGPAL_DOOR;
    if (tile == BGT_PILLAR) return BGPAL_WALL;
    return BGPAL_FLOOR;
}

static void law_set(u8 x, u8 y, u8 tile, u8 live) {
    u8 attr;
    law_set_raw(x, y, tile);
    if (!live) return;
    attr = law_attr(tile);
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &attr);
    VBK_REG = 0;
}

void dungeon_law_apply_room(u8 live) BANKED {
    u8 x, y;
    u8 state;
    u8 kind;
    u8 material;
    u8 h_gap, v_gap;
    if (!law_room_active()) return;
    run_state_ensure_dungeon_law();
    state = (run_state.dungeon_law & DUNGEON_LAW_STATE_BIT) ? 1 : 0;
    kind = run_state.dungeon_law & DUNGEON_LAW_KIND_MASK;
    material = (kind == 0) ? BGT_CRYSTAL
        : (kind == 1) ? BGT_SPIKES : BGT_PILLAR;

    // Two persistent architecture phrases make the state legible from
    // opposite camera sectors. WAX and WANE move a body-wide opening rather
    // than merely recoloring scenery; Prism can be shattered, Thorn can be
    // crossed at a health cost, and Stone demands navigation.
    // Stage silhouettes own the western 20x17 identity screen. Put the
    // mutable Law in the guaranteed far-east and southern court aprons so
    // the two systems compose instead of sandwiching decorative 8px slits.
    // The western altar remains an immediate, readable control point.
    h_gap = state ? 25 : 22;
    for (x = 21; x <= 27; ++x)
        law_set(x, 5, (x == h_gap || x == (u8)(h_gap + 1))
            ? BGT_FLOOR2 : material, live);
    v_gap = state ? 27 : 24;
    for (y = 24; y <= 29; ++y)
        law_set(26, y, (y == v_gap || y == (u8)(v_gap + 1))
            ? BGT_FLOOR2 : material, live);

    if (law_room_has_switch())
        law_set(LAW_SWITCH_X, LAW_SWITCH_Y, BGT_SWITCH, live);
}

u8 dungeon_law_try_toggle_at(u8 tx, u8 ty) BANKED {
    if (!law_room_has_switch() || tx != LAW_SWITCH_X || ty != LAW_SWITCH_Y)
        return 0;
    run_state.dungeon_law ^= DUNGEON_LAW_STATE_BIT;
    dungeon_law_apply_room(1);
    room_shake(2, 22);
    sfx_play(SFX_PUZZLE);
    sram_save_run();
    return 1;
}

u8 dungeon_law_try_player_toggle(void) BANKED {
    return dungeon_law_try_toggle_at((u8)((player.x + 8) >> 3),
        (u8)((player.y + 12) >> 3));
}

void dungeon_law_draw_pack(void) BANKED {
    gotoxy(7, 2);
    if (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter)) {
        text_write("OPEN SKY");
        return;
    }
    run_state_ensure_dungeon_law();
    text_write(law_names[run_state.dungeon_law & DUNGEON_LAW_KIND_MASK]);
    text_write("/");
    text_write((run_state.dungeon_law & DUNGEON_LAW_STATE_BIT)
        ? "WANE" : "WAX");
}
