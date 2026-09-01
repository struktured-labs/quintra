#pragma bank 7

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "content.h"

static void weapon_ch1(u8 nr10, u8 nr11, u8 nr12, u16 freq) {
    sfx_claim_channels(8, 0);
    NR10_REG = nr10;
    NR11_REG = nr11;
    NR12_REG = nr12;
    NR13_REG = (u8)(freq & 0xFF);
    NR14_REG = (u8)(0x80 | (freq >> 8));
}

static void weapon_ch4(u8 nr43, u8 nr42) {
    sfx_claim_channels(0, 8);
    NR42_REG = nr42;
    NR43_REG = nr43;
    NR44_REG = 0x80;
}

void sfx_play_weapon(u8 projectile_kind) BANKED {
    if (sfx_melody_locked()) return;
    if (projectile_kind == PROJ_FLAIL) {
        // Low 75%-duty head impact plus loose 7-bit chain chatter.
        weapon_ch1(0x3A, 0xC0, 0xD3, 1440);
        weapon_ch4(0x49, 0xA3);
    } else if (projectile_kind == PROJ_SPEAR) {
        // Focused rising lance, intentionally cleaner than a bullet zap.
        weapon_ch1(0x23, 0x80, 0xB2, 1810);
    } else {
        // Quick high-to-low steel/organic swipe with a dry cutting edge.
        weapon_ch1(0x1B, 0x40, 0xB1, 1958);
        weapon_ch4(0x23, 0x61);
    }
}

void sfx_play_boomerang(u8 caught) BANKED {
    if (sfx_melody_locked()) return;
    if (caught) {
        weapon_ch1(0x00, 0x80, 0x71, 1942);
        weapon_ch4(0x17, 0x41);
    } else {
        weapon_ch1(0x2B, 0x40, 0x92, 1860);
        weapon_ch4(0x33, 0x42);
    }
}

void sfx_play_equip(void) BANKED {
    // Bright forged ping plus a soft locking click. This stays distinct from
    // both paid coin feedback and the longer puzzle/room-clear fanfares.
    if (sfx_melody_locked()) return;
    weapon_ch1(0x00, 0x80, 0xD4, 1949);
    weapon_ch4(0x24, 0x51);
}
