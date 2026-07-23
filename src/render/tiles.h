// Runtime tile slots and generated sprite-loading contracts.
#ifndef QUINTRA_RENDER_TILES_H
#define QUINTRA_RENDER_TILES_H


#include <gb/gb.h>
#include "core/types.h"

// BG tile slots
#define BGT_VOID   0
#define BGT_FLOOR  1     // plain stone (bright)
#define BGT_WALL   2     // brick face
#define BGT_DOOR   3     // gold door frame

// HUD tile slots (BG tile data, rendered via WINDOW layer)
#define HUD_HEART_FULL  4
#define HUD_HEART_HALF  5
#define HUD_HEART_EMPTY 6
#define HUD_COIN        7
#define HUD_BLANK       8
#define HUD_DIGIT_0     9    // ...9..18 = digits 0..9
// Boss HP bar segments (loaded with the HUD set; slots after dungeon tiles)
#define HUD_BAR_FULL   26
#define HUD_BAR_EMPTY  27
// Merchant proximity offer icons. These live only on the WINDOW HUD, so the
// dungeon tilemap never interprets them as terrain.
#define HUD_OFFER_HEAL   40
#define HUD_OFFER_RELIC  41
#define HUD_OFFER_VITAL  42
#define HUD_OFFER_FORGE  43
#define HUD_OFFER_RUNE   44
#define HUD_OFFER_SURGE  45
#define HUD_OFFER_VAMP   46
#define HUD_OFFER_CHART  47
#define HUD_OFFER_WEAPON 48

// Dungeon tile slots (after HUD block)
#define BGT_FLOOR2  19   // cracked floor variant
#define BGT_FLOOR3  20   // pebbled floor variant
#define BGT_PILLAR  21   // solid obstacle
#define BGT_CRYSTAL 22   // solid glowing obstacle
#define BGT_RUBBLE  23   // walkable decoration
#define BGT_WALL_CRACK 24  // secret wall: solid until shot, then becomes a door
#define BGT_BLOCK      25  // pushable crate TL quadrant (16x16 crate = 4 tiles)
#define BGT_BLOCK_TR   28  // crate top-right
#define BGT_BLOCK_BL   29  // crate bottom-left
#define BGT_BLOCK_BR   30  // crate bottom-right
#define BGT_SPIKES     31  // floor hazard: walkable but damages on contact
#define BGT_POT        32  // breakable clay pot: solid, shoot for loot
#define BGT_SWITCH     33  // one-shot pressure plate: player or block activates it
#define BGT_PORTAL     34  // nonlinear intra-stage rift well
#define BGT_GRASS      35  // outdoor ground: Riftwild + villages
#define BGT_PATH       36  // worn civic/wilderness trail
#define BGT_ROOF       37  // village shingle roof
#define BGT_FENCE      38  // solid timber boundary
#define BGT_TREE       39  // solid outdoor canopy/trunk silhouette

// Spirit Compass-only glyphs. Dedicated symbols keep the SELECT screen an
// abstract map instead of making it look like a tiny dungeon screenshot.
#define BGT_MAP_ROOM    49
#define BGT_MAP_HERE    50
#define BGT_MAP_BOSS    51
#define BGT_MAP_SIGIL   52
#define BGT_MAP_PATH_H  53
#define BGT_MAP_PATH_V  54

// Void Sanctum's final Colossus uses the BG plane for a screen-scale astral
// body while its 32x32 OBJ remains the vulnerable moving core. These tiles
// are walkable projection art, not invisible collision walls.
#define BGT_COLOSSUS_VOID   55
#define BGT_COLOSSUS_SCALE  56
#define BGT_COLOSSUS_EDGE_L 57
#define BGT_COLOSSUS_EDGE_R 58
#define BGT_COLOSSUS_EYE    59
#define BGT_COLOSSUS_FANG   60
#define BGT_COLOSSUS_RUNE   61
#define BGT_COLOSSUS_MAW    62
#define BGT_COLOSSUS_HORN   63

// Compass-only 8px legend letters. Keeping these as authored BG tiles avoids
// invoking the console/font system or turning the map back into a text page.
#define BGT_MAP_LABEL_Y 64
#define BGT_MAP_LABEL_O 65
#define BGT_MAP_LABEL_U 66
#define BGT_MAP_LABEL_S 67
#define BGT_MAP_LABEL_I 68
#define BGT_MAP_LABEL_G 69
#define BGT_MAP_LABEL_L 70
#define BGT_MAP_LABEL_B 71

// Sanctuary-only boss threshold art. The room tilemap retains BGT_DOOR for
// collision/progression; rendering substitutes these unmistakable gate tiles.
#define BGT_BOSS_GATE_L      72
#define BGT_BOSS_GATE_R      73
#define BGT_BOSS_GATE_TOP    74
#define BGT_BOSS_GATE_BOTTOM 75

