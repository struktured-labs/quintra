#ifndef QUINTRA_GAME_STATUS_H
#define QUINTRA_GAME_STATUS_H

#include <gb/gb.h>

#include "core/types.h"
#include "game/entity.h"

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

void status_reset_all(void) BANKED;
void status_clear_enemies(void) BANKED;
void status_player_cure(void) BANKED;
void status_player_refresh_visual(void) BANKED;
void status_draw_pack_label(void) BANKED;
void status_player_apply(u8 kind, u8 ticks) BANKED;
void status_enemy_apply(u8 idx, u8 kind, u8 ticks) BANKED;

// Called only on successful combat contacts; these select authored effects,
// apply resistance/chance rules, and produce their visual tell.
void status_try_player_shot(u8 enemy_idx, u8 shot_idx) BANKED;
void status_try_hostile_hit(u8 hostile_idx) BANKED;
u8 status_hostile_kind_for_enemy(u8 enemy_id) BANKED;

// Active-room clock and adaptive control filter.
void status_tick(void) BANKED;
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
    (player_status_kind == QSTATUS_CURSE)
#define STATUS_PLAYER_HASTED() \
    (player_status_kind == QSTATUS_HASTE)
#define STATUS_PLAYER_INVERTED() \
    (player_status_kind == QSTATUS_INVERSION)

#endif
