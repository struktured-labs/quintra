#ifndef QUINTRA_GAME_MAGIC_H
#define QUINTRA_GAME_MAGIC_H

#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"

// Elemental hero magic (2026-11-17 spec, docs/superpowers/specs/
// 2026-11-17-elemental-hero-magic.md). With the hero power selected as the
// B item: tap B = the hero's attack spell, hold B >= MAGIC_HOLD_FRAMES then
// release = the hero's ward. A pressed during a hold always wins: the A+B
// chord (Oath / Spirit Convergence) runs and no spell is cast.
#define MAGIC_HOLD_FRAMES 24
#define MAGIC_MOTE_FRAMES 6

// Spell ids (class_id * 2 + ward).
#define SPELL_MOONFIRE    0
#define SPELL_FLAME_WARD  1
#define SPELL_THUNDER     2
#define SPELL_STONESKIN   3
#define SPELL_HEX         4
#define SPELL_SHADOW_VEIL 5
#define SPELL_BLIZZARD    6
#define SPELL_CURE        7
#define SPELL_BRAMBLE     8
#define SPELL_THORN_MIRROR 9

// Moving spells are ordinary player projectiles tagged in ai_data[7]
// (0xA0 | spell id). Splash and Echo use only small values there.
#define MAGIC_SHOT_TAG      0xA0
#define MAGIC_IS_SHOT(e)    (((e)->ai_data[7] & 0xF0) == MAGIC_SHOT_TAG)

// VRAM bank-1 OBJ tiles 160..175 (free in rooms).
#define MAGIC_TILE          160
#define MAGIC_TILE_COUNT    17
#define MAGIC_T_FIRE_A      160
#define MAGIC_T_FIRE_B      161
#define MAGIC_T_BOLT        162
#define MAGIC_T_FLASH       163
#define MAGIC_T_HEX_A       164
#define MAGIC_T_HEX_B       165
#define MAGIC_T_ICE         166
#define MAGIC_T_ICE_D       167
#define MAGIC_T_THORN_A     168
#define MAGIC_T_THORN_B     169
#define MAGIC_T_WISP        170
#define MAGIC_T_MOTE        171
#define MAGIC_T_MIRROR      172
#define MAGIC_T_VEIL        173
#define MAGIC_T_CURE        174
#define MAGIC_T_ICE_H       175
#define MAGIC_T_CLAW        176

// Test / HUD telemetry.
extern u8 magic_hold;          // frames B has been held (0 = not charging)
extern u8 magic_last_spell;    // last cast spell id, 0xFF none
extern u8 magic_casts;         // wraps; increments per successful cast
extern u8 magic_ward_ticks;    // frames left on the live ward (pauses Will)
extern u8 magic_ward_kind;     // spell id of the live ward
extern u8 magic_tap_cd;        // attack-spell cooldown frames
extern u8 magic_ward_cd;       // ward cooldown frames (after the ward ends)
extern u8 magic_cure_used;     // Cure is once per room
// entity_init_room bumps this; magic.c drops room-bound state on change.
extern u8 magic_room_serial;

// One call per room frame from the weapon block (replaces the old B press
// branch). Also ticks live spells.
void magic_input(u8 keys, u8 pressed, u8 damage) BANKED;
// Wolfkin starter A: physical close arc, no persistent projectile.
void magic_fang(u8 dir, u8 damage) BANKED;
// Combat status dispatch (one call for ordinary and magic hits).
void magic_hit_status(u8 j, u8 i, u8 survives) BANKED;
// Room entry and Pack/map return: reload spell tiles, drop any charge.
void magic_room_enter(void) BANKED;
// New run: clear everything.
void magic_reset(void) BANKED;

#endif
