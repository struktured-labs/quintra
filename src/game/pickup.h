#ifndef QUINTRA_GAME_PICKUP_H
#define QUINTRA_GAME_PICKUP_H

#include "core/types.h"
#include "game/entity.h"

// Pickup kinds (ai_data[0])
#define PICKUP_HEART_HALF 0
#define PICKUP_COIN_1     1
#define PICKUP_COIN_5     2
#define PICKUP_ITEM       3    // ai_data[1] = index into generated items[]

// Spawn a pickup at the given world coordinates (e.g. enemy death drop)
u8   pickup_spawn(u8 kind, fix8_t x, fix8_t y);

// Spawn a stat-boost item pickup (items[] table index)
u8   pickup_spawn_item(u8 item_index, fix8_t x, fix8_t y);

// RNG-driven drop on enemy death: heart 30%, coin 50%, nothing 20%
void pickup_roll_drop(fix8_t x, fix8_t y);

// Per-frame update (dispatch in entity_update_all)
void pickup_update(entity_t *e, u8 idx);

// Player touch check + apply effect; returns 1 if anything was picked up
u8   pickup_check_player_collision(void);

#endif
