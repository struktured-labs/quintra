#pragma bank 6
#include <gb/gb.h>

#include "audio/music_score.h"

BANKREF(music_stage_score)

// Stage 0 — Crystal Caverns: D-dorian facets and a lower answering arc.
const u8 melody[64] = {
    T_D5,T_A5,T_F5,T_A5, T_C6,T_A5,T_F5,T_A5,
    T_D5,T_A5,T_F5,T_A5, T_E5,T_G5,T_B5,T_G5,
    T_D5,T_A5,T_F5,T_A5, T_C6,T_A5,T_F5,T_A5,
    T_G5,T_B5,T_D6,T_B5, T_A5,T_F5,T_E5,T_C5,
    T_D5,T_F5,T_A5,T_C6, T_A5,T_G5,T_F5,T_E5,
    T_D5,T_E5,T_F5,T_A5, T_G5,T_E5,T_C5,T_REST,
    T_G5,T_A5,T_B5,T_D6, T_C6,T_A5,T_G5,T_E5,
    T_F5,T_E5,T_D5,T_C5, T_D5,T_A5,T_D5,T_REST,
};
const u8 bassline[16] = {
    T_D3,T_D3,T_C3,T_C3,T_D3,T_D3,T_G3,T_A3,
    T_D3,T_F3,T_C3,T_G3,T_D3,T_A3,T_G3,T_D3,
};

// Stage 1 — Verdant Hollow: canopy climb and falling-leaf answer.
const u8 s1_melody[64] = {
    T_E5,T_F5,T_E5,T_C5, T_E5,T_G5,T_F5,T_E5,
    T_A5,T_G5,T_F5,T_E5, T_F5,T_E5,T_C5,T_REST,
    T_E5,T_F5,T_G5,T_A5, T_G5,T_F5,T_E5,T_F5,
    T_C6,T_A5,T_G5,T_F5, T_E5,T_C5,T_E5,T_REST,
    T_G5,T_A5,T_B5,T_G5, T_E5,T_G5,T_A5,T_B5,
    T_C6,T_B5,T_A5,T_G5, T_E5,T_D5,T_E5,T_REST,
    T_E5,T_G5,T_C6,T_B5, T_A5,T_G5,T_E5,T_D5,
    T_G5,T_A5,T_G5,T_E5, T_D5,T_E5,T_G5,T_REST,
};
const u8 s1_bass[16] = {
    T_E3,T_E3,T_C3,T_C3,T_E3,T_G3,T_A3,T_E3,
    T_G3,T_G3,T_C3,T_C3,T_E3,T_A3,T_D3,T_G3,
};

// Stage 2 — Ember Depths: breathless heat figure and scorched descent.
const u8 s2_melody[64] = {
    T_A5,T_REST,T_C6,T_A5, T_G5,T_REST,T_E5,T_G5,
    T_F5,T_REST,T_A5,T_G5, T_E5,T_REST,T_D5,T_REST,
    T_A5,T_C6,T_D6,T_C6, T_A5,T_G5,T_E5,T_G5,
    T_F5,T_E5,T_D5,T_C5, T_D5,T_E5,T_REST,T_REST,
    T_E5,T_F5,T_G5,T_E5, T_C6,T_B5,T_A5,T_F5,
    T_E5,T_E5,T_F5,T_A5, T_G5,T_F5,T_E5,T_D5,
    T_C5,T_E5,T_F5,T_G5, T_A5,T_C6,T_A5,T_G5,
    T_F5,T_E5,T_D5,T_C5, T_E5,T_F5,T_E5,T_REST,
};
const u8 s2_bass[16] = {
    T_A3,T_A3,T_G3,T_G3,T_C3,T_C3,T_D3,T_A3,
    T_E3,T_E3,T_C3,T_C3,T_F3,T_A3,T_D3,T_E3,
};

// Stage 3 — Frost Vault: sparse bells opening into one crystalline run.
const u8 s3_melody[64] = {
    T_G5,T_B5,T_D6,T_B5, T_C6,T_B5,T_A5,T_G5,
    T_E5,T_G5,T_A5,T_B5, T_A5,T_G5,T_E5,T_REST,
    T_G5,T_B5,T_D6,T_E6, T_D6,T_B5,T_C6,T_A5,
    T_B5,T_G5,T_A5,T_FS5, T_G5,T_D5,T_G5,T_REST,
    T_D5,T_REST,T_A5,T_REST, T_FS5,T_REST,T_E5,T_REST,
    T_F5,T_A5,T_D6,T_REST, T_C6,T_A5,T_F5,T_REST,
    T_E5,T_REST,T_B5,T_REST, T_G5,T_REST,T_FS5,T_REST,
    T_D5,T_F5,T_A5,T_C6, T_A5,T_FS5,T_D5,T_REST,
};
const u8 s3_bass[16] = {
    T_G3,T_G3,T_C3,T_C3,T_E3,T_E3,T_D3,T_G3,
    T_D3,T_A3,T_F3,T_C3,T_E3,T_G3,T_A3,T_D3,
};

