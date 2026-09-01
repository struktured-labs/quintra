#pragma bank 5
#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "core/rng.h"
#include "game/entity.h"
#include "game/curse.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/riftwild_phase.h"
#include "game/spawn_reach.h"
#include "game/status.h"
#include "game/waygear.h"
#include "game/dungeon_director.h"
#include "input/input.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"


static u8 pickup_kind_collectible(u8 kind) {
    return kind <= PICKUP_MP || kind == PICKUP_RIFT_SIGIL
        || kind == PICKUP_SURGE || kind == PICKUP_RIFTWELL
        || kind == PICKUP_FARFOLD_RELIC || kind == PICKUP_BOON_CHOICE
        || kind == PICKUP_WAYGEAR || kind == PICKUP_WILDCARD
        || kind == PICKUP_HOLLOW_RELIC;
}

static u8 pickup_tile_safe(u8 tile) {
    return room_tile_walkable(tile) && tile != BGT_SPIKES
        && tile != BGT_PORTAL && tile != BGT_SWITCH;
}

static u8 pickup_position_safe(i16 px, i16 py) {
    if (px < 0 || py < 0 || px > (i16)(room_world_width - 16)
        || py > (i16)(room_world_height - 16)) return 0;
    return pickup_tile_safe(room_tile_at_px(px + 1, py + 1))
        && pickup_tile_safe(room_tile_at_px(px + 14, py + 1))
        && pickup_tile_safe(room_tile_at_px(px + 1, py + 14))
        && pickup_tile_safe(room_tile_at_px(px + 14, py + 14));
}

// Enemy deaths, authored rewards, and seeded fixtures all enter through the
// same constructor. Terrain can change after their preferred coordinate was
// chosen (push-block puzzles are the common case), so snap to the nearest
// complete champion-sized walkable footprint. If an authored pocket has become
// solid, the final fallback is the champion's connected component: a reward
// may arrive at their feet, but can never remain trapped inside scenery.
static void pickup_make_position_safe(fix8_t *x, fix8_t *y) {
    i8 radius, dx, dy;
    i16 px = FIX8_TO_INT(*x);
    i16 py = FIX8_TO_INT(*y);
    if (pickup_position_safe(px, py)) return;
    for (radius = 1; radius <= 4; ++radius) {
        for (dy = (i8)-radius; dy <= radius; ++dy) {
            for (dx = (i8)-radius; dx <= radius; ++dx) {
                i8 ax = dx < 0 ? (i8)-dx : dx;
                i8 ay = dy < 0 ? (i8)-dy : dy;
                i16 nx, ny;
                if ((i8)(ax + ay) != radius) continue;
                nx = px + (i16)dx * 8;
                ny = py + (i16)dy * 8;
                if (pickup_position_safe(nx, ny)) {
                    *x = FIX8(nx); *y = FIX8(ny);
                    return;
                }
            }
        }
    }
    *x = FIX8(player.x);
    *y = FIX8(player.y);
}

u8 pickup_spawn(u8 kind, fix8_t x, fix8_t y) BANKED {
    u8 idx = entity_spawn(ENT_PICKUP);
    if (idx == 0xFF) return 0xFF;
    if (pickup_kind_collectible(kind)) pickup_make_position_safe(&x, &y);
    snap_major_pickup_to_reachable(kind, &x, &y);
    {
        entity_t *e = &entities[idx];
        e->x = x;
        e->y = y;
        e->vx = e->vy = 0;
        e->ai_data[0] = kind;
        e->hitbox     = (6 << 4) | 6;
        e->damage     = 0;
        e->hp         = 1;
        e->state_timer = 240;    // despawn after 4 seconds
        // Specialized pickup constructors replace this default art below;
        // only hearts differ from the coin/orb placeholder here.
        if (kind == PICKUP_HEART_HALF) {
            e->sprite_tile = SPR_HEART;
            e->palette     = 0x04;   // OBJ palette 4 (heart red)
        } else {
            e->sprite_tile = SPR_COIN;
            e->palette     = 0x05;   // OBJ palette 5 (coin gold)
        }
    }
    return idx;
}

u8 pickup_spawn_item(u8 item_index, fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_ITEM, x, y);
    if (idx != 0xFF) {
        // Category tint for the passive orbs (indices 10..19):
        // offense = red, defense = bone-white, utility/luck = gold.
        static const u8 tint[10] = {
            0x00,   // 10 Iron Heart   (defense)
            0x05,   // 11 Speed Ring   (utility)
            0x04,   // 12 PowerStone   (offense)
            0x00,   // 13 Tough Skin   (defense)
            0x05,   // 14 Lucky Coin   (utility)
            0x05,   // 15 Mana Gem     (utility)
            0x00,   // 16 Ward Charm   (defense)
            0x04,   // 17 Swift Fang   (offense)
            0x05,   // 18 HuntersEye   (utility)
            0x04,   // 19 BloodSigil   (offense)
        };
        entities[idx].ai_data[1]  = item_index;
        entities[idx].sprite_tile = pickup_item_sprite(item_index);
        entities[idx].palette     = (item_index >= 10 && item_index <= 19)
            ? tint[item_index - 10] : 0x05;
        entities[idx].state_timer = 255;       // items linger longest
    }
    return idx;
}

static const u8 class_relics[5][3] = {
    { 12, 17, 19 }, // Wolfkin: PowerStone / Swift Fang / Vamp Sigil
    { 10, 16, 19 }, // Sauran: Iron Heart / Ward Charm / Vamp Sigil
    { 11, 12, 17 }, // Corvin: Speed Ring / PowerStone / Swift Fang
    { 12, 15, 16 }, // Picsean: PowerStone / Mana Gem / Ward Charm
    { 12, 17, 19 }  // Vespine: PowerStone / Swift Fang / Vamp Sigil
};

u8 pickup_farfold_relic_for_class(u8 roll) BANKED {
    u8 class_id = player.class_id;
    if (class_id >= 5) class_id = 0;
    while (roll >= 3) roll = (u8)(roll - 3);
    return class_relics[class_id][roll];
}

