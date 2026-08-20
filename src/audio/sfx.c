// Register-level GB SFX. Specs by cowir-sfx (intercom msg 2119), encoded
// as NRxx writes. Freq conversion: x = 2048 - 131072/f.

#include <gb/gb.h>

#include "audio/sfx.h"

// Deferred second-stage actions (two-note jingles, decay bumps)
#define PEND_NONE       0
#define PEND_COIN_NOTE2 1
#define PEND_HEART_NOTE2 2
#define PEND_DEATH_BUMP 3
#define PEND_CLEAR_NOTE2 4
#define PEND_CLEAR_NOTE3 5
#define PEND_WEAK_NOTE2  6
#define PEND_PUZZLE_NOTE2 7
#define PEND_PUZZLE_NOTE3 8
#define PEND_PUZZLE_NOTE4 9
#define PEND_DISTRICT_NOTE2 10

static u8 pend_kind;
static u8 pend_timer;
static u8 ch1_busy_frames;
static u8 ch4_busy_frames;

void sfx_claim_channels(u8 ch1_frames, u8 ch4_frames) {
    if (ch1_frames > ch1_busy_frames) ch1_busy_frames = ch1_frames;
    if (ch4_frames > ch4_busy_frames) ch4_busy_frames = ch4_frames;
}

u8 sfx_music_ch1_clear(void) { return ch1_busy_frames == 0; }
u8 sfx_music_ch4_clear(void) { return ch4_busy_frames == 0; }

static void ch1(u8 nr10, u8 nr11, u8 nr12, u16 freq) {
    sfx_claim_channels(8, 0);
    NR10_REG = nr10;
    NR11_REG = nr11;
    NR12_REG = nr12;
    NR13_REG = (u8)(freq & 0xFF);
    NR14_REG = (u8)(0x80 | (freq >> 8));
}

static void ch4(u8 nr43, u8 nr42) {
    sfx_claim_channels(0, 8);
    NR42_REG = nr42;
    NR43_REG = nr43;
    NR44_REG = 0x80;
}

void sfx_play(u8 id) {
    switch (id) {
        case SFX_FIRE:
            // CH1 duty 25%, 1150Hz, sweep down (1,3), env (12,down,1)
            ch1(0x1B, 0x40, 0xC1, 1934);
            break;
        case SFX_HIT:
            // noise 15-bit, mid clock s=4 r=2, env (12,down,1) ~70ms
            ch4(0x42, 0xC1);
            break;
        case SFX_DEATH:
            // noise 7-bit s=3 r=1, env (13,down,3); clock bump at +200ms
            ch4(0x39, 0xD3);
            pend_kind = PEND_DEATH_BUMP;
            pend_timer = 12;
            sfx_claim_channels(0, 18);
            break;
        case SFX_COIN:
            // CH1 no sweep, duty 50%, B5 then E6, env (13,down,2)
            ch1(0x00, 0x80, 0xD2, 1915);
            pend_kind = PEND_COIN_NOTE2;
            pend_timer = 3;
            sfx_claim_channels(12, 0);
            break;
        case SFX_HEART:
            // A soft high twinkle, deliberately an octave above the short
            // B5->E6 currency chirp: E6 blooms into a glassy upper sparkle.
            ch1(0x00, 0x40, 0x93, 1949);
            pend_kind = PEND_HEART_NOTE2;
            pend_timer = 4;
            sfx_claim_channels(13, 0);
            break;
        case SFX_DOOR:
            // 280Hz sweep UP (2,2), duty 50%, env (10,down,4)
            ch1(0x22, 0x80, 0xA4, 1580);
            break;
        case SFX_ROAR:
            // CH1 duty 75%, 100Hz, slow sweep down (7,1), env (15,down,6)
            ch1(0x79, 0xC0, 0xF6, 737);
            // + noise 7-bit low clock s=5 r=6, env (14,down,5)
            ch4(0x5E, 0xE5);
            break;
        case SFX_HURT:
            // duty 12.5%, 500Hz, sweep down (1,4), env (14,down,1)
            ch1(0x1C, 0x00, 0xE1, 1786);
            break;
        case SFX_CLEAR:
            // Zelda-secret rising arpeggio: G5 -> B5 -> E6, duty 50%,
            // env (12,down,3). Notes 2/3 chained via the pend system.
            ch1(0x00, 0x80, 0xC3, 1881);
            pend_kind = PEND_CLEAR_NOTE2;
            pend_timer = 5;
            sfx_claim_channels(18, 0);
            break;
        case SFX_LOWHP:
            // Soft, short C7 blip — quiet env (6,down,2) so it reads as
            // a heartbeat under combat, not an alarm over it.
            ch1(0x00, 0x80, 0x62, 1985);
            break;
        case SFX_TICK:
            // Quiet high metallic click (noise 15-bit, fast clock,
            // env 5-down-1) — the boss cocking the hammer.
            ch4(0x24, 0x51);
            break;
        case SFX_WEAK:
            // "Super effective" — bright crystal ping, duty 50%, high C7,
            // env (11,down,1) short & sparkly, then a higher note chained.
            ch1(0x00, 0x80, 0xB1, 1985);
            pend_kind = PEND_WEAK_NOTE2;
            pend_timer = 2;
            sfx_claim_channels(11, 0);
            break;
        case SFX_PUZZLE:
            // A landscape secret should linger, not read as another pickup.
            // Start with a stone-deep noise breath, then climb a deliberately
            // uncanny diminished figure (D4-F4-Ab4) into a clear D5 resolve.
            // At twelve frames between attacks the full reveal lasts roughly
            // three quarters of a second before the final note decays.
            ch4(0x5D, 0x84);
            ch1(0x00, 0xC0, 0xA4, 1602);              // D4
            pend_kind = PEND_PUZZLE_NOTE2;
            pend_timer = 12;
            sfx_claim_channels(45, 10);
            break;
        case SFX_DISTRICT:
            // A restrained threshold bell: low A4 establishes distance,
            // then D5 answers after the room seam. It is shorter and calmer
            // than the puzzle fanfare, so crossing a district never sounds
            // like the player solved or collected something.
            ch1(0x00, 0x80, 0x94, 1750);
            pend_kind = PEND_DISTRICT_NOTE2;
            pend_timer = 8;
            sfx_claim_channels(18, 0);
            break;
        case SFX_DASH:
            // A quick rising wind-cut: bright sweep plus a soft narrow-noise
            // scrape. Unlike SFX_DOOR it stops immediately, so repeated combat
            // dodges feel athletic instead of sounding like room transitions.
            ch1(0x24, 0x40, 0xA1, 1874);
            ch4(0x27, 0x72);
            sfx_claim_channels(9, 7);
            break;
        default:
            break;
    }
}

