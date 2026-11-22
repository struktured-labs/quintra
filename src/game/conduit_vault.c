#pragma bank 6
// M5b Conduit vault rules (bank 6): rewrite switches A/B (cairn <->
// rift-stream), the Cinder Kite chain (release plate -> rides the stream ->
// breath shatters the crystal lock), and the Heart two-door choice.
#include <gb/gb.h>
#include "audio/sfx.h"
#include "core/types.h"
#include "game/conduit_room.h"
#include "game/player.h"
#include "game/rime_room.h"
#include "game/room.h"
#include "game/run_state.h"

#define PX CD_PX
#define PY CD_PY
#define HX ((u8)player.x)
#define HY ((u8)player.y)
#define V_SWA 1
#define V_SWB 2
#define V_REL 4

u8 cd_ra, cd_rb, cd_kx, cd_kst, cd_kt, cd_lockup, cd_hkey, cd_hdoor;
u8 cd_coin_given, cd_rewrites, cd_von;
extern u8 cd_dirty;

static u8 vedge(u8 cond, u8 b) {
    if (!cond) { cd_von &= (u8)~b; return 0; }
    if (cd_von & b) return 0;
    cd_von |= b;
    return 1;
}


// Hero feet centre over cells lx..lx+w-1 on feet row ly.
static u8 on_cells(u8 lx, u8 w, u8 ly) {
    u8 x = (u8)(HX + 8);
    return (x >= PX(lx) && x < PX(lx + w)
        && (u8)((u8)(HY + 12) >> 3) == CD_WY(ly)) ? 1 : 0;
}

static void refuse(void) {
    cd_refusals++;
    sfx_play(SFX_REFUSE);
}

// Kite body columns cd_kx..cd_kx+15 overlap region (lx..lx+1)?
static u8 kite_on(u8 lx) {
    return ((u8)(cd_kx + 15) >= PX(lx) && cd_kx < PX(lx + 2)) ? 1 : 0;
}

// Raising a cairn on the Kite is refused (dud clunk); lowering is free.
static u8 can_set(u8 lx, u8 now) {
    return (now || !kite_on(lx) || cd_kst == CD_K_HOME) ? 1 : 0;
}

static void rewrite(u8 a) {
    u8 na = cd_ra, nb = (u8)(cd_rb ^ 1);
    if (a) na ^= 1;
    if ((na != cd_ra && !can_set(CD_RA_X, na)) || !can_set(CD_RB_X, nb)) {
        refuse();
        return;
    }
    if (na != cd_ra) { cd_ra = na; cd_vpaint(0); }
    cd_rb = nb;
    cd_vpaint(1);
    cd_rewrites++;
    cd_dirty = 1;
    sfx_play(SFX_DISTRICT);         // distinct rewrite cue (vault may be off camera)
}

static void kite_step(void) {
    u8 front;
    if (cd_kst == CD_K_FLY) {
        if (cd_kx <= PX(CD_KITE_STOP)) {
            cd_kst = CD_K_BREATH;
            cd_kt = 30;
            sfx_play(SFX_FIRE);
            return;
        }
        // Blocked by a cairn ahead (front column one px west).
        front = (u8)((u8)(cd_kx - 1) >> 3);
        if ((front == CD_WX(CD_RA_X) || front == CD_WX(CD_RA_X + 1)) && !cd_ra) return;
        if ((front == CD_WX(CD_RB_X) || front == CD_WX(CD_RB_X + 1)) && !cd_rb) return;
        cd_kx--;
        return;
    }
    if (cd_kst == CD_K_BREATH) {
        if (--cd_kt) return;
        cd_kst = CD_K_DONE;
        if (cd_lockup) {
            cd_lockup = 0;
            cd_vpaint(2);
            sfx_play(SFX_DEATH);
            room_shake(1, 14);
        }
    }
}

void cd_vault_tick(void) BANKED {
    if (cd_live != 1) return;
    if (vedge(on_cells(CD_SWA_X, 1, CD_SW_ROW), V_SWA)) rewrite(1);
    if (vedge(on_cells(CD_SWB_X, 1, CD_SW_ROW), V_SWB)) rewrite(0);
    // Release plate (wakes the Kite): cd_vault_doors, bank 10.
    if (!room_freeze_beats) kite_step();      // freeze holds the Kite too
    cd_vault_doors();
}
