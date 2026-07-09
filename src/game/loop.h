#ifndef QUINTRA_GAME_LOOP_H
#define QUINTRA_GAME_LOOP_H

#include "core/types.h"
#include "game/screen.h"

extern screen_id_t loop_current_screen;
extern u16         loop_frame_counter;

// Real 60Hz vblank count from a VBL ISR. The room loop overruns one
// vblank under combat load (~33 loop iterations/sec, measured — and
// pre-dating banking), so loop counts are NOT wall time; this is.
// Consumers drain it (e.g. run clock: subtract 60 per counted second).
extern volatile u8 g_vbl_ticks;

void loop_init(screen_id_t start);
void loop_run(void);

#endif
