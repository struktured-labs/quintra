#include <gb/gb.h>

#include "audio/audio.h"
#include "audio/music.h"
#include "audio/sfx.h"
#include "game/loop.h"

static u8 audio_vbl_epoch;

void audio_init(void) {
    NR52_REG = 0x80;   // sound on
    NR50_REG = 0x77;   // max master volume both channels
    NR51_REG = 0xFF;   // all channels to both outputs
    audio_vbl_epoch = g_vbl_epoch;
}

void audio_tick(void) {
    u8 elapsed = (u8)(g_vbl_epoch - audio_vbl_epoch);
    audio_vbl_epoch = g_vbl_epoch;
    // Gameplay occasionally spans two VBlanks in projectile-heavy rooms.
    // Advance envelope ownership and the sequencer once per hardware frame,
    // not once per completed simulation loop, so combat cannot drag pitch
    // phrasing and minute-scale forms 15-20% below their authored tempo.
    while (elapsed--) {
        sfx_tick();
        music_tick();
    }
}