// In-play area labels. These are tile-native landmarks rather than a modal
// font screen: Riftwild and each village quarter identify themselves while
// the hero keeps moving. Room collision continues to use the underlying
// grass/path tile; draw_room_tilemap substitutes these only for display.
#define BGT_AREA_R 76
#define BGT_AREA_I 77
#define BGT_AREA_F 78
#define BGT_AREA_T 79
#define BGT_AREA_W 80
#define BGT_AREA_L 81
#define BGT_AREA_D 82
#define BGT_AREA_V 83
#define BGT_AREA_A 84
#define BGT_AREA_G 85
#define BGT_AREA_E 86
#define BGT_AREA_M 87
#define BGT_AREA_K 88
#define BGT_AREA_O 89

// Compass-only nonlinear edge. Rooms 2 and 8 in later dungeons are joined by
// a rift well in addition to the ordinary walking route; the map draws this
// violet diagonal only as each endpoint is discovered.
#define BGT_MAP_RIFT    90
#define BGT_MAP_LABEL_R 91
#define BGT_MAP_LABEL_F 92
#define BGT_MAP_LABEL_T 93
#define BGT_MAP_LABEL_P 94
#define BGT_MAP_UNKNOWN 95 // dim slot; reveals grid shape, never room identity/link

// Riftwild-only geographic vocabulary. A run rotates four landmark families
// across the authored 4x4 graph, making a cell recognizable without replacing
// procgen or exposing its Compass identity through fog of war.
#define BGT_WILD_FLOWER  96 // walkable meadow color
#define BGT_WILD_WATER   97 // solid pond edge / streamlet
#define BGT_WILD_STONE   98 // solid weathered standing stone
#define BGT_WILD_STUMP   99 // solid old-growth stump

// Compass-only dim connections. These expose the active dungeon lattice from
// the first visit while discovered routes overwrite them with the bright
// path tiles above. Slots 100–101 are otherwise unused by every map atlas.
#define BGT_MAP_PATH_H_DIM 100
#define BGT_MAP_PATH_V_DIM 101

// Dungeon Compass 16×16 node quadrants. Each semantic node owns four
// consecutive tiles in NW, NE, SW, SE order. The larger cells use the same
// 6×5 footprint as gameplay but read as rooms rather than tiny circuit pads.
// These map-only BG slots may numerically overlap OBJ slots: the CGB's signed
// BG tile region is separate from the OBJ data region used by those IDs.
#define BGT_MAP_NODE_ROOM_BASE    102
#define BGT_MAP_NODE_UNKNOWN_BASE 106
#define BGT_MAP_NODE_HERE_BASE    110
#define BGT_MAP_NODE_BOSS_BASE    114
#define BGT_MAP_NODE_SIGIL_BASE   118
#define BGT_MAP_NODE_TRIAL_BASE   122

// CGB BG palette slot per tile kind (written to VRAM bank 1 attributes)
#define BGPAL_FLOOR   0
#define BGPAL_WALL    1
#define BGPAL_CRYSTAL 2
#define BGPAL_DOOR    3
#define BGPAL_CRACK   4     // glowing amber so secret walls stand out

