#pragma bank 8
// Two-page conversations for village residents, merchants, and peaceful
// stage creatures. The room is resumed rather than regenerated on exit, so a
// conversation cannot reroll enemies, stock, secrets, or the dungeon graph.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <gbdk/font.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/dialog.h"
#include "game/pickup.h"
#include "game/room.h"
#include "game/shop_copy.h"
#include "render/palette.h"
#include "render/text.h"
#include "render/tiles.h"

BANKREF(dialog_enter)

u8 dialog_kind;
u8 dialog_topic;
u8 dialog_page;
static u8 dialog_is_reward;

#define SPR_DIALOG_SIGIL 200

// A 16x16 authored artifact replaces the ordinary 8x8 floor pickup on the
// claim page. Four independent quadrants keep the inner rift and pale facets
// readable at native LCD scale instead of crudely repeating one tiny icon.
static const u8 dialog_sigil_tiles[64] = {
    0x01,0x00, 0x02,0x01, 0x04,0x03, 0x09,0x07,
    0x13,0x0F, 0x26,0x1F, 0x4D,0x3E, 0x9B,0x7C,
    0x80,0x00, 0x40,0x80, 0x20,0xC0, 0x90,0xE0,
    0xC8,0xF0, 0x64,0xF8, 0xB2,0x7C, 0xD9,0x3E,
    0x9B,0x7C, 0x4D,0x3E, 0x26,0x1F, 0x13,0x0F,
    0x09,0x07, 0x04,0x03, 0x02,0x01, 0x01,0x00,
    0xD9,0x3E, 0xB2,0x7C, 0x64,0xF8, 0xC8,0xF0,
    0x90,0xE0, 0x20,0xC0, 0x40,0x80, 0x80,0x00,
};

static const u16 dialog_sigil_palette[4] = {
    BGR555(0,0,0), BGR555(6,2,13),
    BGR555(22,8,31), BGR555(31,27,31),
};

static const u16 dialog_palette[4] = {
    BGR555(1, 2, 6), BGR555(7, 10, 17),
    BGR555(21, 22, 25), BGR555(31, 31, 31),
};

static void dialog_lines(const char *a, const char *b, const char *c) {
    gotoxy(1, 5); text_write(a);
    gotoxy(1, 7); text_write(b);
    gotoxy(1, 9); text_write(c);
}

static void wayfarer_title(void) {
    switch (dialog_topic) {
        case 0: text_write("CRYSTAL CRAB"); break;
        case 1: text_write("MOSS COIL"); break;
        case 2: text_write("CINDER KITE"); break;
        case 3: text_write("FROST LANCER"); break;
        case 4: text_write("BOG TOAD"); break;
        case 5: text_write("BRAMBLE SPRITE"); break;
        case 6: text_write("SUNWHEEL"); break;
        case 7: text_write("DUSK MIDGE"); break;
        default: text_write("VOID HALO"); break;
    }
}

static void dialog_title(void) {
    switch (dialog_kind) {
        case PICKUP_RIFT_SIGIL: text_write("RIFT SIGIL"); break;
        case PICKUP_VILLAGER: text_write("HEARTH ELDER"); break;
        case PICKUP_MERCHANT: text_write("RIFT MERCHANT"); break;
        case PICKUP_SMITH: text_write("FORGE KEEPER"); break;
        case PICKUP_APOTHECARY: text_write("RUNE TENDER"); break;
        case PICKUP_CARTOGRAPHER: text_write("CHARTWRIGHT"); break;
        case PICKUP_WAYKEEPER: text_write("WAYKEEPER"); break;
        case PICKUP_LOREKEEPER: text_write("LORE WITNESS"); break;
        case PICKUP_BELLKEEPER: text_write("BELL KEEPER"); break;
        default: wayfarer_title(); break;
    }
}

