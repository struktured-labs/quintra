#ifndef QUINTRA_GAME_STATUS_H
#define QUINTRA_GAME_STATUS_H

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/curse.h"

// One primary condition per actor keeps the GBC combat language readable:
// a new affliction replaces the old one, while every application refreshes
// its own clearly bounded duration. Timers are measured in eight-frame beats.
enum {
    QSTATUS_NONE = 0,
    QSTATUS_POISON,
    QSTATUS_BURN,
    QSTATUS_SLOW,
    QSTATUS_STOP,
    QSTATUS_BLIND,
    QSTATUS_CONFUSION,
    QSTATUS_MUTE,
    QSTATUS_BRITTLE,
    QSTATUS_BLEED,
    QSTATUS_CURSE,
    QSTATUS_REGEN,
    QSTATUS_HASTE,
    QSTATUS_INVERSION,
    QSTATUS_COUNT,
};

enum {
    QSTATUS_STAT_ATK = 0,
    QSTATUS_STAT_DEF,
    QSTATUS_STAT_SPD,
    QSTATUS_STAT_LCK,
};

// Rift Inversion's enemy-side interpretation, cached when it lands.
enum {
    QSTATUS_INVERT_ARMOR = 0,
    QSTATUS_INVERT_DAMAGE,
    QSTATUS_INVERT_SPEED,
    QSTATUS_INVERT_POISE,
};

extern u8 player_status_kind;
// Confusion uses the shared 8-frame status beat. At 60 Hz that is
// 23 beats = 3.067 s, 75 = 10 s, 150 = 20 s. Player applications roll
// a triangular duration around 10 s, then clamp to this range. Easy
// keeps the same shape at 3/5 scale, still never below 3 s.
#define STATUS_CONFUSION_MIN_TICKS  23
#define STATUS_CONFUSION_MEAN_TICKS 75
#define STATUS_CONFUSION_MAX_TICKS  150
// 600 frames = 10 s at 60 Hz. Long enough that a new proc cannot
// chain back to back even after a short roll. u16 because 600 does
// not fit in a byte.
#define STATUS_CONFUSION_IMMUNE_FRAMES 600
extern u16 confusion_immune;
extern u8 player_status_ticks;
extern u8 enemy_status_kind[MAX_ENTITIES];
extern u8 enemy_status_ticks[MAX_ENTITIES];
extern u8 enemy_status_aux[MAX_ENTITIES];

// The entity dispatcher exposes its current hostile actor only while that
// actor's AI is running. Projectile/summon constructors use this context for
// Mute, Blind, Confusion, and Rift Inversion without changing entity ABI.
extern u8 status_enemy_actor;
// Zero in ordinary play. Combat enters the O(n²) friendly-fire resolver only
// while at least one genuinely confused hostile projectile survives.
extern u8 status_confused_projectiles;
// Hot-room gate: zero until an enemy receives a condition. It deliberately
// remains set for the rest of that room, avoiding kill/expiry bookkeeping in
// ROM0 while ordinary untouched rooms skip a far call and 32-slot scan.
extern u8 status_enemy_active;
extern u8 status_clock;

void status_reset_all(void) BANKED;
void status_clear_enemies(void) BANKED;
void status_player_cure(void) BANKED;
void status_player_refresh_visual(void) BANKED;
void status_draw_pack_label(void) BANKED;
void status_player_apply(u8 kind, u8 ticks) BANKED;
// 0 = idle. Tests (and only tests) write a QSTATUS_* kind here;
// status_tick consumes it as a forced status_player_apply(kind, 0).
extern u8 status_apply_req;
extern const u8 status_class_resist_kind[5];
u8 status_resist_adjust(u8 kind, u8 ticks) BANKED;
void status_enemy_apply(u8 idx, u8 kind, u8 ticks) BANKED;