// OBJ tile slots — 5 classes × 4 tiles each (metasprite) + 4 enemies + 4 boss tiles + pickups + bullet
#define SPR_CLASS_BASE     0     // 5 classes × 4 tiles = 0..19
#define SPR_CLASS_STRIDE   4
#define SPR_CLASS_WALK_BASE 82  // 5 authored step poses: 82..101
#define SPR_CLASS_ASCENDED_BASE 102 // 5 Spirit Convergence forms: 102..121
#define SPR_ENEMY_CRAWLER  20
#define SPR_ENEMY_HORNET   21
#define SPR_ENEMY_SKELETON 22
#define SPR_ENEMY_ORC      23
#define SPR_BOSS           24    // 4 tiles: 24..27
#define SPR_BULLET         28    // 2-frame anim: SPR_BULLET + SPR_BULLET_B
#define SPR_BULLET_B       29
#define SPR_HEART          30
#define SPR_COIN           31
#define SPR_FX_MUZZLE      32
#define SPR_FX_IMPACT      33
#define SPR_ENEMY_WISP     34
#define SPR_ITEM_ORB       35
#define SPR_ENEMY_BOMBER   36
#define SPR_ENEMY_SHADE    37
#define SPR_ENEMY_WARLOCK  38
#define SPR_ENEMY_ROPE     39
#define SPR_ENEMY_SENTRY   68  // stationary turret (after bruiser blocks)
#define SPR_VILLAGER       69  // town elder / sanctuary keeper
#define SPR_ENEMY_PRISM_SKITTER SPR_VILLAGER // dungeon-only orbiting caster
#define SPR_MERCHANT       70  // town/dungeon shopkeeper
#define SPR_SMITH          71  // village forge keeper
#define SPR_ENEMY_FOLD_STAR 72 // contracted/expanded diagonal replicator
#define SPR_ENEMY_FLUTTERBAT 73 // Keese-like flyer
#define SPR_ENEMY_GLOAM_LEECH 74 // attaching life-drain creature
#define SPR_ENEMY_CINDER_MAW 75 // Ember area-denial caster
#define SPR_ENEMY_RIFT_OOZE  76 // splitting late-stage blob
#define SPR_ENEMY_MIRROR_MOTH 77 // Frost Vault movement-reflecting flyer
#define SPR_ENEMY_MIRE_SPORE  78 // Toxic Mire proximity-armed radial mine
#define SPR_APOTHECARY        79 // village rune keeper
#define SPR_ENEMY_DUSK_MIDGE  SPR_APOTHECARY // combat-only fast fan harrier
#define SPR_ENEMY_SUNWHEEL    SPR_APOTHECARY // Golden Temple-only orbiting lane shaper
#define SPR_ENEMY_CINDER_KITE SPR_APOTHECARY // Ember-only fast fan harrier
#define SPR_ENEMY_BOG_TOAD    SPR_APOTHECARY // Toxic Mire-only pounce bruiser
#define SPR_ENEMY_BRAMBLE_SPRITE SPR_APOTHECARY // Shadow-only thorn orbit pair
#define SPR_ENEMY_FROST_LANCER SPR_APOTHECARY // Frost-only telegraphed charge
#define SPR_ENEMY_VINE_COIL    SPR_APOTHECARY // Verdant-only orbiting seed-pair caster
#define SPR_ENEMY_SHARD_CRAB   SPR_APOTHECARY // Crystal-only shell-counter skirmisher
#define SPR_ENEMY_VOID_HALO    SPR_APOTHECARY // Void-only wide orbit lane shaper
// Arrival-square only reuse: the Bellkeeper is a civic landmark, while the
// apothecary owns this tile in the craft quarter. Those residents never share
// a town screen, and dungeon entry reloads the stage specialist before combat.
#define SPR_TOWN_BELLKEEPER    SPR_APOTHECARY
#define SPR_ENEMY_ECHO_GUARD  80 // Golden Temple shield-counter duelist
#define SPR_SHOP_TAG         81 // animated for-sale marker; never loose currency
#define SPR_ENEMY_RIFT_WARDEN SPR_SHOP_TAG // combat-only late five-way caster
#define SPR_FX_SWING        122 // Wolfkin's physical sword strike
#define SPR_CARTOGRAPHER    123 // village chartwright; reveals the next route
// Slot 123 is Chartwright art in towns and the Astral Spear only in combat
// rooms; those populations never coexist, preserving the OBJ VRAM budget.
#define SPR_FX_SPEAR        SPR_CARTOGRAPHER
#define SPR_ENEMY_RUNE_LANTERN 124 // late drifting four-lane ring caster
// Town-only reuse: villages never spawn Rune Lanterns, and each dungeon room
// reloads the normal lantern art before enemies exist.
#define SPR_TOWN_WAYKEEPER   SPR_ENEMY_RUNE_LANTERN
#define SPR_MERCHANT_CALLOUT 125 // town-local proximity bubble (trade or lore)
#define SPR_ENEMY_DREAD_BELL SPR_MERCHANT_CALLOUT // combat-only late eight-way caster
#define SPR_SURGE_ORB        126 // temporary weapon-speed/damage pickup
#define SPR_TOWN_LOREKEEPER  SPR_SURGE_ORB // town-arrival storyteller; no active Surge there
#define SPR_SHIELD_AURA      127 // Sauran Stoneskin orbiting ward shard
#define SPR_BOSS_BIG       40    // 16 tiles: 40..55 (32x32 final boss)
// Bruiser tier: heavy enemies rendered player-sized (16x16 = 4 tiles each)
#define SPR_BRUISER_ORC     56   // 56..59
#define SPR_BRUISER_BOMBER  60   // 60..63
#define SPR_BRUISER_WARLOCK 64   // 64..67
// Legacy aliases (kept for back-compat with existing code):
#define SPR_PLAYER         SPR_CLASS_BASE
#define SPR_ENEMY          SPR_ENEMY_CRAWLER

