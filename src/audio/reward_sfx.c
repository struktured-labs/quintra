#pragma bank 2

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"

static void reward_ch1(u8 nr10, u8 nr11, u8 nr12, u16 freq) {
    sfx_claim_channels(12, 0);
    NR10_REG = nr10;
    NR11_REG = nr11;
    NR12_REG = nr12;
    NR13_REG = (u8)(freq & 0xFF);
    NR14_REG = (u8)(0x80 | (freq >> 8));
}

static void reward_ch4(u8 nr43, u8 nr42) {
    sfx_claim_channels(0, 12);
    NR42_REG = nr42;
    NR43_REG = nr43;
    NR44_REG = 0x80;
}

void sfx_play_reward(u8 kind) BANKED {
    switch (kind) {
        case SFX_REWARD_MAGIC:
            // Clean high upward shimmer: MP/wells, never currency.
            reward_ch1(0x23, 0x40, 0xA3, 1902);
            break;
        case SFX_REWARD_SIGIL:
            // Resonant key claim: low square bell plus crystalline breath.
            reward_ch1(0x36, 0xC0, 0xD5, 1688);
            reward_ch4(0x55, 0x63);
            break;
        case SFX_REWARD_SURGE:
            // Fast power bloom replaces the boss-roar/boom formerly reused
            // by temporary weapon upgrades.
            reward_ch1(0x27, 0x80, 0xE3, 1849);
            reward_ch4(0x33, 0x72);
            break;
        case SFX_REWARD_PURCHASE:
            // Short register-like acknowledgement with a dry receipt click.
            reward_ch1(0x00, 0x40, 0x92, 1969);
            reward_ch4(0x24, 0x41);
            break;
        case SFX_REWARD_UNLOCK:
            // Heavy latch followed by an upward sweep. Deliberately unlike
            // an enemy death, loose coin, or the longer puzzle revelation.
            reward_ch4(0x5A, 0xB3);
            reward_ch1(0x26, 0x80, 0xC4, 1700);
            break;
        default:
            // Permanent relic/boon: a forged ping with a locking click.
            reward_ch1(0x00, 0x80, 0xD4, 1949);
            reward_ch4(0x24, 0x51);
            break;
    }
}
