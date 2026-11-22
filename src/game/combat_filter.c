#pragma bank 23

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/hexa_boss.h"
#include "render/large_boss.h"

// Shot box of the current player shot (combat.c, combat_load_shot_box).
extern i16 shot_sx, shot_sy, shot_right, shot_bottom;

// Next slot >= start that the cutting player shot `i` may act on: an
// on-screen enemy or a hostile shot whose box overlaps (exact SHOT_MISSES),
// or the giant/Hexa body, whose own overlap test stays in combat.c.
// 0xFF when none remain. Kept as a small leaf so SDCC holds the walk in
// registers; see combat_scan_listed.
u8 combat_next_cut_candidate(u8 i, u8 start) BANKED {
    const entity_t *e = &entities[start];
    u8 j = start;
    for (; j < MAX_ENTITIES; ++j, ++e) {
        u8 fl = e->flags;
        i16 v;
        if (!(fl & EF_ACTIVE) || j == i) continue;
        if (e->type == ENT_ENEMY) {
            if (!(fl & EF_ON_SCREEN)) continue;
            if (j == large_boss_index
                || (hexa_boss_active && j == hexa_core_entity)) return j;
        } else if (e->type != ENT_PROJECTILE || (fl & EF_PLAYER_PROJ)) {
            continue;
        }
        v = e->x;
        if (shot_right <= v) continue;
        if ((i16)(v + (u8)(e->hitbox >> 4)) <= shot_sx) continue;
        v = e->y;
        if (shot_bottom <= v) continue;
        if ((i16)(v + (u8)(e->hitbox & 0x0F)) <= shot_sy) continue;
        return j;
    }
    return 0xFF;
}
