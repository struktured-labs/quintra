#pragma bank 6
#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/player.h"
#include "content.h"

// The Folding Star is deliberately isolated from the generic AI dispatcher:
// it has its own two-phase damage contract and four-echo movement language.
// Keeping it with the other specialist movement modules frees the crowded
// bank-2 dispatcher for shared behavior and makes the timing lesson easier
// to evolve without entangling unrelated enemies.
void fold_star_update(entity_t *e, const enemy_def_t *def) BANKED {
    // state 0 = contracted and vulnerable; state 1 = expanded/untouchable.
    // ai_data[1] is the phase clock, ai_data[2] selects the odd 7/13/9 beat,
    // ai_data[3] rotates the diagonal sequence.
    static const u8 beat[3] = { 7, 13, 9 };
    if (e->ai_data[1] == 0) {
        if (e->state == 0) {
            e->state = 1;
            e->ai_data[1] = def->ai_p0;
            e->palette = 0x00; // pale and diffuse while expanded
        } else {
            e->state = 0;
            e->ai_data[1] = def->ai_p1;
            e->palette = 0x05; // bright core announces damage window
            sfx_play(SFX_WEAK);
        }
    }
    e->ai_data[1]--;

    if (e->state == 0) {
        // Contract toward the player: a slow, readable diagonal hunt.
        if ((e->ai_data[1] & 3) == 0) {
            i16 ex = FIX8_TO_INT(e->x), ey = FIX8_TO_INT(e->y);
            i8 dx = (player.x > ex) ? 1 : -1;
            i8 dy = (player.y > ey) ? 1 : -1;
            enemy_try_step(e, dx, dy);
        }
        return;
    }

    // Expanded: shed four short-lived replicas on diagonal rays. They are FX,
    // not extra hostiles, so room-clear accounting and the 32-entity budget
    // remain stable. The core itself steps through the same diagonal sequence.
    if ((e->ai_data[1] % beat[e->ai_data[2] % 3]) == 0) {
        i16 x = FIX8_TO_INT(e->x), y = FIX8_TO_INT(e->y);
        u8 d = (u8)(6 + ((e->ai_data[3] & 3) << 1));
        fx_spawn(e->sprite_tile, 0x05, x - d, y - d, 16);
        fx_spawn(e->sprite_tile, 0x05, x + d, y - d, 16);
        fx_spawn(e->sprite_tile, 0x05, x - d, y + d, 16);
        fx_spawn(e->sprite_tile, 0x05, x + d, y + d, 16);
        e->ai_data[2] = (u8)((e->ai_data[2] + 1) % 3);
        e->ai_data[3]++;
        enemy_try_step(e, dir8_dx[(u8)((e->ai_data[3] * 2 + 1) & 7)],
                          dir8_dy[(u8)((e->ai_data[3] * 2 + 1) & 7)]);
    }
}