// Tile blobs
extern const u8 bg_tile_void[16];
extern const u8 sprite_tile_heart[16];
extern const u8 sprite_tile_coin[16];

extern const u8 hud_tiles[][16];
#define HUD_TILE_COUNT 15

void tiles_load_pickup_sprites(void) BANKED;
void tiles_load_town_waykeeper_sprite(void) BANKED;
void tiles_load_town_bellkeeper_sprite(void) BANKED;
void tiles_load_town_lorekeeper_sprite(void) BANKED;
void tiles_load_town_lore_callout_sprite(void) BANKED;
void tiles_load_hud(void) BANKED;

// Phase 12 metasprite loaders
void tiles_load_all_class_sprites(void) BANKED;   // loads 5 classes × 4 tiles = 20 OBJ tiles
void tiles_load_ascended_sprites(void) BANKED;    // bank-3 transform atlas -> fixed OBJ slots
void tiles_load_all_enemy_sprites(void) BANKED;   // 4 enemy tiles
void tiles_load_dread_bell_sprite(void) BANKED;   // combat-only reuse of callout slot
void tiles_load_rift_warden_sprite(void) BANKED;  // combat-only reuse of sale-tag slot
void tiles_load_prism_skitter_sprite(void) BANKED; // combat-only reuse of elder slot
void tiles_load_dusk_midge_sprite(void) BANKED;    // combat-only reuse of apothecary slot
void tiles_load_cinder_kite_sprite(void) BANKED;   // Ember-only reuse of apothecary slot
void tiles_load_bog_toad_sprite(void) BANKED;      // Toxic Mire reuse of apothecary slot
void tiles_load_bramble_sprite(void) BANKED;       // Shadow Keep reuse of that slot
void tiles_load_frost_lancer_sprite(void) BANKED;  // Frost Vault reuse of that slot
void tiles_load_vine_coil_sprite(void) BANKED;     // Verdant Hollow reuse of that slot
void tiles_load_shard_crab_sprite(void) BANKED;    // Crystal Caverns reuse of that slot
void tiles_load_void_halo_sprite(void) BANKED;     // Void Sanctum reuse of that slot
void tiles_load_sunwheel_sprite(void) BANKED;      // Golden Temple reuse of that slot
void tiles_load_merchant_callout_sprite(void) BANKED;
void tiles_load_spear_sprite(void) BANKED;
void tiles_load_miniboss(u8 stage) BANKED;        // stage's distinct 16x16 mini-boss into SPR_BOSS
void tiles_load_boss_big(u8 stage) BANKED;        // load stage's 32x32 boss (16 tiles at SPR_BOSS_BIG)
void tiles_load_fx_sprites(void) BANKED;          // bullet (2 frames), muzzle, impact
void tiles_load_dungeon_bg(void) BANKED;          // dungeon tileset (replaces flat placeholders)
void tiles_load_map_bg(void) BANKED;              // dungeon set + Compass glyphs
void tiles_load_colossus_bg(u8 stage) BANKED;     // nine screen-scale boss bodies
void tiles_paint_crystal_projection(void) BANKED;
void tiles_paint_serpent_projection(void) BANKED;
void tiles_paint_cinder_projection(void) BANKED;
void tiles_paint_spider_projection(void) BANKED;
void tiles_paint_reaper_projection(void) BANKED;
void tiles_paint_golem_projection(void) BANKED;
void tiles_paint_mire_projection(u8 expanded, u8 draw_vram) BANKED;
void tiles_paint_hydra_projection(void) BANKED;
void tiles_paint_void_projection(void) BANKED;
void tiles_prepare_colossal_edges(void) BANKED; // safe 0..3px camera overscan
void tiles_load_boss_cue_bg(void) BANKED;         // sanctuary skull/barred threshold
void tiles_draw_boss_cue(u8 entered_from) BANKED; // project its 16x16 edge seal
void tiles_load_area_labels(void) BANKED;          // RIFTWILD + village quarter landmarks
void tiles_draw_area_label(u8 kind) BANKED;        // 1 Riftwild, 2 Village, 3 Market, 4 Forge
void tiles_animate_colossus_bg(u8 closed) BANKED; // blink the BG-plane eyes
void tiles_animate_serpent_bg(u8 alternate) BANKED; // electric coil travel
void tiles_animate_cinder_bg(u8 active) BANKED;   // breath/lunge vs recovery jaw
void tiles_animate_spider_bg(u8 closed) BANKED;   // web charge + eye pulse
void tiles_animate_reaper_bg(u8 phased) BANKED;   // spectral cloak fade
void tiles_animate_golem_bg(u8 dormant) BANKED;   // stone sleep / sun-rune wake
void tiles_animate_hydra_bg(u8 center_open) BANKED;

#endif
