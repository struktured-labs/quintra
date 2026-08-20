#include <gb/gb.h>
#include <string.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/enemy_ai.h"
#include "game/pickup.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"
#include "content.h"

entity_t entities[MAX_ENTITIES];
// Maintained alongside the fixed table so an empty post-combat field does not
// keep paying the banked camera-sector scan while its last bullets expire.
u8 entity_enemy_count;
// Visibility is a camera-sector concern, not an animation concern. A sentinel
// forces the first wide-field population scan; subsequent scans happen only
// after the camera crosses a 16px sector boundary.
static u8 visibility_sector_x = 0xFF;
static u8 visibility_sector_y = 0xFF;

// Free-running counter driving the enemy waddle: for half its cycle the enemy
// sprite is X-flipped (OAM attr bit 5), reading as a 2-frame idle/walk motion
// with no extra tile art.
u8 entity_anim_counter;
// Highest OAM cursor used by the previous entity draw. Only slots that became
// unused need parking; rewriting every remaining hardware sprite each frame
// wastes a large share of the Riftwild video budget.
u8 entity_oam_high = 4;

void entity_update_from(u8 start) BANKED;

// 8-direction deltas: 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW
const i8 dir8_dx[8] = {  0, +1, +1, +1,  0, -1, -1, -1 };
const i8 dir8_dy[8] = { -1, -1,  0, +1, +1, +1,  0, -1 };

static u8 hitbox_w(const entity_t *e) { return (e->hitbox >> 4) & 0x0F; }
static u8 hitbox_h(const entity_t *e) { return  e->hitbox       & 0x0F; }

u8 entity_spawn(u8 type) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) {
            memset(&entities[i], 0, sizeof(entity_t));
            entities[i].type    = type;
            entities[i].flags   = EF_ACTIVE | EF_ALIVE;
            if (type == ENT_ENEMY) {
                // Compact-room bodies are visible immediately. Wide fields
                // run the forced first camera-sector refresh below and clear
                // only the distant bodies; teleport limbo also clears this
                // same authoritative render/collision flag.
                entities[i].flags |= EF_ON_SCREEN;
                if (entity_enemy_count == 0) {
                    visibility_sector_x = 0xFF;
                    visibility_sector_y = 0xFF;
                }
                entity_enemy_count++;
            }
            // OAM slots 0-3 reserved for player metasprite; entities use 4+
            entities[i].oam_slot = (u8)(4 + i);
            return i;
        }
    }
    return 0xFF;
}

