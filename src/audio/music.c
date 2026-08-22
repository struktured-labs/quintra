#include <gb/gb.h>

#include "audio/music.h"
#include "audio/music_data.h"
#include "audio/music_director.h"
#include "audio/music_score.h"
#include "audio/sfx.h"

// Long-form adaptive sequencer. CH2 and CH3 carry authored melody/bass while
// CH1 and CH4 add generated harmony/percussion whenever SFX have released
// them. Eight authored 16-row ideas are arranged through a unique 32-section
// form for every stage and boss. The reader switches score bank once per row
// and restores the gameplay bank before touching sound registers.

// Hardware frequency values. Pulse notes use x = 2048 - 131072/f; bass
// notes use x = 2048 - 65536/f. Entry order matches music_score.h.
static const u16 tone_freq[T_COUNT] = {
    0,0, // REST, HOLD (HOLD leaves CH2 untouched)
    1547,1575,1602,1627,1650,1673,1694,1714,1732,1750,1767,1783,
    1798,1812,1825,1837,1849,1860,1871,1881,1890,1899,1907,1915,
    1923,1930,1936,1943,1949,
};

static u8 playing;
static u8 frame_div;
u8 music_row;
u8 music_form_step;
u8 music_pattern_row;
static u8 frames_per_row;
static u8 phrase_rows;
static u8 pulse_duty;
static u8 pulse_envelope;
static u8 wave_level;
static u8 accent_mask;
static u8 swing_amount;
static u8 current_row_frames;
static u8 active_harmony[36];
u8 music_drum_timbre;
u8 music_drum_strong;
u8 music_drum_soft;
static u8 score_bank;
static u8 development_bank;
static u8 long_form;
static u8 active_bass_code;
u8 music_motif;
u8 music_health_tier;
u8 music_threat_tier;
u8 music_context;
u8 music_power_tier;
u8 music_relic_tier;
u8 music_health_target;
u8 music_threat_target;
u8 music_context_target;
u8 music_power_target;
u8 music_relic_target;
static const u8 *cur_melody;
static const u8 *cur_bass;
static const u8 *cur_development_melody;
static const u8 *cur_development_bass;
static const u8 *cur_form;
u8 music_track_id;
u8 music_stage_number;

void music_select_variant(const music_variant_t *v, const u8 *form,
    const u8 *development_melody, const u8 *development_bass,
    u8 bank, u8 id) {
    cur_melody = v->melody;
    cur_bass = v->bass;
    frames_per_row = v->tempo;
    pulse_duty = v->duty;
    pulse_envelope = v->envelope;
    wave_level = v->wave;
    accent_mask = v->accent;
    swing_amount = v->swing;
    current_row_frames = frames_per_row + swing_amount;
    music_prepare_harmony(v->scale, active_harmony);
    music_drum_timbre = v->drum_timbre;
    music_drum_strong = v->drum_strong;
    music_drum_soft = v->drum_soft;
    score_bank = bank;
    development_bank = BANK(music_development_score);
    cur_form = form;
    cur_development_melody = development_melody;
    cur_development_bass = development_bass;
    long_form = 1;
    music_track_id = id;
    playing = 1;
    frame_div = 0;
    music_row = 0;
    music_form_step = 0;
    music_pattern_row = 0;
    active_bass_code = T_REST;
    music_motif = 0;
    music_health_tier = music_health_target = 0;
    music_threat_tier = music_threat_target = 1;
    music_context = music_context_target = MUSIC_CONTEXT_EXPLORE;
    music_power_tier = music_power_target = 0;
    music_relic_tier = music_relic_target = 0;
}

void music_play_stage(void) {
    u8 stage = music_stage_number;
    music_variant_t variant;
    while (stage >= MUSIC_STAGE_COUNT) stage -= MUSIC_STAGE_COUNT;
    music_read_variant(stage, 0, &variant);
    music_load_wave(variant.wave_shape);
    music_select_variant(&variant, stage_forms[stage],
        stage_development_melody[stage], stage_development_bass[stage],
        BANK(music_stage_score), stage);
}

void music_play_boss(void) {
    u8 stage = music_stage_number;
    music_variant_t variant;
    while (stage >= MUSIC_STAGE_COUNT) stage -= MUSIC_STAGE_COUNT;
    music_read_variant(stage, 1, &variant);
    music_load_wave(variant.wave_shape);
    music_select_variant(&variant, boss_forms[stage],
        boss_development_melody[stage], boss_development_bass[stage],
        BANK(music_boss_score),
        (u8)(MUSIC_BOSS_BASE + stage));
}

