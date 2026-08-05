#pragma bank 7
#include <gb/gb.h>

#include "audio/music_score.h"

BANKREF(music_boss_score)

// Each Colossus answers its stage motif with a separate 64-row combat form.
const u8 boss_melody[64] = {
    T_E5,T_E5,T_G5,T_E5, T_B5,T_A5,T_G5,T_A5,
    T_E5,T_E5,T_G5,T_E5, T_D6,T_B5,T_A5,T_G5,
    T_E5,T_G5,T_B5,T_E6, T_D6,T_B5,T_A5,T_G5,
    T_FS5,T_A5,T_D6,T_A5, T_B5,T_G5,T_FS5,T_E5,
    T_E5,T_G5,T_B5,T_D6, T_E6,T_D6,T_B5,T_G5,
    T_FS5,T_FS5,T_A5,T_B5, T_D6,T_B5,T_A5,T_FS5,
    T_E5,T_B5,T_E6,T_D6, T_B5,T_A5,T_G5,T_FS5,
    T_E5,T_G5,T_FS5,T_D5, T_E5,T_B5,T_E5,T_REST,
};
const u8 boss_bass[16] = {
    T_E3,T_E3,T_G3,T_G3,T_A3,T_A3,T_E3,T_B3,
    T_E3,T_G3,T_A3,T_B3,T_E3,T_D3,T_B3,T_E3,
};

const u8 boss2_melody[64] = {
    T_A5,T_A5,T_C6,T_A5, T_E6,T_D6,T_C6,T_B5,
    T_A5,T_A5,T_C6,T_A5, T_G5,T_A5,T_B5,T_C6,
    T_A5,T_C6,T_E6,T_A5, T_E6,T_D6,T_C6,T_B5,
    T_G5,T_B5,T_D6,T_G5, T_A5,T_E5,T_A5,T_REST,
    T_A5,T_C6,T_E6,T_C6, T_A5,T_G5,T_E5,T_G5,
    T_A5,T_B5,T_C6,T_D6, T_E6,T_C6,T_B5,T_A5,
    T_G5,T_G5,T_B5,T_D6, T_C6,T_B5,T_A5,T_G5,
    T_E5,T_A5,T_C6,T_B5, T_A5,T_E5,T_A5,T_REST,
};
const u8 boss2_bass[16] = {
    T_A3,T_A3,T_G3,T_G3,T_C3,T_C3,T_E3,T_A3,
    T_A3,T_C3,T_G3,T_E3,T_A3,T_G3,T_E3,T_A3,
};

const u8 boss3_melody[64] = {
    T_D5,T_D5,T_F5,T_A5, T_D6,T_A5,T_F5,T_E5,
    T_D5,T_F5,T_A5,T_C6, T_D6,T_C6,T_A5,T_F5,
    T_E5,T_G5,T_B5,T_D6, T_C6,T_B5,T_A5,T_G5,
    T_F5,T_E5,T_D5,T_C5, T_D5,T_REST,T_REST,T_REST,
    T_D5,T_A5,T_D6,T_C6, T_A5,T_F5,T_E5,T_D5,
    T_F5,T_A5,T_C6,T_D6, T_C6,T_A5,T_G5,T_F5,
    T_E5,T_G5,T_B5,T_D6, T_B5,T_G5,T_F5,T_E5,
    T_D5,T_F5,T_E5,T_C5, T_D5,T_A5,T_D5,T_REST,
};
const u8 boss3_bass[16] = {
    T_D3,T_D3,T_A3,T_A3,T_C3,T_C3,T_G3,T_D3,
    T_D3,T_A3,T_F3,T_C3,T_E3,T_G3,T_A3,T_D3,
};

const u8 boss4_melody[64] = {
    T_F5,T_A5,T_C6,T_A5, T_F5,T_E5,T_F5,T_G5,
    T_A5,T_C6,T_D6,T_C6, T_A5,T_G5,T_F5,T_E5,
    T_F5,T_F5,T_A5,T_C6, T_E6,T_D6,T_C6,T_A5,
    T_G5,T_F5,T_E5,T_D5, T_C5,T_REST,T_REST,T_REST,
    T_F5,T_C6,T_F5,T_E5, T_F5,T_A5,T_C6,T_D6,
    T_C6,T_A5,T_G5,T_F5, T_E5,T_F5,T_G5,T_A5,
    T_C6,T_E6,T_D6,T_C6, T_A5,T_G5,T_F5,T_E5,
    T_D5,T_F5,T_C6,T_A5, T_F5,T_C5,T_F5,T_REST,
};
const u8 boss4_bass[16] = {
    T_F3,T_F3,T_C3,T_C3,T_A3,T_A3,T_G3,T_F3,
    T_F3,T_C3,T_F3,T_A3,T_G3,T_E3,T_C3,T_F3,
};

