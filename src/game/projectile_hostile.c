#pragma bank 16
// Hostile bullet motion lives outside bank 3. That bank already holds the
// player-shot resolver and was under the 256-byte emergency floor once the
// fast path was added beside it. Bank 16 has the room. The call is banked;
// the common floor case below does not make another one.

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/room.h"
#include "render/tiles.h"

// Tile ids at or below BGT_FLOOR3, other than the wall at 2, are not in the
// hostile solid set (pillar 21, crystal 22, crack 24, pot 32, tree 39).
// Passing over floor is the same decision as the old six-way solid test.
void projectile_update_hostile(entity_t *e, u8 idx) BANKED {
    i16 px = (i16)(e->x + e->vx);
    i16 py = (i16)(e->y + e->vy);
    i16 sx, sy;
    u8 ux, uy, tx, ty, t;
    e->x = px;
    e->y = py;
    ux = (u8)px;
    uy = (u8)py;
    // A nonzero high byte is px/py < 0 or >= 256, which also fails the
    // signed edge test. In-range pixels then compare as plain bytes.
    if (((u8)((u16)px >> 8) | (u8)((u16)py >> 8)) != 0
        || ux < 8 || ux > (u8)(room_world_width - 8)
        || uy < 8 || uy > (u8)(room_world_height - 8)) {
        entity_kill(idx);
        return;
    }
    sx = (i16)(ux + 4);
    sy = (i16)(uy + 4);
    tx = (u8)(sx >> 3);
    ty = (u8)(sy >> 3);
    t = (room_world_width == ROOM_VIEW_W_PX
            || (sx < ROOM_VIEW_W_PX && sy < ROOM_VIEW_H_PX))
        ? room_tilemap[ty][tx]
        : room_tile_at_px(sx, sy);
    if (t <= BGT_FLOOR3 && t != BGT_WALL) return;
    if (e->damage >= 2 && t == BGT_CRYSTAL) {
        room_break_crystal(tx, ty);
        fx_spawn(SPR_FX_IMPACT, 2, px, py, 8);
        entity_kill(idx);
        return;
    }
    if (e->damage >= 2 && t == BGT_POT) {
        room_break_pot(tx, ty);
        fx_spawn(SPR_FX_IMPACT, 2, px, py, 8);
        entity_kill(idx);
        return;
    }
    if (t == BGT_WALL || t == BGT_PILLAR || t == BGT_TREE || t == BGT_CRYSTAL
        || t == BGT_WALL_CRACK || t == BGT_POT) {
        fx_spawn(SPR_FX_IMPACT, 2, px, py, 4);
        entity_kill(idx);
    }
}
