#pragma bank 15
#include "audio/boss_voice.h"
#include "audio/sfx.h"
#include "game/entity.h"

void boss_voice(u8 stage, u8 cue) BANKED {
    static const u8 noise[9] = { 0x64,0x27,0x53,0x19,0x75,0x4B,0x36,0x45,0x6D };
    static const u8 sweep[9] = { 0x2B,0x37,0x2E,0x13,0x6D,0x67,0x22,0x4B,0x7E };
    static const u8 duty[9] = { 0x80,0x40,0xC0,0x00,0x80,0x40,0x80,0xC0,0x40 };
    static const u16 pitch[9] = { 910,1680,740,1840,1080,1520,1760,1220,610 };
    static u8 last_frame, last_stage, has_voice;
    u8 volume, decay;
    u16 frequency;
    if (stage >= 9 || sfx_melody_locked()) return;
    if (has_voice && cue == BOSS_VOICE_DOOR && stage == last_stage
        && (u8)(entity_anim_counter-last_frame) < 180) return;
    if ((cue == BOSS_VOICE_ATTACK || cue == BOSS_VOICE_PAIN)
        && stage == last_stage && (u8)(entity_anim_counter-last_frame) < 72) return;
    last_frame = entity_anim_counter;
    last_stage = stage;
    has_voice = 1;
    volume = cue == BOSS_VOICE_DOOR ? 3 : cue == BOSS_VOICE_PAIN ? 7 : 11;
    decay = cue == BOSS_VOICE_DEATH ? 5 : cue == BOSS_VOICE_PAIN ? 1 : 3;
    frequency = pitch[stage];
    if (cue == BOSS_VOICE_PAIN) frequency += 90;
    if (cue == BOSS_VOICE_DEATH) frequency -= 180;
    sfx_claim_channels(cue == BOSS_VOICE_PAIN ? 0 : 22, 20);
    NR41_REG = 0;
    NR42_REG = (volume << 4) | decay;
    NR43_REG = noise[stage];
    NR44_REG = 0x80;
    if (cue != BOSS_VOICE_PAIN) {
        NR10_REG = sweep[stage];
        NR11_REG = duty[stage];
        NR12_REG = (volume << 4) | decay;
        NR13_REG = (u8)frequency;
        NR14_REG = 0x80 | (u8)(frequency >> 8);
    }
}
