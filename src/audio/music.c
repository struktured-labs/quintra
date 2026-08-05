#include <gb/gb.h>

#include "audio/music.h"
#include "audio/music_score.h"

// Compact two-voice sequencer: CH2 pulse melody + CH3 wave bass. Gameplay
// scores are note-coded in two fixed data banks; this always-mapped reader
// briefly selects the right score bank once per row and restores whichever
// gameplay bank was active. That gives all nine stages and all nine bosses
// real 64-row arrangements without growing the 128 KiB cartridge.

// Hardware frequency values. Pulse notes use x = 2048 - 131072/f; bass
// notes use x = 2048 - 65536/f. Entry order matches music_score.h.
static const u16 tone_freq[T_COUNT] = {
    0,
    1547, 1601, 1650, 1673, 1713, 1750, 1783, // C3..B3 (wave)
    1798, 1825, 1849, 1860, 1871, 1881, 1899, 1915, // C5..B5
    1923, 1936, 1949, // C6..E6
};

// Triangle wavetable (32 four-bit samples).
static const u8 tri_wave[16] = {
    0x01, 0x23, 0x45, 0x67, 0x89, 0xAB, 0xCD, 0xEF,
    0xFE, 0xDC, 0xBA, 0x98, 0x76, 0x54, 0x32, 0x10,
};

// Compact screen themes stay in home ROM because they are intentionally
// 32-row cues rather than long exploration/combat arrangements.
static const u8 title_melody[32] = {
    T_A5,T_REST,T_C6,T_REST, T_E6,T_REST,T_C6,T_REST,
    T_B5,T_REST,T_G5,T_REST, T_A5,T_REST,T_REST,T_REST,
    T_A5,T_REST,T_D6,T_REST, T_C6,T_REST,T_A5,T_REST,
    T_G5,T_REST,T_E5,T_REST, T_A5,T_REST,T_REST,T_REST,
};
static const u8 title_bass[8] = {
    T_A3,T_A3,T_G3,T_G3,T_C3,T_C3,T_D3,T_A3,
};

static const u8 vic_melody[32] = {
    T_C5,T_E5,T_G5,T_C6, T_G5,T_C6,T_E6,T_C6,
    T_D5,T_G5,T_B5,T_D6, T_B5,T_D6,T_D6,T_REST,
    T_C5,T_E5,T_G5,T_C6, T_E6,T_C6,T_G5,T_E5,
    T_C6,T_C6,T_C6,T_REST, T_C6,T_REST,T_REST,T_REST,
};

static const u8 go_melody[32] = {
    T_A5,T_REST,T_G5,T_REST, T_F5,T_REST,T_E5,T_REST,
    T_D5,T_REST,T_C5,T_REST, T_D5,T_REST,T_REST,T_REST,
    T_A5,T_REST,T_G5,T_REST, T_E5,T_REST,T_D5,T_REST,
    T_C5,T_REST,T_C5,T_REST, T_REST,T_REST,T_REST,T_REST,
};

typedef struct {
    const u8 *melody;
    const u8 *bass;
    u8 tempo;
    u8 duty;
    u8 envelope;
    u8 wave;
} music_variant_t;

// Stable stage numbers 0..8. Each biome owns melody, bass, pacing, pulse
// shape, articulation, and wave mix—not merely a different public track ID.
static const music_variant_t stage_music[MUSIC_STAGE_COUNT] = {
    { melody,    bassline, 9,  0x40, 0x63, 0x40 }, // Crystal Caverns
    { s1_melody, s1_bass,  8,  0x80, 0x73, 0x40 }, // Verdant Hollow
    { s2_melody, s2_bass,  7,  0x00, 0x83, 0x40 }, // Ember Depths
    { s3_melody, s3_bass,  11, 0x40, 0x52, 0x20 }, // Frost Vault
    { s4_melody, s4_bass,  9,  0xC0, 0x62, 0x40 }, // Toxic Mire
    { s5_melody, s5_bass,  8,  0x40, 0x73, 0x40 }, // Shadow Keep
    { s6_melody, s6_bass,  9,  0x80, 0x83, 0x40 }, // Golden Temple
    { s7_melody, s7_bass,  7,  0x00, 0x83, 0x40 }, // Bloodmoon
    { s8_melody, s8_bass,  10, 0xC0, 0x52, 0x20 }, // Void Sanctum
};

static const music_variant_t boss_music[MUSIC_STAGE_COUNT] = {
    { boss_melody,  boss_bass,  7, 0x40, 0xA2, 0x40 },
    { boss2_melody, boss2_bass, 7, 0x00, 0xA2, 0x40 },
    { boss3_melody, boss3_bass, 7, 0x80, 0xA2, 0x40 },
    { boss4_melody, boss4_bass, 6, 0xC0, 0xA2, 0x40 },
    { boss5_melody, boss5_bass, 6, 0x40, 0xB2, 0x40 },
    { boss6_melody, boss6_bass, 6, 0x80, 0xB2, 0x40 },
    { boss7_melody, boss7_bass, 5, 0x00, 0xB2, 0x40 },
    { boss8_melody, boss8_bass, 5, 0xC0, 0xB2, 0x20 },
    { boss9_melody, boss9_bass, 4, 0x40, 0xC2, 0x20 },
};

