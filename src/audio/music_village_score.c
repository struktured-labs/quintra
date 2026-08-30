#pragma bank 3

#include <gb/gb.h>

#include "audio/music.h"
#include "audio/music_data.h"
#include "audio/music_score.h"

BANKREF(music_village_score)
BANKREF_EXTERN(music_village_score)

// Hearthlight Common — an 85-second G-major village form. Four daylight
// ideas (square, market, hearth, road) develop into bell, dance, dusk, and
// homecoming sections. It deliberately shares no stage/boss score pointer:
// a village is an audible rest between regions, not the next dungeon foyer.
static const u8 village_melody[64] = {
    T_G5,T_HOLD,T_B5,T_D6, T_HOLD,T_B5,T_A5,T_G5,
    T_E5,T_HOLD,T_G5,T_A5, T_B5,T_A5,T_G5,T_REST,
    T_D5,T_G5,T_A5,T_B5, T_D6,T_HOLD,T_B5,T_G5,
    T_A5,T_B5,T_D6,T_E6, T_D6,T_B5,T_A5,T_REST,
    T_E5,T_HOLD,T_G5,T_B5, T_A5,T_HOLD,T_FS5,T_E5,
    T_D5,T_G5,T_HOLD,T_B5, T_A5,T_G5,T_D5,T_REST,
    T_G5,T_B5,T_D6,T_G5, T_E6,T_D6,T_B5,T_A5,
    T_G5,T_A5,T_B5,T_D6, T_B5,T_A5,T_G5,T_REST,
};

static const u8 village_bass[16] = {
    T_G3,T_C3,T_E3,T_D3, T_G3,T_D3,T_E3,T_C3,
    T_E3,T_B3,T_C3,T_D3, T_G3,T_E3,T_C3,T_D3,
};

static const u8 village_development_melody[64] = {
    T_B5,T_HOLD,T_D6,T_E6, T_D6,T_B5,T_G5,T_REST,
    T_A5,T_HOLD,T_C6,T_B5, T_G5,T_E5,T_D5,T_REST,
    T_G5,T_A5,T_B5,T_D6, T_E6,T_D6,T_B5,T_G5,
    T_E5,T_G5,T_B5,T_A5, T_G5,T_FS5,T_E5,T_REST,
    T_D6,T_HOLD,T_B5,T_G5, T_E5,T_HOLD,T_D5,T_REST,
    T_C5,T_E5,T_G5,T_B5, T_A5,T_G5,T_D5,T_REST,
    T_E5,T_HOLD,T_G5,T_A5, T_B5,T_HOLD,T_D6,T_REST,
    T_E6,T_D6,T_B5,T_A5, T_G5,T_E5,T_D5,T_REST,
};

static const u8 village_development_bass[16] = {
    T_G3,T_E3,T_C3,T_D3, T_G3,T_C3,T_E3,T_D3,
    T_B3,T_E3,T_C3,T_D3, T_C3,T_A3,T_D3,T_G3,
};

static const u8 village_form[MUSIC_FORM_SECTIONS] = {
    0,0,1,0, 2,1,3,0, 4,1,5,2, 6,4,7,3,
    0,4,1,5, 2,6,3,7, 4,5,2,6, 3,1,0,0,
};

static const music_variant_t village_music = {
    village_melody, village_bass,
    10, 0x80, 0x63, 0x40, 1, 0x11, 0, 0x0AD5, 0x25, 0x11, 0x44,
};

void music_play_village(void) BANKED {
    music_load_wave(village_music.wave_shape);
    music_select_variant(&village_music, village_form,
        village_development_melody, village_development_bass,
        BANK(music_village_score), BANK(music_village_score), MUSIC_VILLAGE);
}
