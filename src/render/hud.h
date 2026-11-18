// HUD — bottom-row strip rendered via the GBC WINDOW layer.
// Shows: hearts (HP) | MP | depth | boss health | coins
#ifndef QUINTRA_RENDER_HUD_H
#define QUINTRA_RENDER_HUD_H

#include <gb/gb.h>
#include "core/types.h"

// 8 hearts = 16 half-hearts. Sauran starts at seven hearts, leaving room for
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
void hud_show_offer(u8 ware, u8 price) BANKED; // icon + market price in cols 12..15
void hud_clear_offer(void) BANKED;    // clear a proximity price after leaving the stall
// Active power-up in the contextual lane: icon, zero-padded seconds,
// optional Aegis pip tile (hits 0xFF = none). blink hides the icon
// during the last seconds.
void hud_show_powerup(u8 icon, u8 secs, u8 hits, u8 blink) BANKED;
void hud_powerup_release(void) BANKED;
void hud_show_loot_timer(u8 seconds) BANKED; // secret-vault relic icon + seconds
void hud_clear_loot_timer(void) BANKED;
// Boss HP as a 4-segment bar (cols 12-15). max==0 clears the bar.
// Caches internally: cheap to call every frame.
void hud_redraw_boss(u8 cur, u8 max) BANKED;
// A four-segment ready bar in the same contextual HUD lane as boss health.
// The caller owns priority: boss and nearby-shop prompts supersede it.
void hud_redraw_action_charge(u8 cur, u8 max) BANKED;
// Low-HP danger pulse: phase 1 flashes the heart color white-hot,
// phase 0 restores it. Cached — safe to call every frame.
void hud_low_hp_pulse(u8 phase) BANKED;
// Set before hud_low_hp_pulse(0) so a wrapped counter or a borrowed
// palette 7 cannot skip the restore to heart-red.
extern u8 hud_heart_force;
// Brief pickup/status card in cols 10..15. Multi-effect relics retain every
// meaningful stat/status card instead of silently hiding later effects.
void hud_show_stat_gain(u8 stat, u8 amount) BANKED;
void hud_show_status(u8 status) BANKED;
void hud_show_healing_blocked(void) BANKED;
void hud_show_hunger_curse(void) BANKED;
void hud_show_mp_full(void) BANKED;
void hud_show_hp_full(void) BANKED;
// Antidote cue: CURED in green.
void hud_show_cured(void) BANKED;
void hud_show_cache_guarded(void) BANKED;
// Name the capped stat when a boost cannot apply, e.g. SPDMAX.
void hud_show_stat_max(u8 stat) BANKED;
// Pickup words (six HUD cells). Keep in sync with notice_words[].
enum {
    NW_REVIVE, NW_FORK, NW_BOUNCE, NW_THORNS, NW_DRUM, NW_FLASK, NW_BLAST,
    NW_BEAM, NW_VAMP, NW_WARD, NW_CHART, NW_WEAPON, NW_HEALED, NW_SCOUT,
    NW_CLEAN, NW_BURST, NW_CHIME, NW_MIRROR, NW_CURE1, NW_HURT1,
    NW_COINMAX, NW_OWNED, NW_NOROOM, NW_KNOWN, NW_LOWHP, NW_ASWAP,
    NW_WARDED,
    // Secret merchants: bottle latch, Riftwell re-arm, charm names.
    NW_ARMED, NW_REARM, NW_LIGHT, NW_COMB, NW_CINDER, NW_SKATES, NW_MASK,
    NW_LAMP, NW_SEAL, NW_PACT, NW_LAST, NW_BELL, NW_LURE, NW_WICK,
    // Power-up cards (held HUD_NOTICE_POWERUP_FRAMES). Keep NW_AEGIS first.
    NW_AEGIS, NW_BLOCK3, NW_LIMIT, NW_FREEMP, NW_MEND, NW_REGEN, NW_ENDED,
    NW_COUNT
};
// Pickup notice kinds (below the 0x80 status flag, above the stat ids).
#define HUD_NOTICE_WORD  0x74   // amount = NW_* word id
#define HUD_NOTICE_HEAL  0x73   // HEAL+n
#define HUD_NOTICE_MANA  0x72   // MANA+n
#define HUD_NOTICE_COIN  0x71   // coin +nn
#define HUD_NOTICE_LOSS  0x70   // amount = stat << 4 | n: ATK-1, MAX heart-2
#define HUD_NOTICE_NEED  0x6F   // NEEDnn: a ware costs more than the purse
// Bank 14: queue a pickup card unless the same kind+amount is already up.
void hud_notice_pair(u8 kind, u8 amount) BANKED;
// Bank 17 (pickup_notice.c): fill six word cells, return its palette code.
u8 hud_notice_word_fill(u8 word, u8 *row) BANKED;
void hud_show_word(u8 word) BANKED;       // 0xFF / out of range: no-op
void hud_show_heal(u8 n) BANKED;          // HEAL+n (refill, not max HP)
void hud_show_mana(u8 n) BANKED;          // MANA+n (refill, not max MP)
void hud_show_coins(u8 n) BANKED;         // coin +nn
void hud_show_need(u8 price) BANKED;      // NEEDnn: ware too expensive
void hud_show_stat_loss(u8 stat, u8 n) BANKED; // ATK-1, MAX heart-2
void hud_show_item(u8 item_id) BANKED;    // presence relic / tool word
void hud_show_curse(u8 kind) BANKED;      // CURSE + its concrete cost
void hud_show_boomerang(void) BANKED;
void hud_show_hookshot(void) BANKED;
void hud_show_secondary(u8 bomb) BANKED;
void hud_show_boss_link(u8 mode) BANKED;
void hud_tick_notice(void) BANKED;
void hud_redraw_all(void) BANKED;

#endif
