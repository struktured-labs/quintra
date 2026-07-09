// Battery-backed suspend save (SRAM bank 0). One slot: the current run.
// Saved on every room entry, cleared on death/victory/new-run — so quitting
// mid-run resumes at the current room, but permadeath still means death.
#ifndef QUINTRA_GAME_SRAM_H
#define QUINTRA_GAME_SRAM_H

#include "core/types.h"

u8   sram_run_valid(void);   // 1 = a resumable run is stored
void sram_save_run(void);    // snapshot run_state + player
u8   sram_load_run(void);    // restore; 1 = ok, 0 = invalid/corrupt
void sram_clear_run(void);   // invalidate (death / victory / new run)

#endif