// Stage 4 — Toxic Mire: sinking steps and a slow surface ripple.
const u8 s4_melody[64] = {
    T_F5,T_REST,T_A5,T_C6, T_A5,T_F5,T_E5,T_REST,
    T_F5,T_G5,T_A5,T_G5, T_F5,T_E5,T_D5,T_REST,
    T_C5,T_F5,T_A5,T_C6, T_D6,T_C6,T_A5,T_G5,
    T_F5,T_REST,T_E5,T_F5, T_C5,T_REST,T_REST,T_REST,
    T_F5,T_REST,T_C6,T_A5, T_G5,T_F5,T_E5,T_REST,
    T_C5,T_E5,T_F5,T_A5, T_G5,T_E5,T_D5,T_REST,
    T_F5,T_A5,T_C6,T_D6, T_C6,T_A5,T_G5,T_F5,
    T_E5,T_D5,T_C5,T_REST, T_F5,T_REST,T_REST,T_REST,
};
const u8 s4_bass[16] = {
    T_C3,T_C3,T_F3,T_F3,T_C3,T_A3,T_G3,T_C3,
    T_F3,T_C3,T_A3,T_G3,T_F3,T_E3,T_C3,T_F3,
};

// Stage 5 — Shadow Keep: D-minor pursuit with a distant response.
const u8 s5_melody[64] = {
    T_D5,T_F5,T_A5,T_F5, T_D5,T_E5,T_F5,T_G5,
    T_A5,T_G5,T_F5,T_E5, T_D5,T_REST,T_C5,T_REST,
    T_D5,T_F5,T_A5,T_C6, T_A5,T_G5,T_F5,T_E5,
    T_D5,T_C5,T_D5,T_E5, T_F5,T_REST,T_REST,T_REST,
    T_A5,T_C6,T_D6,T_A5, T_F5,T_E5,T_D5,T_C5,
    T_D5,T_F5,T_G5,T_A5, T_C6,T_A5,T_G5,T_F5,
    T_E5,T_G5,T_B5,T_G5, T_E5,T_D5,T_C5,T_D5,
    T_F5,T_E5,T_D5,T_C5, T_D5,T_REST,T_REST,T_REST,
};
const u8 s5_bass[16] = {
    T_D3,T_D3,T_A3,T_A3,T_C3,T_C3,T_G3,T_D3,
    T_D3,T_F3,T_G3,T_A3,T_E3,T_C3,T_G3,T_D3,
};

// Stage 6 — Golden Temple: broad processional and sunlit counter-theme.
const u8 s6_melody[64] = {
    T_C5,T_E5,T_G5,T_C6, T_E6,T_C6,T_G5,T_E5,
    T_D5,T_F5,T_A5,T_D6, T_C6,T_A5,T_F5,T_D5,
    T_C5,T_E5,T_G5,T_C6, T_G5,T_E5,T_D5,T_B5,
    T_C6,T_D6,T_E6,T_D6, T_C6,T_REST,T_REST,T_REST,
    T_G5,T_C6,T_E6,T_C6, T_G5,T_E5,T_D5,T_C5,
    T_F5,T_A5,T_C6,T_A5, T_F5,T_D5,T_E5,T_G5,
    T_C6,T_B5,T_A5,T_G5, T_E5,T_G5,T_C6,T_E6,
    T_D6,T_B5,T_G5,T_E5, T_C5,T_G5,T_C6,T_REST,
};
const u8 s6_bass[16] = {
    T_C3,T_C3,T_G3,T_G3,T_A3,T_A3,T_F3,T_C3,
    T_C3,T_G3,T_F3,T_A3,T_C3,T_E3,T_G3,T_C3,
};

// Stage 7 — Bloodmoon: clipped ritual with a rising second invocation.
const u8 s7_melody[64] = {
    T_A5,T_C6,T_A5,T_E5, T_A5,T_C6,T_D6,T_C6,
    T_G5,T_B5,T_G5,T_E5, T_G5,T_A5,T_B5,T_A5,
    T_A5,T_E6,T_D6,T_C6, T_B5,T_A5,T_G5,T_E5,
    T_D5,T_E5,T_G5,T_A5, T_REST,T_REST,T_REST,T_REST,
    T_A5,T_A5,T_C6,T_E6, T_D6,T_C6,T_A5,T_G5,
    T_E5,T_G5,T_B5,T_D6, T_C6,T_B5,T_G5,T_E5,
    T_A5,T_C6,T_E6,T_C6, T_B5,T_A5,T_G5,T_E5,
    T_D5,T_E5,T_G5,T_REST, T_A5,T_REST,T_REST,T_REST,
};
const u8 s7_bass[16] = {
    T_A3,T_A3,T_E3,T_E3,T_G3,T_G3,T_D3,T_A3,
    T_A3,T_C3,T_E3,T_G3,T_A3,T_E3,T_D3,T_A3,
};

// Stage 8 — Void Sanctum: fractured intervals and deliberate vacuum.
const u8 s8_melody[64] = {
    T_C5,T_REST,T_E5,T_G5, T_REST,T_C6,T_B5,T_REST,
    T_A5,T_F5,T_REST,T_D5, T_E5,T_REST,T_G5,T_A5,
    T_C6,T_REST,T_D6,T_E6, T_REST,T_D6,T_C6,T_A5,
    T_G5,T_REST,T_E5,T_C5, T_REST,T_REST,T_REST,T_REST,
    T_D5,T_A5,T_REST,T_E5, T_B5,T_REST,T_F5,T_C6,
    T_REST,T_G5,T_D6,T_REST, T_A5,T_E6,T_REST,T_B5,
    T_C5,T_REST,T_FS5,T_C6, T_E5,T_REST,T_B5,T_D6,
    T_A5,T_F5,T_D5,T_C5, T_REST,T_REST,T_REST,T_REST,
};
const u8 s8_bass[16] = {
    T_C3,T_G3,T_A3,T_E3,T_C3,T_D3,T_G3,T_C3,
    T_D3,T_E3,T_F3,T_B3,T_C3,T_A3,T_G3,T_C3,
};