static void select_home_theme(const u8 *melody_data, const u8 *bass_data,
    u8 tempo, u8 duty, u8 envelope, u8 wave, u8 id) {
    music_load_wave(id == MUSIC_GAMEOVER ? 4 : 1);
    cur_melody = melody_data;
    cur_bass = bass_data;
    frames_per_row = tempo;
    pulse_duty = duty;
    pulse_envelope = envelope;
    wave_level = wave;
    accent_mask = 0x11;
    swing_amount = 0;
    current_row_frames = frames_per_row;
    score_bank = BANK(music_development_score);
    phrase_rows = 32;
    music_drum_timbre = 0x35;
    music_drum_strong = 0x11;
    music_drum_soft = 0x44;
    long_form = 0;
    music_track_id = id;
    playing = 1;
    frame_div = 0;
    music_row = 0;
    music_form_step = 0;
    music_pattern_row = 0;
    active_bass_code = T_REST;
    music_motif = 0;
}

void music_play_title(void) {
    select_home_theme(title_melody, title_bass, 10, 0x80, 0x63, 0x40,
        MUSIC_TITLE);
}

void music_play_victory(void) {
    // The victorious cadence borrows the Golden Temple development bass.
    music_load_wave(3);
    cur_melody = victory_melody;
    cur_bass = stage_development_bass[6];
    frames_per_row = 6;
    pulse_duty = 0x80; pulse_envelope = 0x83; wave_level = 0x40;
    accent_mask = 0x55;
    swing_amount = 0;
    current_row_frames = frames_per_row;
    score_bank = BANK(music_development_score);
    phrase_rows = 32;
    long_form = 0;
    music_track_id = MUSIC_VICTORY;
    playing = 1; frame_div = 0; music_row = 0;
    music_form_step = 0; music_pattern_row = 0;
    active_bass_code = T_REST;
    music_motif = 0;
}

void music_play_gameover(void) {
    select_home_theme(gameover_melody, title_bass, 12, 0xC0, 0x52, 0x20,
        MUSIC_GAMEOVER);
}

void music_stop(void) {
    playing = 0;
    music_track_id = MUSIC_STOPPED;
    NR22_REG = 0x00; NR24_REG = 0x80;
    NR30_REG = 0x00;
}

static void play_harmony(void) {
    u8 root;
    u8 phase;
    u8 code;
    u8 envelope;
    u16 note;
    if (!sfx_music_ch1_clear() || active_bass_code < T_C3 ||
        active_bass_code > T_B3 || music_form_step == 12) return;

    if (!(music_mix_harmony_mask
        & (u8)(1u << (music_pattern_row & 0x07)))) return;
    envelope = music_mix_harmony_envelope;

    root = active_bass_code - T_C3;
    phase = (u8)((music_pattern_row >> 1) + music_form_step
        + music_health_tier + music_relic_tier);
    while (phase >= 3) phase -= 3;
    code = active_harmony[(u8)(root * 3 + phase)];
    note = tone_freq[code];
    NR10_REG = 0x00;
    NR11_REG = pulse_duty ^ 0x40;
    NR12_REG = envelope;
    NR13_REG = (u8)(note & 0xFF);
    NR14_REG = (u8)(0x80 | (note >> 8));
}

static u8 adaptive_lead_envelope(void) {
    u8 envelope = music_mix_lead_envelope;
    if ((accent_mask & (u8)(1u << (music_pattern_row & 0x07)))
        && (envelope & 0xF0) < 0xF0) envelope += 0x10;
    return envelope;
}

static void play_percussion(u8 boss) {
    u8 beat = music_pattern_row & 0x07;
    u8 bit = (u8)(1u << beat);
    if (!sfx_music_ch4_clear() || music_form_step < 2
        || music_form_step == 12
        || music_context == MUSIC_CONTEXT_SANCTUARY
        || music_context == MUSIC_CONTEXT_MERCHANT) return;
    if (music_drum_strong & bit) {
        NR42_REG = (boss || music_context == MUSIC_CONTEXT_MINIBOSS)
            ? 0x82 : 0x52;
        NR43_REG = music_drum_timbre;
    } else if (music_drum_soft & bit) {
        NR42_REG = (boss || music_context == MUSIC_CONTEXT_MINIBOSS)
            ? 0x72 : 0x42;
        NR43_REG = music_drum_timbre ^ 0x08;
    } else if (music_health_tier == 3 && (beat == 0 || beat == 4)) {
        NR42_REG = 0x62; NR43_REG = 0x55;
    } else if ((music_context == MUSIC_CONTEXT_MINIBOSS
            || music_threat_tier >= 3) && !(beat & 1)) {
        NR42_REG = 0x42; NR43_REG = music_drum_timbre ^ 0x10;
    } else return;
    NR44_REG = 0x80;
}

