#pragma bank 22

#include <gb/gb.h>
#include "render/tiles.h"
#include "render/sprites_gen.h"

const u8 bgt_switch_pressed[16] = {
    0x42, 0xFF, 0x42, 0x81, 0x3C, 0x81, 0x24, 0x99,
    0x3C, 0x81, 0x3C, 0x81, 0x43, 0x81, 0x01, 0xFE
};

void tiles_load_switch_pressed(void) BANKED {
    set_bkg_data(BGT_SWITCH_PRESSED, 1, bgt_switch_pressed);
}
