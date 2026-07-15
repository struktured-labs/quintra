// HUD — bottom-row strip rendered via the GBC WINDOW layer.
// Shows: hearts (HP) | MP | depth | boss health | coins
#ifndef QUINTRA_RENDER_HUD_H
#define QUINTRA_RENDER_HUD_H

#include "core/types.h"

// 8 hearts = 16 half-hearts. Sauran starts at six hearts, leaving room for
// procedural Iron Heart / Vampiric Sigil upgrades like every other vessel.
#define HUD_MAX_HEARTS 8
#define HP_CAP        16     // half-hearts; enforced on all HP gains

void hud_init(void);          // load tiles + position window + initial draw
void hud_show(void);          // SHOW_WIN
void hud_hide(void);          // HIDE_WIN
void hud_redraw_hp(void);     // call when player.hp / hp_max changes
void hud_redraw_mp(void);     // call when player.mp changes (blue digits)
void hud_redraw_coins(void);  // call when player.coins changes
void hud_redraw_depth(void);  // call when run_state.room_counter changes
// Boss HP as a 4-segment bar (cols 12-15). max==0 clears the bar.
// Caches internally: cheap to call every frame.
void hud_redraw_boss(u8 cur, u8 max);
// Low-HP danger pulse: phase 1 flashes the heart color white-hot,
// phase 0 restores it. Cached — safe to call every frame.
void hud_low_hp_pulse(u8 phase);
void hud_redraw_all(void);

#endif
