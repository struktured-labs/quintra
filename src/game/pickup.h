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
#define PICKUP_WEAPON     5    // ai_data[1] = weapon item index; A confirms A-weapon swap
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
#define PICKUP_RIFTWELL     16 // one-use overworld restoration landmark
#define PICKUP_LOREKEEPER   17 // permanent town storyteller / lore fixture
#define PICKUP_BELLKEEPER    18 // permanent town arrival-square bellkeeper
#define PICKUP_FARFOLD_RELIC 19 // persistent optional dungeon-cache relic
#define PICKUP_BOON_CHOICE    20 // one of a mutually exclusive director pair
#define PICKUP_WAYFARER       21 // peaceful stage creature; A opens lore/advice

// Shop ware kinds
#define WARE_HEART   0   // +2 HP refill, 10 coins
#define WARE_ITEM    1   // random stat item, 25 coins
#define WARE_BIG     2   // Iron Heart (+2 max HP), 40 coins
#define WARE_FORGE   3   // Power Stone (+1 ATK), village forge only
#define WARE_RUNE    4   // Mana Gem (+2 max MP), village apothecary only
#define WARE_SURGE   5   // 15-second weapon burst, dungeon premium stock
#define WARE_VAMP    6   // Vampiric Sigil (+ATK/+max HP; heal every fifth kill)
#define WARE_CHART   7   // Cartographer's Chart (reveal active/next dungeon)
#define WARE_WEAPON  8   // seed-stable alternate A-weapon; town market trade
#define WARE_GLASS   9   // Glass Fang pact: -2 max HP, +2 ATK, +1 SPD
#define WARE_PHOENIX 10  // Phoenix Thread: consumed to revive once
#define WARE_ASCEND  11  // Spirit Draught: refill MP + temporary weapon Surge
#define WARE_ECHO    12  // Echo Prism: every fourth A attack forks
#define WARE_RICOCHET 13 // Ricochet Rune: primary attacks rebound once
#define WARE_THORN   14  // Thorn Crown: taking damage fires a counter-volley
#define WARE_DRUM    15  // War Drum: every fifth kill readies B and restores MP
#define WARE_FLASK   16  // Moon Flask: surplus heart drops become MP

// Stable content ids used by runtime hooks outside generated content tables.
#define ITEM_ID_IRON_HEART    20u
#define ITEM_ID_SPEED_RING    21u
#define ITEM_ID_POWER_STONE   22u
#define ITEM_ID_MANA_GEM      25u
#define ITEM_ID_SWIFT_FANG    27u
#define ITEM_ID_BLOOD_SIGIL   29u
#define ITEM_ID_GLASS_FANG    32u
#define ITEM_ID_PHOENIX_THREAD 33u
#define ITEM_ID_ECHO_PRISM     34u
#define ITEM_ID_RICOCHET_RUNE  35u
#define ITEM_ID_THORN_CROWN     36u
#define ITEM_ID_WAR_DRUM        37u
#define ITEM_ID_MOON_FLASK      38u
#define ITEM_ID_RIFT_BOMB       40u
#define ITEM_ID_ECHO_CHIME      41u
#define ITEM_ID_MIRROR_SHARD    42u

// Spawn a pickup at the given world coordinates (e.g. enemy death drop)
u8   pickup_spawn(u8 kind, fix8_t x, fix8_t y) BANKED;

// Spawn a stat-boost item pickup (items[] table index)
u8   pickup_spawn_item(u8 item_index, fix8_t x, fix8_t y) BANKED;
// Resolve generated content to the same readable world silhouette used by
// shops, boss rewards, optional caches, and ordinary enemy drops.
u8   pickup_item_sprite(u8 item_index) BANKED;

// Guaranteed colossus reward: roll from the active champion's small, useful
// relic pool instead of allowing a first boss to pay only a luck-sidegrade.
u8   pickup_boss_relic_for_class(void) BANKED;
// Seed-pure counterpart used by the optional Farfold Cache. `roll` selects
// one of the active champion's same three useful build branches.
u8   pickup_farfold_relic_for_class(u8 roll) BANKED;

// Spawn a weapon orb (generated weapon item index). Permanent, never magnetizes;
// overlap it and press A to swap the A-weapon, dropping the old one in place.
u8   pickup_spawn_weapon(u8 weapon_index, fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_farfold_relic(u8 item_index, fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_choice(u8 item_index, fix8_t x, fix8_t y) BANKED;

// Content-driven weapon-orb selection. These avoid assuming weapon entries
// occupy a contiguous prefix of items[] as the roster grows.
u8   pickup_weapon_count(void) BANKED;
u8   pickup_weapon_from_roll(u8 roll) BANKED;
u8   pickup_next_weapon(u8 current) BANKED;
void pickup_configure_shop_ware(u8 entity_index, u8 ware) BANKED;
u8   pickup_dungeon_featured_ware(u8 shelf) BANKED;
u8   pickup_dungeon_ware_price(u8 ware) BANKED;

// Spawn a +1 MP wisp (shattered-crystal drop)
u8   pickup_spawn_mp(fix8_t x, fix8_t y) BANKED;
void pickup_spawn_surge(fix8_t x, fix8_t y) BANKED;

// Spawn a permanent town elder who restores HP/MP once per room visit.
u8   pickup_spawn_villager(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_merchant(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_smith(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_apothecary(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_cartographer(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_waykeeper(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_lorekeeper(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_bellkeeper(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_wayfarer(u8 stage, fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_riftwell(fix8_t x, fix8_t y) BANKED;
u8   pickup_spawn_shop_tag(fix8_t x, fix8_t y) BANKED;

// RNG-driven drop on enemy death: heart 30%, coin 50%, nothing 20%
void pickup_roll_drop(fix8_t x, fix8_t y) BANKED;

// Per-frame update (dispatch in entity_update_all)
void pickup_update(entity_t *e, u8 idx) BANKED;

// Player touch check + apply effect; returns 1 if anything was picked up
u8   pickup_check_player_collision(void) BANKED;
u8   pickup_nearby_shop_offer(u8 *ware_out, u8 *price_out) BANKED;
u8   pickup_nearby_speaker(u8 *kind_out, u8 *topic_out) BANKED;
void pickup_echo_primary(u8 dir, u8 damage, u8 kind) BANKED;
u8   pickup_try_phoenix_revive(void) BANKED;

#endif
