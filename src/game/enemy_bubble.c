#pragma bank 26

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/enemy_bubble.h"
#include "game/entity.h"
#include "game/player.h"
#include "render/tiles.h"

/* GPT Image 2.6 Sunburst, quantized to 8x8 2bpp. Placeholder skull is
   swapped for the chosen sheet tile once the generation pass finishes. */
const u8 sprite_enemy_bubble[16] = {
    /* GPT Image 2.6 Sunburst, classic front skull (sheet tile skull_a). */
    0x3C, 0x00, 0x7E, 0x30, 0x7E, 0x20, 0xDB, 0x00,
    0xDB, 0x00, 0x7E, 0x00, 0x3C, 0x00, 0x24, 0x00
};

void tiles_load_bubble_sprite(void) BANKED {
    /* Shadow Keep and Void Sanctum never spawn Mire Spore, so their
       resident slot 78 can carry the Bubble without a new OBJ tile. */
    set_sprite_data(SPR_ENEMY_BUBBLE, 1, sprite_enemy_bubble);
}

/* Zelda 1 Bubble: diagonal drift, bounce on the blocked axis, flash. */
void bubble_tick(entity_t *e) BANKED {
    u8 dir = e->state & 0x07;
    i8 dx, dy;
    u8 immortal = (e->ai_data[2] == ENEMY_AUX_BUBBLE_IMMORTAL);

    /* Killable: bone / violet. Unkillable: red / violet, faster flash. */
    if (immortal)
        e->palette = (entity_anim_counter & 8) ? 4 : 6;
    else
        e->palette = (entity_anim_counter & 16) ? 0 : 6;

    /* Keep a diagonal heading; spawn should already have chosen one. */
    if (!(dir & 1)) dir = (u8)(dir + 1);
    dx = dir8_dx[dir];
    dy = dir8_dy[dir];
    if ((entity_anim_counter & 1) == 0) return;
    if (enemy_try_step(e, dx, dy)) {
        e->state = dir;
        return;
    }
    if (dx && enemy_try_step(e, (i8)-dx, dy)) {
        e->state = (u8)((dir + 6) & 7);
        return;
    }
    if (dy && enemy_try_step(e, dx, (i8)-dy)) {
        e->state = (u8)((dir + 2) & 7);
        return;
    }
    if (enemy_try_step(e, (i8)-dx, (i8)-dy))
        e->state = (u8)((dir + 4) & 7);
    else
        e->state = dir;
}

u8 bubble_reject_hit(u8 shot_idx, u8 enemy_idx) BANKED {
    entity_t *shot;
    entity_t *e;
    if (shot_idx >= MAX_ENTITIES || enemy_idx >= MAX_ENTITIES) return 0;
    e = &entities[enemy_idx];
    if (e->ai_data[2] != ENEMY_AUX_BUBBLE_IMMORTAL) return 0;
    shot = &entities[shot_idx];
    /* Deflect: reverse the shot and step it out of the body so it cannot
       immediately re-collide. Damage stays 0. */
    shot->vx = (i8)(-shot->vx);
    shot->vy = (i8)(-shot->vy);
    if (shot->vx) shot->x = (ppos_t)(shot->x + shot->vx);
    if (shot->vy) shot->y = (ppos_t)(shot->y + shot->vy);
    if (shot->vx) shot->x = (ppos_t)(shot->x + shot->vx);
    if (shot->vy) shot->y = (ppos_t)(shot->y + shot->vy);
    e->ai_data[7] = 6;
    fx_spawn(SPR_FX_IMPACT, 0,
        FIX8_TO_INT(shot->x), FIX8_TO_INT(shot->y), 6);
    sfx_play(SFX_TICK);
    return 1;
}
