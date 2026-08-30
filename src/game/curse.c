#pragma bank 13

#include <gb/gb.h>
#include <gbdk/console.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/curse.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/room.h"
#include "game/status.h"
#include "render/hud.h"
#include "render/text.h"
#include "render/tiles.h"

static u8 has_ward_charm(void) {
    u8 i;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == ITEM_ID_WARD_CHARM) return 1;
    return 0;
}

u8 curse_apply(u8 kind, u8 rooms, u8 monster_source) BANKED {
    if (!(kind & (CURSE_FRAIL | CURSE_MISFORTUNE
            | CURSE_DULL | CURSE_HUNGER))) return 0;

    // Ward Charm is now a true ward, not merely a generically strong relic:
    // hostile curse procs are stopped outright. A knowingly touched Wildcard
    // can still turn, but the charm converts permanent doom into a short hex.
    if (has_ward_charm()) {
        if (monster_source) {
            fx_spawn(SPR_FX_IMPACT, 5, (i16)player.x + 4,
                (i16)player.y + 2, 14);
            sfx_play_reward(SFX_REWARD_MAGIC);
            return 0;
        }
        if (kind == CURSE_FRAIL) kind = CURSE_DULL;
        else if (kind == CURSE_MISFORTUNE) kind = CURSE_HUNGER;
        if (!rooms || rooms > 4) rooms = 4;
    }

    player.curse_flags |= kind;
    if (kind & CURSE_TIMED_MASK) {
        if (!rooms) rooms = 6;
        if (rooms > player.curse_rooms) player.curse_rooms = rooms;
    }
    fx_spawn(SPR_FX_IMPACT, 6, (i16)player.x + 4,
        (i16)player.y + 2, 18);
    room_shake(1, 6);
    sfx_play(SFX_WEAK);
    hud_show_status(QSTATUS_CURSE);
    return 1;
}

void curse_advance_room(void) BANKED {
    if (!(player.curse_flags & CURSE_TIMED_MASK) || !player.curse_rooms)
        return;
    if (--player.curse_rooms == 0)
        player.curse_flags &= (u8)~CURSE_TIMED_MASK;
}

void curse_cleanse(void) BANKED {
    if (!player.curse_flags) return;
    player.curse_flags = 0;
    player.curse_rooms = 0;
    fx_spawn(SPR_FX_IMPACT, 5, (i16)player.x + 4,
        (i16)player.y + 2, 18);
    sfx_play_reward(SFX_REWARD_MAGIC);
}

u8 curse_adjust_stat(u8 stat, u8 value) BANKED {
    if (stat == QSTATUS_STAT_ATK && (player.curse_flags & CURSE_DULL))
        return value ? (u8)(value - 1) : 0;
    if (stat == QSTATUS_STAT_LCK && (player.curse_flags & CURSE_MISFORTUNE))
        return value > 2 ? (u8)(value - 2) : 0;
    return value;
}

u8 curse_incoming_bonus(void) BANKED {
    return (player.curse_flags & CURSE_FRAIL) ? 1 : 0;
}

void curse_draw_pack_label(void) BANKED {
    const char *name;
    if (player.curse_flags & CURSE_FRAIL) name = "FRAIL  ";
    else if (player.curse_flags & CURSE_MISFORTUNE) name = "MISFORT";
    else if (player.curse_flags & CURSE_DULL) name = "DULL   ";
    else name = "HUNGER ";
    gotoxy(12, 1);
    text_write(name);
}
