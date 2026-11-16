#ifndef QUINTRA_GAME_ANTIDOTE_H
#define QUINTRA_GAME_ANTIDOTE_H

#include <gb/gb.h>
#include "core/types.h"

// Antidote: a stackable Pack TOOL (inventory id ITEM_ID_ANTIDOTE) that cures
// every damage-over-time condition: Poison, Burn and Bleed. It lives in the ordinary saved inventory bytes, so suspend saves
// need no new field. Up to ANTIDOTE_CARRY_MAX are carried at once.
#define ANTIDOTE_CARRY_MAX 3
#define ANTIDOTE_PRICE     12

u8   antidote_count(void) BANKED;
u8   antidote_can_carry(void) BANKED;
// Adds one carried Antidote. 0 when the pouch or the inventory is full.
u8   antidote_grant(void) BANKED;
// Cures the current condition with the cured cue (does not touch inventory).
void antidote_cure(void) BANKED;
// Floor safety net: when a Poison/Burn/Bleed tick reaches the last
// half-heart (which it never takes), spend a carried Antidote to end the
// condition. 1 when it fired.
u8   antidote_try_rescue(void) BANKED;
// Floor vial (bought=0) or shop purchase (bought=1). A purchase made while
// poisoned, burning or bleeding is used on the spot. 0 when the pouch is full.
u8   antidote_collect(u8 bought) BANKED;
u8   antidote_spawn(fix8_t x, fix8_t y) BANKED;
// Poison-source kills (and kills made while poisoned and empty-handed) can
// leave an Antidote. Deterministic, consumes no RNG. 1 when one dropped.
u8   antidote_try_drop(u8 eid, fix8_t x, fix8_t y) BANKED;

#endif
