#pragma bank 6

#include <gb/gb.h>
#include <gb/cgb.h>

#include "core/types.h"
#include "game/player.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/palette.h"
#include "render/tiles.h"

// HUD palette — bright accent (red hearts, gold coin) on dark BG
static const u16 hud_palette[4] = {
    BGR555( 0,  0,  0),    // 0: transparent / dark BG
    BGR555(10, 14, 20),    // 1: outline gray-blue
    BGR555(31, 20,  6),    // 2: coin gold
    BGR555(31,  6,  8),    // 3: heart red
};

// MP variant: same tiles, color 3 flips to magic blue. Assigned to the
// MP digit columns via per-tile attributes — no extra tile data needed.
static const u16 hud_palette_mp[4] = {
    BGR555( 0,  0,  0),
    BGR555(10, 14, 20),
    BGR555(31, 20,  6),
    BGR555( 8, 22, 31),    // 3: MP blue
};

// A full meter is also the readiness condition for the shared A/B Spirit
// Convergence chord. Brighten only the existing MP digits so the HUD teaches
// "charged" without consuming another tile lane or flashing the whole frame.
static const u16 hud_palette_mp_full[4] = {
    BGR555( 0,  0,  0),
    BGR555(10, 14, 20),
    BGR555(31, 20,  6),
    BGR555(24, 31, 31),    // 3: icy-white, ready to ascend
};

// Shops call hud_show_offer every frame while the hero is nearby. Cache the
// rendered price so this context hint costs no repeated VRAM traffic.
static u8 offer_price = 0xFF;
static u8 offer_ware = 0xFF;

// 1-row HUD layout (20 tiles wide):
//
//   col:  0.......7 8 9 10 11 12.....15 16 17 18 19
//        [hearts ×8][MP] [depth] [boss×4] [$] [coins]

void hud_init(void) BANKED {
    tiles_load_hud();
    // Place HUD on BG palette slot 7 (won't collide with room pal 0);
    // slot 6 is the blue MP variant for the MP digit columns.
    palette_bg_load(7, hud_palette);
    palette_bg_load(6, hud_palette_mp);

    // Fill all 20 WIN tiles with blank, then set palette attribute = 7
    // (except the MP columns 8-9, which take the blue palette 6)
    {
        u8 row[20];
        u8 attr[20];
        u8 i;
        for (i = 0; i < 20; ++i) { row[i] = HUD_BLANK; attr[i] = 0x07; }
        attr[8] = attr[9] = 0x06;
        VBK_REG = 0; set_win_tiles(0, 0, 20, 1, row);
        VBK_REG = 1; set_win_tiles(0, 0, 20, 1, attr);
        VBK_REG = 0;
    }

    // Bottom-strip HUD: the GB window extends to the bottom-right of the
    // frame from wherever it starts, so a top-row HUD would occlude the
    // whole playfield (the Phase-6..13 "blank room" bug). WY=136 shows
    // only the last 8 scanlines. WX=7 = window x=0.
    WY_REG = 136;
    WX_REG = 7;
    LCDC_REG |= 0x40;   // WIN map = 0x9C00 (match set_win_tiles target)

    hud_redraw_all();
}

void hud_show(void) BANKED { SHOW_WIN; }
void hud_hide(void) BANKED { HIDE_WIN; }

void hud_redraw_hp(void) BANKED {
    u8 row[HUD_MAX_HEARTS];
    u8 hearts_total = player.hp_max;     // half-hearts
    u8 hearts_filled = player.hp;
    u8 i;

    for (i = 0; i < HUD_MAX_HEARTS; ++i) {
        u8 cap_full  = (u8)(2 + (i * 2));    // half-hearts up to and including full
        u8 cap_half  = (u8)(1 + (i * 2));
        if ((u8)((i * 2)) >= hearts_total) {
            row[i] = HUD_BLANK;             // no heart slot for this class
        } else if (hearts_filled >= cap_full) {
            row[i] = HUD_HEART_FULL;
        } else if (hearts_filled >= cap_half) {
            row[i] = HUD_HEART_HALF;
        } else {
            row[i] = HUD_HEART_EMPTY;
        }
    }
    VBK_REG = 0;
    set_win_tiles(0, 0, HUD_MAX_HEARTS, 1, row);
}

void hud_redraw_coins(void) BANKED {
    u8 row[4];
    u16 c = player.coins;
    if (c > COIN_CAP) c = COIN_CAP;
    row[0] = HUD_COIN;
    row[1] = (u8)(HUD_DIGIT_0 + (c / 100));
    row[2] = (u8)(HUD_DIGIT_0 + ((c / 10) % 10));
    row[3] = (u8)(HUD_DIGIT_0 + (c % 10));
    VBK_REG = 0;
    set_win_tiles(16, 0, 4, 1, row);
}

void hud_redraw_mp(void) BANKED {
    // MP as blue digits (cols 8-9), right-aligned; hidden for MP-less state
    u8 row[2];
    u8 m = player.mp;
    if (m > 99) m = 99;
    row[0] = (m >= 10) ? (u8)(HUD_DIGIT_0 + (m / 10)) : HUD_BLANK;
    row[1] = (u8)(HUD_DIGIT_0 + (m % 10));
    VBK_REG = 0;
    set_win_tiles(8, 0, 2, 1, row);
    palette_bg_load(6, (player.mp_max && player.mp >= player.mp_max)
        ? hud_palette_mp_full : hud_palette_mp);
}

