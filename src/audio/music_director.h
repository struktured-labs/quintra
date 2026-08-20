#ifndef QUINTRA_AUDIO_MUSIC_DIRECTOR_H
#define QUINTRA_AUDIO_MUSIC_DIRECTOR_H

#include <gb/gb.h>

// Reconcile adaptive music targets from live room state.
void music_director_refresh(void) BANKED;

extern u8 music_mix_lead_envelope;
extern u8 music_mix_harmony_mask;
extern u8 music_mix_harmony_envelope;
extern u8 music_mix_wave_level;
void music_adaptive_prepare_section(u8 base_envelope, u8 base_wave,
    u8 form, u8 boss) BANKED;

#endif
