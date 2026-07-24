#include <gb/gb.h>
#include <string.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/enemy_ai.h"
#include "game/pickup.h"
#include "game/room.h"
#include "content.h"

entity_t entities[MAX_ENTITIES];

// Free-running counter driving the enemy waddle: for half its cycle the enemy
// sprite is X-flipped (OAM attr bit 5), reading as a 2-frame idle/walk motion
// with no extra tile art.
static u8 g_enemy_anim;

// 8-direction deltas: 0=N, 1=NE, 2=E, 3=SE, 4=S, 5=SW, 6=W, 7=NW
const i8 dir8_dx[8] = {  0, +1, +1, +1,  0, -1, -1, -1 };
const i8 dir8_dy[8] = { -1, -1,  0, +1, +1, +1,  0, -1 };

static u8 hitbox_w(const entity_t *e) { return (e->hitbox >> 4) & 0x0F; }
static u8 hitbox_h(const entity_t *e) { return  e->hitbox       & 0x0F; }

void entity_init_all(void) {
    u8 i;
    memset(entities, 0, sizeof(entities));
    // Park entity sprites (slots 4..35) + boss metasprite overlay (36..39)
    for (i = 4; i < 40; ++i) {
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

void entity_update_all(u8 keys, u8 pressed) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        switch (entities[i].type) {
            case ENT_PROJECTILE: projectile_update(&entities[i], i); break;
            case ENT_ENEMY:      enemy_update(&entities[i], i);      break;
            case ENT_PICKUP:     pickup_update(&entities[i], i);     break;
            case ENT_FX:         fx_update(&entities[i], i);         break;
            default: break;
        }
        keys; pressed;
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

void fx_update(entity_t *e, u8 idx) {
    if (e->state_timer == 0) { entity_kill(idx); return; }
    e->state_timer--;
}

// 16x16 enemies (2x2 tiles): the mini-boss Sentinel and the bruiser tier
// (orc 4, bomber 6, warlock 8). Their sprite_tile points at a 4-tile block
// TL,TR,BL,BR. The 32x32 Colossus (giant flag) is handled separately.
static u8 enemy_is_big16(const entity_t *e) {
    u8 eid = e->ai_data[0];
    if (e->type != ENT_ENEMY) return 0;
    if (eid == ENEMY_STONE_SENTINEL) return 1;
    return (eid == ENEMY_ORC || eid == ENEMY_BOMBER || eid == ENEMY_WARLOCK);
}

// Per-frame OAM allocator. Player owns 0-3; entities are laid out from a
// cursor starting at 4 each frame (giant=16 tiles, 16x16=4, else 1), so no
// entity is pinned to a fixed slot — which also fixes the old latent overlap
// between the entity range and the boss overlay block. Past OAM 40 we simply
// stop drawing (GB-authentic drop); unused slots are parked off-screen.
void entity_draw_all(void) {
    u8 i;
    u8 oam = 4;
    g_enemy_anim++;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        u8 sx, sy, pal, flash;
        if (!(e->flags & EF_ACTIVE)) continue;
        sx  = (u8)(FIX8_TO_INT(e->x) - room_camera_x + 8);
        sy  = (u8)(FIX8_TO_INT(e->y) + 16);
        pal = e->palette;
        flash = (e->type == ENT_ENEMY && e->ai_data[7]) ? 1 : 0;

        // 32x32 Colossus — 16 tiles, row-major 4x4
        if (e->type == ENT_ENEMY && e->ai_data[0] == ENEMY_STONE_SENTINEL && e->ai_data[3]) {
            u8 r, c, tile = e->sprite_tile;
            if (flash) e->ai_data[7]--;
            if (oam + 16 > 40) continue;
            for (r = 0; r < 4; ++r) {
                for (c = 0; c < 4; ++c) {
                    set_sprite_tile(oam, tile);
                    set_sprite_prop(oam, pal);
                    if (flash && (e->ai_data[7] & 1)) move_sprite(oam, 0, 0);
                    else move_sprite(oam, (u8)(sx + c * 8), (u8)(sy + r * 8));
                    oam++; tile++;
                }
            }
            continue;
        }

        // 16x16 — mini-boss or bruiser, 2x2 tiles
        if (enemy_is_big16(e)) {
            u8 t = e->sprite_tile;
            if (flash) e->ai_data[7]--;
            if (oam + 4 > 40) continue;
            if (flash && (e->ai_data[7] & 1)) {
                move_sprite(oam, 0, 0);     move_sprite((u8)(oam+1), 0, 0);
                move_sprite((u8)(oam+2), 0, 0); move_sprite((u8)(oam+3), 0, 0);
            } else {
                set_sprite_tile(oam,        t);
                set_sprite_tile((u8)(oam+1), (u8)(t+1));
                set_sprite_tile((u8)(oam+2), (u8)(t+2));
                set_sprite_tile((u8)(oam+3), (u8)(t+3));
                set_sprite_prop(oam, pal);        set_sprite_prop((u8)(oam+1), pal);
                set_sprite_prop((u8)(oam+2), pal); set_sprite_prop((u8)(oam+3), pal);
                move_sprite(oam,         sx,         sy);
                move_sprite((u8)(oam+1), (u8)(sx+8), sy);
                move_sprite((u8)(oam+2), sx,         (u8)(sy+8));
                move_sprite((u8)(oam+3), (u8)(sx+8), (u8)(sy+8));
            }
            oam += 4;
            continue;
        }

        // 8x8 — everything else (small enemies, projectiles, pickups, fx)
        if (oam >= 40) continue;
        if (flash) {
            e->ai_data[7]--;
            if (e->ai_data[7] & 0x01) continue;   // blink: skip drawing (slot parked below)
        }
        set_sprite_tile(oam, e->sprite_tile);
        {
            u8 prop = pal;
            if (e->type == ENT_ENEMY && (g_enemy_anim & 0x10)) prop |= S_FLIPX;
            if (e->type == ENT_PROJECTILE) {
                if (e->ai_data[4] & PROJ_VIS_FLIP_X) prop |= S_FLIPX;
                if (e->ai_data[4] & PROJ_VIS_FLIP_Y) prop |= S_FLIPY;
            }
            set_sprite_prop(oam, prop);
        }
        move_sprite(oam, sx, sy);
        oam++;
    }
    // Park every unused OAM slot off-screen
    while (oam < 40) { move_sprite(oam, 0, 0); oam++; }
}
