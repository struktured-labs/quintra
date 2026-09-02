#pragma bank 14
// Zelda/Ultima-shaped PACK panel. START pauses into one framed visual page:
// hero portrait, vitals, equipped A/B verbs, quest, tools, and Oath. It
// returns through room_resume so opening the panel never regenerates a room.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <gbdk/font.h>
#include <stdio.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/inventory.h"
#include "game/inventory_copy.h"
#include "game/inventory_visual.h"
#include "game/inventory_waygear.h"
#include "game/dungeon_tools.h"
#include "game/curse.h"
#include "game/dungeon_law.h"
#include "game/oath_arts.h"
#include "game/player.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "game/will.h"
#include "render/palette.h"
#include "render/text.h"
#include "content.h"

BANKREF(inventory_enter)

static u8 inventory_page;

static const u16 inv_palette[4] = {
    BGR555( 1,  2,  6), BGR555( 6,  9, 18),
    BGR555(18, 21, 28), BGR555(31, 31, 31),
};
static const u16 inv_gold_bg[4] = {
    BGR555( 1,  2,  6), BGR555(13,  8,  1),
    BGR555(25, 18,  4), BGR555(31, 29, 16),
};
static const u16 inv_magic_bg[4] = {
    BGR555( 1,  2,  6), BGR555( 8,  3, 15),
    BGR555(18,  8, 27), BGR555(29, 22, 31),
};
static const u16 inv_quest_bg[4] = {
    BGR555( 1,  2,  6), BGR555( 3, 10,  6),
    BGR555( 8, 22, 12), BGR555(24, 31, 20),
};

// Dedicated 2bpp rails replace the old literal '+', '-' and '|' glyphs.
// Bright inner strokes and a darker one-pixel bevel make the four PACK
// regions read as one carved interface on color, grayscale, and IPS panels.
#define INV_FRAME_BASE ((u8)0xF6u)
#define INV_FRAME_H    ((u8)0xF6u)
#define INV_FRAME_VL   ((u8)0xF7u)
#define INV_FRAME_VR   ((u8)0xF8u)
#define INV_FRAME_TL   ((u8)0xF9u)
#define INV_FRAME_TR   ((u8)0xFAu)
#define INV_FRAME_BL   ((u8)0xFBu)
#define INV_FRAME_BR   ((u8)0xFCu)
#define INV_FRAME_TLJ  ((u8)0xFDu)
#define INV_FRAME_TRJ  ((u8)0xFEu)

static const u8 inv_frame_tiles[9][16] = {
    { 0,0, 0,0, 0,0, 0xFF,0xFF, 0,0xFF, 0,0, 0,0, 0,0 },
    { 0x10,0x18, 0x10,0x18, 0x10,0x18, 0x10,0x18,
      0x10,0x18, 0x10,0x18, 0x10,0x18, 0x10,0x18 },
    { 0x08,0x18, 0x08,0x18, 0x08,0x18, 0x08,0x18,
      0x08,0x18, 0x08,0x18, 0x08,0x18, 0x08,0x18 },
    { 0,0, 0,0, 0,0, 0x1F,0x1F, 0x10,0x1F,
      0x10,0x18, 0x10,0x18, 0x10,0x18 },
    { 0,0, 0,0, 0,0, 0xF8,0xF8, 0x08,0xF8,
      0x08,0x18, 0x08,0x18, 0x08,0x18 },
    { 0x10,0x18, 0x10,0x18, 0x10,0x18, 0x1F,0x1F,
      0,0x1F, 0,0, 0,0, 0,0 },
    { 0x08,0x18, 0x08,0x18, 0x08,0x18, 0xF8,0xF8,
      0,0xF8, 0,0, 0,0, 0,0 },
    { 0x10,0x18, 0x10,0x18, 0x10,0x18, 0x1F,0x1F,
      0x10,0x1F, 0x10,0x18, 0x10,0x18, 0x10,0x18 },
    { 0x08,0x18, 0x08,0x18, 0x08,0x18, 0xF8,0xF8,
      0x08,0xF8, 0x08,0x18, 0x08,0x18, 0x08,0x18 },
};

