#include <gb/gb.h>

#include "audio/audio.h"
#include "audio/music.h"
#include "audio/sfx.h"

void audio_init(void) {
    NR52_REG = 0x80;   // sound on
    NR50_REG = 0x77;   // max master volume both channels
    NR51_REG = 0xFF;   // all channels to both outputs
}

void audio_tick(void) {
    sfx_tick();
    music_tick();
}