void sfx_play_rune(u8 step) {
    // C5, E5, G5: unmistakable positive positional feedback without spending
    // the longer SFX_PUZZLE fanfare until the complete order is correct.
    static const u16 notes[3] = { 1798, 1849, 1881 };
    if (step > 2) step = 2;
    pend_kind = PEND_NONE;
    ch1(0x00, 0x80, 0xA2, notes[step]);
}

void sfx_tick(void) {
    if (ch1_busy_frames) ch1_busy_frames--;
    if (ch4_busy_frames) ch4_busy_frames--;
    if (pend_kind == PEND_NONE) return;
    if (--pend_timer) return;
    switch (pend_kind) {
        case PEND_COIN_NOTE2:
            NR13_REG = (u8)(1949 & 0xFF);
            NR14_REG = (u8)(0x80 | (1949 >> 8));
            break;
        case PEND_HEART_NOTE2:
            NR12_REG = 0xB4;
            NR13_REG = (u8)(2010 & 0xFF);
            NR14_REG = (u8)(0x80 | (2010 >> 8));
            break;
        case PEND_DEATH_BUMP:
            NR43_REG = 0x69;   // s=6, 7-bit — buzz falls apart as it fades
            break;
        case PEND_CLEAR_NOTE2:
            NR13_REG = (u8)(1915 & 0xFF);              // B5
            NR14_REG = (u8)(0x80 | (1915 >> 8));
            pend_kind = PEND_CLEAR_NOTE3;              // chain note 3
            pend_timer = 5;
            return;
        case PEND_CLEAR_NOTE3:
            NR12_REG = 0xD4;                           // fresh, longer env
            NR13_REG = (u8)(1949 & 0xFF);              // E6
            NR14_REG = (u8)(0x80 | (1949 >> 8));
            break;
        case PEND_WEAK_NOTE2:
            NR12_REG = 0xA1;                           // brief, bright
            NR13_REG = (u8)(2010 & 0xFF);              // up an octave-ish
            NR14_REG = (u8)(0x80 | (2010 >> 8));
            break;
        case PEND_PUZZLE_NOTE2:
            NR12_REG = 0xA4;
            NR13_REG = (u8)(1673 & 0xFF);              // F4
            NR14_REG = (u8)(0x80 | (1673 >> 8));
            pend_kind = PEND_PUZZLE_NOTE3;
            pend_timer = 12;
            return;
        case PEND_PUZZLE_NOTE3:
            NR12_REG = 0xB4;
            NR13_REG = (u8)(1732 & 0xFF);              // Ab4
            NR14_REG = (u8)(0x80 | (1732 >> 8));
            pend_kind = PEND_PUZZLE_NOTE4;
            pend_timer = 12;
            return;
        case PEND_PUZZLE_NOTE4:
        case PEND_DISTRICT_NOTE2:
            // Both figures resolve to D5; only the puzzle's final envelope
            // is longer and brighter than the threshold bell.
            NR12_REG = (pend_kind == PEND_PUZZLE_NOTE4) ? 0xD6 : 0xB4;
            NR13_REG = (u8)(1825 & 0xFF);              // D5
            NR14_REG = (u8)(0x80 | (1825 >> 8));
            break;
    }
    pend_kind = PEND_NONE;
}
