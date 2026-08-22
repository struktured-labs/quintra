#ifndef QUINTRA_GAME_WAYGEAR_H
#define QUINTRA_GAME_WAYGEAR_H

#include <gb/gb.h>
#include "core/types.h"
#include "game/player.h"
#include "render/tiles.h"

enum {
    WAYGEAR_GLOVE = 0,
    WAYGEAR_RAFT,
    WAYGEAR_HOOK,
    WAYGEAR_COUNT,
};

#define WAYGEAR_BIT(g) ((u8)(1u << (g)))

// Hero nature is the primary key; one equipped permanent implement can
// substitute for the three traditional traversal families.
#define WAYGEAR_TILE_PASSABLE(t) ( \
    ((t) == BGT_GATE_BOULDER \
        && (player.class_id == 1 \
            || player.waygear_equipped == WAYGEAR_GLOVE)) \
    || ((t) == BGT_GATE_WATER \
        && (player.class_id == 3 \
            || player.waygear_equipped == WAYGEAR_RAFT)) \
    || ((t) == BGT_GATE_CHASM \
        && (player.class_id == 2 \
            || player.waygear_equipped == WAYGEAR_HOOK)) \
    || ((t) == BGT_GATE_THORNS && player.class_id == 0) \
    || ((t) == BGT_GATE_VENT && player.class_id == 4))

u8 waygear_grant(u8 gear) BANKED;
void waygear_prepare_world_field(void) BANKED;

#endif
