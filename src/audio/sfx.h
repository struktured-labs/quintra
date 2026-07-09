// SFX driver — one-shot register-write effects per cowir-sfx's designs.
// Channel budget: CH1 (pulse+sweep) + CH4 (noise) belong to SFX;
// CH2 + CH3 belong to the music sequencer.
#ifndef QUINTRA_AUDIO_SFX_H
#define QUINTRA_AUDIO_SFX_H

#include "core/types.h"

enum {
    SFX_FIRE = 0,     // player shot: thin fast zap
    SFX_HIT,          // enemy takes damage: dry crunch
    SFX_DEATH,        // enemy dies: metallic 7-bit buzz falling apart
    SFX_COIN,         // B5 -> E6 two-note classic
    SFX_HEART,        // 660 -> 880 softer rise
    SFX_DOOR,         // rising whoosh
    SFX_ROAR,         // boss: low 75%-duty growl + slow noise
    SFX_HURT,         // player hurt: harsh 12.5%-duty snap
    SFX_CLEAR,        // room cleared: G5 -> B5 -> E6 rising arpeggio
    SFX_LOWHP,        // danger pulse: single soft high blip
};

void sfx_play(u8 id);
void sfx_tick(void);      // per-frame: second notes / mid-sound bumps

#endif