static void wayfarer_lore(void) {
    switch (dialog_topic) {
        case 0: dialog_lines("STONE KEEPS ECHOES", "OF THE FIRST RIFT", "LISTEN FOR ECHOES"); break;
        case 1: dialog_lines("ROOTS REMEMBER FIVE", "SPARKS BEFORE KINGS", "THE SERPENT HUNGERS"); break;
        case 2: dialog_lines("EMBER FED THE OATH", "WHEN THE SKY BROKE", "ASH STILL KNOWS IT"); break;
        case 3: dialog_lines("ICE HOLDS A NAME", "THE VOID CANNOT EAT", "SPEAK IT IN WINTER"); break;
        case 4: dialog_lines("MIRES DREAM OF RAIN", "BENEATH THE ROT", "OLD WATER ENDURES"); break;
        case 5: dialog_lines("SHADOW IS A DOOR", "NOT ITS MASTER", "FIVE WALKED THROUGH"); break;
        case 6: dialog_lines("THE SUNWHEEL TURNED", "BEFORE TIME DAWNED", "GOLD RECALLS FIRE"); break;
        case 7: dialog_lines("MOON MARKS THE DEBT", "THE FIVE STILL OWE", "NIGHT KEEPS TALLY"); break;
        default: dialog_lines("VOID FEARS MEMORY", "SPEAK NAMES ALOUD", "NOTHINGNESS LISTENS"); break;
    }
}

static void wayfarer_advice(void) {
    switch (dialog_topic) {
        case 0: dialog_lines("SHOOT THE CRYSTALS", "SOME HOLD MAGIC", "CRACKS HIDE PATHS"); break;
        case 1: dialog_lines("THE SERPENT FEEDS", "DENY FOUR STORMS", "FLEE THE FULL COIL"); break;
        case 2: dialog_lines("CINDER MAWS HOLD", "THREE BURNING LANES", "CROSS AFTER THE FAN"); break;
        case 3: dialog_lines("WATCH FOR THE BLINK", "THEN CROSS THE WEB", "DO NOT WAIT CENTER"); break;
        case 4: dialog_lines("LEAVE THE PULSE", "BEFORE MIRE SWELLS", "RETURN AFTER IMPACT"); break;
        case 5: dialog_lines("REAPER WARPS NEAR", "KEEP AN EXIT LINE", "FIRE AFTER THE WARP"); break;
        case 6: dialog_lines("GOLEM SLAMS TWICE", "MOVE AFTER THE RING", "CORNERS BUY TIME"); break;
        case 7: dialog_lines("HYDRA HEADS WEAVE", "CUT THROUGH THE GAP", "DO NOT CHASE EDGES"); break;
        default: dialog_lines("VOID HEALS SLOWLY", "PRESS EVERY OPENING", "FLEE THE COLLAPSE"); break;
    }
}

static void resident_copy(void) {
    if (dialog_is_reward && dialog_kind == PICKUP_RIFT_SIGIL) {
        dialog_lines("DUNGEON KEY CLAIMED", "NEXT TRIAL AWAKENS",
            "SELECT SHOWS PATH");
        return;
    }
    if (!dialog_page) {
        switch (dialog_kind) {
            case PICKUP_VILLAGER: dialog_lines("FIVE SPARKS PASS ON", "WE KEEP THEIR FIRE", "REST BEFORE NORTH"); break;
            case PICKUP_MERCHANT: dialog_lines("STAND NEAR A WARE", "HUD SHOWS ICON+COST", "A TALKS TOUCH BUYS"); break;
            case PICKUP_SMITH: dialog_lines("FANG ONCE CUT STONE", "STEEL REMEMBERS IT", "POWER SHAPES COLOR"); break;
            case PICKUP_APOTHECARY: dialog_lines("FIN TAUGHT WATER", "TO CARRY MEMORY", "SIGILS DRINK MAGIC"); break;
            case PICKUP_CARTOGRAPHER: dialog_lines("ROADS SHIFT PER RUN", "LANDMARKS HOLD FAST", "I MARK WHAT I CAN"); break;
            case PICKUP_WAYKEEPER: dialog_lines("NORTH LEAVES HAVEN", "THE NEXT RIFT WAITS", "RETURN WHEN WEARY"); break;
            case PICKUP_LOREKEEPER: dialog_lines("FANG SCALE WING FIN", "AND STING BORE FIRE", "FIVE DEFY UNNAMING"); break;
            default: dialog_lines("BELLS NAME THE LOST", "SO VOID CANNOT", "MAKE THEM NEVER BE"); break;
        }
    } else {
        switch (dialog_kind) {
            case PICKUP_VILLAGER: dialog_lines("TOUCH ME FOR REST", "HP AND MAGIC REFILL", "BLESSING IS FREE"); break;
            case PICKUP_MERCHANT: shop_write_live_stock(); break;
            case PICKUP_SMITH: dialog_lines("POWER RAISES ATTACK", "WEAPONS CHANGE A", "GOLD MEANS STRONG"); break;
            case PICKUP_APOTHECARY: dialog_lines("VAMP HEALS ON KILLS", "RUNES RAISE MAGIC", "SURGE IS TEMPORARY"); break;
            case PICKUP_CARTOGRAPHER: dialog_lines("TOUCH TO SCOUT", "SELECT OPENS MAP", "FOG RESETS NEXT STG"); break;
            case PICKUP_WAYKEEPER: dialog_lines("GO NORTH TO LEAVE", "TOWN EACH 3 BOSSES", "SIDE ROADS: SHOPS"); break;
            case PICKUP_LOREKEEPER: dialog_lines("SIGIL OPENS GATE", "SECRET ROOMS HIDE", "TRY ORDINARY WALLS"); break;
            default: dialog_lines("ODD WALLS MAY OPEN", "SHOOT PUSH OR WALK", "HEAR SECRET CHIME"); break;
        }
    }
}

