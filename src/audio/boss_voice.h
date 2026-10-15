#ifndef QUINTRA_BOSS_VOICE_H
#define QUINTRA_BOSS_VOICE_H
#include <gb/gb.h>
#include "core/types.h"
#define BOSS_VOICE_DOOR 0
#define BOSS_VOICE_ARRIVE 1
#define BOSS_VOICE_ATTACK 2
#define BOSS_VOICE_PAIN 3
#define BOSS_VOICE_DEATH 4
#define BOSS_VOICE_PHASE 5
void boss_voice(u8 stage, u8 cue) BANKED;
#endif