static u8 playing;
static u8 frame_div;
u8 music_row;
static u8 frames_per_row = 8;
static u8 phrase_rows = 32;
static u8 pulse_duty = 0x80;
static u8 pulse_envelope = 0x63;
static u8 wave_level = 0x40;
static u8 score_bank;
static const u8 *cur_melody = title_melody;
static const u8 *cur_bass = title_bass;
u8 music_track_id = MUSIC_STOPPED;
u8 music_stage_number;

static void load_wave(void) {
    u8 i;
    NR30_REG = 0x00;
    for (i = 0; i < 16; ++i)
        *((volatile u8 *)(0xFF30 + i)) = tri_wave[i];
    NR30_REG = 0x80;
}

static void select_variant(const music_variant_t *v, u8 bank, u8 id) {
    cur_melody = v->melody;
    cur_bass = v->bass;
    frames_per_row = v->tempo;
    pulse_duty = v->duty;
    pulse_envelope = v->envelope;
    wave_level = v->wave;
    score_bank = bank;
    phrase_rows = 64;
    music_track_id = id;
    playing = 1;
    frame_div = 0;
    music_row = 0;
}

void music_play_caverns(void) {
    music_stage_number = 0;
    music_play_stage();
}

void music_play_stage(void) {
    u8 stage = music_stage_number;
    load_wave();
    while (stage >= MUSIC_STAGE_COUNT) stage -= MUSIC_STAGE_COUNT;
    select_variant(&stage_music[stage], BANK(music_stage_score), stage);
}

void music_play_boss(void) {
    u8 stage = music_stage_number;
    load_wave();
    while (stage >= MUSIC_STAGE_COUNT) stage -= MUSIC_STAGE_COUNT;
    select_variant(&boss_music[stage], BANK(music_boss_score),
        (u8)(MUSIC_BOSS_BASE + stage));
}

static void select_home_theme(const u8 *melody_data, const u8 *bass_data,
    u8 tempo, u8 duty, u8 envelope, u8 wave, u8 id) {
    load_wave();
    cur_melody = melody_data;
    cur_bass = bass_data;
    frames_per_row = tempo;
    pulse_duty = duty;
    pulse_envelope = envelope;
    wave_level = wave;
    score_bank = 0;
    phrase_rows = 32;
    music_track_id = id;
    playing = 1;
    frame_div = 0;
    music_row = 0;
}

void music_play_title(void) {
    select_home_theme(title_melody, title_bass, 10, 0x80, 0x63, 0x40,
        MUSIC_TITLE);
}

void music_play_victory(void) {
    // The victorious cadence deliberately borrows the opening Colossus bass
    // but reads it from the boss score bank instead of duplicating 16 bytes.
    load_wave();
    cur_melody = vic_melody;
    cur_bass = boss_bass;
    frames_per_row = 6;
    pulse_duty = 0x80; pulse_envelope = 0x83; wave_level = 0x40;
    score_bank = BANK(music_boss_score);
    phrase_rows = 32;
    music_track_id = MUSIC_VICTORY;
    playing = 1; frame_div = 0; music_row = 0;
}

void music_play_gameover(void) {
    select_home_theme(go_melody, title_bass, 12, 0xC0, 0x52, 0x20,
        MUSIC_GAMEOVER);
}

void music_stop(void) {
    playing = 0;
    music_track_id = MUSIC_STOPPED;
    NR22_REG = 0x00; NR24_REG = 0x80;
    NR30_REG = 0x00;
}

void music_tick(void) {
    u8 note_code;
    u8 bass_code = T_REST;
    u16 note;
    if (!playing) return;
    if (frame_div++ < frames_per_row) return;
    frame_div = 0;

    if (score_bank) {
        u8 previous_bank = CURRENT_BANK;
        SWITCH_ROM(score_bank);
        note_code = cur_melody[music_row];
        if ((music_row & 0x03) == 0) bass_code = cur_bass[music_row >> 2];
        SWITCH_ROM(previous_bank);
    } else {
        note_code = cur_melody[music_row];
        if ((music_row & 0x03) == 0) bass_code = cur_bass[music_row >> 2];
    }

    note = tone_freq[note_code < T_COUNT ? note_code : T_REST];
    if (note != 0) {
        NR21_REG = pulse_duty;
        NR22_REG = pulse_envelope;
        NR23_REG = (u8)(note & 0xFF);
        NR24_REG = (u8)(0x80 | (note >> 8));
    } else {
        // Real rests stop the prior pluck; without this every sparse score
        // smeared into the same drone even though its note table said REST.
        NR22_REG = 0x00;
    }

    if ((music_row & 0x03) == 0) {
        u16 bass = tone_freq[bass_code < T_COUNT ? bass_code : T_REST];
        if (bass != 0) {
            NR31_REG = 0x00;
            NR32_REG = wave_level;
            NR33_REG = (u8)(bass & 0xFF);
            NR34_REG = (u8)(0x80 | (bass >> 8));
        } else {
            NR32_REG = 0x00;
        }
    }

    music_row++;
    if (music_row >= phrase_rows) music_row = 0;
}