u8 pickup_boss_relic_for_class(void) BANKED {
    // Boss rewards are the run's guaranteed power curve, not ordinary random
    // trash drops. Each champion retains three meaningful build branches,
    // while a pure-LCK result can no longer make a hard-earned first Colossus
    // feel like it granted no immediate combat help. Values are authored
    // `items[]` indices (the same representation pickup_spawn_item uses).
    return pickup_farfold_relic_for_class(rng_range(3));
}

u8 pickup_spawn_mp(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_MP, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_ENEMY_WISP;
        entities[idx].palette     = 0x06;   // stage-glow: reads as magic
    }
    return idx;
}

#if 0
void pickup_spawn_wildcard(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_WILDCARD, x, y);
    if (idx != 0xFF) {
        entity_t *e = &entities[idx];
        e->sprite_tile = SPR_SURGE_ORB;
        e->palette = 0x06;
        e->hitbox = 0x88;
        e->state_timer = 255;
        // A different phase per drop keeps a pile from flashing in lockstep.
        e->state = (u8)(rng_next_u8() & 31);
    }
}
#endif

// Town residents are all persistent, wide collision anchors. Keeping their
// common construction here avoids six nearly identical code paths consuming
// bank-5 space while public spawn functions retain their semantic names.
static u8 pickup_spawn_resident(u8 kind, u8 sprite_tile, u8 palette,
    fix8_t x, fix8_t y) {
    u8 idx = pickup_spawn(kind, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = sprite_tile;
        entities[idx].palette = palette;
        // Larger than ordinary loot so walking up to a full-size resident is
        // an easy, forgiving interaction rather than pixel hunting.
        entities[idx].hitbox = (u8)0xCC;
        entities[idx].state_timer = 0;
    }
    return idx;
}

u8 pickup_spawn_villager(fix8_t x, fix8_t y) BANKED {
    return pickup_spawn_resident(PICKUP_VILLAGER, SPR_TOWN_RESIDENT_BIG, 0x05, x, y);
}

u8 pickup_spawn_merchant(fix8_t x, fix8_t y) BANKED {
    u8 idx;
    // A merchant owns the shared callout tile. This also repairs the OBJ slot
    // after an in-place transition from a Dread Bell combat room.
    idx = pickup_spawn_resident(PICKUP_MERCHANT, SPR_TOWN_MERCHANT_BIG, 0x04, x, y);
    if (idx != 0xFF) tiles_load_merchant_callout_sprite();
    return idx;
}

u8 pickup_spawn_smith(fix8_t x, fix8_t y) BANKED {
    return pickup_spawn_resident(PICKUP_SMITH, SPR_TOWN_ARTISAN_BIG, 0x06, x, y);
}

u8 pickup_spawn_apothecary(fix8_t x, fix8_t y) BANKED {
    return pickup_spawn_resident(PICKUP_APOTHECARY, SPR_TOWN_SAGE_BIG, 0x07, x, y);
}

u8 pickup_spawn_cartographer(fix8_t x, fix8_t y) BANKED {
    return pickup_spawn_resident(PICKUP_CARTOGRAPHER, SPR_TOWN_SAGE_BIG, 0x06, x, y);
}

u8 pickup_spawn_waykeeper(fix8_t x, fix8_t y) BANKED {
    return pickup_spawn_resident(PICKUP_WAYKEEPER, SPR_TOWN_ARTISAN_BIG, 0x06, x, y);
}

u8 pickup_spawn_lorekeeper(fix8_t x, fix8_t y) BANKED {
    return pickup_spawn_resident(PICKUP_LOREKEEPER, SPR_TOWN_SAGE_BIG, 0x05, x, y);
}

u8 pickup_spawn_bellkeeper(fix8_t x, fix8_t y) BANKED {
    return pickup_spawn_resident(PICKUP_BELLKEEPER, SPR_TOWN_ARTISAN_BIG, 0x04, x, y);
}

u8 pickup_spawn_wayfarer(u8 stage, fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn_resident(
        PICKUP_WAYFARER, SPR_TOWN_RESIDENT_BIG, 0x06, x, y);
    if (idx != 0xFF) entities[idx].ai_data[1] = stage < 13 ? stage : 12;
    return idx;
}

u8 pickup_spawn_shop_tag(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_SHOP_TAG, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_SHOP_TAG;
        entities[idx].palette = 0x05;
        entities[idx].hitbox = 0;       // visual context, never a pickup
        entities[idx].state_timer = 0;  // persistent while its ware exists
    }
    return idx;
}

static u8 pickup_is_town_resident(u8 kind) {
    return (kind >= PICKUP_VILLAGER && kind <= PICKUP_APOTHECARY)
        || kind == PICKUP_CARTOGRAPHER || kind == PICKUP_WAYKEEPER
        || kind == PICKUP_LOREKEEPER || kind == PICKUP_BELLKEEPER;
}

// These residents provide visual context (and, in the merchant/Lorekeeper
// cases, an update-time proximity cue) but no collision-time transaction.
// Keep the healer and Chartwright out of this set: their one-per-visit
// blessings are intentionally handled as explicit cases below.
static u8 pickup_is_visual_town_resident(u8 kind) {
    return kind == PICKUP_MERCHANT || kind == PICKUP_SMITH
        || kind == PICKUP_APOTHECARY || kind == PICKUP_WAYKEEPER
        || kind == PICKUP_LOREKEEPER || kind == PICKUP_BELLKEEPER
        || kind == PICKUP_WAYFARER || kind == PICKUP_COMPANION;
}