void music_tick(void) {
    u8 note_code;
    u8 bass_code = T_REST;
    u8 source_row;
    u8 boss;
    u8 read_bank;
    const u8 *melody_data;
    const u8 *bass_data;
    u16 note;
    if (!playing) return;
    if (++frame_div < current_row_frames) return;
    frame_div = 0;

    // Sample live room state and cache the whole 16-row arrangement in one
    // cold-bank crossing. Every row below then consumes only WRAM values.
    if (long_form && music_pattern_row == 0) {
        u8 boss_track = (u8)(music_track_id - MUSIC_BOSS_BASE)
            < MUSIC_STAGE_COUNT;
        music_adaptive_prepare_section(pulse_envelope, wave_level,
            music_form_step, boss_track);
    }

    if (long_form && music_pattern_row == 0) {
        u8 previous_bank = CURRENT_BANK;
        SWITCH_ROM(development_bank);
        music_motif = cur_form[music_form_step] & 0x07;
        SWITCH_ROM(previous_bank);
    }

    if (long_form) {
        if (music_motif >= 4) {
            source_row = (u8)(((music_motif - 4) << 4) | music_pattern_row);
            melody_data = cur_development_melody;
            bass_data = cur_development_bass;
            read_bank = development_bank;
        } else {
            source_row = (u8)((music_motif << 4) | music_pattern_row);
            melody_data = cur_melody;
            bass_data = cur_bass;
            read_bank = score_bank;
        }
    } else {
        source_row = music_row;
        melody_data = cur_melody;
        bass_data = cur_bass;
        read_bank = score_bank;
    }

    if (read_bank) {
        u8 previous_bank = CURRENT_BANK;
        SWITCH_ROM(read_bank);
        note_code = melody_data[source_row];
        if ((source_row & 0x03) == 0) bass_code = bass_data[source_row >> 2];
        SWITCH_ROM(previous_bank);
    } else {
        note_code = melody_data[source_row];
        if ((source_row & 0x03) == 0) bass_code = bass_data[source_row >> 2];
    }

    if ((source_row & 0x03) == 0) active_bass_code = bass_code;
    boss = long_form && (u8)(music_track_id - MUSIC_BOSS_BASE)
        < MUSIC_STAGE_COUNT;

    note = tone_freq[note_code < T_COUNT ? note_code : T_REST];
    if (note_code == T_HOLD) {
        // A tie consumes its score row but deliberately preserves CH2's
        // oscillator and envelope; this is what makes authored durations
        // audible rather than retriggering every eighth-note pulse.
    } else if (note != 0) {
        // B/development sections change the lead's pulse shape; the opening
        // and final return retain the track's identifying timbre.
        NR21_REG = (music_form_step >= 8 && music_form_step < 24) ?
            (pulse_duty ^ 0x40) : pulse_duty;
        NR22_REG = long_form ? adaptive_lead_envelope() : pulse_envelope;
        NR23_REG = (u8)(note & 0xFF);
        NR24_REG = (u8)(0x80 | (note >> 8));
    } else {
        // Real rests stop the prior pluck; without this every sparse score
        // smeared into the same drone even though its note table said REST.
        NR22_REG = 0x00;
    }

    if ((source_row & 0x03) == 0) {
        u16 bass = tone_freq[bass_code < T_COUNT ? bass_code : T_REST];
        if (bass != 0) {
            NR31_REG = 0x00;
            NR32_REG = long_form ? music_mix_wave_level : wave_level;
            NR33_REG = (u8)(bass & 0xFF);
            NR34_REG = (u8)(0x80 | (bass >> 8));
        } else {
            NR32_REG = 0x00;
        }
    }

    if (long_form) {
        play_harmony();
        play_percussion(boss);
        music_pattern_row++;
        if (music_pattern_row >= 16) {
            music_pattern_row = 0;
            music_form_step++;
            if (music_form_step >= MUSIC_FORM_SECTIONS) music_form_step = 0;
        }
        // Compute timing once per score row instead of spending this branch
        // on every video frame. Long/short pairs retain the same total time;
        // the exposed bridge temporarily returns to a straight pulse.
        current_row_frames = frames_per_row;
        if (swing_amount && music_form_step != 12) {
            if (music_pattern_row & 0x01)
                current_row_frames -= swing_amount;
            else
                current_row_frames += swing_amount;
        }
        music_row++; // 8-bit position telemetry; form_step proves full loop
    } else {
        music_row++;
        if (music_row >= phrase_rows) music_row = 0;
    }
}