// Called only on successful combat contacts; these select authored effects,
// apply resistance/chance rules, and produce their visual tell.
void status_try_player_shot(u8 enemy_idx, u8 shot_idx) BANKED;
void status_try_hostile_hit(u8 hostile_idx) BANKED;
u8 status_hostile_kind_for_enemy(u8 enemy_id) BANKED;
// Chance 0-100 for a hostile status landing. guaranteed is 1 for rare
// enemies and flagged 100% shots. Lives in bank 24 so bank 13 stays
// under the emergency floor.
u8 status_hostile_proc_chance(u8 kind, u8 guaranteed) BANKED;

// Active-room clock and adaptive control filter.
void status_tick(void) BANKED;
void status_tick_gate(void) BANKED;
void status_player_filter_input(u8 *keys, u8 *pressed) BANKED;
void status_enemy_moved(u8 idx) BANKED;
// Cold-path hostile update used only while an enemy is conditioned. Ordinary
// enemies remain on the home-bank direct path, preserving the crowded-room
// frame budget while keeping the status scheduler out of scarce ROM0.
void status_update_enemy_condition(u8 idx) BANKED;
void status_resolve_confused_projectiles(void) BANKED;
u8 status_player_palette_prop(void) BANKED;
u8 status_enemy_palette_prop(u8 idx) BANKED;

// Effective-stat view used by combat and movement. Permanent build values
// are never rewritten, so pickups earned during Inversion remain correct.
u8 status_player_effective_stat(u8 stat) BANKED;

// Small direct predicates are intentionally macros: hot paths avoid a far
// call while the overwhelmingly common state is QSTATUS_NONE.
#define STATUS_PLAYER_MUTED() \
    (player_status_kind == QSTATUS_MUTE)
#define STATUS_PLAYER_HEALING_BLOCKED() \
    (player_status_kind == QSTATUS_CURSE || CURSE_PLAYER_HEALING_BLOCKED())
#define STATUS_PLAYER_HASTED() \
    (player_status_kind == QSTATUS_HASTE)
#define STATUS_PLAYER_INVERTED() \
    (player_status_kind == QSTATUS_INVERSION)
#define STATUS_PLAYER_BURNED() \
    (player_status_kind == QSTATUS_BURN)
// Burn and Rift Inversion are the only conditions that rewrite ATK
// through status_player_effective_stat. A far call is paid only then.
#define STATUS_PLAYER_ATK_MODIFIED() \
    (STATUS_PLAYER_INVERTED() || STATUS_PLAYER_BURNED())

// Damage-over-time conditions. Standing rule: Burn never takes the
// last half-heart on its own (a hit, not Burn, ends a run). Poison
// and Bleed can kill. Burn also halves attack while it lasts, never
// below 1. The Antidote cures all three; at 1 HP a carried vial still
// breaks and cures before the tick. Regen and Haste are the only
// boons; everything else is harm and gets a reminder while it lasts
// and a CURED card when it ends.
#define STATUS_KIND_IS_DOT(k) \
    ((k) == QSTATUS_POISON || (k) == QSTATUS_BURN || (k) == QSTATUS_BLEED)
#define STATUS_PLAYER_DOT() STATUS_KIND_IS_DOT(player_status_kind)
#define STATUS_KIND_IS_HARM(k) \
    ((k) != QSTATUS_NONE && (k) != QSTATUS_REGEN && (k) != QSTATUS_HASTE)
// Bleed: one half-heart per this many frames spent moving.
#define STATUS_BLEED_STRIDE 128
// Burn: one half-heart every this many eight-frame beats.
#define STATUS_BURN_PERIOD  12
// Cinder Maw / Cinder Kite Burn proc, as a percent. Trimmed below the
// generic hostile chance (16 Easy / 42 Normal) so Ember rooms stay
// dangerous without dominating deaths. Kept nonzero so Burn still
// appears. Easy is scaled in proportion to the Normal trim.
#define STATUS_BURN_PROC_NORMAL  12
#define STATUS_BURN_PROC_EASY    5

#endif
