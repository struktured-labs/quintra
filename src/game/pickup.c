#pragma bank 5
#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "core/rng.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

u8 pickup_spawn(u8 kind, fix8_t x, fix8_t y) BANKED {
    u8 idx = entity_spawn(ENT_PICKUP);
    if (idx == 0xFF) return 0xFF;
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
        entities[idx].sprite_tile = SPR_ITEM_ORB;
        entities[idx].palette     = (item_index >= 10 && item_index <= 19)
            ? tint[item_index - 10] : 0x05;
        entities[idx].state_timer = 255;       // items linger longest
    }
    return idx;
}

u8 pickup_spawn_mp(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_MP, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_ENEMY_WISP;
        entities[idx].palette     = 0x06;   // stage-glow: reads as magic
    }
    return idx;
}

u8 pickup_spawn_villager(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_VILLAGER, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_VILLAGER;
        entities[idx].palette = 0x05;
        entities[idx].hitbox = (u8)0x88;
        entities[idx].state_timer = 0;
    }
    return idx;
}

u8 pickup_spawn_merchant(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_MERCHANT, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_MERCHANT;
        entities[idx].palette = 0x04;
        entities[idx].hitbox = (u8)0x88;
        entities[idx].state_timer = 0;
    }
    return idx;
}

u8 pickup_spawn_smith(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_SMITH, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_SMITH;
        entities[idx].palette = 0x06;
        entities[idx].hitbox = (u8)0x88;
        entities[idx].state_timer = 0;
    }
    return idx;
}

u8 pickup_spawn_apothecary(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_APOTHECARY, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_APOTHECARY;
        entities[idx].palette = 0x07;
        entities[idx].hitbox = (u8)0x88;
        entities[idx].state_timer = 0;
    }
    return idx;
}

u8 pickup_spawn_cartographer(fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_CARTOGRAPHER, x, y);
    if (idx != 0xFF) {
        entities[idx].sprite_tile = SPR_CARTOGRAPHER;
        entities[idx].palette = 0x06;
        entities[idx].hitbox = (u8)0x88;
        entities[idx].state_timer = 0;
    }
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
        || kind == PICKUP_CARTOGRAPHER;
}

// Context, not a purchase: reveal the nearest ware's price before the player
// touches it. This makes the merchant's offer legible without a costly modal
// screen or an accidental walk-into purchase.
u8 pickup_nearby_shop_price(u8 *price_out) BANKED {
    u8 i, found = 0, best_distance = 0xFF;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        i16 dx, dy;
        u8 distance;
        if (!(entities[i].flags & EF_ACTIVE) || entities[i].type != ENT_PICKUP
            || entities[i].ai_data[0] != PICKUP_SHOP) continue;
        dx = FIX8_TO_INT(entities[i].x) - (i16)player.x;
        dy = FIX8_TO_INT(entities[i].y) - (i16)player.y;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        if (dx > 32 || dy > 32) continue;
        distance = (u8)(dx + dy);
        if (!found || distance < best_distance) {
            best_distance = distance;
            *price_out = entities[i].ai_data[2];
            found = 1;
        }
    }
    return found;
}

u8 pickup_spawn_weapon(u8 weapon_index, fix8_t x, fix8_t y) BANKED {
    u8 idx = pickup_spawn(PICKUP_WEAPON, x, y);
    if (idx != 0xFF) {
        entities[idx].ai_data[1]  = weapon_index;
        entities[idx].sprite_tile = SPR_ITEM_ORB;
        entities[idx].palette     = 0x04;      // red orb = weapon
        entities[idx].state       = 45;        // grace: no instant pickup
    }
    return idx;
}

void pickup_roll_drop(fix8_t x, fix8_t y) BANKED {
    u8 r = rng_next_u8();
    if      (r < 0x40) pickup_spawn(PICKUP_HEART_HALF, x, y);   // 25%
    else if (r < 0xB3) pickup_spawn(PICKUP_COIN_1,     x, y);   // 45%
    else if (r < 0xCC) {                                        // 10%: item
        // Passive stat-boosters live at items[] indices 10..19
        pickup_spawn_item((u8)(10 + rng_range(10)), x, y);
    }
    // else: no drop (20%)
}

