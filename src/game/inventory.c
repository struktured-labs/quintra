#pragma bank 4
// INVENTORY / STATS pause screen. Opened with START from a room; shows the
// hero's class, live stats, held weapon + signature, coins, and run depth.
// Returns to the room via a resume flag so the room is NOT regenerated.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <gbdk/font.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/inventory.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/palette.h"
#include "render/text.h"
#include "content.h"

BANKREF(inventory_enter)

static const u16 inv_palette[4] = {
    BGR555( 1,  2,  6),    // 0: deep blue
    BGR555( 8, 10, 20),    // 1: slate
    BGR555(20, 20, 28),    // 2: light
    BGR555(31, 31, 31),    // 3: white
};

static const char *class_name(u8 id) {
    if (id < N_CLASSES) return classes[id].name;
    return "?";
}

// stage_names now comes from the generated stage tables (stages.h).

// Class passive perk names, indexed by class id (see player.c/room.c
// for the mechanics each one drives).
static const char *const perk_names[5] = {
    "SWIFT PAWS",     // Wolfkin: +1 SPD
    "SCALED HIDE",    // Sauran: slow HP regen
    "RAVEN SIGHT",    // Corvin: HUD bar reads enemy HP
    "TIDE ATTUNED",   // Picsean: MP regen x2
    "VENOM SYNERGY",  // Vespine: elemental hits +1
};

// items[] is keyed by array position but item.id != index beyond the 5
// starters — resolve the real entry by id (small table, linear scan is fine).
static const char *item_name_by_id(u16 id) {
    u8 i;
    for (i = 0; i < N_ITEMS; ++i) {
        if (items[i].id == id) return items[i].name;
    }
    return "-";
}

// The pause screen is only 20 columns wide. Full item descriptions belong in
// content and shop context; these are one-line action reminders that never
// clip or repeat the B label already shown above.
static const char *const active_tips[5] = {
    "8WAY WARD",      // Howl, item id 10
    "BLOCK HITS",     // Stoneskin, 11
    "3WAY FAN",       // Murder, 12
    "3BUB WARD",      // Tidal Wave, 13
    "4FAN WARD",      // Swarm, 14
};

static const char *active_tip_by_id(u16 id) {
    return (id >= 10 && id < 15) ? active_tips[id - 10] : "SEE SIG";
}

static const char *item_name_by_index(u8 index) {
    return index < N_ITEMS ? items[index].name : "-";
}

void inventory_enter(void) {
    DISPLAY_OFF;
    HIDE_SPRITES;
    HIDE_WIN;
    palette_bg_load(0, inv_palette);
    palette_bg_load(7, inv_palette);

    font_init();
    { font_t f = font_load(font_min); font_set(f); }
    cls();

    gotoxy(5, 0);  text_write("- PACK -");
    gotoxy(1, 2);  text_write(class_name(player.class_id));
    {
        // Endless descent wraps the theme cycle — name what you see
        u8 s = (u8)(run_state.bosses_beaten % 9);
        // Riftwild is an outdoors connector, not a dungeon stage.  Naming
        // both its current mode and destination keeps the green path from
        // reading as an unexplained "Stage N".
        if (run_state.world_mode) {
            gotoxy(11, 2); text_write("RIFTWILD");
            gotoxy(0, 3);  text_write("NEXT "); text_write(stage_names[s]);
        } else if (RUN_ROOM_IS_TOWN(run_state.room_counter)) {
            gotoxy(11, 2); text_write("VILLAGE");
            gotoxy(1, 3);  text_write("SAFE HAVEN");
        } else {
            gotoxy(11, 2); text_write("stage "); text_u16((u16)(run_state.bosses_beaten + 1));
            gotoxy(1, 3);  text_write(stage_names[s]);
        }
    }

    gotoxy(1, 4);  text_write("HP "); text_u16((u16)player.hp); text_write("/"); text_u16((u16)player.hp_max);
    gotoxy(11, 4); text_write("MP "); text_u16((u16)player.mp); text_write("/"); text_u16((u16)player.mp_max);
    gotoxy(1, 6);  text_write("ATK "); text_u16((u16)player.atk);
    gotoxy(8, 6);  text_write("DEF "); text_u16((u16)player.def);
    gotoxy(1, 8);  text_write("SPD "); text_u16((u16)player.spd);
    gotoxy(8, 8);  text_write("LCK "); text_u16((u16)player.lck);

    gotoxy(1, 10); text_write("WPN A:");
    text_write(item_name_by_index(player.starter_weapon));
    gotoxy(1, 11); text_write("SIG B:");
    text_write(item_name_by_id(player.active_item));
    gotoxy(1, 12); text_write("PERK  ");
    text_write(perk_names[player.class_id < 5 ? player.class_id : 0]);
    gotoxy(1, 13); text_write("ACT "); text_write(active_tip_by_id(player.active_item));

    gotoxy(1, 14); text_write("coins "); text_u16((u16)player.coins);
    gotoxy(10, 14);
    if (run_state.run_timer < 6000) {
        text_write("TIME "); text_u16((u16)(run_state.run_timer / 60)); text_write(":");
        text_digit((u8)((run_state.run_timer % 60) / 10));
        text_digit((u8)(run_state.run_timer % 10));
    } else {
        text_write("TIME 99+");
    }
    gotoxy(1, 15); text_write("bosses "); text_u16((u16)run_state.bosses_beaten);
    text_write("/"); text_u16((u16)BOSSES_TO_WIN);
    gotoxy(1, 16); text_write("kills "); text_u16((u16)run_state.enemies_killed);
    gotoxy(13, 16); text_write(RUN_IS_EASY() ? "EASY" : "NORM");

    // Spirit Convergence is Quintra's defining Penta-style temporary power
    // form, but a README-only chord is effectively a hidden mechanic. The
    // same START/B input that opened this modal already makes resuming
    // discoverable; spend the final row on the action players cannot infer.
    gotoxy(1, 17); text_write("FULL MP A B CHORD");

    palette_bg_fill_attrs(0);
    SHOW_BKG;
    DISPLAY_ON;
}

void inventory_exit(void) {}

screen_id_t inventory_tick(u8 keys, u8 pressed) {
    keys;
    if (pressed & (J_START | J_B)) {
        sfx_play(SFX_COIN);
        room_request_resume();
        return SCREEN_ROOM;
    }
    return SCREEN_SELF;
}

void inventory_draw(void) {}