// A is intentionally contextual only inside this small proximity box. The
// player can still attack normally elsewhere in the room, while standing by
// a resident or peaceful wayfarer makes the conversation win over a stray
// turbo shot. The nearest speaker wins when a village crowd overlaps ranges.
u8 pickup_nearby_speaker(u8 *kind_out, u8 *topic_out) BANKED {
    u8 i, found = 0, best_distance = 0xFF;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        i16 dx, dy;
        u8 kind, distance;
        if (!(entities[i].flags & EF_ACTIVE)
            || entities[i].type != ENT_PICKUP) continue;
        kind = entities[i].ai_data[0];
        if (!pickup_is_town_resident(kind) && kind != PICKUP_WAYFARER)
            continue;
        dx = FIX8_TO_INT(entities[i].x) - (i16)player.x;
        dy = FIX8_TO_INT(entities[i].y) - (i16)player.y;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        if (dx > 28 || dy > 28) continue;
        distance = (u8)(dx + dy);
        if (!found || distance < best_distance) {
            found = 1;
            best_distance = distance;
            *kind_out = kind;
            *topic_out = entities[i].ai_data[1];
        }
    }
    return found;
}

u8 pickup_weapon_count(void) BANKED {
    u8 i, count = 0;
    for (i = 0; i < N_ITEMS; ++i)
        if (items[i].kind == ITEM_KIND_WEAPON) count++;
    return count;
}

u8 pickup_weapon_from_roll(u8 roll) BANKED {
    u8 i;
    for (i = 0; i < N_ITEMS; ++i) {
        if (items[i].kind != ITEM_KIND_WEAPON) continue;
        if (roll == 0) return i;
        roll--;
    }
    return 0;
}

u8 pickup_next_weapon(u8 current) BANKED {
    u8 i, found = 0, first = 0xFF;
    for (i = 0; i < N_ITEMS; ++i) {
        if (items[i].kind != ITEM_KIND_WEAPON) continue;
        if (first == 0xFF) first = i;
        if (found) return i;
        if (i == current) found = 1;
    }
    return first == 0xFF ? 0 : first;
}

u8 pickup_spawn_weapon(u8 weapon_index, fix8_t x, fix8_t y) BANKED {
    u8 idx;
    if (weapon_index >= N_ITEMS || items[weapon_index].kind != ITEM_KIND_WEAPON)
        return 0xFF;
    idx = pickup_spawn(PICKUP_WEAPON, x, y);
    if (idx != 0xFF) {
        entities[idx].ai_data[1]  = weapon_index;
        entities[idx].sprite_tile = SPR_ITEM_WEAPON;
        entities[idx].palette     = 0x04;      // red orb = weapon
        entities[idx].state       = 45;        // grace: no instant pickup
    }
    return idx;
}

u8 pickup_spawn_farfold_relic(u8 item_index, fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_FARFOLD_RELIC, x, y);
    if (idx != 0xFF) {
        entities[idx].ai_data[1] = item_index;
        entities[idx].sprite_tile = pickup_item_sprite(item_index);
        entities[idx].palette = 0x06;
        entities[idx].hitbox = (u8)0x88;
        // Optional exploration cannot be a four-second reaction test. The
        // cache orb persists until claimed or the player leaves the district.
        entities[idx].state_timer = 0;
    }
    return idx;
}

u8 pickup_spawn_choice(u8 item_index, fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_BOON_CHOICE, x, y);
    if (idx != 0xFF) {
        entities[idx].ai_data[1] = item_index;
        entities[idx].sprite_tile = pickup_item_sprite(item_index);
        // Alternate class-attuned branches remain distinguishable even when
        // both use the shared orb tile: offense glows red, sustain/utility
        // cyan. The exact mechanical name remains visible in the Pack after
        // collection, avoiding another tiny modal text screen mid-fight.
        entities[idx].palette = (item_index == 12 || item_index == 17
            || item_index == 19) ? 0x04 : 0x06;
        entities[idx].hitbox = (u8)0x88;
        entities[idx].state_timer = 0;
        entities[idx].state = 30;
    }
    return idx;
}

void pickup_spawn_boon_pair(u8 roll) BANKED {
    u8 first = pickup_farfold_relic_for_class(roll);
    u8 second = pickup_farfold_relic_for_class((u8)(roll + 1));
    // The director queues this transaction, then the room calls it only
    // after the director bank has returned. Keep all constructors local to
    // the pickup bank so completion cannot strand a sealed room.
    pickup_spawn_choice(first, FIX8(104), FIX8(120));
    pickup_spawn_choice(second, FIX8(136), FIX8(120));
}

void pickup_settle_pending_boon(void) BANKED {
    if (!room_encounter_reward_pending) return;
    pickup_spawn_boon_pair((u8)(run_state.room_counter
        + (u8)run_state.run_seed + player.class_id));
    room_encounter_reward_pending = 0;
}

#if 0
void pickup_roll_drop(fix8_t x, fix8_t y) BANKED {
    u8 r = rng_next_u8();
    // More bodies should create combat pressure, not turn every district
    // into a permanent-equipment fountain. Easy raises recovery and temporary
    // expression while keeping roughly the same relics-per-room as Normal's
    // larger population.
    if (RUN_IS_EASY()) {
        if      (r < 72)  pickup_spawn(PICKUP_HEART_HALF, x, y); // 28%
        else if (r < 179) pickup_spawn(PICKUP_COIN_1, x, y);     // 42%
        else if (r < 187)                                        // 3% relic
            pickup_spawn_item((u8)(10 + rng_range(10)), x, y);
        else if (r < 207) pickup_spawn_surge(x, y);              // 8%
        else if (r < 212) pickup_spawn_wildcard(x, y);           // 2%
        // else nothing (17%)
    } else {
        if      (r < 46)  pickup_spawn(PICKUP_HEART_HALF, x, y); // 18%
        else if (r < 161) pickup_spawn(PICKUP_COIN_1, x, y);     // 45%
        else if (r < 166)                                        // 2% relic
            pickup_spawn_item((u8)(10 + rng_range(10)), x, y);
        else if (r < 181) pickup_spawn_surge(x, y);              // 6%
        else if (r < 191) pickup_spawn_wildcard(x, y);           // 4%
        // else nothing (25%)
    }
}
#endif