void pickup_update(entity_t *e, u8 idx) BANKED {
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
    if (pickup_is_town_resident(e->ai_data[0])) return;
    if (e->ai_data[0] == PICKUP_RIFT_SIGIL) return;
    if (e->ai_data[0] == PICKUP_SHOP_TAG) return;
    // Weapon orbs: permanent, stationary, guarded by a pickup-grace timer
    // (the swap drops your old weapon underfoot — without the grace you'd
    // ping-pong between the two forever).
    if (e->ai_data[0] == PICKUP_WEAPON) {
        if (e->state > 0) e->state--;
        return;
    }
    if (e->state_timer == 0) { entity_kill(idx); return; }
    e->state_timer--;

    // Magnetism: within a ~28px box of the player, drift 1px/frame toward
    // them (2px when very close) — loot hoovers itself up, Zelda-style.
    {
        i16 ex = FIX8_TO_INT(e->x);
        i16 ey = FIX8_TO_INT(e->y);
        i16 dx = (i16)player.x - ex;
        i16 dy = (i16)player.y - ey;
        i16 adx = dx < 0 ? -dx : dx;
        i16 ady = dy < 0 ? -dy : dy;
        if (adx < 28 && ady < 28) {
            u8 step = (adx < 12 && ady < 12) ? 2 : 1;
            if (dx > 0)      ex += step;
            else if (dx < 0) ex -= step;
            if (dy > 0)      ey += step;
            else if (dy < 0) ey -= step;
            e->x = FIX8(ex);
            e->y = FIX8(ey);
        }
    }
}

static u8 add_capped(u8 value, u8 delta, u8 cap) {
    if (value >= cap || delta >= (u8)(cap - value)) return cap;
    return (u8)(value + delta);
}

// Apply a generated item's StatBoost effects to the live player.
static void apply_item_effects(u8 item_idx) {
    const item_def_t *it;
    u8 k;
    if (item_idx >= N_ITEMS) return;
    it = &items[item_idx];
    // Passive relics persist for this run and remain inspectable by behavioral
    // hooks (vampirism, future on-kill/on-dash effects). Stat boosts still
    // stack; record each copy while inventory capacity remains.
    for (k = 0; k < INVENTORY_SLOTS; ++k) {
        if (player.inventory[k] == 0xFF) {
            player.inventory[k] = (u8)it->id;
            break;
        }
    }
    for (k = 0; k < it->n_effects; ++k) {
        const effect_t *ef = &it->effects[k];
        if (ef->kind != EFFECT_STAT_BOOST) continue;
        switch (ef->d0) {
            case STAT_HP:
                player.hp_max = add_capped(player.hp_max, ef->d1, HP_CAP);
                player.hp = add_capped(player.hp, ef->d1, player.hp_max);
                break;
            case STAT_MP:
                player.mp_max = add_capped(player.mp_max, ef->d1, 20);
                player.mp = add_capped(player.mp, ef->d1, player.mp_max);
                break;
            case STAT_ATK:
                player.atk = add_capped(player.atk, ef->d1, 15);
                break;
            case STAT_DEF:
                player.def = add_capped(player.def, ef->d1, 10);
                break;
            case STAT_SPD:
                player.spd = add_capped(player.spd, ef->d1, 9);
                break;
            case STAT_LCK:
                player.lck = add_capped(player.lck, ef->d1, 10);
                break;
        }
    }
    hud_redraw_all();
}

