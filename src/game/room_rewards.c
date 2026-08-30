#pragma bank 14
// Cold major-reward and secret-vault transactions. Keeping entity scans and
// one-shot VRAM uploads out of bank 1 protects the 60 Hz room/combat budget.

#include <gb/gb.h>

#include "audio/music.h"
#include "audio/sfx.h"
#include "core/types.h"
#include "game/dialog.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/room.h"
#include "game/waygear.h"
#include "render/hud.h"
#include "render/tiles.h"

#define ROOM_MAJOR_REWARD_FRAMES 120
#define ROOM_SECRET_LOOT_FRAMES  720u

static u8 room_secret_loot_second;

void room_start_death(void) BANKED {
    // Every lethal source shares one readable fall beat. Keeping this cold
    // presentation transaction outside bank 1 also protects combat headroom.
    death_timer = 50;
    player.iframes = 50;
    sfx_play(SFX_DEATH);
    music_stop();
    room_shake(2, 30);
    fx_spawn(SPR_FX_IMPACT, 2, (i16)player.x,     (i16)player.y,     16);
    fx_spawn(SPR_FX_IMPACT, 2, (i16)player.x - 8, (i16)player.y - 8, 24);
    fx_spawn(SPR_FX_IMPACT, 2, (i16)player.x + 8, (i16)player.y + 8, 32);
    hud_redraw_hp();
}

void room_start_major_reward(u8 kind, u8 topic) BANKED {
    u8 class_id = player.class_id < 5 ? player.class_id : 0;
    dialog_prepare_reward(kind, topic);
    if (kind == PICKUP_WAYGEAR && topic < WAYGEAR_COUNT)
        room_major_reward_icon = (u8)(SPR_WAYGEAR_GLOVE + topic);
    else if (kind == PICKUP_HOLLOW_RELIC)
        room_major_reward_icon = topic == ITEM_ID_BLAST_SEED
            ? SPR_ITEM_BLAST_SEED : topic == ITEM_ID_RIFT_LENS
            ? SPR_ITEM_RIFT_LENS : SPR_ITEM_MIRROR_SHARD;
    else room_major_reward_icon = SPR_ITEM_RIFT_SIGIL;
    room_major_reward_pending = ROOM_MAJOR_REWARD_FRAMES;
    tiles_load_class_claim_sprite(class_id);
    room_player_pose_base = SPR_CLASS_BASE;
    room_player_pose_locked = 1;
    player.anim_frame = 0;
    // Pickup collision resolves before hostile contact in combat_resolve().
    // Protect the claim frame so the ceremony cannot become a same-frame KO.
    if (player.iframes < 90) player.iframes = 90;
}

static u8 room_secret_loot_kind(u8 kind) {
    return kind == PICKUP_HEART_HALF || kind == PICKUP_COIN_1
        || kind == PICKUP_COIN_5 || kind == PICKUP_ITEM
        || kind == PICKUP_MP || kind == PICKUP_SURGE
        || kind == PICKUP_WEAPON;
}

void room_begin_secret_loot_timer(void) BANKED {
    u8 i, found = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)
            || entities[i].type != ENT_PICKUP
            || !room_secret_loot_kind(entities[i].ai_data[0])) continue;
        entities[i].ai_data[7] |= PICKUP_SECRET_TIMER_MARK;
        // One visible room clock owns expiry. Individual u8 timers used to
        // remove early pieces while the player was still opening the ring.
        entities[i].state_timer = 0;
        found = 1;
    }
    if (found) {
        room_secret_loot_timer = ROOM_SECRET_LOOT_FRAMES;
        room_secret_loot_second = 12;
    }
}

void room_update_secret_loot_timer(void) BANKED {
    u8 i, found = 0;
    u8 seconds;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE)
            && entities[i].type == ENT_PICKUP
            && (entities[i].ai_data[7] & PICKUP_SECRET_TIMER_MARK)) {
            found = 1;
            break;
        }
    }
    if (!found) {
        room_secret_loot_timer = 0;
        hud_clear_loot_timer();
        return;
    }
    room_secret_loot_timer--;
    seconds = (u8)((room_secret_loot_timer + 59u) / 60u);
    if (seconds != room_secret_loot_second) {
        room_secret_loot_second = seconds;
        sfx_play(SFX_TICK);
    }
    if (room_secret_loot_timer) return;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE)
            && entities[i].type == ENT_PICKUP
            && (entities[i].ai_data[7] & PICKUP_SECRET_TIMER_MARK))
            entity_kill(i);
    }
    hud_clear_loot_timer();
}
