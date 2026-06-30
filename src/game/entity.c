#include <gb/gb.h>
#include <string.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/enemy_ai.h"
#include "game/pickup.h"

entity_t entities[MAX_ENTITIES];

// 8-direction deltas: 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW
const i8 dir8_dx[8] = {  0, +1, +1, +1,  0, -1, -1, -1 };
const i8 dir8_dy[8] = { -1, -1,  0, +1, +1, +1,  0, -1 };

static u8 hitbox_w(const entity_t *e) { return (e->hitbox >> 4) & 0x0F; }
static u8 hitbox_h(const entity_t *e) { return  e->hitbox       & 0x0F; }

void entity_init_all(void) {
    u8 i;
    memset(entities, 0, sizeof(entities));
    // Park entity sprites off-screen (slots 4..35)
    for (i = 4; i < 4 + MAX_ENTITIES; ++i) {
        move_sprite(i, 0, 0);
    }
}

u8 entity_spawn(u8 type) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) {
            memset(&entities[i], 0, sizeof(entity_t));
            entities[i].type    = type;
            entities[i].flags   = EF_ACTIVE | EF_ALIVE;
            // OAM slots 0-3 reserved for player metasprite; entities use 4+
            entities[i].oam_slot = (u8)(4 + i);
            return i;
        }
    }
    return 0xFF;
}

void entity_kill(u8 idx) {
    if (idx >= MAX_ENTITIES) return;
    entities[idx].flags &= (u8)~(EF_ACTIVE | EF_ALIVE);
    entities[idx].type   = ENT_NONE;
    move_sprite(entities[idx].oam_slot, 0, 0);   // hide
}

u8 aabb_overlap_ee(const entity_t *a, const entity_t *b) {
    i16 ax = FIX8_TO_INT(a->x), ay = FIX8_TO_INT(a->y);
    i16 bx = FIX8_TO_INT(b->x), by = FIX8_TO_INT(b->y);
    u8  aw = hitbox_w(a),       ah = hitbox_h(a);
    u8  bw = hitbox_w(b),       bh = hitbox_h(b);
    if (ax + (i16)aw <= bx) return 0;
    if (bx + (i16)bw <= ax) return 0;
    if (ay + (i16)ah <= by) return 0;
    if (by + (i16)bh <= ay) return 0;
    return 1;
}

u8 aabb_overlap_player(const entity_t *e) {
    i16 ex = FIX8_TO_INT(e->x), ey = FIX8_TO_INT(e->y);
    i16 px = (i16)player.x, py = (i16)player.y;     // player is i16 pixels
    u8  ew = hitbox_w(e), eh = hitbox_h(e);
    px += 1; py += 1;
    if (px + 6 <= ex) return 0;
    if (ex + (i16)ew <= px) return 0;
    if (py + 6 <= ey) return 0;
    if (ey + (i16)eh <= py) return 0;
    return 1;
}

void entity_update_all(u8 keys, u8 pressed) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        switch (entities[i].type) {
            case ENT_PROJECTILE: projectile_update(&entities[i], i); break;
            case ENT_ENEMY:      enemy_update(&entities[i], i);      break;
            case ENT_PICKUP:     pickup_update(&entities[i], i);     break;
            default: break;
        }
        keys; pressed; // not used by current entity types
    }
}

void entity_draw_all(void) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) {
            // Already hidden by entity_kill — nothing to do.
            continue;
        }
        set_sprite_tile(entities[i].oam_slot, entities[i].sprite_tile);
        set_sprite_prop(entities[i].oam_slot, entities[i].palette);
        move_sprite(entities[i].oam_slot,
            (u8)(FIX8_TO_INT(entities[i].x) + 8),
            (u8)(FIX8_TO_INT(entities[i].y) + 16));
    }
}