const u8 boss5_melody[64] = {
    T_G5,T_B5,T_D6,T_B5, T_G5,T_A5,T_B5,T_D6,
    T_E6,T_D6,T_B5,T_A5, T_G5,T_E5,T_G5,T_A5,
    T_B5,T_D6,T_E6,T_D6, T_B5,T_A5,T_G5,T_E5,
    T_D5,T_E5,T_G5,T_B5, T_G5,T_REST,T_REST,T_REST,
    T_G5,T_D6,T_B5,T_G5, T_A5,T_B5,T_D6,T_E6,
    T_D6,T_B5,T_A5,T_G5, T_E5,T_G5,T_A5,T_B5,
    T_C6,T_E6,T_D6,T_B5, T_A5,T_G5,T_E5,T_D5,
    T_G5,T_A5,T_B5,T_D6, T_B5,T_G5,T_G5,T_REST,
};
const u8 boss5_bass[16] = {
    T_G3,T_G3,T_D3,T_D3,T_E3,T_E3,T_C3,T_G3,
    T_G3,T_D3,T_E3,T_C3,T_G3,T_A3,T_D3,T_G3,
};

const u8 boss6_melody[64] = {
    T_C5,T_C5,T_E5,T_G5, T_C6,T_G5,T_E5,T_D5,
    T_C5,T_E5,T_G5,T_C6, T_E6,T_D6,T_C6,T_B5,
    T_A5,T_C6,T_E6,T_C6, T_A5,T_G5,T_E5,T_D5,
    T_C5,T_D5,T_E5,T_G5, T_C6,T_REST,T_REST,T_REST,
    T_C5,T_G5,T_C6,T_E6, T_D6,T_C6,T_B5,T_G5,
    T_A5,T_C6,T_E6,T_D6, T_C6,T_A5,T_G5,T_E5,
    T_F5,T_A5,T_C6,T_A5, T_F5,T_E5,T_D5,T_C5,
    T_E5,T_G5,T_C6,T_D6, T_C6,T_G5,T_C5,T_REST,
};
const u8 boss6_bass[16] = {
    T_C3,T_C3,T_G3,T_G3,T_A3,T_A3,T_F3,T_C3,
    T_C3,T_G3,T_A3,T_E3,T_F3,T_A3,T_G3,T_C3,
};

const u8 boss7_melody[64] = {
    T_A5,T_G5,T_A5,T_C6, T_E6,T_C6,T_A5,T_G5,
    T_F5,T_E5,T_F5,T_A5, T_D6,T_A5,T_F5,T_E5,
    T_A5,T_C6,T_E6,T_D6, T_C6,T_B5,T_A5,T_G5,
    T_E5,T_D5,T_E5,T_G5, T_A5,T_REST,T_REST,T_REST,
    T_A5,T_E6,T_C6,T_A5, T_G5,T_E5,T_D5,T_E5,
    T_F5,T_A5,T_D6,T_C6, T_A5,T_F5,T_E5,T_D5,
    T_E5,T_G5,T_B5,T_D6, T_C6,T_A5,T_G5,T_E5,
    T_A5,T_C6,T_B5,T_G5, T_A5,T_E5,T_A5,T_REST,
};
const u8 boss7_bass[16] = {
    T_A3,T_A3,T_E3,T_E3,T_F3,T_F3,T_G3,T_A3,
    T_A3,T_E3,T_F3,T_C3,T_E3,T_G3,T_D3,T_A3,
};

const u8 boss8_melody[64] = {
    T_E5,T_G5,T_B5,T_E6, T_B5,T_G5,T_E5,T_FS5,
    T_A5,T_C6,T_E6,T_C6, T_A5,T_G5,T_FS5,T_E5,
    T_D5,T_FS5,T_A5,T_D6, T_A5,T_FS5,T_E5,T_D5,
    T_E5,T_G5,T_B5,T_E6, T_E5,T_REST,T_REST,T_REST,
    T_E5,T_B5,T_E6,T_B5, T_G5,T_FS5,T_E5,T_D5,
    T_FS5,T_A5,T_D6,T_A5, T_FS5,T_E5,T_D5,T_FS5,
    T_A5,T_C6,T_E6,T_D6, T_C6,T_A5,T_G5,T_FS5,
    T_E5,T_G5,T_B5,T_D6, T_B5,T_FS5,T_E5,T_REST,
};
const u8 boss8_bass[16] = {
    T_E3,T_E3,T_B3,T_B3,T_A3,T_A3,T_D3,T_E3,
    T_E3,T_B3,T_D3,T_A3,T_E3,T_G3,T_D3,T_E3,
};

const u8 boss9_melody[64] = {
    T_C5,T_E5,T_G5,T_B5, T_D6,T_B5,T_G5,T_E5,
    T_F5,T_A5,T_C6,T_E6, T_D6,T_C6,T_A5,T_F5,
    T_E5,T_G5,T_B5,T_D6, T_E6,T_D6,T_B5,T_G5,
    T_F5,T_E5,T_D5,T_C5, T_C6,T_REST,T_REST,T_REST,
    T_C5,T_G5,T_B5,T_D6, T_E6,T_D6,T_B5,T_G5,
    T_F5,T_A5,T_C6,T_E6, T_D6,T_B5,T_G5,T_E5,
    T_D5,T_FS5,T_A5,T_C6, T_B5,T_G5,T_E5,T_D5,
    T_C5,T_E5,T_G5,T_B5, T_D6,T_C6,T_C5,T_REST,
};
const u8 boss9_bass[16] = {
    T_C3,T_C3,T_G3,T_G3,T_A3,T_A3,T_D3,T_C3,
    T_C3,T_G3,T_F3,T_A3,T_D3,T_E3,T_G3,T_C3,
};
