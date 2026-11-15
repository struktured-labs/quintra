#pragma bank 6
// Mini-boss body animation. The five variants share the four-tile SPR_BOSS
// slot, so poses are streamed into it only when the wanted pose changes:
// two walk beats on a 16-frame cadence and an attack telegraph held for the
// last 12 ticks of the volley countdown (the existing white blink lands at 8).
// Purely visual: movement, volley timing, hitbox and OAM use are unchanged.

#include <gb/gb.h>

#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "render/tiles.h"

#define MINIBOSS_TELL_TICKS 12u

void miniboss_anim_tick(entity_t *e) BANKED {
    u8 timer = e->ai_data[1];
    u8 variant = e->ai_data[2];
    u8 pose = (timer != 0 && timer <= MINIBOSS_TELL_TICKS) ? 2
        : (u8)((entity_anim_counter >> 4) & 1);
    u8 key;
    if (variant > 4) variant = 0;
    // `vx` is unused by mini-boss bodies (boss_chase_tick steps through
    // enemy_try_step); it caches the resident pose as key + 1, and a fresh
    // spawn's zero forces the first upload without any new WRAM.
    key = (u8)(variant * 3u + pose + 1u);
    if ((u8)e->vx == key) return;
    e->vx = (i8)key;
    miniboss_pose_load((u8)(key - 1u));
}
