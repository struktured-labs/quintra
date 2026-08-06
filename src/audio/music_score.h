#ifndef QUINTRA_AUDIO_MUSIC_SCORE_H
#define QUINTRA_AUDIO_MUSIC_SCORE_H

#include <gb/gb.h>
#include "core/types.h"
#include "audio/music.h"

// Compact score symbols. Runtime expands one byte to the hardware frequency;
// the old u16-per-note representation spent more ROM on repeated register
// values than on composition. Each gameplay score supplies eight authored
// 16-row sections and a 32-section form.
#define MUSIC_FORM_SECTIONS 32
enum {
    T_REST = 0,
    // Sustain the currently sounding lead without retriggering its envelope.
    // Authored ties give the score real note lengths instead of making every
    // row the same clipped attack. Bass notes already sustain for four rows.
    T_HOLD,
    // Chromatic bass and lead ranges let every dungeon own a real key and
    // mode instead of forcing eighteen scores through the C-major pitch set.
    T_C3, T_CS3, T_D3, T_DS3, T_E3, T_F3,
    T_FS3, T_G3, T_GS3, T_A3, T_AS3, T_B3,
    T_C5, T_CS5, T_D5, T_DS5, T_E5, T_F5,
    T_FS5, T_G5, T_GS5, T_A5, T_AS5, T_B5,
    T_C6, T_CS6, T_D6, T_DS6, T_E6,
    T_COUNT
};

BANKREF_EXTERN(music_stage_score)
BANKREF_EXTERN(music_boss_score)
BANKREF_EXTERN(music_development_score)

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
extern const u8 stage_development_melody[MUSIC_STAGE_COUNT][64];
extern const u8 stage_development_bass[MUSIC_STAGE_COUNT][16];
extern const u8 boss_development_melody[MUSIC_STAGE_COUNT][64];
extern const u8 boss_development_bass[MUSIC_STAGE_COUNT][16];
extern const u8 stage_forms[MUSIC_STAGE_COUNT][MUSIC_FORM_SECTIONS];
extern const u8 boss_forms[MUSIC_STAGE_COUNT][MUSIC_FORM_SECTIONS];
extern const u8 title_melody[32];
extern const u8 title_bass[8];
extern const u8 victory_melody[32];
extern const u8 gameover_melody[32];

#endif
