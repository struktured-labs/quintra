#pragma bank 11

#include <gb/gb.h>

#include "audio/music.h"
#include "audio/music_data.h"
#include "audio/music_score.h"

BANKREF(music_riftwild_score)
BANKREF_EXTERN(music_riftwild_score)

// The Unbound Road — Riftwild's long-form A-minor expedition score. Its
// opening A-C-E-C / B-G-A contour is the title oath heard in motion: the
// sparse menu call becomes a confident walking phrase, then opens into wind,
// horizon, ruins, and a final homeward restatement. This makes the overworld
// immediately part of Quintra's identity without looping the title screen.
static const u8 riftwild_melody[64] = {
    T_A5,T_HOLD,T_C6,T_HOLD, T_E6,T_HOLD,T_C6,T_HOLD,
    T_B5,T_HOLD,T_G5,T_HOLD, T_A5,T_HOLD,T_REST,T_REST,
    T_E5,T_A5,T_C6,T_E6, T_D6,T_C6,T_A5,T_G5,
    T_E5,T_G5,T_A5,T_C6, T_B5,T_G5,T_E5,T_REST,
    T_A5,T_HOLD,T_E6,T_D6, T_C6,T_A5,T_G5,T_E5,
    T_D5,T_E5,T_G5,T_A5, T_C6,T_B5,T_A5,T_REST,
    T_C6,T_HOLD,T_E6,T_HOLD, T_D6,T_C6,T_A5,T_REST,
    T_G5,T_A5,T_C6,T_B5, T_G5,T_E5,T_A5,T_REST,
};

static const u8 riftwild_bass[16] = {
    T_A3,T_A3,T_G3,T_G3, T_C3,T_C3,T_D3,T_A3,
    T_A3,T_E3,T_G3,T_D3, T_C3,T_G3,T_E3,T_A3,
};

static const u8 riftwild_development_melody[64] = {
    T_E5,T_HOLD,T_A5,T_C6, T_E6,T_D6,T_C6,T_A5,
    T_G5,T_HOLD,T_D6,T_C6, T_B5,T_G5,T_E5,T_REST,
    T_A5,T_C6,T_E6,T_HOLD, T_D6,T_C6,T_B5,T_G5,
    T_E5,T_G5,T_B5,T_D6, T_C6,T_A5,T_E5,T_REST,
    T_D5,T_A5,T_C6,T_D6, T_E6,T_C6,T_A5,T_G5,
    T_E5,T_D5,T_E5,T_G5, T_A5,T_C6,T_B5,T_REST,
    // Climactic, exact title-oath restatement. The denser marching mix below
    // turns the menu's lonely call into a horizon-sized answer.
    T_A5,T_REST,T_C6,T_REST, T_E6,T_REST,T_C6,T_REST,
    T_B5,T_REST,T_G5,T_REST, T_A5,T_HOLD,T_REST,T_REST,
};

static const u8 riftwild_development_bass[16] = {
    T_A3,T_C3,T_G3,T_E3, T_D3,T_A3,T_C3,T_G3,
    T_E3,T_G3,T_D3,T_A3, T_C3,T_D3,T_E3,T_A3,
};

static const u8 riftwild_form[MUSIC_FORM_SECTIONS] = {
    0,0,1,0, 2,1,3,0, 4,1,5,2, 6,4,7,3,
    0,4,1,5, 2,6,3,7, 4,5,2,6, 3,1,0,0,
};

static const music_variant_t riftwild_music = {
    riftwild_melody, riftwild_bass,
    // Hollow-organ wave, firmer lead, and a two-level processional drum
    // lattice give the road real epic weight while the form still opens
    // sparsely (the sequencer withholds drums for its first two sections).
    8, 0x80, 0x93, 0x20, 4, 0xD5, 1, 0x05AD, 0x2D, 0x99, 0x66,
};

// The Road Unremembered — the title oath survives, but its answer falls into
// E/F semitone tension and the bass refuses the Waking cadence. Lower lead,
// hollow wave, slower pulse and a broken drum lattice make Hollow Riftwild a
// separate place while keeping the game's central motif unmistakable.
static const u8 hollow_melody[64] = {
    T_A5,T_HOLD,T_C6,T_HOLD, T_E6,T_HOLD,T_C6,T_HOLD,
    T_F5,T_HOLD,T_E5,T_HOLD, T_D5,T_C5,T_C5,T_REST,
    T_E5,T_F5,T_A5,T_G5, T_E5,T_D5,T_C5,T_C5,
    T_F5,T_E5,T_C5,T_D5, T_C5,T_HOLD,T_REST,T_REST,
    T_C5,T_C5,T_E5,T_F5, T_E5,T_C5,T_D5,T_C5,
    T_F5,T_HOLD,T_D5,T_C5, T_D5,T_C5,T_E5,T_REST,
    T_C5,T_E5,T_F5,T_E5, T_D5,T_C5,T_C5,T_REST,
    T_F5,T_E5,T_D5,T_C5, T_D5,T_C5,T_REST,T_REST,
};

static const u8 hollow_bass[16] = {
    T_A3,T_A3,T_F3,T_E3, T_D3,T_C3,T_F3,T_E3,
    T_A3,T_F3,T_D3,T_E3, T_C3,T_F3,T_E3,T_A3,
};

static const u8 hollow_development_melody[64] = {
    T_E5,T_F5,T_E5,T_C5, T_D5,T_C5,T_C5,T_REST,
    T_F5,T_HOLD,T_A5,T_G5, T_E5,T_D5,T_C5,T_REST,
    T_C5,T_C5,T_F5,T_E5, T_D5,T_D5,T_C5,T_C5,
    T_E5,T_F5,T_A5,T_HOLD, T_G5,T_E5,T_D5,T_REST,
    T_C5,T_D5,T_F5,T_E5, T_C5,T_C5,T_D5,T_REST,
    T_F5,T_E5,T_D5,T_C5, T_D5,T_C5,T_E5,T_REST,
    T_A5,T_REST,T_C6,T_REST, T_E6,T_REST,T_C6,T_REST,
    T_F5,T_REST,T_E5,T_REST, T_D5,T_C5,T_C5,T_REST,
};

static const u8 hollow_development_bass[16] = {
    T_A3,T_F3,T_E3,T_D3, T_C3,T_F3,T_E3,T_A3,
    T_F3,T_D3,T_C3,T_E3, T_A3,T_F3,T_E3,T_A3,
};

static const u8 hollow_form[MUSIC_FORM_SECTIONS] = {
    0,0,2,1, 4,2,5,1, 6,3,7,5, 2,6,4,7,
    1,5,3,6, 0,7,2,4, 5,6,3,7, 2,1,0,0,
};

static const music_variant_t hollow_music = {
    hollow_melody, hollow_bass,
    10, 0xC0, 0x72, 0x40, 4, 0x91, 2, 0x05AB, 0x35, 0x91, 0x44,
};

void music_play_riftwild(void) BANKED {
    music_load_wave(riftwild_music.wave_shape);
    music_select_variant(&riftwild_music, riftwild_form,
        riftwild_development_melody, riftwild_development_bass,
        BANK(music_riftwild_score), BANK(music_riftwild_score),
        MUSIC_RIFTWILD);
}

void music_play_hollow_riftwild(void) BANKED {
    music_load_wave(hollow_music.wave_shape);
    music_select_variant(&hollow_music, hollow_form,
        hollow_development_melody, hollow_development_bass,
        BANK(music_riftwild_score), BANK(music_riftwild_score),
        MUSIC_HOLLOW_RIFTWILD);
}
