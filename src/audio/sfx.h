// SFX driver — one-shot register-write effects per cowir-sfx's designs.
// Music may borrow CH1/CH4 for harmony and percussion between effects; these
// ownership helpers keep a pickup fanfare or weapon hit from being overwritten.
#ifndef QUINTRA_AUDIO_SFX_H
#define QUINTRA_AUDIO_SFX_H

#include <gb/gb.h>
#include "core/types.h"

enum {
    SFX_FIRE = 0,     // player shot: thin fast zap
    SFX_HIT,          // enemy takes damage: dry crunch
    SFX_DEATH,        // enemy dies: metallic 7-bit buzz falling apart
    SFX_COIN,         // B5 -> E6 two-note classic
    SFX_HEART,        // soft E6 -> glassy upper twinkle
    SFX_DOOR,         // rising whoosh
    SFX_ROAR,         // boss: low 75%-duty growl + slow noise
    SFX_HURT,         // player hurt: harsh 12.5%-duty snap
    SFX_CLEAR,        // room cleared: G5 -> B5 -> E6 rising arpeggio
    SFX_LOWHP,        // danger pulse: single soft high blip
    SFX_TICK,         // boss telegraph: quiet mechanical click
    SFX_WEAK,         // elemental super-effective: bright rising crystal ping
    SFX_PUZZLE,       // landscape secret: long spooky four-note discovery cue
    SFX_DISTRICT,     // crossing a dungeon depth band: low/high wayfinding bell
    SFX_DASH,         // double-tap dodge: short rising wind-cut, never a door
    SFX_SIGIL,        // major dungeon key: six-note, one-second claim fanfare
};

// Banked reward voices keep pickups mechanically legible without bloating the
// resident combat dispatcher or turning every collectible into the coin cue.
enum {
    SFX_REWARD_RELIC = 0,
    SFX_REWARD_MAGIC,
    SFX_REWARD_SIGIL,
    SFX_REWARD_SURGE,
    SFX_REWARD_PURCHASE,
    SFX_REWARD_UNLOCK,
};

void sfx_play(u8 id);
// Banked, low-frequency variants keep weapon/equipment identity out of the
// precious always-mapped audio dispatcher.
void sfx_play_weapon(u8 projectile_kind) BANKED;
void sfx_play_equip(void) BANKED;
void sfx_play_reward(u8 kind) BANKED;
// Ordered floor runes answer with a rising pitch before the full solve cue.
void sfx_play_rune(u8 step);
void sfx_tick(void);      // per-frame: second notes / mid-sound bumps
void sfx_claim_channels(u8 ch1_frames, u8 ch4_frames);
// Long discovery/clear figures own the effect bus until their scheduled
// notes resolve. Banked pickup and weapon voices use this to avoid replacing
// a fanfare halfway through its melody.
u8 sfx_melody_locked(void);
u8 sfx_music_ch1_clear(void);
u8 sfx_music_ch4_clear(void);

#endif