static const char *class_name(u8 id) {
    if (id < N_CLASSES) return classes[id].name;
    return "?";
}

// stage_names now comes from the generated stage tables (stages.h).

// Class passive perk names, indexed by class id (see player.c/room.c
// for the mechanics each one drives).
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
    "8 SHOTS + WARD",  // Howl, item id 10
    "FULL HIT SHIELD", // Stoneskin, 11
    "MARK + RAVEN DIVE", // Raven Mark, 12
    "3 BUBBLES + WARD", // Tidal Wave, 13
    "ORBITING STINGERS", // Swarm, 14
};

static const char *active_tip_by_id(u16 id) {
    return (id >= 10 && id < 15) ? active_tips[id - 10] : "SEE SIG";
}

static const char *item_name_by_index(u8 index) {
    return index < N_ITEMS ? items[index].name : "-";
}

static void write_field(const char *s, u8 width) {
    while (width && *s) { putchar(*s++); width--; }
    while (width--) putchar(' ');
}

static u8 *inventory_bg_map(void) {
    return (LCDC_REG & LCDCF_BG9C00) ? (u8 *)0x9C00 : (u8 *)0x9800;
}

static void frame_row(u8 y, u8 left, u8 right) {
    u8 row[20];
    u8 x;
    row[0] = left;
    for (x = 1; x < 19; ++x) row[x] = INV_FRAME_H;
    row[19] = right;
    set_tiles(0, y, 20, 1, inventory_bg_map(), row);
}

static void frame_sides(u8 y) {
    u8 tile = INV_FRAME_VL;
    set_tiles(0, y, 1, 1, inventory_bg_map(), &tile);
    tile = INV_FRAME_VR;
    set_tiles(19, y, 1, 1, inventory_bg_map(), &tile);
}

static void draw_pack_frames(void) {
    u8 y;
    VBK_REG = 0;
    set_bkg_data(INV_FRAME_BASE, 9, inv_frame_tiles[0]);
    frame_row(0, INV_FRAME_TL, INV_FRAME_TR);
    for (y = 1; y <= 3; ++y) frame_sides(y);
    frame_row(4, INV_FRAME_TLJ, INV_FRAME_TRJ);
    for (y = 5; y <= 7; ++y) frame_sides(y);
    frame_row(8, INV_FRAME_TLJ, INV_FRAME_TRJ);
    for (y = 9; y <= 12; ++y) frame_sides(y);
    frame_row(13, INV_FRAME_TLJ, INV_FRAME_TRJ);
    for (y = 14; y <= 16; ++y) frame_sides(y);
    frame_row(17, INV_FRAME_BL, INV_FRAME_BR);
}

static void attr_row(u8 y, u8 slot) {
    u8 attrs[20];
    u8 x;
    u8 *map = (LCDC_REG & LCDCF_BG9C00) ? (u8 *)0x9C00 : (u8 *)0x9800;
    for (x = 0; x < 20; ++x) attrs[x] = slot;
    VBK_REG = 1;
    set_tiles(0, y, 20, 1, map, attrs);
    VBK_REG = 0;
}

