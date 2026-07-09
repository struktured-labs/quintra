#include <gb/gb.h>

#include "core/rng.h"
#include "input/input.h"
#include "audio/audio.h"
#include "game/loop.h"
#include "game/title.h"
#include "game/scratch.h"
#include "game/class_select.h"
#include "game/run_init.h"
#include "game/room.h"
#include "game/gameover.h"
#include "game/victory.h"
#include "game/inventory.h"

screen_id_t loop_current_screen = SCREEN_BOOT;
u16         loop_frame_counter  = 0;

// Bank references for the banked screen files (each defines a matching
// BANKREF(); bankpack patches these to the real assigned bank numbers).
BANKREF_EXTERN(title_enter)
BANKREF_EXTERN(class_select_enter)
BANKREF_EXTERN(room_enter)
BANKREF_EXTERN(inventory_enter)
BANKREF_EXTERN(gameover_enter)
BANKREF_EXTERN(victory_enter)
BANKREF_EXTERN(scratch_enter)

// The screen table. Each screen lives in its own translation unit; banked
// screens carry their BANK(fn) so the dispatcher can map them first.
const screen_t screens[SCREEN_COUNT] = {
    [SCREEN_BOOT]         = { 0, 0, 0, 0, 0 },
    [SCREEN_TITLE]        = { BANK(title_enter), title_enter,   title_exit,   title_tick,   title_draw   },
    [SCREEN_CLASS_SELECT] = { BANK(class_select_enter), class_select_enter, class_select_exit, class_select_tick, class_select_draw },
    [SCREEN_RUN_INIT]     = { 0, run_init_enter,     run_init_exit,     run_init_tick,     run_init_draw     },
    [SCREEN_PROCGEN]      = { 0, 0, 0, 0, 0 },
    [SCREEN_ROOM]         = { BANK(room_enter), room_enter,         room_exit,         room_tick,         room_draw         },
    [SCREEN_REST_ROOM]    = { 0, 0, 0, 0, 0 },
    [SCREEN_BOSS]         = { 0, 0, 0, 0, 0 },
    [SCREEN_INVENTORY]    = { BANK(inventory_enter), inventory_enter, inventory_exit, inventory_tick, inventory_draw },
    [SCREEN_DIALOG]       = { 0, 0, 0, 0, 0 },
    [SCREEN_GAMEOVER]     = { BANK(gameover_enter), gameover_enter, gameover_exit, gameover_tick, gameover_draw },
    [SCREEN_VICTORY]      = { BANK(victory_enter), victory_enter,  victory_exit,  victory_tick,  victory_draw  },
    [SCREEN_SCRATCH]      = { BANK(scratch_enter), scratch_enter, scratch_exit, scratch_tick, scratch_draw },
};

// Map a screen's bank before touching its function pointers (bank 0 =
// screen code is home / always mapped, leave the window alone).
static void screen_map(screen_id_t s) {
    if (screens[s].bank) SWITCH_ROM(screens[s].bank);
}

void loop_init(screen_id_t start) {
    loop_current_screen = start;
    loop_frame_counter  = 0;
    screen_map(start);
    if (screens[start].enter) screens[start].enter();
}

void loop_run(void) {
    screen_id_t cur = loop_current_screen;
    screen_id_t next;

    for (;;) {
        input_poll();

        screen_map(cur);
        if (screens[cur].tick) {
            next = screens[cur].tick(input_keys, input_pressed);
            if (next != SCREEN_SELF && next != cur) {
                if (screens[cur].exit)  screens[cur].exit();
                cur = next;
                loop_current_screen = cur;
                screen_map(cur);
                if (screens[cur].enter) screens[cur].enter();
            }
        }

        if (screens[cur].draw) { screen_map(cur); screens[cur].draw(); }

        audio_tick();

        wait_vbl_done();
        loop_frame_counter++;
        // Mix a bit of the frame counter into the RNG state for entropy
        if ((loop_frame_counter & 0x3FFF) == 0) rng_next();
    }
}
