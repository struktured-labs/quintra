#ifndef QUINTRA_GAME_WILL_H
#define QUINTRA_GAME_WILL_H

#include <gb/gb.h>
#include "core/types.h"

// Three seconds of deliberate restraint at 60 Hz. Unlike a cooldown, every
// ordinary primary attack spends the partial meter, so waiting is a choice.
#define WILL_MAX 180

// B is each champion's dependable tactical verb, not another claimant on the
// MP/Will hoarding economy.  These class-shaped bases are shortened further by
// run-earned SPD; A+B and Oath Arts retain MP as their separate magic ladder.
#define SIGNATURE_CD_WOLFKIN 72
#define SIGNATURE_CD_SAURAN  90
#define SIGNATURE_CD_CORVIN   54
#define SIGNATURE_CD_PICSEAN 120
#define SIGNATURE_CD_VESPINE  72
#define SIGNATURE_CD_MIN      36

// Corvin's B marks one live foe instead of duplicating Murderstorm's fan.
// Combat reads these two bytes directly on its existing collision pass.
#define WILL_CORVIN_MARK_BONUS 1
extern u8 will_corvin_mark_slot;
extern u8 will_corvin_mark_ticks;
extern u8 will_corvin_mark_damage;

// Howl remains an eight-way crowd burst, but at most three of those blades
// may multiply against one Colossus. Ordinary enemies keep the full ring.
#define WILL_HOWL_GIANT_HIT_CAP 3
extern u8 will_howl_giant_hits;
void will_howl_clear_nearby_shots(void) BANKED;

// Vespine's B is a short rotating swarm rather than another instantaneous
// forward fan. The room only pays the banked update while this byte is live.
extern u8 will_vespine_swarm_ticks;
extern u8 will_vespine_swarm_dir;
extern u8 will_vespine_swarm_damage;

// Launch the equipped weapon's full-Will art. Returns nonzero only if at
// least one gameplay hitbox could be allocated, so a saturated entity table
// never silently steals the charge.
u8 will_fire_max(u8 weapon_index, u8 dir, u8 damage) BANKED;
// Invoke the active champion's distinct B verb. Returns nonzero when the
// signature committed a real defensive, marked-target, or swarm effect.
u8 will_fire_signature(u8 dir, u8 damage) BANKED;
// Begin the class-tuned, SPD-scaled cooldown after a successful signature.
void will_begin_signature(void) BANKED;

#endif
