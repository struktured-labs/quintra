// Private state shared by lock_room.c (27), lock_room_view.c (23),
// lock_room_draw.c (31). Not for other modules.
#ifndef GAME_LOCK_ROOM_INT_H
#define GAME_LOCK_ROOM_INT_H
#include "core/types.h"
extern u8 lk_queue, lk_flash, lk_flash_t, lk_cue, lk_epoch, lk_dirty;
extern u8 lk_on_reset, lk_on_flip, lk_on_ped, lk_on_lure, lk_on_goal, lk_touch;
extern u8 lk_inside, lk_coin_given;
extern i16 lk_safe_x, lk_safe_y;
void lk_reg_write(u8 r) BANKED;
void lk_view_step(void) BANKED;
void lk_restore(void) BANKED;
void lk_solve(void) BANKED;
void lk_guard_step(void) BANKED;
#endif
