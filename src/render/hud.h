// HUD — bottom-row strip rendered via the GBC WINDOW layer.
// Shows: hearts (HP) | MP | depth | boss health | coins
#ifndef QUINTRA_RENDER_HUD_H
#define QUINTRA_RENDER_HUD_H

#include <gb/gb.h>
#include "core/types.h"

// 8 hearts = 16 half-hearts. Sauran starts at six hearts, leaving room for
// procedural Iron Heart / Vampiric Sigil upgrades like every other vessel.
#define HUD_MAX_HEARTS 8
#define HP_CAP        16     // half-hearts; enforced on all HP gains

void hud_init(void) BANKED;          // load tiles + position window + initial draw
void hud_show(void) BANKED;          // SHOW_WIN
void hud_hide(void) BANKED;          // HIDE_WIN
void hud_redraw_hp(void) BANKED;     // call when player.hp / hp_max changes
void hud_redraw_mp(void) BANKED;     // call when player.mp changes (blue digits)
void hud_redraw_coins(void) BANKED;  // call when player.coins changes
void hud_redraw_depth(void) BANKED;  // call when run_state.room_counter changes
void hud_show_offer(u8 price) BANKED; // show market price in cols 12..15
void hud_clear_offer(void) BANKED;    // clear a proximity price after leaving the stall
// Boss HP as a 4-segment bar (cols 12-15). max==0 clears the bar.
// Caches internally: cheap to call every frame.
void hud_redraw_boss(u8 cur, u8 max) BANKED;
// Low-HP danger pulse: phase 1 flashes the heart color white-hot,
// phase 0 restores it. Cached — safe to call every frame.
void hud_low_hp_pulse(u8 phase) BANKED;
void hud_redraw_all(void) BANKED;

#endif