// Merchant and Lorekeeper both advertise their purpose only while nearby.
// The active room chooses what tile slot 125 means (coin thought or scroll),
// so this shared timing/geometry path keeps their interaction behavior in
// sync without duplicating the same cooldown arithmetic for each resident.
static void pickup_near_callout(entity_t *e, u8 palette, u8 tile) {
    if (e->state_timer != 0) {
        e->state_timer--;
    } else {
        i16 dx = FIX8_TO_INT(e->x) - (i16)player.x;
        i16 dy = FIX8_TO_INT(e->y) - (i16)player.y;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        if (dx <= 32 && dy <= 32
            && fx_spawn(tile, palette,
                FIX8_TO_INT(e->x), FIX8_TO_INT(e->y) - 10, 45) != 0xFF)
            e->state_timer = 105; // visible 0.75s, then a short rest
    }
}

void pickup_update(entity_t *e, u8 idx) BANKED {
    if (e->ai_data[0] == PICKUP_WILDCARD) {
        // Violet/red/gold cycling is an explicit risk tell: this is neither
        // ordinary loot nor a guaranteed upgrade. It remains optional.
        e->state++;
        if ((e->state & 31) < 11) e->palette = 0x06;
        else if ((e->state & 31) < 22) e->palette = 0x04;
        else e->palette = 0x05;
    }
    // Shop wares are permanent until bought; state counts a retry delay.
    // They never magnetize (flying wares would force accidental purchases).
    if (e->ai_data[0] == PICKUP_SHOP) {
        // Keep the actual heart/relic art assigned by the shop generator.
        // Older builds overwrote every ware with the same orange sale glyph,
        // making paid stock look like broken loose currency. ai_data[4] is a
        // contact latch for the reject
        // buzz; reset it only after the player actually steps away.
        if (!aabb_overlap_player_wide(e)) e->ai_data[4] = 0;
        if (e->state > 0) e->state--;
        return;
    }
    // Hunger deliberately leaves recovery on the floor. Re-arm its one-shot
    // rejection cue only after the champion steps away, so standing on a
    // heart cannot buzz or refill the notice queue every frame.
    if (e->ai_data[0] == PICKUP_HEART_HALF
        && !aabb_overlap_player_wide(e)) e->ai_data[4] = 0;
    if (e->ai_data[0] == PICKUP_MERCHANT) {
        // The floor labels and HUD identify each price; this one small thought
        // bubble tells a nearby player that the character is actually a
        // trader. state_timer is otherwise unused by permanent residents.
        pickup_near_callout(e, 0x05, SPR_MERCHANT_CALLOUT);
        return;
    }
    if (e->ai_data[0] == PICKUP_LOREKEEPER) {
        // The arrival-only slot contains an open-scroll bubble here (rather
        // than the merchant's coin). It makes the authored lore fixture read
        // as someone worth approaching without adding a modal text screen or
        // a new interaction economy.
        pickup_near_callout(e, 0x06, SPR_MERCHANT_CALLOUT);
        return;
    }
    if (e->ai_data[0] == PICKUP_WAYFARER) {
        // Dungeon sprite slot 79 already carries a different stage-native
        // creature silhouette in each biome. A small sparkle is the neutral
        // "this one will talk" cue; slot 125 remains combat's Dread Bell.
        pickup_near_callout(e, 0x06, SPR_FX_MUZZLE);
        return;
    }
    if (pickup_is_town_resident(e->ai_data[0])) return;
    if (e->ai_data[0] == PICKUP_RIFTWELL
        || e->ai_data[0] == PICKUP_FARFOLD_RELIC
        || e->ai_data[0] == PICKUP_WAYGEAR
        || e->ai_data[0] == PICKUP_HOLLOW_RELIC) return;
    if (e->ai_data[0] == PICKUP_BOON_CHOICE) {
        // A directive can resolve while the champion stands on the nearest
        // safe reward cell. Preserve the visible two-way decision long
        // enough to step back and choose instead of auto-taking one branch.
        if (e->state) e->state--;
        return;
    }
    if (e->ai_data[0] == PICKUP_RIFT_SIGIL) return;
    if (e->ai_data[0] == PICKUP_SHOP_TAG) {
        // ai_data[1] names the ware slot this tag advertises. A sale marker
        // must vanish with sold stock rather than leaving a ghost price over
        // an empty tile (or over a later entity that reuses the slot).
        u8 ware = e->ai_data[1];
        if (ware >= MAX_ENTITIES || !(entities[ware].flags & EF_ACTIVE)
            || entities[ware].type != ENT_PICKUP
            || entities[ware].ai_data[0] != PICKUP_SHOP) {
            entity_kill(idx);
        }
        return;
    }
    // Weapon orbs: permanent, stationary, guarded by a pickup-grace timer.
    // They also require a fresh A press to trade: walking across a dropped
    // orb must never silently replace a champion's primary weapon.
    if (e->ai_data[0] == PICKUP_WEAPON) {
        if (e->state > 0) e->state--;
        return;
    }
    if (e->ai_data[7] & PICKUP_SECRET_TIMER_MARK) return;
    if (e->state_timer == 0) { entity_kill(idx); return; }
    e->state_timer--;

    // Pickups deliberately stay where they drop. The former magnet routine
    // could corrupt coordinates in the banked update path, making a visible
    // reward jump away just as the player reached it. The generous collision
    // box still makes a direct walk-over collection reliable and predictable.
}

static u8 add_capped(u8 value, u8 delta, u8 cap) {
    if (value >= cap || delta >= (u8)(cap - value)) return cap;
    return (u8)(value + delta);
}

static u8 item_would_change_stats(u8 item_idx) {
    const item_def_t *it;
    u8 k;
    if (item_idx >= N_ITEMS) return 0;
    it = &items[item_idx];
    for (k = 0; k < it->n_effects; ++k) {
        const effect_t *ef = &it->effects[k];
        if (ef->kind != EFFECT_STAT_BOOST) continue;
        if ((ef->d0 == STAT_HP && player.hp_max < HP_CAP)
            || (ef->d0 == STAT_MP && player.mp_max < 20)
            || (ef->d0 == STAT_ATK && player.atk < 15)
            || (ef->d0 == STAT_DEF && player.def < 10)
            || (ef->d0 == STAT_SPD && player.spd < 9)
            || (ef->d0 == STAT_LCK && player.lck < 10)) return 1;
    }
    return 0;
}