u8 pickup_check_player_collision(void) BANKED {
    u8 i;
    u8 any = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        if (entities[i].type != ENT_PICKUP)   continue;
        if (aabb_overlap_player_wide(&entities[i])) {
            switch (entities[i].ai_data[0]) {
                case PICKUP_HEART_HALF:
                    if (player.hp < player.hp_max) {
                        player.hp = (u8)(player.hp + 1);
                        if (player.hp > player.hp_max) player.hp = player.hp_max;
                        hud_redraw_hp();
                    }
                    sfx_play(SFX_HEART);
                    break;
                case PICKUP_COIN_1:
                    if (player.coins < 999) player.coins++;
                    hud_redraw_coins();
                    sfx_play(SFX_COIN);
                    break;
                case PICKUP_COIN_5:
                    player.coins = (u16)(player.coins + 5);
                    if (player.coins > 999) player.coins = 999;
                    hud_redraw_coins();
                    sfx_play(SFX_COIN);
                    break;
                case PICKUP_ITEM:
                    apply_item_effects(entities[i].ai_data[1]);
                    sfx_play(SFX_HEART);
                    break;
                case PICKUP_MP:
                    if (player.mp < player.mp_max) {
                        player.mp++;
                        hud_redraw_mp();
                    }
                    sfx_play(SFX_HEART);
                    break;
                case PICKUP_RIFT_SIGIL:
                    run_state.rift_sigils |= RUN_STAGE_SIGIL_BIT(run_state.bosses_beaten);
                    sfx_play(SFX_CLEAR);
                    break;
                case PICKUP_WEAPON: {
                    // Swap A-weapons: take the orb's, drop yours in its
                    // place (with grace so it isn't instantly re-grabbed).
                    u8 old_w = player.starter_weapon;
                    if (entities[i].state > 0) { any = 1; continue; }
                    player.starter_weapon = entities[i].ai_data[1];
                    sfx_play(SFX_DOOR);
                    if (old_w < 5) {
                        pickup_spawn_weapon(old_w, entities[i].x, entities[i].y);
                    }
                    break;
                }
                case PICKUP_SHOP: {
                    // Walk into a ware to buy it. Not enough coins → error
                    // beep with a retry delay so it doesn't spam.
                    u8 price = entities[i].ai_data[2];
                    hud_show_offer(price);
                    if (player.coins >= price) {
                        player.coins = (u16)(player.coins - price);
                        hud_redraw_coins();
                        switch (entities[i].ai_data[1]) {
                            case WARE_HEART:
                                player.hp = (u8)(player.hp + 2);
                                if (player.hp > player.hp_max) player.hp = player.hp_max;
                                hud_redraw_hp();
                                break;
                            case WARE_ITEM:
                                apply_item_effects((u8)(10 + rng_range(10)));
                                break;
                            case WARE_BIG:
                                apply_item_effects(10);   // Iron Heart
                                break;
                            case WARE_FORGE:
                                apply_item_effects(12);   // Power Stone
                                break;
                            case WARE_RUNE:
                                apply_item_effects(15);   // Mana Gem
                                break;
                        }
                        sfx_play(SFX_COIN);
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
                        player.hp = player.hp_max;
                        player.mp = player.mp_max;
                        player.iframes = 90;
                        entities[i].state = 1;
                        entities[i].palette = 0x06;
                        hud_redraw_all();
                        sfx_play(SFX_HEART);
                    }
                    any = 1;
                    continue;
                case PICKUP_MERCHANT:
                    // Visual anchor for the stall; wares own purchases.
                    any = 1;
                    continue;
                case PICKUP_SMITH:
                    // Visual anchor for the forge; its Power Stone owns the sale.
                    any = 1;
                    continue;
                case PICKUP_APOTHECARY:
                    // Visual anchor for the rune counter; the Mana Gem owns the sale.
                    any = 1;
                    continue;
                case PICKUP_CARTOGRAPHER:
                    // One free town blessing: reveal the first two chambers
                    // of the route ahead. This preserves a fogged procgen
                    // map while making villages tactically meaningful.
                    if (entities[i].state == 0) {
                        run_state.dungeon_seen |= 0x03;
                        entities[i].state = 1;
                        entities[i].palette = 0x02;
                        sfx_play(SFX_CLEAR);
                    }
                    any = 1;
                    continue;
            }
            entity_kill(i);
            any = 1;
        }
    }
    return any;
}