static void inventory_help_enter(void) {
    u8 i;
    DISPLAY_OFF;
    HIDE_SPRITES;
    cls();
    draw_pack_frames();
    gotoxy(5, 0); text_write(" COMBAT ");
    gotoxy(5, 4); text_write(" SIGNATURE ");
    gotoxy(5, 8); text_write(" SPIRIT ");
    gotoxy(4, 13); text_write(" EQUIPMENT ");

    gotoxy(1, 1); text_write("A  PRIMARY WEAPON");
    gotoxy(2, 2); write_field(item_name_by_index(player.starter_weapon), 16);
    gotoxy(1, 3); text_write("RED ORB + A = SWAP");

    gotoxy(1, 5); text_write("B  FREE SIGNATURE");
    gotoxy(2, 6); write_field(item_name_by_id(player.active_item), 16);
    gotoxy(1, 7); text_write("RECHARGES; NO MP");

    gotoxy(1, 9); text_write("A+B OATH: 2 MP");
    gotoxy(1, 10); text_write("FULL MP: CONVERGE");
    gotoxy(1, 11); text_write("RELEASE A FOR 3S");
    gotoxy(1, 12); text_write("NEXT A: WILL MAX");

    gotoxy(1, 14); text_write("WEAPONS: ORB + A");
    gotoxy(1, 15); text_write("PACK: SEL FOR GEAR");
    gotoxy(1, 16); text_write("UP/DN + A EQUIPS");
    gotoxy(1, 17); text_write("SEL PACK B RETURN");

    palette_bg_fill_attrs(0);
    attr_row(0, 1); attr_row(4, 1); attr_row(8, 2);
    for (i = 9; i <= 12; ++i) attr_row(i, 2);
    attr_row(13, 3);
    for (i = 14; i <= 16; ++i) attr_row(i, 3);
    attr_row(17, 1);
    SHOW_BKG;
    DISPLAY_ON;
}

// One progression-aware line turns the Pack into a useful "what do I do
// next?" screen. In particular, calling the stage key only a Sigil made its
// purpose opaque to a first-time player even after the Compass correctly
// marked its room. Every phrase fits the physical 20-column LCD exactly.
void inventory_enter(void) {
    u8 i;
    inventory_page = 0;
    DISPLAY_OFF;
    VBK_REG = 0;
    HIDE_SPRITES;
    HIDE_WIN;
    palette_bg_load(0, inv_palette);
    palette_bg_load(1, inv_gold_bg);
    palette_bg_load(2, inv_magic_bg);
    palette_bg_load(3, inv_quest_bg);
    palette_bg_load(7, inv_palette);

    font_init();
    { font_t f = font_load(font_min); font_set(f); }
    cls();

    draw_pack_frames();
    gotoxy(5, 0); text_write(" QUINTRA ");
    gotoxy(5, 4); text_write(" VITALS ");
    gotoxy(7, 8); text_write(" ARMS ");
    gotoxy(6, 13); text_write(" QUEST ");
    gotoxy(2, 17); text_write("SEL GEAR B BACK");
    inventory_prepare_sprites();

    gotoxy(4, 1); write_field(class_name(player.class_id), 7);
    if (player_status_kind != QSTATUS_NONE) status_draw_pack_label();
    else if (player.curse_flags) curse_draw_pack_label();
    else if (room_weapon_surge_ticks || room_transform_ticks
        || player.shield_timer || will_corvin_mark_ticks
        || will_vespine_swarm_ticks) {
        gotoxy(12, 1); text_write("BOOSTED");
    }
    else { gotoxy(12, 1); text_write(RUN_IS_EASY() ? "EASY" : "NORMAL"); }
    {
        u8 s = (u8)(run_state.bosses_beaten % 9);
        gotoxy(4, 2);
        if (run_state.world_mode) {
            text_write("RIFTWILD");
        } else if (RUN_ROOM_IS_TOWN(run_state.room_counter)) {
            text_write("VILLAGE");
        } else {
            text_write("STAGE ");
            text_u16((u16)(run_state.bosses_beaten + 1));
        }
        gotoxy(1, 3); write_field(stage_names[s], 17);
    }
    dungeon_law_draw_pack();

    gotoxy(1, 5); text_write("HP "); text_u16((u16)player.hp);
    text_write("/"); text_u16((u16)player.hp_max);
    gotoxy(11, 5); text_write("MP "); text_u16((u16)player.mp);
    text_write("/"); text_u16((u16)player.mp_max);
    gotoxy(1, 6); text_write("ATK "); text_u16((u16)(STATUS_PLAYER_INVERTED()
        ? status_player_effective_stat(QSTATUS_STAT_ATK) : player.atk));
    gotoxy(7, 6); text_write("DEF "); text_u16((u16)(STATUS_PLAYER_INVERTED()
        ? status_player_effective_stat(QSTATUS_STAT_DEF) : player.def));
    gotoxy(13, 6); text_write("SPD "); text_u16((u16)(STATUS_PLAYER_INVERTED()
        ? status_player_effective_stat(QSTATUS_STAT_SPD) : player.spd));
    gotoxy(1, 7); text_write("LCK "); text_u16((u16)(STATUS_PLAYER_INVERTED()
        ? status_player_effective_stat(QSTATUS_STAT_LCK) : player.lck));
    gotoxy(9, 7); text_u16((u16)player.coins);
    gotoxy(13, 7); text_write("W[");
    for (i = 0; i < 3; ++i)
        putchar((u16)player.will_charge * 3u
            >= (u16)(i + 1) * WILL_MAX ? '#' : '-');
    putchar(']');

    gotoxy(1, 9); text_write("A");
    gotoxy(5, 9); write_field(item_name_by_index(player.starter_weapon), 13);
    gotoxy(2, 10);
    inventory_write_weapon_tip(player.starter_weapon);
    gotoxy(1, 11); text_write("B");
    gotoxy(5, 11); write_field(item_name_by_id(player.active_item), 13);
    gotoxy(2, 12);
    text_write(active_tip_by_id(player.active_item));
    inventory_write_current_goal();
    dungeon_tools_draw_pack();
    oath_arts_draw_pack();

    palette_bg_fill_attrs(0);
    attr_row(0, 1); attr_row(4, 1); attr_row(8, 2);
    for (i = 9; i <= 12; ++i) attr_row(i, 2);
    attr_row(13, 3);
    for (i = 14; i <= 16; ++i) attr_row(i, 3);
    attr_row(17, 1);
    SHOW_SPRITES;
    SHOW_BKG;
    DISPLAY_ON;
}

