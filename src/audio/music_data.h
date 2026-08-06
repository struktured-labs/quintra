#ifndef QUINTRA_AUDIO_MUSIC_DATA_H
#define QUINTRA_AUDIO_MUSIC_DATA_H

#include <gb/gb.h>
#include "core/types.h"

// Cold track metadata lives in bank 3. The sequencer copies one selection
// into home-bank state when music changes, so per-row playback never pays a
// bank call for mode, groove, or articulation data.
typedef struct {
    const u8 *melody;
    const u8 *bass;
    u8 tempo;
    u8 duty;
    u8 envelope;
    u8 wave;
    u8 wave_shape;
    u8 accent;
    u8 swing;
    u16 scale;
    u8 drum_timbre;
    u8 drum_strong;
    u8 drum_soft;
} music_variant_t;

void music_read_variant(u8 stage, u8 boss, music_variant_t *out) BANKED;
void music_load_wave(u8 shape) BANKED;
void music_prepare_harmony(u16 scale, u8 *out) BANKED;

#endif