// Apply a generated item's StatBoost effects to the live player. Return zero
// only when a behavioral relic cannot be represented in the full Pack.
static u8 apply_item_effects(u8 item_idx) {
    const item_def_t *it;
    u8 k;
    if (item_idx >= N_ITEMS) return 0;
    it = &items[item_idx];
    // Consumables are physical charges: duplicates deliberately occupy
    // separate Pack slots and each activation removes exactly one copy.
    if (it->kind == ITEM_KIND_CONSUMABLE) {
        for (k = 0; k < INVENTORY_SLOTS; ++k) {
            if (player.inventory[k] == 0xFF) {
                player.inventory[k] = (u8)it->id;
                return 1;
            }
        }
        return 0;
    }
    // Passive relics persist for this run and remain inspectable by behavioral
    // hooks (vampirism, future on-kill/on-dash effects). Stat boosts still
    // stack, but presence-based hooks do not need duplicate IDs. Coalescing
    // copies keeps the ten passive families inside the 16-slot inventory so a
    // late guaranteed boss relic cannot apply its stats and then vanish
    // without being registered for its lasting mechanic.
    for (k = 0; k < INVENTORY_SLOTS; ++k) {
        if (player.inventory[k] == (u8)it->id) break;
    }
    if (k == INVENTORY_SLOTS) {
        for (k = 0; k < INVENTORY_SLOTS; ++k) {
            if (player.inventory[k] == 0xFF) {
                player.inventory[k] = (u8)it->id;
                break;
            }
        }
    }
    // Vampirism is presence-based. Applying its visible +ATK/+HP while
    // silently failing to store id 29 breaks the promised fifth-kill heal.
    if (k == INVENTORY_SLOTS && it->id == ITEM_ID_BLOOD_SIGIL) return 0;
    for (k = 0; k < it->n_effects; ++k) {
        const effect_t *ef = &it->effects[k];
        u8 before;
        if (ef->kind != EFFECT_STAT_BOOST) continue;
        switch (ef->d0) {
            case STAT_HP:
                before = player.hp_max;
                player.hp_max = add_capped(player.hp_max, ef->d1, HP_CAP);
                if (!STATUS_PLAYER_HEALING_BLOCKED())
                    player.hp = add_capped(player.hp, ef->d1, player.hp_max);
                hud_show_stat_gain(STAT_HP, (u8)(player.hp_max - before));
                break;
            case STAT_MP:
                before = player.mp_max;
                player.mp_max = add_capped(player.mp_max, ef->d1, 20);
                player.mp = add_capped(player.mp, ef->d1, player.mp_max);
                hud_show_stat_gain(STAT_MP, (u8)(player.mp_max - before));
                break;
            case STAT_ATK:
                before = player.atk;
                player.atk = add_capped(player.atk, ef->d1, 15);
                hud_show_stat_gain(STAT_ATK, (u8)(player.atk - before));
                break;
            case STAT_DEF:
                before = player.def;
                player.def = add_capped(player.def, ef->d1, 10);
                hud_show_stat_gain(STAT_DEF, (u8)(player.def - before));
                break;
            case STAT_SPD:
                before = player.spd;
                player.spd = add_capped(player.spd, ef->d1, 9);
                hud_show_stat_gain(STAT_SPD, (u8)(player.spd - before));
                break;
            case STAT_LCK:
                before = player.lck;
                player.lck = add_capped(player.lck, ef->d1, 10);
                hud_show_stat_gain(STAT_LCK, (u8)(player.lck - before));
                break;
        }
    }
    hud_redraw_all();
    projectile_sync_player_relics();
    room_refresh_player_appearance(1);
    return 1;
}

// Loose procedural pickups intentionally store an items[] index in their
// entity payload. Merchant stock is semantic content, however: resolve its
// stable item ID at the boundary instead of coupling shop behavior to table
// order. Missing content becomes a harmless no-op rather than applying an
// unrelated relic after a data reorder.
static u8 apply_item_effects_by_id(u16 item_id) {
    u8 item_idx;
    for (item_idx = 0; item_idx < N_ITEMS; ++item_idx) {
        if (items[item_idx].id == item_id) {
            return apply_item_effects(item_idx);
        }
    }
    return 0;
}

static u8 player_has_item(u8 item_id) {
    u8 i;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == item_id) return 1;
    return 0;
}

static u8 player_has_inventory_space(void) {
    u8 i;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == 0xFF) return 1;
    return 0;
}

static void grant_special_item(u8 item_id) {
    u8 i;
    if (player_has_item(item_id)) return;
    for (i = 0; i < INVENTORY_SLOTS; ++i) {
        if (player.inventory[i] == 0xFF) {
            player.inventory[i] = item_id;
            projectile_sync_player_relics();
            room_refresh_player_appearance(1);
            return;
        }
    }
}

