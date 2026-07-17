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
#define PICKUP_WEAPON     5    // ai_data[1] = weapon item index; swaps A-weapon
#define PICKUP_MP         6    // +1 MP wisp (dropped by shattered crystals)
#define PICKUP_VILLAGER   7    // permanent town elder; touch for sanctuary blessing
#define PICKUP_MERCHANT   8    // permanent visual shopkeeper; non-collectible
#define PICKUP_SMITH      9    // permanent village forge keeper; non-collectible
#define PICKUP_APOTHECARY 10   // permanent village rune keeper; non-collectible
#define PICKUP_RIFT_SIGIL 11   // stage objective; unlocks its colossus threshold
#define PICKUP_CARTOGRAPHER 12 // village chartwright; reveals nearby route
#define PICKUP_SHOP_TAG     13 // inert gold sale marker, floats above a ware
#define PICKUP_SURGE        14 // temporary primary-weapon burst (about 15s)
#define PICKUP_WAYKEEPER    15 // permanent town north-gate resident

// Shop ware kinds
#define WARE_HEART   0   // +2 HP refill, 10 coins
#define WARE_ITEM    1   // random stat item, 25 coins
#define WARE_BIG     2   // Iron Heart (+2 max HP), 40 coins
#define WARE_FORGE   3   // Power Stone (+1 ATK), village forge only
#define WARE_RUNE    4   // Mana Gem (+2 max MP), village apothecary only
#define WARE_SURGE   5   // 15-second weapon burst, dungeon premium stock
#define WARE_VAMP    6   // Vampiric Sigil (+ATK/+max HP; heal every fifth kill)

// Spawn a pickup at the given world coordinates (e.g. enemy death drop)
u8   pickup_spawn(u8 kind, fix8_t x, fix8_t y) BANKED;

// Spawn a stat-boost item pickup (items[] table index)
u8   pickup_spawn_item(u8 item_index, fix8_t x, fix8_t y) BANKED;

// Spawn a weapon orb (generated weapon item index). Permanent, never magnetizes;
// walking over it swaps the A-weapon and drops the old one in its place.
u8   pickup_spawn_weapon(u8 weapon_index, fix8_t x, fix8_t y) BANKED;

// Content-driven weapon-orb selection. These avoid assuming weapon entries
// occupy a contiguous prefix of items[] as the roster grows.
u8   pickup_weapon_count(void) BANKED;
u8   pickup_weapon_from_roll(u8 roll) BANKED;
u8   pickup_next_weapon(u8 current) BANKED;

// Spawn a +1 MP wisp (shattered-crystal drop)
u8   pickup_spawn_mp(fix8_t x, fix8_t y) BANKED;

// Spawn a permanent town elder who restores HP/MP once per room visit.
u8   pickup_spawn_villager(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_merchant(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_smith(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_apothecary(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_cartographer(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_waykeeper(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_shop_tag(fix8_t x, fix8_t y) BANKED;

// RNG-driven drop on enemy death: heart 30%, coin 50%, nothing 20%
void pickup_roll_drop(fix8_t x, fix8_t y) BANKED;

// Per-frame update (dispatch in entity_update_all)
void pickup_update(entity_t *e, u8 idx) BANKED;

// Player touch check + apply effect; returns 1 if anything was picked up
u8   pickup_check_player_collision(void) BANKED;
u8   pickup_nearby_shop_offer(u8 *ware_out, u8 *price_out) BANKED;

#endif
