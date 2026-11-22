#pragma bank 16
// M5a Conduit: rolling-stone lane and the Stone Jagger (bank 16).
// Split from conduit_room.c (bank 24) for space.
#include <gb/gb.h>
#include "audio/sfx.h"
#include "core/types.h"
#include "game/conduit_room.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/rime_room.h"
#include "game/room.h"
#include "game/run_state.h"

#define PX CD_PX
#define PY CD_PY
#define HX ((u8)player.x)
#define HY ((u8)player.y)
extern u8 cd_dirty;

static u8 feet_hit(u8 ax, u8 ay, u8 bx, u8 by) {
    return ((u8)(ax + 2) <= (u8)(bx + 13) && (u8)(bx + 2) <= (u8)(ax + 13)
        && (u8)(ay + 8) <= (u8)(by + 15) && (u8)(by + 8) <= (u8)(ay + 15)) ? 1 : 0;
}

// ---- rolling stone + Jagger ----
static u8 jag_fits(u8 nx, u8 ny) {
    return feet_hit(nx, ny, HX, HY) ? 0 : 1;
}

static void jagger_step(void) {
    u8 tx;
    if (cd_jst == CD_J_DEAD || room_freeze_beats) return;
    // Out of the lane while a stone is coming, back into it after.
    if (cd_sst) {
        if (cd_jy > PY(CD_LANE_Y - 2) && jag_fits(cd_jx, cd_jy - 1)) cd_jy--;
        return;
    }
    if (cd_jy < PY(CD_LANE_Y)) {
        if (jag_fits(cd_jx, cd_jy + 1)) cd_jy++;
        return;
    }
    // Guard: shadow the hero along the lane in front of the Star door.
    tx = HX;
    if (tx < PX(3)) tx = PX(3);
    if (tx > PX(9)) tx = PX(9);         // M5b: door at 6..7; lure either side
    if (tx < cd_jx && jag_fits(cd_jx - 1, cd_jy)) cd_jx--;
    else if (tx > cd_jx && jag_fits(cd_jx + 1, cd_jy)) cd_jx++;
}

static u8 stone_hits(u8 x, u8 y) {
    return ((u8)(x + 13) >= cd_sx && x <= (u8)(cd_sx + 13)
        && (u8)(y + 15) >= PY(CD_LANE_Y) && (u8)(y + 8) < PY(CD_LANE_Y + 2)) ? 1 : 0;
}

static void stone_step(void) {
    u8 i;
    if (cd_sst == 0) {
        if (--cd_st) return;
        cd_sst = 1;
        cd_st = 40;
        sfx_play(SFX_ROAR);
        room_shake(1, 8);
        return;
    }
    if (cd_sst == 1) {
        if (--cd_st) return;
        cd_sst = 2;
        cd_sx = PX(CD_W - 2);
        return;
    }
    cd_sx -= 2;
    if (cd_jst != CD_J_DEAD && stone_hits(cd_jx, cd_jy)) {
        if (room_freeze_beats) {
            // A frozen Jagger in the lane is crushed (reset brings it back).
            cd_jst = CD_J_DEAD;
            cd_crushed++;
            cd_dirty = 1;
            sfx_play(SFX_DEATH);
            room_shake(1, 16);
        } else {                    // it shatters on a Jagger that is awake
            cd_sst = 0;
            cd_st = RUN_IS_EASY() ? 170 : 140;
            return;
        }
    }
    for (i = 0; i < 2; ++i)
        if (cd_pack[i] != 0xFF && entities[cd_pack[i]].type == ENT_ENEMY
            && (entities[cd_pack[i]].flags & EF_ACTIVE) && stone_hits((u8)entities[cd_pack[i]].x,
                (u8)entities[cd_pack[i]].y - 4))
            { if (entities[cd_pack[i]].flags & EF_ACTIVE) entity_kill(cd_pack[i]); cd_pack[i] = 0xFF; }
    if (stone_hits(HX, HY)) {
        // Shove the hero out of the lane (north); never damage.
        cd_shoves++;
        if (cd_jst == CD_J_DEAD || !feet_hit(HX, (u8)(PY(CD_LANE_Y - 1) - 8), cd_jx, cd_jy))
            player.y = (i16)PY(CD_LANE_Y - 1) - 8;
        else if (HX > PX(1)) player.x -= 2;
        if (player.iframes < 20) player.iframes = 20;
    }
    if (cd_sx <= PX(1)) {
        cd_sst = 0;
        cd_st = RUN_IS_EASY() ? 170 : 140;
    }
}

void cd_lane_step(void) BANKED {
    stone_step();
    jagger_step();
}
