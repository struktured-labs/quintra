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

// Meta-progress (SRAM bank 1) — survives across runs. "Only knowledge
// persists" stays true for the RUN; these are the pilot's trophies.
u16  sram_meta_best(void);           // best score ever (0 on fresh cart)
u16  sram_meta_wins(void);           // total victorious runs
u16  sram_meta_runs(void);           // total runs ended (win or death)
u16  sram_meta_best_time(void);      // fastest WIN in seconds (0xFFFF = none)
// Record a run's end. Returns flag bits: 1 = new best score,
// 2 = new fastest win (only possible when won).
u8   sram_meta_record(u16 score, u8 won, u16 time_s);

#endif
