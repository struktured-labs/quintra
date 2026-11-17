// Attract-mode demo recordings, included only by src/game/intro.c (bank 22).
// Each demo: class id, stage warp (0xFF = stage 1 foyer), run seed (u16 LE,
// fed to run_init through loop_frame_counter), then (keys, frames) pairs
// ending with (0, 0). Playback is deterministic: same seed, same input.
#ifndef QUINTRA_GAME_ATTRACT_DEMO_DATA_H
#define QUINTRA_GAME_ATTRACT_DEMO_DATA_H

#define ATTRACT_DEMO_COUNT 1
#define ATTRACT_DEMO_FRAMES 1200u   // 20 s, then back to the title

static const u8 attract_demo0[] = {
    0, 0xFF, 0x34, 0x12,
    0x00, 30, 0x04, 40, 0x05, 20, 0x04, 10, 0x01, 30, 0x00, 10, 0x02, 40,
    0x00, 0
};

static const u8 * const attract_demos[ATTRACT_DEMO_COUNT] = { attract_demo0 };

#endif