void inventory_exit(void) {
    u8 i;
    for (i = 0; i < 40; ++i) move_sprite(i, 0, 0);
    HIDE_SPRITES;
}

screen_id_t inventory_tick(u8 keys, u8 pressed) {
    u8 tool_action;
    keys;
    if (inventory_page) {
        if (inventory_page == 3) {
            if (pressed & (J_START | J_B)) {
                sfx_play(SFX_COIN);
                room_request_resume();
                return SCREEN_ROOM;
            }
            if (pressed & J_SELECT) {
                inventory_enter();
                return SCREEN_SELF;
            }
            return SCREEN_SELF;
        }
        if (inventory_page == 2) {
            if (pressed & (J_START | J_B)) {
                sfx_play(SFX_COIN);
                room_request_resume();
                return SCREEN_ROOM;
            }
            if (pressed & J_SELECT) {
                inventory_page = 3;
                inventory_help_enter();
                return SCREEN_SELF;
            }
            return SCREEN_SELF;
        }
        u8 gear_action = inventory_waygear_tick(pressed);
        if (gear_action == INVENTORY_WAYGEAR_EXIT) {
            sfx_play(SFX_COIN);
            room_request_resume();
            return SCREEN_ROOM;
        }
        if (gear_action == INVENTORY_WAYGEAR_PACK) {
            inventory_page = 2;
            inventory_status_enter();
            return SCREEN_SELF;
        }
        return SCREEN_SELF;
    }
    if (pressed & (J_START | J_B)) {
        sfx_play(SFX_COIN);
        room_request_resume();
        return SCREEN_ROOM;
    }
    if (pressed & J_SELECT) {
        inventory_page = 1;
        inventory_waygear_enter();
        return SCREEN_SELF;
    }
    if (oath_arts_pack_input(pressed)) return SCREEN_SELF;
    tool_action = dungeon_tools_pack_input(pressed);
    if (tool_action == 2) {
        room_request_resume();
        return SCREEN_ROOM;
    }
    return SCREEN_SELF;
}

void inventory_draw(void) {}
