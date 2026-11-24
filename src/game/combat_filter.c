#pragma bank 23

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/hexa_boss.h"
#include "render/large_boss.h"

// Shot box of the current player shot (combat.c, combat_load_shot_box).
extern i16 shot_sx, shot_sy, shot_right, shot_bottom;
extern u8 shot_sx_b, shot_sy_b, shot_right_b, shot_bottom_b, shot_box_wide;

// A resolved stroke leaves this hurtbox in WRAM. Discard it at the end of
// combat_resolve so a later overlap cannot chip a body with an unplaced
// shot (impact at 0,0, damage 0 becoming 1). right/bottom at I16_MIN makes
// (right <= x) true for every i16 body, including those that straddle 0.
// Lives in this bank so the call from combat_resolve is a real side effect.
void combat_reset_shot_box(void) BANKED {
    shot_sx = shot_sy = 0;
    shot_right = shot_bottom = (i16)-0x8000;
    shot_sx_b = shot_sy_b = 0;
    shot_right_b = shot_bottom_b = 0;
    shot_box_wide = 0;
}

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

extern u8 shot_targets[MAX_ENTITIES];
extern u8 shot_list_n;

// Next index k into the ordinary-bullet target list (combat.c,
// combat_collect_targets) whose enemy is active and overlaps the shot box
// (exact SHOT_MISSES), or that is the giant/Hexa body. 0xFF when none
// remain. The spilled pair test in combat_resolve_ordinary cost ~800
// clocks per missed pair; this leaf keeps the walk in registers.
u8 combat_next_ordinary_hit(u8 k) BANKED {
    for (; k < shot_list_n; ++k) {
        u8 j = shot_targets[k];
        const entity_t *e = &entities[j];
        i16 v;
        if (!(e->flags & EF_ACTIVE)) continue;
        if ((hexa_boss_active && j == hexa_core_entity)
            || j == large_boss_index) return k;
        v = e->x;
        if (shot_right <= v) continue;
        if ((i16)(v + (u8)(e->hitbox >> 4)) <= shot_sx) continue;
        v = e->y;
        if (shot_bottom <= v) continue;
        if ((i16)(v + (u8)(e->hitbox & 0x0F)) <= shot_sy) continue;
        return k;
    }
    return 0xFF;
}