void hud_redraw_depth(void) BANKED {
    // Room depth as 2 digits (cols 10-11). Stage identity remains available
    // from biome art and the pack screen; the old redundant digit made max-HP
    // relics impossible to display for Sauran.
    u8 row[2];
    u8 d = run_state.room_counter;
    if (d > 99) d = 99;
    row[0] = (u8)(HUD_DIGIT_0 + (d / 10));
    row[1] = (u8)(HUD_DIGIT_0 + (d % 10));
    VBK_REG = 0;
    set_win_tiles(10, 0, 2, 1, row);
}

void hud_show_offer(u8 ware, u8 price) BANKED {
    u8 row[4];
    u8 icon;
    if (price == offer_price && ware == offer_ware) return;
    offer_price = price;
    offer_ware = ware;
    // Stock prices are deliberately two-digit (5..40), leaving one HUD cell
    // for a semantic icon. The nearby heart/orb already shows physical art;
    // this tells the player what the purchase does before contact.
    switch (ware) {
        case 0:  icon = HUD_OFFER_HEAL;  break; // WARE_HEART
        case 2:  icon = HUD_OFFER_VITAL; break; // WARE_BIG
        case 3:  icon = HUD_OFFER_FORGE; break; // WARE_FORGE
        case 4:  icon = HUD_OFFER_RUNE;  break; // WARE_RUNE
        case 5:  icon = HUD_OFFER_SURGE; break; // WARE_SURGE
        case 6:  icon = HUD_OFFER_VAMP;  break; // WARE_VAMP
        case 7:  icon = HUD_OFFER_CHART; break; // WARE_CHART
        case 8:  icon = HUD_OFFER_WEAPON; break; // WARE_WEAPON
        default: icon = HUD_OFFER_RELIC; break; // WARE_ITEM / future relics
    }
    row[0] = icon;
    row[1] = HUD_COIN;
    row[2] = (price >= 10) ? (u8)(HUD_DIGIT_0 + price / 10) : HUD_BLANK;
    row[3] = (u8)(HUD_DIGIT_0 + price % 10);
    VBK_REG = 0;
    set_win_tiles(12, 0, 4, 1, row);
}

void hud_clear_offer(void) BANKED {
    static const u8 row[4] = { HUD_BLANK, HUD_BLANK, HUD_BLANK, HUD_BLANK };
    if (offer_price == 0xFF) return;
    offer_price = 0xFF;
    offer_ware = 0xFF;
    VBK_REG = 0;
    set_win_tiles(12, 0, 4, 1, row);
}

void hud_redraw_boss(u8 cur, u8 max) BANKED {
    // 4 segments, each worth max/4 HP (rounded up). Cached so per-frame
    // polling only writes VRAM when the segment count actually changes.
    static u8 last_segs = 0xFF;
    u8 segs, i;
    u8 row[4];

    if (max == 0) {
        segs = 0xFE;                     // sentinel: bar hidden
        if (segs == last_segs) return;
        for (i = 0; i < 4; ++i) row[i] = HUD_BLANK;
    } else {
        // ceil(cur * 4 / max), clamped 1..4 while alive
        u16 t = (u16)((u16)cur * 4);
        segs = (u8)((t + max - 1) / max);
        if (segs > 4) segs = 4;
        if (cur > 0 && segs == 0) segs = 1;
        if (segs == last_segs) return;
        for (i = 0; i < 4; ++i) {
            row[i] = (i < segs) ? HUD_BAR_FULL : HUD_BAR_EMPTY;
        }
    }
    last_segs = segs;
    VBK_REG = 0;
    set_win_tiles(12, 0, 4, 1, row);
}

void hud_redraw_action_charge(u8 cur, u8 max) BANKED {
    u8 row[4];
    u8 segs, i;
    if (max == 0) return;
    segs = (u8)(((u16)cur * 4u) / max);
    if (segs > 4) segs = 4;
    for (i = 0; i < 4; ++i)
        row[i] = (i < segs) ? HUD_BAR_FULL : HUD_BAR_EMPTY;
    // This lane can be replaced by a shop offer immediately after the hero
    // moves. Four WINDOW tiles per normal Wolfkin frame is intentionally
    // cheap and avoids a stale cached charge bar after that context change.
    VBK_REG = 0;
    set_win_tiles(12, 0, 4, 1, row);
}

void hud_low_hp_pulse(u8 phase) BANKED {
    // Swap HUD palette color 3 (heart red) between normal and white-hot.
    static u8 last_phase = 0xFF;
    u16 pal[4];
    u8 i;
    if (phase == last_phase) return;
    last_phase = phase;
    for (i = 0; i < 4; ++i) pal[i] = hud_palette[i];
    if (phase) pal[3] = BGR555(31, 26, 24);   // white-hot flash
    palette_bg_load(7, pal);
}

void hud_redraw_all(void) BANKED {
    hud_redraw_hp();
    hud_redraw_mp();
    hud_redraw_coins();
    hud_redraw_depth();
    hud_redraw_boss(0, 0);   // hidden until a boss is polled alive
}
