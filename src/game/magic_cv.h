#ifndef QUINTRA_MAGIC_CV_H
#define QUINTRA_MAGIC_CV_H

#include <gb/gb.h>
#include "core/types.h"

/* Bank-23 Convergence tick/reset + bank-31 table accessors. */
extern u8 magic_cv_busy;
void magic_convergence_tick(void) BANKED;
void magic_convergence_reset(void) BANKED;
u16  magic_cv_reach_at(u8 lv) BANKED;
u16  magic_cv_dmg_at(u8 lv) BANKED;
u8   magic_cv_pal_at(u8 c) BANKED;

#endif