static void dialog_paint(void) {
    DISPLAY_OFF;
    cls();
    gotoxy(1, 1); dialog_title();
    gotoxy(1, 2); text_write("------------------");
    if (dialog_kind == PICKUP_WAYFARER) {
        if (dialog_page) wayfarer_advice();
        else wayfarer_lore();
    } else resident_copy();
    gotoxy(1, 13);
    if (dialog_is_reward)
        text_write("THE RIFT REMEMBERS.");
    else if (dialog_kind == PICKUP_MERCHANT && dialog_page)
        text_write("TOUCH ICON TO BUY");
    else text_write(dialog_page ? "THE ROAD REMEMBERS." : "... ... ...");
    gotoxy(1, 16);
    text_write(dialog_is_reward ? "A/B CONTINUE"
        : dialog_page ? "A/B RETURN" : "A NEXT   B RETURN");
    palette_bg_fill_attrs(0);
    SHOW_BKG;
    DISPLAY_ON;
    if (dialog_kind == PICKUP_MERCHANT && dialog_page) SHOW_SPRITES;
}

void dialog_prepare(u8 kind, u8 topic) BANKED {
    dialog_kind = kind;
    dialog_topic = topic < 9 ? topic : 8;
    dialog_page = 0;
    dialog_is_reward = 0;
}

void dialog_prepare_reward(u8 kind, u8 topic) BANKED {
    dialog_kind = kind;
    dialog_topic = topic < 9 ? topic : 8;
    dialog_page = 0;
    dialog_is_reward = 1;
}

void dialog_enter(void) {
    u8 i;
    DISPLAY_OFF;
    HIDE_SPRITES;
    HIDE_WIN;
    // The room renderer may have occupied every hardware sprite. Dialogue
    // pages own a clean four-icon strip; parking the rest prevents enemies,
    // sale tags, or residents from leaking through when that strip is shown.
    for (i = 0; i < 40; ++i) move_sprite(i, 0, 0);
    palette_bg_load(0, dialog_palette);
    palette_bg_load(7, dialog_palette);
    font_init();
    { font_t f = font_load(font_min); font_set(f); }
    dialog_paint();
    if (dialog_is_reward && dialog_kind == PICKUP_RIFT_SIGIL) {
        u8 part;
        palette_obj_load(1, dialog_sigil_palette);
        set_sprite_data(SPR_DIALOG_SIGIL, 4, dialog_sigil_tiles);
        for (part = 0; part < 4; ++part) {
            set_sprite_tile(part, (u8)(SPR_DIALOG_SIGIL + part));
            set_sprite_prop(part, 1);
            move_sprite(part, (u8)(80 + ((part & 1) ? 8 : 0)),
                (u8)(44 + ((part >= 2) ? 8 : 0)));
        }
        SHOW_SPRITES;
    }
}

void dialog_exit(void) {
    u8 i;
    for (i = 0; i < 4; ++i) move_sprite(i, 0, 0);
    HIDE_SPRITES;
}

screen_id_t dialog_tick(u8 keys, u8 pressed) {
    keys;
    if (dialog_is_reward && (pressed & (J_A | J_B | J_START))) {
        room_request_resume();
        return SCREEN_ROOM;
    }
    if ((pressed & J_A) && !dialog_page) {
        dialog_page = 1;
        sfx_play(SFX_TICK);
        dialog_paint();
        return SCREEN_SELF;
    }
    if (pressed & (J_A | J_B | J_START)) {
        sfx_play(SFX_COIN);
        room_request_resume();
        return SCREEN_ROOM;
    }
    return SCREEN_SELF;
}

void dialog_draw(void) {}
