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

static u8 pend_kind;
static u8 pend_timer;

static void ch1(u8 nr10, u8 nr11, u8 nr12, u16 freq) {
    NR10_REG = nr10;
    NR11_REG = nr11;
    NR12_REG = nr12;
    NR13_REG = (u8)(freq & 0xFF);
    NR14_REG = (u8)(0x80 | (freq >> 8));
}

static void ch4(u8 nr43, u8 nr42) {
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
            break;
        case SFX_COIN:
            // CH1 no sweep, duty 50%, B5 then E6, env (13,down,2)
            ch1(0x00, 0x80, 0xD2, 1915);
            pend_kind = PEND_COIN_NOTE2;
            pend_timer = 3;
            break;
        case SFX_HEART:
            // 660Hz then 880Hz, duty 50%, env (11,down,3)
            ch1(0x00, 0x80, 0xB3, 1849);
            pend_kind = PEND_HEART_NOTE2;
            pend_timer = 4;
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
        default:
            break;
    }
}

void sfx_tick(void) {
    if (pend_kind == PEND_NONE) return;
    if (--pend_timer) return;
    switch (pend_kind) {
        case PEND_COIN_NOTE2:
            NR13_REG = (u8)(1949 & 0xFF);
            NR14_REG = (u8)(0x80 | (1949 >> 8));
            break;
        case PEND_HEART_NOTE2:
            NR13_REG = (u8)(1899 & 0xFF);
            NR14_REG = (u8)(0x80 | (1899 >> 8));
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
    }
    pend_kind = PEND_NONE;
}