u8 pickup_check_player_collision(void) BANKED {
    u8 i;
    u8 any = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        if (entities[i].type != ENT_PICKUP)   continue;
        if (aabb_overlap_player_wide(&entities[i])) {
            // Permanent visual residents never vanish on contact and have no
            // purchase/blessing effect. Share this result instead of keeping
            // one identical collision branch per civic silhouette.
            if (pickup_is_visual_town_resident(entities[i].ai_data[0])) {
                any = 1;
                continue;
            }
            if (entities[i].ai_data[0] == PICKUP_BOON_CHOICE
                && entities[i].state) {
                any = 1;
                continue;
            }
            switch (entities[i].ai_data[0]) {
                case PICKUP_HEART_HALF:
                    // A full-health walk-over used to consume the heart and
                    // play its happy chime without changing the HUD. It read
                    // as a broken pickup. Moon Flask deliberately changes
                    // that resource rule: surplus recovery distills into one
                    // MP, making old heart drops tactically useful to every
                    // champion. If both gauges are full, leave it in place.
                    if (STATUS_PLAYER_HEALING_BLOCKED()) {
                        if (!entities[i].ai_data[4]) {
                            entities[i].ai_data[4] = 1;
                            hud_show_healing_blocked();
                            sfx_play(SFX_WEAK);
                        }
                        any = 1;
                        continue;
                    }
                    if (player.hp >= player.hp_max) {
                        if (!player_has_item(ITEM_ID_MOON_FLASK)
                            || player.mp >= player.mp_max) continue;
                        player.mp++;
                        hud_redraw_mp();
                        sfx_play(SFX_HEART);
                        break;
                    }
                    player.hp = (u8)(player.hp + 1);
                    if (player.hp > player.hp_max) player.hp = player.hp_max;
                    hud_redraw_hp();
                    sfx_play(SFX_HEART);
                    break;
                case PICKUP_COIN_1:
                    // Match capped hearts/MP: a full purse must not eat a
                    // visible coin, play the happy chime, and leave the HUD
                    // unchanged. Keep it available until the player spends.
                    if (player.coins >= COIN_CAP) continue;
                    player.coins++;
                    hud_redraw_coins();
                    sfx_play(SFX_COIN);
                    break;
                case PICKUP_COIN_5:
                    if (player.coins >= COIN_CAP) continue;
                    player.coins = (u16)(player.coins + 5);
                    if (player.coins > COIN_CAP) player.coins = COIN_CAP;
                    hud_redraw_coins();
                    sfx_play(SFX_COIN);
                    break;
                case PICKUP_ITEM:
                    if (!apply_item_effects(entities[i].ai_data[1])) {
                        any = 1;
                        continue;
                    }
                    // Permanent build growth has a forged relic voice; hearts,
                    // currency, MP, Sigils, and temporary Surges each differ.
                    sfx_play_reward(SFX_REWARD_RELIC);
                    break;
                case PICKUP_FARFOLD_RELIC:
                    if (!apply_item_effects(entities[i].ai_data[1])) {
                        any = 1;
                        continue;
                    }
                    sfx_play_reward(SFX_REWARD_RELIC);
                    run_state.dungeon_phase |= RUN_FARFOLD_CACHE_BIT;
                    break;
                case PICKUP_BOON_CHOICE: {
                    u8 other;
                    if (!apply_item_effects(entities[i].ai_data[1])) {
                        any = 1;
                        continue;
                    }
                    // The room offers a build decision, not two automatic
                    // stat drops. Retire the sibling before the common tail
                    // removes the selected orb.
                    for (other = 0; other < MAX_ENTITIES; ++other) {
                        if (other != i
                            && (entities[other].flags & EF_ACTIVE)
                            && entities[other].type == ENT_PICKUP
                            && entities[other].ai_data[0]
                                == PICKUP_BOON_CHOICE)
                            entity_kill(other);
                    }
                    sfx_play_reward(SFX_REWARD_RELIC);
                    break;
                }
                case PICKUP_MP:
                    // Match the heart rule above: consuming a full-MP wisp
                    // with a cheerful chime but no visible HUD change reads
                    // as a broken pickup. Leave it available until it can
                    // actually restore one point.
                    if (player.mp >= player.mp_max) continue;
                    player.mp++;
                    hud_redraw_mp();
                    sfx_play_reward(SFX_REWARD_MAGIC);
                    break;
                case PICKUP_SURGE:
                    room_start_weapon_surge();
                    break;
                case PICKUP_WILDCARD: {
                    pickup_resolve_wildcard();
#if 0
                    u8 fate = (u8)rng_range(8);
                    if (fate == 0) {
                        u8 before = player.atk;
                        player.atk = add_capped(player.atk, 1, 15);
                        if (player.atk != before)
                            hud_show_stat_gain(STAT_ATK, 1);
                        else {
                            player.coins = (u16)(player.coins + 15);
                            if (player.coins > COIN_CAP) player.coins = COIN_CAP;
                            hud_redraw_coins();
                        }
                        sfx_play_reward(SFX_REWARD_RELIC);
                    } else if (fate == 1) {
                        curse_cleanse();
                        player.hp = player.hp_max;
                        player.mp = player.mp_max;
                        hud_redraw_all();
                        sfx_play_reward(SFX_REWARD_MAGIC);
                    } else if (fate == 2) {
                        player.coins = (u16)(player.coins + 25);
                        if (player.coins > COIN_CAP) player.coins = COIN_CAP;
                        hud_redraw_coins();
                        sfx_play_reward(SFX_REWARD_PURCHASE);
                    } else if (fate == 3) {
                        if (player.curse_flags) curse_cleanse();
                        else {
                            u8 before = player.lck;
                            player.lck = add_capped(player.lck, 1, 10);
                            hud_show_stat_gain(STAT_LCK,
                                (u8)(player.lck - before));
                            sfx_play_reward(SFX_REWARD_RELIC);
                        }
                    } else if (fate == 4)
                        curse_apply(CURSE_FRAIL, 0, 0);
                    else if (fate == 5)
                        curse_apply(CURSE_MISFORTUNE, 0, 0);
                    else if (fate == 6)
                        curse_apply(CURSE_DULL, 6, 0);
                    else curse_apply(CURSE_HUNGER, 6, 0);
#endif
                    break;
                }
                case PICKUP_RIFT_SIGIL:
                    run_state.rift_sigils |= RUN_STAGE_SIGIL_BIT(run_state.bosses_beaten);
                    sfx_play_reward(SFX_REWARD_SIGIL);
                    room_start_major_reward(PICKUP_RIFT_SIGIL,
                        run_state.bosses_beaten);
                    break;
                case PICKUP_WAYGEAR: {
                    u8 gear = entities[i].ai_data[1];
                    if (!waygear_grant(gear)) {
                        any = 1;
                        continue;
                    }
                    // Traversal gear changes the shape of the whole
                    // Riftwild route. Give it the same protected two-second
                    // raised-arm ceremony as a dungeon Sigil instead of
                    // letting this progression beat vanish under the hero.
                    room_start_major_reward(PICKUP_WAYGEAR, gear);
                    break;
                }
                case PICKUP_HOLLOW_RELIC: {
                    u8 item_id = entities[i].ai_data[1];
                    if (!riftwild_claim_hollow_relic(item_id,
                            entities[i].ai_data[2])) {
                        any = 1;
                        continue;
                    }
                    sfx_play_reward(SFX_REWARD_RELIC);
                    room_start_major_reward(PICKUP_HOLLOW_RELIC, item_id);
                    break;
                }
                case PICKUP_WEAPON: {
                    // A deliberate A press trades weapons. The dropped old
                    // weapon receives grace so a confirmation press cannot
                    // immediately ping-pong between the two orbs.
                    u8 old_w = player.starter_weapon;
                    if (entities[i].state > 0) { any = 1; continue; }
                    if (!(input_pressed & J_A)) { any = 1; continue; }
                    player.starter_weapon = entities[i].ai_data[1];
                    room_refresh_player_appearance(1);
                    if (old_w < N_ITEMS && items[old_w].kind == ITEM_KIND_WEAPON) {
                        pickup_spawn_weapon(old_w, entities[i].x, entities[i].y);
                    }
                    // room_refresh_player_appearance already plays the forged
                    // equipment cue for a real weapon change.
                    break;
                }
                case PICKUP_SHOP: {
                    // Walk into a ware to buy it. Not enough coins → error
                    // beep with a retry delay so it doesn't spam.
                    u8 price = entities[i].ai_data[2];
                    u8 ware = entities[i].ai_data[1];
                    hud_show_offer(entities[i].ai_data[1], price);
                    // Unique contracts cannot be bought twice, and Glass
                    // Fang must always collect its promised one-heart stake.
                    // Every paid transaction must also have somewhere to put
                    // a persistent relic; otherwise the old code took the
                    // coins, erased the ware, and silently delivered nothing.
                    if ((ware == WARE_PHOENIX
                            && player_has_item(ITEM_ID_PHOENIX_THREAD))
                        || (ware == WARE_ECHO
                            && player_has_item(ITEM_ID_ECHO_PRISM))
                        || (ware == WARE_RICOCHET
                            && player_has_item(ITEM_ID_RICOCHET_RUNE))
                        || (ware == WARE_THORN
                            && player_has_item(ITEM_ID_THORN_CROWN))
                        || (ware == WARE_DRUM
                            && player_has_item(ITEM_ID_WAR_DRUM))
                        || (ware == WARE_FLASK
                            && player_has_item(ITEM_ID_MOON_FLASK))
                        || (ware == WARE_BLAST
                            && player_has_item(ITEM_ID_BLAST_SEED))
                        || (ware == WARE_BOOMERANG
                            && player_has_item(ITEM_ID_BOOMERANG))
                        || (ware == WARE_GLASS && player.hp_max <= 2)
                        || (ware == WARE_HEART
                            && (player.hp >= player.hp_max
                                || STATUS_PLAYER_HEALING_BLOCKED()))
                        || (ware == WARE_ITEM
                            && !item_would_change_stats(entities[i].ai_data[3]))
                        || (ware == WARE_BIG && player.hp_max >= HP_CAP)
                        || (ware == WARE_FORGE && player.atk >= 15)
                        || (ware == WARE_RUNE && player.mp_max >= 20)
                        || (ware == WARE_VAMP && player.atk >= 15
                            && player.hp_max >= HP_CAP)
                        || (ware == WARE_VAMP
                            && !player_has_item(ITEM_ID_BLOOD_SIGIL)
                            && !player_has_inventory_space())
                        || (ware == WARE_CHART
                            && (RUN_ROOM_IS_TOWN(run_state.room_counter)
                                ? (run_state.next_dungeon_reveal == 0xFF
                                    && run_state.next_dungeon_reveal_hi == 0xFF
                                    && run_state.next_dungeon_reveal_xhi == 0xFF
                                    && run_state.next_dungeon_reveal_xxhi == 0x3F)
                                : (run_state.dungeon_seen == 0xFF
                                    && run_state.dungeon_seen_hi == 0xFF
                                    && run_state.dungeon_seen_xhi == 0xFF
                                    && run_state.dungeon_seen_xxhi == 0x3F)))
                        || ((ware == WARE_GLASS || ware == WARE_PHOENIX
                                || ware == WARE_ECHO || ware == WARE_RICOCHET
                                || ware == WARE_THORN || ware == WARE_DRUM
                                || ware == WARE_FLASK || ware == WARE_BLAST
                                || ware == WARE_BOOMERANG)
                            && !player_has_inventory_space())) {
                        if (entities[i].ai_data[4] == 0) {
                            sfx_play(SFX_HURT);
                            entities[i].ai_data[4] = 1;
                        }
                        any = 1;
                        continue;
                    }
                    if (player.coins >= price) {
                        player.coins = (u16)(player.coins - price);
                        hud_redraw_coins();
                        sfx_play_reward(SFX_REWARD_PURCHASE);
                        switch (entities[i].ai_data[1]) {
                            case WARE_HEART:
                                player.hp = (u8)(player.hp + 2);
                                if (player.hp > player.hp_max) player.hp = player.hp_max;
                                hud_redraw_hp();
                                break;
                            case WARE_ITEM:
                                apply_item_effects(entities[i].ai_data[3]);
                                break;
                            case WARE_BIG:
                                apply_item_effects_by_id(ITEM_ID_IRON_HEART);
                                break;
                            case WARE_FORGE:
                                apply_item_effects_by_id(ITEM_ID_POWER_STONE);
                                break;
                            case WARE_RUNE:
                                apply_item_effects_by_id(ITEM_ID_MANA_GEM);
                                break;
                            case WARE_VAMP:
                                apply_item_effects_by_id(ITEM_ID_BLOOD_SIGIL);
                                break;
                            case WARE_CHART:
                                // Full route knowledge is deliberately a
                                // one-dungeon service: coins buy planning
                                // power without permanently removing fog.
                                // Town charts queue the route ahead; a chart
                                // bought from a dungeon merchant must reveal
                                // the active route while it is still useful.
                                if (RUN_ROOM_IS_TOWN(run_state.room_counter)) {
                                    run_state.next_dungeon_reveal = 0xFF;
                                    run_state.next_dungeon_reveal_hi = 0xFF;
                                    run_state.next_dungeon_reveal_xhi = 0xFF;
                                    run_state.next_dungeon_reveal_xxhi = 0x3F;
                                } else {
                                    run_state.dungeon_seen = 0xFF;
                                    run_state.dungeon_seen_hi = 0xFF;
                                    run_state.dungeon_seen_xhi = 0xFF;
                                    run_state.dungeon_seen_xxhi = 0x3F;
                                }
                                break;
                            case WARE_WEAPON: {
                                u8 weapon = entities[i].ai_data[3];
                                // Unlike a loose dungeon orb this is a paid
                                // merchant trade: retain the new A weapon and
                                // do not scatter the old one back on the same
                                // counter for an accidental free re-swap.
                                if (weapon < N_ITEMS
                                    && items[weapon].kind == ITEM_KIND_WEAPON) {
                                    player.starter_weapon = weapon;
                                    room_refresh_player_appearance(1);
                                }
                                break;
                            }
                            case WARE_SURGE:
                                room_start_weapon_surge();
                                break;
                            case WARE_GLASS:
                            {
                                u8 old_atk = player.atk;
                                u8 old_spd = player.spd;
                                player.atk = add_capped(player.atk, 2, 15);
                                player.spd = add_capped(player.spd, 1, 9);
                                hud_show_stat_gain(STAT_ATK,
                                    (u8)(player.atk - old_atk));
                                hud_show_stat_gain(STAT_SPD,
                                    (u8)(player.spd - old_spd));
                                grant_special_item(ITEM_ID_GLASS_FANG);
                                player.hp_max = (u8)(player.hp_max - 2);
                                if (player.hp > player.hp_max)
                                    player.hp = player.hp_max;
                                hud_redraw_hp();
                                break;
                            }
                            case WARE_PHOENIX:
                                grant_special_item(ITEM_ID_PHOENIX_THREAD);
                                break;
                            case WARE_ASCEND:
                                player.mp = player.mp_max;
                                hud_redraw_mp();
                                room_start_weapon_surge();
                                break;
                            case WARE_ECHO:
                                grant_special_item(ITEM_ID_ECHO_PRISM);
                                break;
                            case WARE_RICOCHET:
                                grant_special_item(ITEM_ID_RICOCHET_RUNE);
                                break;
                            case WARE_THORN:
                                grant_special_item(ITEM_ID_THORN_CROWN);
                                break;
                            case WARE_DRUM:
                                grant_special_item(ITEM_ID_WAR_DRUM);
                                break;
                            case WARE_FLASK:
                                grant_special_item(ITEM_ID_MOON_FLASK);
                                break;
                            case WARE_BLAST:
                                grant_special_item(ITEM_ID_BLAST_SEED);
                                break;
                            case WARE_BOOMERANG:
                                grant_special_item(ITEM_ID_BOOMERANG);
                                hud_show_boomerang();
                                break;
                        }
                        entity_kill(i);
                    } else if (entities[i].ai_data[4] == 0) {
                        sfx_play(SFX_HURT);
                        entities[i].ai_data[4] = 1; // once until contact ends
                    }
                    any = 1;
                    continue;
                }
                case PICKUP_VILLAGER:
                    // Town healing is embodied by a resident instead of
                    // firing invisibly on room entry. State prevents chime
                    // spam while the player remains in contact.
                    if (entities[i].state == 0) {
                        status_player_cure();
                        player.hp = player.hp_max;
                        player.mp = player.mp_max;
                        player.iframes = 90;
                        entities[i].state = 1;
                        entities[i].palette = 0x06;
                        hud_redraw_all();
                        sfx_play(SFX_HEART);
                        status_player_apply(QSTATUS_REGEN, 90);
                    }
                    any = 1;
                    continue;
                case PICKUP_CARTOGRAPHER:
                    // One free town blessing: scout the first two chambers
                    // of the route ahead. It must be stored for the next
                    // dungeon; dungeon_seen belongs to the current screen
                    // and is reset at the north gate.
                    if (entities[i].state == 0) {
                        run_state.next_dungeon_reveal |= 0x03;
                        entities[i].state = 1;
                        entities[i].palette = 0x02;
                        sfx_play_reward(SFX_REWARD_MAGIC);
                    }
                    any = 1;
                    continue;
                case PICKUP_RIFTWELL:
                    // A Riftwell is the one fixed post-boss refuge in each
                    // Riftwild crossing. Two hearts are enough to turn a
                    // battered boss clear into a recoverable expedition,
                    // without replacing the later town healer or making the
                    // landmark farmable. Leave it lit at full resources so
                    // it never pretends to grant an invisible reward.
                    if (player.hp >= player.hp_max && player.mp >= player.mp_max
                        && player_status_kind == QSTATUS_NONE)
                        continue;
                    status_player_cure();
                    player.hp = add_capped(player.hp, 4, player.hp_max);
                    player.mp = add_capped(player.mp, 2, player.mp_max);
                    run_state.riftwild_flags |= RIFT_REGION_WELL_USED_BIT;
                    hud_redraw_all();
                    sfx_play_reward(SFX_REWARD_MAGIC);
                    status_player_apply(QSTATUS_REGEN, 60);
                    break;
            }
            entity_kill(i);
            any = 1;
        }
    }
    return any;
}
