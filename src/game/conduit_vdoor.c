#pragma bank 10
// M5b Conduit vault: Heart key and the Heart two-door choice (bank 10).
#include <gb/gb.h>
#include "audio/sfx.h"
#include "core/types.h"
#include "game/conduit_room.h"
#include "game/pickup.h"
#include "game/player.h"

#define PX CD_PX
#define PY CD_PY
#define HX ((u8)player.x)
#define HY ((u8)player.y)

extern u8 cd_dirty;
static u8 hd_on;

static u8 hero_box(u8 x0, u8 y0, u8 w, u8 h) {
    return ((u8)(HX + 13) >= x0 && (u8)(HX + 2) < (u8)(x0 + w)
        && (u8)(HY + 15) >= y0 && (u8)(HY + 8) < (u8)(y0 + h)) ? 1 : 0;
}

// Heart doors (1x2, vertical): touching one with the Heart key opens it and
// spends the key; the other stays locked (choice). Reset returns the key.
static void heart_door(u8 bit, u8 lx) {
    if (cd_hdoor & bit) return;
    if (!hero_box((u8)(PX(lx) - 1), PY(CD_HD_Y), 10, 16)) return;
    if (hd_on) return;
    hd_on = 1;
    if (cd_held & 2) {
        cd_held &= (u8)~2;
        cd_hdoor |= bit;
        cd_dirty = 1;
        cd_vpaint(bit == 1 ? 3 : 4);
        sfx_play(SFX_DOOR);
        if (bit == 1 && !cd_coin_given) {     // optional treasure, once per visit
            cd_coin_given = 1;
            pickup_spawn(PICKUP_COIN_5, (i16)PX(CD_COIN_X), (i16)PY(CD_COIN_Y));
        }
    } else {
        cd_refusals++;
        sfx_play(SFX_REFUSE);
    }
}


void cd_vault_doors(void) BANKED {
    u8 on;
    // Heart key, once the lock is gone (2x2 cells).
    if (!cd_lockup && cd_hkey && hero_box(PX(CD_LOCK_X), PY(CD_LOCK_Y), 16, 16)) {
        cd_hkey = 0;
        cd_held |= 2;
        cd_dirty = 1;
        sfx_play(SFX_COIN);
    }
    on = (hero_box((u8)(PX(CD_HDA_X) - 1), PY(CD_HD_Y), 10, 16)
        || hero_box((u8)(PX(CD_HDB_X) - 1), PY(CD_HD_Y), 10, 16)) ? 1 : 0;
    if (!on) hd_on = 0;
    heart_door(1, CD_HDA_X);
    heart_door(2, CD_HDB_X);
}
