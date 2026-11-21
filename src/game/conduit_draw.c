#pragma bank 14
// M5a Conduit: OBJ list (shared lk_spr_* buffer) and Pack line (bank 14).
#include <gb/gb.h>
#include <gbdk/console.h>
#include "core/types.h"
#include "game/conduit_room.h"
#include "game/lock_room.h"
#include "game/player.h"
#include "game/rime_room.h"
#include "render/conduit_art.h"
#include "render/text.h"

#define PX CD_PX
#define PY CD_PY

// ---- OBJ list (shared lk_spr_* buffer, drawn by enemy_new_draw) ----
static void sp(u8 x, u8 y, u8 t, u8 p) {
    u8 n = lk_spr_n;
    if (n >= LK_SPR_MAX) return;
    lk_spr_x[n] = x; lk_spr_y[n] = y; lk_spr_t[n] = t; lk_spr_p[n] = p;
    lk_spr_n = (u8)(n + 1);
}

static void sq(u8 x, u8 y, u8 t, u8 p) {
    sp(x, y, t, p); sp((u8)(x + 8), y, (u8)(t + 1), p);
    sp(x, (u8)(y + 8), (u8)(t + 2), p); sp((u8)(x + 8), (u8)(y + 8), (u8)(t + 3), p);
}

void cd_sprites(void) BANKED {
    u8 x, y, n = 0;
    lk_spr_n = 0;
    if (cd_jst != CD_J_DEAD)
        sq(cd_jx, cd_jy, CD_TILE_JAGGER, room_freeze_beats ? (3 | 0x08) : (0 | 0x08));
    if (cd_thp) {
        // Telegraph: body flashes, a spark marks the lane, and the switch
        // flashes gold when that lane crosses it.
        sq(PX(CD_TUR_X), PY(CD_TUR_Y), CD_TILE_TURRET,
            ((cd_tell && (cd_tell & 4)) || cd_tflash) ? (4 | 0x08) : (3 | 0x08));
        if (cd_tell) {
            if (cd_thead) sp((u8)(PX(CD_TUR_X) + 4), PY(CD_TUR_Y + 2), CD_TILE_SPARK, 2 | 0x08);
            else sp((u8)(PX(CD_TUR_X) - 8), (u8)(PY(CD_TUR_Y) + 4), CD_TILE_SPARK, 2 | 0x08);
            if (cd_thead && (cd_tell & 4))
                sq(PX(CD_SW_X), PY(CD_SW_Y), CD_TILE_SWITCH, 5 | 0x08);
        }
    }
    if (cd_sst == 2) sq(cd_sx, PY(CD_LANE_Y), CD_TILE_STONE, 0 | 0x08);
    else if (cd_sst == 1 && (cd_st & 4)) sq(PX(CD_W - 2), PY(CD_LANE_Y), CD_TILE_STONE, 0 | 0x08);
    if (cd_key) {
        sp((u8)(PX(CD_KEY_X) + 4), PY(CD_KEY_Y), CD_TILE_BOW, 5 | 0x08);
        sp((u8)(PX(CD_KEY_X) + 4), (u8)(PY(CD_KEY_Y) + 8), CD_TILE_SHAFT, 5 | 0x08);
    }
    if (!cd_open) sp((u8)(PX(CD_DOOR_X) + 4), PY(CD_DOOR_Y), CD_TILE_BOW, 5 | 0x08);
    if (!cd_charge && !room_freeze_beats)
        sp((u8)(PX(CD_FRZ_X) + 4), (u8)(PY(CD_FRZ_Y) + 4), CD_TILE_PIP, 3 | 0x08);
    // Held pips above the hero: Star key, Rime charge.
    x = (u8)((u8)player.x + 4);
    y = (u8)((u8)player.y - 9);
    if (cd_held) { sp(x, y, CD_TILE_BOW, 5 | 0x08); n = 8; }
    if (cd_charge) sp((u8)(x + n), y, CD_TILE_PIP, 3 | 0x08);
}

// Pack TOOL entries: 0 = FREEZE, 1 = RESET ROOM.
void cd_pack_draw(u8 idx) BANKED {
    gotoxy(3, 15);
    if (idx == 0) {
        text_write("TOOL FREEZE x");
        text_u16(cd_charge);
        text_write("  ");
        set_sprite_tile(8, CD_TILE_PIP);
        set_sprite_prop(8, 3 | 0x08);
    } else {
        text_write("TOOL RESET ROOM");
        set_sprite_tile(8, CD_TILE_SPARK);
        set_sprite_prop(8, 5 | 0x08);
    }
    move_sprite(8, 16, 135);
}
