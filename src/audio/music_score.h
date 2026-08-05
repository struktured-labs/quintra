#ifndef QUINTRA_AUDIO_MUSIC_SCORE_H
#define QUINTRA_AUDIO_MUSIC_SCORE_H

#include <gb/gb.h>
#include "core/types.h"
#include "audio/music.h"

// Compact score symbols. Runtime expands one byte to the hardware frequency;
// the old u16-per-note representation spent more ROM on repeated register
// values than on composition. One shared vocabulary lets all eighteen long
// arrangements fit the original 128 KiB cartridge with bank headroom intact.
enum {
    T_REST = 0,
    T_C3, T_D3, T_E3, T_F3, T_G3, T_A3, T_B3,
    T_C5, T_D5, T_E5, T_F5, T_FS5, T_G5, T_A5, T_B5,
    T_C6, T_D6, T_E6,
    T_COUNT
};

BANKREF_EXTERN(music_stage_score)
BANKREF_EXTERN(music_boss_score)

extern const u8 melody[64];
extern const u8 bassline[16];
extern const u8 s1_melody[64];
extern const u8 s1_bass[16];
extern const u8 s2_melody[64];
extern const u8 s2_bass[16];
extern const u8 s3_melody[64];
extern const u8 s3_bass[16];
extern const u8 s4_melody[64];
extern const u8 s4_bass[16];
extern const u8 s5_melody[64];
extern const u8 s5_bass[16];
extern const u8 s6_melody[64];
extern const u8 s6_bass[16];
extern const u8 s7_melody[64];
extern const u8 s7_bass[16];
extern const u8 s8_melody[64];
extern const u8 s8_bass[16];

extern const u8 boss_melody[64];
extern const u8 boss_bass[16];
extern const u8 boss2_melody[64];
extern const u8 boss2_bass[16];
extern const u8 boss3_melody[64];
extern const u8 boss3_bass[16];
extern const u8 boss4_melody[64];
extern const u8 boss4_bass[16];
extern const u8 boss5_melody[64];
extern const u8 boss5_bass[16];
extern const u8 boss6_melody[64];
extern const u8 boss6_bass[16];
extern const u8 boss7_melody[64];
extern const u8 boss7_bass[16];
extern const u8 boss8_melody[64];
extern const u8 boss8_bass[16];
extern const u8 boss9_melody[64];
extern const u8 boss9_bass[16];

#endif
