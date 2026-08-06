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
#include "game/inventory_copy.h"
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
    "FAST MOVEMENT",    // Wolfkin: +1 SPD
    "HEALTH REGEN",     // Sauran: slow HP regen
    "SHOW ENEMY HP",    // Corvin: HUD bar reads enemy HP
    "FAST MAGIC REGEN", // Picsean: MP regen x2
    "STRONG ELEMENTS",  // Vespine: elemental hits +1
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
    "8 SHOTS BRIEF WARD", // Howl, item id 10
    "BLOCKS ALL HITS",    // Stoneskin, 11
    "3 SHARD FAN",        // Murder, 12
    "3 BUBBLES AND WARD", // Tidal Wave, 13
    "4 STINGERS WARD",    // Swarm, 14
};

static const char *active_tip_by_id(u16 id) {
    return (id >= 10 && id < 15) ? active_tips[id - 10] : "SEE SIG";
}

static const char *item_name_by_index(u8 index) {
    return index < N_ITEMS ? items[index].name : "-";
}

static u8 relic_count(void) {
    u8 i, count = 0;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] != 0xFF) count++;
    return count;
}

static const char *gear_color(void) {
    if (room_appearance_tier == 1) return "BLUE";
    if (room_appearance_tier == 2) return "RED";
    if (room_appearance_tier >= 3) return "GOLD";
    return "BASE";
}

// One progression-aware line turns the Pack into a useful "what do I do
// next?" screen. In particular, calling the stage key only a Sigil made its
// purpose opaque to a first-time player even after the Compass correctly
// marked its room. Every phrase fits the physical 20-column LCD exactly.
static void write_current_goal(void) {
    gotoxy(0, 14);
    if (run_state.world_mode) {
        text_write("NEXT FIND DUNGEON");
    } else if (RUN_ROOM_IS_TOWN(run_state.room_counter)) {
        text_write("NEXT REST THEN NORTH");
    } else if (run_state_is_boss_room()) {
        text_write("NEXT BREAK COLOSSUS");
    } else if (!(run_state.rift_sigils
            & RUN_STAGE_SIGIL_BIT(run_state.bosses_beaten))) {
        text_write("NEXT FIND SIGIL KEY");
    } else if (!(run_state.dungeon_puzzles & RUN_WARDEN_BOON_BIT)) {
        text_write("NEXT CLEAR WARDEN");
    } else if (run_state_dungeon_size() >= 12
            && !(run_state.dungeon_puzzles & RUN_WAYSTONE_BIT)) {
        text_write("NEXT WAKE WAYSTONE");
    } else if (run_state_dungeon_size() >= 14
            && !(run_state.dungeon_phase & RUN_DEEP_WARDEN_BIT)) {
        text_write("NEXT CLEAR DEEP WARD");
    } else if (run_state_dungeon_size() >= 20
            && !(run_state.dungeon_phase & RUN_DEEP_PHASE_OPEN_BIT)) {
        text_write("NEXT OPEN DEEP SEAL");
    } else {
        text_write("NEXT SEEK SKULL GATE");
    }
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

    gotoxy(0, 0);  text_write("PACK  ");
    text_write(class_name(player.class_id));
    {
        // Endless descent wraps the theme cycle — name what you see
        u8 s = (u8)(run_state.bosses_beaten % 9);
        // Riftwild is an outdoors connector, not a dungeon stage.  Naming
        // both its current mode and destination keeps the green path from
        // reading as an unexplained "Stage N".
        if (run_state.world_mode) {
            gotoxy(0, 1); text_write(RUN_IS_EASY() ? "EASY  RIFTWILD" : "NORMAL  RIFTWILD");
            gotoxy(0, 2); text_write("NEXT "); text_write(stage_names[s]);
        } else if (RUN_ROOM_IS_TOWN(run_state.room_counter)) {
            gotoxy(0, 1); text_write(RUN_IS_EASY() ? "EASY  VILLAGE" : "NORMAL  VILLAGE");
            gotoxy(0, 2); text_write("SAFE HAVEN");
        } else {
            gotoxy(0, 1); text_write(RUN_IS_EASY() ? "EASY  STAGE " : "NORMAL  STAGE ");
            text_u16((u16)(run_state.bosses_beaten + 1));
            gotoxy(0, 2); text_write(stage_names[s]);
        }
    }

    gotoxy(0, 4); text_write("HEALTH "); text_u16((u16)player.hp);
    text_write("/"); text_u16((u16)player.hp_max);
    gotoxy(0, 5); text_write("MAGIC  "); text_u16((u16)player.mp);
    text_write("/"); text_u16((u16)player.mp_max);
    gotoxy(0, 6); text_write("ATTACK "); text_u16((u16)player.atk);
    text_write("  ARMOR "); text_u16((u16)player.def);
    gotoxy(0, 7); text_write("SPEED  "); text_u16((u16)player.spd);
    text_write("  LUCK "); text_u16((u16)player.lck);
    gotoxy(0, 8); text_write("RELICS "); text_u16((u16)relic_count());
    text_write(" COLOR "); text_write(gear_color());

    gotoxy(0, 9); text_write("A ");
    text_write(item_name_by_index(player.starter_weapon));
    gotoxy(0, 10); text_write("  ");
    inventory_write_weapon_tip(player.starter_weapon);
    gotoxy(0, 11); text_write("B ");
    text_write(item_name_by_id(player.active_item));
    gotoxy(0, 12); text_write("  ");
    text_write(active_tip_by_id(player.active_item));
    gotoxy(0, 13); text_write("TRAIT ");
    text_write(perk_names[player.class_id < 5 ? player.class_id : 0]);
    write_current_goal();

    gotoxy(0, 15); text_write("COINS "); text_u16((u16)player.coins);
    text_write(" BOSSES "); text_u16((u16)run_state.bosses_beaten);
    text_write("/"); text_u16((u16)BOSSES_TO_WIN);
    gotoxy(0, 16); text_write("FULL MP A+B ASCEND");
    gotoxy(0, 17); text_write("START OR B BACK");

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
