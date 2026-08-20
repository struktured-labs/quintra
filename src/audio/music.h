// Four-channel adaptive sequencer: CH2 authored melody, CH3 authored bass,
// plus generated CH1 harmony and CH4 percussion whenever SFX are not using
// those channels. Gameplay tracks are 32-section dramatic forms.
#ifndef QUINTRA_AUDIO_MUSIC_H
#define QUINTRA_AUDIO_MUSIC_H

#include <gb/gb.h>
#include "core/types.h"

#define MUSIC_STAGE_COUNT 9
#define MUSIC_BOSS_BASE   9
#define MUSIC_TITLE       18
#define MUSIC_VICTORY     19
#define MUSIC_GAMEOVER    20
#define MUSIC_STOPPED     0xFF

enum {
    MUSIC_CONTEXT_EXPLORE = 0,
    MUSIC_CONTEXT_MERCHANT,
    MUSIC_CONTEXT_SANCTUARY,
    MUSIC_CONTEXT_MINIBOSS,
};

extern u8 music_track_id;       // observable stable music number
extern u8 music_stage_number;   // requested stage, normalized by player
extern u8 music_row;            // current sequencer row (read-only telemetry)
extern u8 music_form_step;      // current 16-row section, 0..31
extern u8 music_pattern_row;    // row within the current section, 0..15
extern u8 music_motif;          // authored idea A..H as 0..7
// Phrase-latched adaptive orchestration. The director writes pending values
// from room state; the sequencer adopts them only on a 16-row boundary.
extern u8 music_health_tier;     // 0 healthy .. 3 critical
extern u8 music_threat_tier;     // 0 clear .. 3 crowded/close
extern u8 music_context;         // MUSIC_CONTEXT_*
extern u8 music_power_tier;      // 1 when the run build outpaces its stage
extern u8 music_relic_tier;      // 0 absent, 1 near, 2 within discovery range
extern u8 music_health_target;
extern u8 music_threat_target;
extern u8 music_context_target;
extern u8 music_power_target;
extern u8 music_relic_target;
extern u8 music_drum_timbre;
extern u8 music_drum_strong;
extern u8 music_drum_soft;

void music_play_caverns(void);
void music_play_stage(void);    // unique ids 0..8
void music_play_boss(void);     // matching boss ids 9..17
void music_play_title(void);
void music_play_victory(void);
void music_play_gameover(void);
void music_stop(void);
void music_tick(void);          // call once per frame

#endif
