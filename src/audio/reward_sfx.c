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
    // Discovery and room-clear melodies schedule later CH1 notes. A reward
    // collected during that window stays mechanically collected but silent,
    // rather than cutting the fanfare into unrelated fragments.
    if (kind != SFX_REWARD_SIGIL && sfx_melody_locked()) return;
    sfx_will_active = 0;
    switch (kind) {
        case SFX_REWARD_MAGIC:
            // Clean high upward shimmer: MP/wells, never currency.
            reward_ch1(0x23, 0x40, 0xA3, 1902);
            break;
        case SFX_REWARD_SIGIL:
            // The mandatory stage objective owns a true major-item fanfare.
            // It may supersede a coincident incidental secret melody rather
            // than becoming a silent inventory bit the player never notices.
            sfx_play(SFX_SIGIL);
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

// Full Will is a power-up, not a pickup. CH1 only. A sweep climbs from C4
// while the volume swells from 4 toward 10, then a short 25% duty G6 ring
// shimmers at the top. Peak volume stays under a shot (12). Nothing here
// writes the music lead or the noise channel, and nothing locks the effect
// bus. The whole gesture is about 0.45s, with none of the coin's B5-E6 pair.
#define WILL_NOTES 2
#define WILL_CLAIM 34
static const u8 will_gap[WILL_NOTES] = { 20, 0 };
static const u8 will_sweep[WILL_NOTES] = { 0x55, 0x00 };
static const u8 will_duty[WILL_NOTES] = { 0x80, 0x40 };
static const u8 will_env[WILL_NOTES] = { 0x4C, 0xA1 };
static const u16 will_freq[WILL_NOTES] = { 1547, 1964 };

static u8 will_step;
static u8 will_timer;

static void will_emit(u8 step) {
    NR10_REG = will_sweep[step];
    NR11_REG = will_duty[step];
    NR12_REG = will_env[step];
    NR13_REG = (u8)(will_freq[step] & 0xFF);
    NR14_REG = (u8)(0x80 | (will_freq[step] >> 8));
}

void sfx_play_will(void) BANKED {
    sfx_will_active = 1;
    will_step = 0;
    will_timer = will_gap[0];
    sfx_claim_channels(WILL_CLAIM, 0);
    will_emit(0);
}

void sfx_tick_will(void) BANKED {
    u8 next;
    if (--will_timer) return;
    next = (u8)(will_step + 1);
    will_step = next;
    will_emit(next);
    if ((u8)(next + 1) >= WILL_NOTES) {
        sfx_will_active = 0;
        return;
    }
    will_timer = will_gap[next];
}
