#include <gb/gb.h>

#include "core/rng.h"
#include "input/input.h"
#include "audio/audio.h"
#include "game/loop.h"
#include "game/title.h"
#include "game/class_select.h"
#include "game/run_init.h"
#include "game/room.h"
#include "game/gameover.h"
#include "game/victory.h"
#include "game/inventory.h"
#include "game/map.h"
#include "game/dialog.h"
#include "game/vignette.h"
#include "game/attract.h"
#include "render/palette.h"

/* Bare decls: do not include enemy_new_ai.h (pulls entity.h into HOME). */
extern u8 leybeam_flush_pending;
void leybeam_vblank_flush(void) BANKED;


screen_id_t loop_current_screen = SCREEN_BOOT;
u16         loop_frame_counter  = 0;

// True-60Hz tick source (see loop.h). ISRs must live in home and stay
// tiny: one increment.
volatile u8 g_vbl_ticks = 0;
// Monotonic hardware-audio clock. Unlike g_vbl_ticks, room_tick never drains
// this byte; audio_tick takes an unsigned delta from its own last observation.
// That keeps tempo at 59.7 Hz even when a dense simulation spans two VBlanks.
volatile u8 g_vbl_epoch = 0;
static void loop_vbl_isr(void) NONBANKED {
    g_vbl_ticks++;
    g_vbl_epoch++;
}

// Bank references for the banked screen files (each defines a matching
// BANKREF(); bankpack patches these to the real assigned bank numbers).
BANKREF_EXTERN(title_enter)
BANKREF_EXTERN(class_select_enter)
BANKREF_EXTERN(run_init_enter)
BANKREF_EXTERN(room_enter)
BANKREF_EXTERN(inventory_enter)
BANKREF_EXTERN(map_enter)
BANKREF_EXTERN(dialog_enter)
BANKREF_EXTERN(gameover_enter)
BANKREF_EXTERN(victory_enter)
BANKREF_EXTERN(vignette_enter)
BANKREF_EXTERN(intro_enter)

// The screen table. Each screen lives in its own translation unit; banked
// screens carry their BANK(fn) so the dispatcher can map them first.
const screen_t screens[SCREEN_COUNT] = {
    [SCREEN_BOOT]         = { 0, 0, 0, 0, 0 },
    [SCREEN_TITLE]        = { BANK(title_enter), title_enter,   title_exit,   title_tick,   title_draw   },
    [SCREEN_CLASS_SELECT] = { BANK(class_select_enter), class_select_enter, class_select_exit, class_select_tick, class_select_draw },
    [SCREEN_RUN_INIT]     = { BANK(run_init_enter), run_init_enter, run_init_exit, run_init_tick, run_init_draw },
    [SCREEN_INTRO]        = { BANK(intro_enter), intro_enter, intro_exit, intro_tick, 0 },
    [SCREEN_ROOM]         = { BANK(room_enter), room_enter,         room_exit,         room_tick,         room_draw         },
    [SCREEN_VIGNETTE]     = { BANK(vignette_enter), vignette_enter, 0, vignette_tick, 0 },
    [SCREEN_BOSS]         = { 0, 0, 0, 0, 0 },
    [SCREEN_MAP]          = { BANK(map_enter), map_enter, map_exit, map_tick, map_draw },
    [SCREEN_INVENTORY]    = { BANK(inventory_enter), inventory_enter, inventory_exit, inventory_tick, inventory_draw },
    [SCREEN_DIALOG]       = { BANK(dialog_enter), dialog_enter, dialog_exit, dialog_tick, dialog_draw },
    [SCREEN_GAMEOVER]     = { BANK(gameover_enter), gameover_enter, gameover_exit, gameover_tick, gameover_draw },
    [SCREEN_VICTORY]      = { BANK(victory_enter), victory_enter,  victory_exit,  victory_tick,  victory_draw  },
};

// Map a screen's bank before touching its function pointers (bank 0 =
// screen code is home / always mapped, leave the window alone).
static void screen_map(screen_id_t s) {
    if (screens[s].bank) SWITCH_ROM(screens[s].bank);
}

void loop_init(screen_id_t start) {
    loop_current_screen = start;
    loop_frame_counter  = 0;
    CRITICAL {
        add_VBL(loop_vbl_isr);
    }
    screen_map(start);
    if (screens[start].enter) screens[start].enter();
}

// Exit the current screen and enter `next`. Home-only: it maps other banks.
// input_poll() also calls it when an attract demo hands back to the title.
void loop_switch(screen_id_t next) {
    screen_id_t cur = loop_current_screen;
    screen_map(cur);
    if (screens[cur].exit) screens[cur].exit();
    loop_current_screen = next;
    screen_map(next);
    if (screens[next].enter) screens[next].enter();
}

void loop_run(void) {
    screen_id_t cur;
    screen_id_t next;

    for (;;) {
        // Record the VBlank epoch at the start of the iteration.
        u8 vbl_at_start = g_vbl_epoch;
        input_poll();
        cur = loop_current_screen;

        screen_map(cur);
        if (screens[cur].tick) {
            next = screens[cur].tick(input_keys, input_pressed);
            if (next != SCREEN_SELF && next != cur) {
                loop_switch(next);
                cur = next;
            }
        }

        if (screens[cur].draw) { screen_map(cur); screens[cur].draw(); }

        audio_tick();

        // If this iteration already crossed VBlank, skip a second wait so
        // a tiny overrun stays at 60 Hz. A first mid-room palette heal
        // pass (or a Leybeam BG stamp) must still land in LY 144-149:
        // commit immediately when still in that window, otherwise wait
        // once if no pass has landed yet. Later pending passes ride a
        // future on-time frame so a busy effect (Tide Vortex) is not
        // forced to 30 Hz for every armed heal.
        {
            u8 can_commit = 0;
            if (g_vbl_epoch == vbl_at_start) {
                wait_vbl_done();
                can_commit = 1;
            } else if (palette_obj_pending_commit
                       || palette_bg_pending_commit
                       || leybeam_flush_pending) {
                if (LY_REG >= 144u && LY_REG < 150u) {
                    can_commit = 1;
                } else if (palette_bg_pending_commit == PALETTE_BG_COMMIT_PASSES
                           || palette_obj_pending_commit == PALETTE_OBJ_COMMIT_PASSES
                           || leybeam_flush_pending) {
                    wait_vbl_done();
                    can_commit = 1;
                }
            }
            if (can_commit) {
                // OBJ first: the title commit needs the top VBlank lines.
                if (palette_obj_pending_commit) palette_obj_commit_vblank();
                else if (palette_bg_pending_commit) palette_bg_commit_vblank();
                if (leybeam_flush_pending) leybeam_vblank_flush();
            }
        }

        loop_frame_counter++;
        // Mix a bit of the frame counter into the RNG state for entropy
        if ((loop_frame_counter & 0x3FFF) == 0) rng_next();
    }
}
