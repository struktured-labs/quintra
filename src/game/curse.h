#ifndef QUINTRA_GAME_CURSE_H
#define QUINTRA_GAME_CURSE_H

#include <gb/gb.h>

#include "core/types.h"
#include "game/player.h"

// Run curses deliberately live outside the short room-status slot. Frail and
// Misfortune last until cleansed; Dull and Hunger expire after room travel.
#define CURSE_FRAIL       0x01u  // +1 damage taken
#define CURSE_MISFORTUNE  0x02u  // -2 effective LCK
#define CURSE_DULL        0x04u  // -1 effective ATK
#define CURSE_HUNGER      0x08u  // hearts and vampirism cannot heal
#define CURSE_TIMED_MASK  (CURSE_DULL | CURSE_HUNGER)

#define CURSE_PLAYER_HEALING_BLOCKED() \
    ((player.curse_flags & CURSE_HUNGER) != 0)

u8 curse_apply(u8 kind, u8 rooms, u8 monster_source) BANKED;
void curse_advance_room(void) BANKED;
void curse_cleanse(void) BANKED;
u8 curse_adjust_stat(u8 stat, u8 value) BANKED;
u8 curse_incoming_bonus(void) BANKED;
void curse_draw_pack_label(void) BANKED;

#endif
