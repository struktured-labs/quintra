#pragma bank 19

#include <gb/gb.h>
#include "audio/sfx.h"
#include "core/types.h"

static const u16 rune_notes[5] = { 1798, 1825, 1849, 1881, 1915 };

static void rune_ch1(u8 env, u16 freq) {
    NR10_REG = 0x00;
    NR11_REG = 0x80;
    NR12_REG = env;
    NR13_REG = (u8)(freq & 0xFF);
    NR14_REG = (u8)(0x80 | (freq >> 8));
}

void sfx_play_rune_echo(u8 step) BANKED {
    if (step > 4) step = 4;
    sfx_will_active = 0;
    rune_ch1(0xF2, rune_notes[step]);
    sfx_claim_channels(24, 0);
}

void sfx_play_rune_final(u8 step) BANKED {
    if (step > 4) step = 4;
    sfx_will_active = 0;
    rune_ch1(0xF7, rune_notes[step]);
    sfx_claim_channels(56, 0);
    sfx_play_puzzle_after_note();
}
