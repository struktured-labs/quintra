#ifndef QUINTRA_GAME_PICKUP_H
#define QUINTRA_GAME_PICKUP_H


#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"

// Pickup kinds (ai_data[0])
#define PICKUP_HEART_HALF 0
#define PICKUP_COIN_1     1
#define PICKUP_COIN_5     2
#define PICKUP_ITEM       3    // ai_data[1] = index into generated items[]
#define PICKUP_SHOP       4    // shop ware: ai_data[1]=ware kind, ai_data[2]=price
#define PICKUP_WEAPON     5    // ai_data[1] = weapon item index (0-4); swaps A-weapon
#define PICKUP_MP         6    // +1 MP wisp (dropped by shattered crystals)
#define PICKUP_VILLAGER   7    // permanent town elder; touch for sanctuary blessing
#define PICKUP_MERCHANT   8    // permanent visual shopkeeper; non-collectible
#define PICKUP_SMITH      9    // permanent village forge keeper; non-collectible

// Shop ware kinds
#define WARE_HEART   0   // +2 HP refill, 10 coins
#define WARE_ITEM    1   // random stat item, 25 coins
#define WARE_BIG     2   // Iron Heart (+2 max HP), 40 coins
#define WARE_FORGE   3   // Power Stone (+1 ATK), village forge only

// Spawn a pickup at the given world coordinates (e.g. enemy death drop)
u8   pickup_spawn(u8 kind, fix8_t x, fix8_t y) BANKED;

// Spawn a stat-boost item pickup (items[] table index)
u8   pickup_spawn_item(u8 item_index, fix8_t x, fix8_t y) BANKED;

// Spawn a weapon orb (weapon index 0-4). Permanent, never magnetizes;
// walking over it swaps the A-weapon and drops the old one in its place.
u8   pickup_spawn_weapon(u8 weapon_index, fix8_t x, fix8_t y) BANKED;

// Spawn a +1 MP wisp (shattered-crystal drop)
u8   pickup_spawn_mp(fix8_t x, fix8_t y) BANKED;

// Spawn a permanent town elder who restores HP/MP once per room visit.
u8   pickup_spawn_villager(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_merchant(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_smith(fix8_t x, fix8_t y) BANKED;

// RNG-driven drop on enemy death: heart 30%, coin 50%, nothing 20%
void pickup_roll_drop(fix8_t x, fix8_t y) BANKED;

// Per-frame update (dispatch in entity_update_all)
void pickup_update(entity_t *e, u8 idx) BANKED;

// Player touch check + apply effect; returns 1 if anything was picked up
u8   pickup_check_player_collision(void) BANKED;

#endif