void entity_kill(u8 idx) {
    if (idx >= MAX_ENTITIES) return;
    if (entities[idx].type == ENT_ENEMY && entity_enemy_count)
        entity_enemy_count--;
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

// HURTBOX: small box at the body's center of mass (x+5..x+10,
// y+9..y+14). Bullet-hell fairness: the 16x16 body is generous to look
// at, stingy to hit — standard shmup design.
u8 aabb_overlap_player(const entity_t *e) {
    i16 ex = FIX8_TO_INT(e->x), ey = FIX8_TO_INT(e->y);
    i16 px = (i16)player.x, py = (i16)player.y;     // player is i16 pixels
    u8  ew = hitbox_w(e), eh = hitbox_h(e);
    px += 5; py += 9;
    if (px + 6 <= ex) return 0;
    if (ex + (i16)ew <= px) return 0;
    if (py + 6 <= ey) return 0;
    if (ey + (i16)eh <= py) return 0;
    return 1;
}

// PICKUP box: the full feet-anchored body (x+2..x+13, y+8..y+15) —
// generous for loot, matches the wall-collision silhouette.
u8 aabb_overlap_player_wide(const entity_t *e) {
    i16 ex = FIX8_TO_INT(e->x), ey = FIX8_TO_INT(e->y);
    i16 px = (i16)player.x, py = (i16)player.y;
    u8  ew = hitbox_w(e), eh = hitbox_h(e);
    px += 2; py += 8;
    if (px + 12 <= ex) return 0;
    if (ex + (i16)ew <= px) return 0;
    if (py + 8 <= ey) return 0;
    if (ey + (i16)eh <= py) return 0;
    return 1;
}

// Home-bank half of the adaptive dispatcher. Projectile/FX-free rooms stay
// here for the complete scan; the first projectile or effect transfers only
// the unprocessed suffix to bank 3, where both updates are direct calls.
void entity_update_nonprojectile(u8 idx) {
    switch (entities[idx].type) {
        case ENT_ENEMY:
            if ((room_world_width <= ROOM_VIEW_W_PX
                    && room_world_height <= ROOM_VIEW_H_PX)
                // A Colossus owns the complete scrolling arena. Its pattern
                // cannot freeze merely because a blink, weave, or player
                // camera move puts its body beyond the current viewport.
                || (entities[idx].ai_data[3] & 1)
                // A Shade deliberately clears EF_ON_SCREEN while vanished;
                // its hidden return timer must still reach materialization.
                || (entities[idx].ai_data[0] == ENEMY_SHADE
                    && entities[idx].ai_data[2] != 0)
                || (entities[idx].flags & EF_ON_SCREEN))
                enemy_update(&entities[idx], idx);
            break;
        case ENT_PICKUP:
            pickup_update(&entities[idx], idx);
            break;
        default:
            break;
    }
}

void entity_update_all(void) {
    u8 i;
    // Scrolling fields can hold a full district population, but only the
    // current camera cluster spends AI/projectile time. Refresh when either
    // camera axis enters a new 16px sector. This keeps activation responsive
    // while a stationary scene pays no periodic far-call tax.
    if ((room_world_width > ROOM_VIEW_W_PX
            || room_world_height > ROOM_VIEW_H_PX)
        && entity_enemy_count
        && ((room_camera_x >> 4) != visibility_sector_x
            || (room_camera_y >> 4) != visibility_sector_y)) {
        visibility_sector_x = (u8)(room_camera_x >> 4);
        visibility_sector_y = (u8)(room_camera_y >> 4);
        entity_refresh_world_visibility();
    }
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        if (entities[i].type == ENT_PROJECTILE
            || entities[i].type == ENT_FX) {
            entity_update_from(i);
            return;
        }
        entity_update_nonprojectile(i);
    }
}

u8 fx_spawn(u8 sprite_tile, u8 palette, i16 px, i16 py, u8 ttl) {
    u8 idx = entity_spawn(ENT_FX);
    if (idx == 0xFF) return 0xFF;
    {
        entity_t *e = &entities[idx];
        e->x = FIX8(px);
        e->y = FIX8(py);
        e->sprite_tile = sprite_tile;
        e->palette     = palette;
        e->state_timer = ttl;
        e->hitbox      = 0;
        e->damage      = 0;
    }
    return idx;
}

// 16x16 enemies (2x2 tiles): the mini-boss Sentinel and the bruiser tier
// (orc 4, bomber 6, warlock 8), plus Ember's narrow middle-scale Cinder Maw.
// Their sprite_tile points at a 4-tile block TL,TR,BL,BR. The 32x32 Colossus
// (giant flag) is handled separately.
static u8 enemy_is_big16(const entity_t *e) {
    u8 eid = e->ai_data[0];
    if (e->type != ENT_ENEMY) return 0;
    if (eid == ENEMY_STONE_SENTINEL) return 1;
    return (eid == ENEMY_ORC || eid == ENEMY_BOMBER || eid == ENEMY_WARLOCK
        || eid == ENEMY_CINDER_MAW);
}

// Per-frame OAM allocator. Player owns 0-3; entities are laid out from a
// cursor starting at 4 each frame (giant=16 tiles, 16x16=4, else 1), so no
// entity is pinned to a fixed slot — which also fixes the old latent overlap
// between the entity range and the boss overlay block. Logical iteration
// rotates so OAM/scanline overflow becomes fair, GB-authentic flicker rather
// than permanent invisibility; unused slots are parked off-screen.
void entity_draw_all(void) {
    u8 i;
    u8 oam = serpent_tail_active ? 32 : cinder_pack_active ? 22 : 4;
#define ENTITY_DRAW_SX(e) \
    ((u8)(FIX8_TO_INT((e)->x) - room_camera_x + 8))
#define ENTITY_DRAW_SY(e) \
    ((u8)(FIX8_TO_INT((e)->y) - room_camera_y + 16))
#include "game/entity_draw_core.h"
#undef ENTITY_DRAW_SX
#undef ENTITY_DRAW_SY
}
