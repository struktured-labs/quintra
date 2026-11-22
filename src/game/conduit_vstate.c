#pragma bank 29
// M5b Conduit vault: stamp, restore, redress (bank 29).
#include <gb/gb.h>
#include "core/types.h"
#include "game/conduit_room.h"
#include "game/rime_room.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/kite_art.h"
#include "render/tiles.h"

#define PX CD_PX
#define PY CD_PY
extern u8 cd_von, cd_hdon;

static void fixed_parts(void) {
    u8 x;
    cd_vfill(CD_T_STREAM, BGPAL_CRYSTAL);
    for (x = 1; x <= 9; x += 2)
        if (x != CD_RB_X && x != CD_RA_X) cd_vblk(x, CD_STREAM_Y, 2, 2);
    cd_vfill(96, BGPAL_DOOR);
    cd_vblk(CD_REL_X, CD_REL_Y, 2, 1);
    cd_vfill((run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT) ? BGT_SWITCH_PRESSED : BGT_SWITCH,
        BGPAL_DOOR);
    cd_vblk(CD_GOAL_X, CD_GOAL_Y, 2, 1);
}

static void paint_all(void) {
    u8 r;
    for (r = 0; r < 5; ++r) cd_vpaint(r);
}

// Stamp rows 13..16 (and the two switch glyphs) after the layout table.
void cd_vault_prepare(void) BANKED {
    u8 y;
    cd_vfill(BGT_FLOOR, BGPAL_FLOOR);
    for (y = 13; y <= 14; ++y) {
        cd_vblk(1, y, 2, 1); cd_vblk(6, y, 2, 1); cd_vblk(9, y, 2, 1);
    }
    fixed_parts();
    cd_vault_restore();
}

void cd_vault_restore(void) BANKED {
    cd_ra = 0;
    cd_rb = 1;
    cd_kx = PX(CD_KITE_HOME);
    cd_kst = CD_K_HOME;
    cd_kt = 0;
    cd_lockup = 1;
    cd_hkey = 1;
    cd_hdoor = 0;
    cd_von = 0xFF;
    cd_hdon = 1;
    paint_all();
}

void cd_vault_redress(void) BANKED {
    kt_bg_art_load();               // cairn, stream, lock (M3 art); door/bars reloaded after
    cd_vart_load();
    fixed_parts();
    paint_all();
}
