// Tiny 2-voice music sequencer: CH2 pulse melody + CH3 wave bass.
// Placeholder engine until hUGEDriver + cowir-music's composed tracks land.
#ifndef QUINTRA_AUDIO_MUSIC_H
#define QUINTRA_AUDIO_MUSIC_H

#include "core/types.h"

#define MUSIC_STAGE_COUNT 9
#define MUSIC_BOSS_BASE   9
#define MUSIC_TITLE       18
#define MUSIC_VICTORY     19
#define MUSIC_GAMEOVER    20
#define MUSIC_STOPPED     0xFF

extern u8 music_track_id;       // observable stable music number
extern u8 music_stage_number;   // requested stage, normalized by player

void music_play_caverns(void);
void music_play_stage(void);    // unique ids 0..8
void music_play_boss(void);     // matching boss ids 9..17
void music_play_title(void);
void music_play_victory(void);
void music_play_gameover(void);
void music_stop(void);
void music_tick(void);        // call once per frame

#endif
