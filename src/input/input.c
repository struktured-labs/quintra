#include <gb/gb.h>

#include "input/input.h"
#include "game/attract.h"
#include "game/loop.h"

u8 input_keys     = 0;
u8 input_prev     = 0;
u8 input_pressed  = 0;
u8 input_released = 0;

void input_init(void) {
    input_keys = input_prev = input_pressed = input_released = 0;
}

void input_poll(void) {
    input_prev    = input_keys;
    input_keys    = joypad();
    input_pressed  = input_keys & ~input_prev;
    input_released = input_prev & ~input_keys;
    // Attract demo: recorded input replaces the joypad. A real press or the
    // end of the recording hands back to the title before this frame ticks.
    if (attract_demo && attract_demo_frame() != SCREEN_SELF)
        loop_switch(SCREEN_TITLE);
}
