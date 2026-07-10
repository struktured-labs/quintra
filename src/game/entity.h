// ECS-lite — fixed entity table, 32 slots × 24 bytes.
// Lives in WRAM at the address chosen by the linker (eventually $C100
// per the spec). Per-type dispatch via switch in entity_update_all().
#ifndef QUINTRA_GAME_ENTITY_H
#define QUINTRA_GAME_ENTITY_H

#include "core/types.h"

#define MAX_ENTITIES 32

enum {
    ENT_NONE = 0,
    ENT_PROJECTILE,
    ENT_ENEMY,
    ENT_PICKUP,
    ENT_FX,         // visual-only, no collision, decays on state_timer=0
    ENT_TYPE_COUNT,
};

#define EF_ACTIVE      0x01
#define EF_ALIVE       0x02
#define EF_ON_SCREEN   0x04
#define EF_DIRTY       0x08
#define EF_PLAYER_PROJ 0x10   // player-owned projectile (vs enemy projectile)
#define EF_ELITE       0x20   // elite enemy: boss-glow, 2x HP, sure loot

typedef struct {
    u8     type;
    u8     flags;
    fix8_t x, y;            // 8.8 fixed-point world coords (pixels) — i32 each
    i8     vx, vy;           // per-tick velocity delta (pixels, scaled)
    u8     sprite_tile;
    u8     palette;          // CGB OBJ palette index 0-7
    u8     hp;               // or projectile pierce count
    u8     state;
    u8     state_timer;
    u8     ai_data[8];       // per-type scratch (enemy_id, etc.)
    u8     hitbox;           // 4-bit w, 4-bit h
    u8     damage;
    u8     oam_slot;         // OAM index (1..32; 0 reserved for player)
} entity_t;
// entity_t is now 28 bytes (was 24) due to i32 fix8_t.

extern entity_t entities[MAX_ENTITIES];

// 8-direction movement deltas (px scaled per dir index)
extern const i8 dir8_dx[8];
extern const i8 dir8_dy[8];

void entity_init_all(void);
u8   entity_spawn(u8 type);        // returns idx, or 0xFF if no free slot
void entity_kill(u8 idx);
void entity_update_all(u8 keys, u8 pressed);
void entity_draw_all(void);

// AABB test: returns 1 if hitboxes overlap. Hitbox interpreted as
// 4-bit w in high nibble, 4-bit h in low nibble; box anchored at (x,y).
u8   aabb_overlap_ee(const entity_t *a, const entity_t *b);
u8   aabb_overlap_player(const entity_t *e);        // small center HURTBOX
u8   aabb_overlap_player_wide(const entity_t *e);   // full feet-anchored body (pickups)

// FX: visual-only entity (no collision, decays on state_timer=0).
// sprite_tile is the OBJ tile slot; ttl is frames until despawn.
u8   fx_spawn(u8 sprite_tile, u8 palette, i16 px, i16 py, u8 ttl);
void fx_update(entity_t *e, u8 idx);

#endif
