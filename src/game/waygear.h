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
    WAYGEAR_WORLDGLASS,
    WAYGEAR_COUNT,
};

// The first three discoveries also unlock Will tiers.
#define WAYGEAR_EQUIP_COUNT 3

#define WAYGEAR_BIT(g) ((u8)(1u << (g)))

// Innate abilities and every owned implement remain active together.
#define WAYGEAR_TILE_PASSABLE(t) ( \
    ((t) == BGT_GATE_BOULDER \
        && (player.class_id == 1 \
            || (player.waygear_owned & WAYGEAR_BIT(WAYGEAR_GLOVE)))) \
    || (((t) == BGT_GATE_WATER || (t) == BGT_WILD_WATER) \
        && (player.class_id == 3 \
            || (player.waygear_owned & WAYGEAR_BIT(WAYGEAR_RAFT)))) \
    || (((t) == BGT_GATE_CHASM || (t) == BGT_WILD_HOLE) \
        && (player.class_id == 2 \
            || (player.waygear_owned & WAYGEAR_BIT(WAYGEAR_HOOK)))) \
    || ((t) == BGT_GATE_THORNS && player.class_id == 0) \
    || ((t) == BGT_GATE_VENT && player.class_id == 4))

u8 waygear_grant(u8 gear) BANKED;
void waygear_prepare_world_field(void) BANKED;

#endif
