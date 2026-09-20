#pragma bank 12
// Two-page conversations for village residents, merchants, and peaceful
// stage creatures. The room is resumed rather than regenerated on exit, so a
// conversation cannot reroll enemies, stock, secrets, or the dungeon graph.

#include <gb/gb.h>
#include <gb/cgb.h>
#include <gbdk/console.h>
#include <gbdk/font.h>
#include <stdio.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/dialog.h"
#include "game/companion.h"
#include "game/pickup.h"
#include "game/room.h"
#include "game/shop_copy.h"
#include "render/palette.h"
#include "render/text.h"
#include "render/tiles.h"
#include "content.h"

BANKREF(dialog_enter)

u8 dialog_kind;
u8 dialog_topic;
u8 dialog_page;
static u8 dialog_is_reward;
static u8 dialog_is_stage;
static u16 dialog_stage_ticks;

static const u16 dialog_palette[4] = {
    BGR555(1, 2, 6), BGR555(7, 10, 17),
    BGR555(21, 22, 25), BGR555(31, 31, 31),
};

static const u16 dialog_accents[4][4] = {
    { BGR555(1, 2, 6), BGR555(7, 10, 17), BGR555(21, 22, 25), BGR555(31, 27, 12) },
    { BGR555(1, 2, 6), BGR555(7, 10, 17), BGR555(21, 22, 25), BGR555(15, 31, 18) },
    { BGR555(1, 2, 6), BGR555(7, 10, 17), BGR555(21, 22, 25), BGR555(15, 28, 31) },
    { BGR555(1, 2, 6), BGR555(7, 10, 17), BGR555(21, 22, 25), BGR555(31, 17, 13) },
};

// Inline ^0 resets; ^1 treasure, ^2 benefit, ^3 action, ^4 danger.
static void dialog_line(u8 row, const char *text) {
    u8 col = 1;
    u8 accent = 0;
    gotoxy(col, row);
    while (*text && col < 20) {
        if (*text == '^' && text[1] >= '0' && text[1] <= '4') {
            accent = (u8)(text[1] - '0');
            text += 2;
        } else {
            putchar(*text++);
            VBK_REG = 1;
            set_tiles(col++, row, 1, 1, (u8 *)0x9800, &accent);
            VBK_REG = 0;
        }
    }
}

static void dialog_lines(const char *a, const char *b, const char *c) {
    dialog_line(5, a);
    dialog_line(7, b);
    dialog_line(9, c);
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
        case 8: text_write("VOID HALO"); break;
        case 9: text_write("WAKING ARCH"); break;
        case 10: text_write("SLEEPING ARCH"); break;
        case 11: text_write("FARFOLD CAVE"); break;
        default: text_write("MEMORY VAULT"); break;
    }
}

static void dialog_title(void) {
    if (dialog_is_stage) {
        text_write(dialog_topic < N_STAGES ? stage_names[dialog_topic]
            : "THE DEEP RIFT");
        return;
    }
    switch (dialog_kind) {
        case PICKUP_FARFOLD_RELIC:
            text_write(dialog_topic < N_ITEMS ? items[dialog_topic].name : "FARFOLD RELIC");
            break;
        case PICKUP_RIFT_SIGIL: text_write("RIFT SIGIL"); break;
        case PICKUP_WAYGEAR:
            if (dialog_topic == 0) text_write("TITAN GLOVE");
            else if (dialog_topic == 1) text_write("TIDE RAFT");
            else if (dialog_topic == 2) text_write("RIFT HOOK");
            else text_write("WORLDGLASS");
            break;
        case PICKUP_COMPANION:
            if (dialog_topic == COMPANION_HEARTH) text_write("HEARTH ECHO");
            else if (dialog_topic == COMPANION_AETHER) text_write("AETHER ECHO");
            else text_write("WAY ECHO");
            break;
        case PICKUP_HOLLOW_RELIC:
            if (dialog_topic == ITEM_ID_BLAST_SEED) text_write("BLAST SEED");
            else if (dialog_topic == ITEM_ID_RIFT_LENS) text_write("RIFT LENS");
            else text_write("MIRROR SHARD");
            break;
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
        case 8: dialog_lines("VOID FEARS MEMORY", "SPEAK NAMES ALOUD", "NOTHINGNESS LISTENS"); break;
        case 9: dialog_lines("THIS ARCH IS AWAKE", "STEP INTO BLUE FIRE", "A DUNGEON WAITS"); break;
        case 10: dialog_lines("THIS ARCH SLEEPS", "ANOTHER BURNS BLUE", "FOLLOW YOUR MAP"); break;
        case 11: dialog_lines("FARFOLD STAIRS BEND", "LINK DISTANT WOODS", "DESCEND TO CROSS"); break;
        default: dialog_lines("ONE VAULT PER WILD", "MEMORY GUARDS GIFT", "CLAIM IT ONLY ONCE"); break;
    }
}

static void wayfarer_advice(void) {
    switch (dialog_topic) {
        case 0: dialog_lines("^3SHOOT^0 THE ^1CRYSTALS", "SOME HOLD ^2MAGIC", "^1CRACKS^0 HIDE PATHS"); break;
        case 1: dialog_lines("THE SERPENT FEEDS", "DENY ^1FOUR STORMS", "^3FLEE^0 THE ^4FULL COIL"); break;
        case 2: dialog_lines("CINDER MAWS HOLD", "^4THREE BURNING LANES", "CROSS ^3AFTER THE FAN"); break;
        case 3: dialog_lines("WATCH FOR THE ^1BLINK", "THEN ^3CROSS^0 THE WEB", "^4DO NOT WAIT CENTER"); break;
        case 4: dialog_lines("^3LEAVE^0 THE PULSE", "^4BEFORE^0 MIRE SWELLS", "RETURN ^3AFTER IMPACT"); break;
        case 5: dialog_lines("REAPER ^4WARPS NEAR", "KEEP AN ^2EXIT LINE", "FIRE ^3AFTER THE WARP"); break;
        case 6: dialog_lines("GOLEM ^4SLAMS TWICE", "MOVE ^3AFTER THE RING", "^2CORNERS^0 BUY TIME"); break;
        case 7: dialog_lines("HYDRA HEADS WEAVE", "CUT THROUGH ^2THE GAP", "^4DO NOT CHASE EDGES"); break;
        case 8: dialog_lines("VOID ^4HEALS SLOWLY", "PRESS ^3EVERY OPENING", "^3FLEE^0 THE ^4COLLAPSE"); break;
        case 9: dialog_lines("OTHER ARCHES SLEEP", "WIN WAKES THE ROAD", "THE MAP KEEPS MARKS"); break;
        case 10: dialog_lines("SEEK THE BLUE ARCH", "RETURN AFTER WIN", "OLD GATES THEN WAKE"); break;
        case 11: dialog_lines("^1TOOLS^0 OPEN GROVES", "REMEMBER ^1OLD GATES", "^3RETURN WITH GEAR"); break;
        case 12: dialog_lines("VAULTS ^4NEVER REFILL", "ROADS HIDE GEAR", "WILD REWARDS MEMORY"); break;
        default: dialog_lines("WILD WARDEN HOLDS", "FIND ITS RED MARK", "WIN WAKES THIS ARCH"); break;
    }
}

static void resident_copy(void) {
    if (dialog_is_reward && dialog_kind == PICKUP_FARFOLD_RELIC) {
        dialog_lines("^2TREASURE WON", "", "^3PACK^0 SHOWS STATS");
        switch (dialog_topic) {
            case 10: dialog_line(7, "^2MAX HP +2"); break;
            case 11: dialog_line(7, "^2SPD +1"); break;
            case 12: dialog_line(7, "^2ATK +1"); break;
            case 15: dialog_line(7, "^2MAX MP +2"); break;
            case 16: dialog_line(7, "^2DEF +1  LCK +1"); break;
            case 17: dialog_line(7, "^2SPD +1  ATK +1"); break;
            case 19:
                dialog_line(7, "^2ATK +1  MAX HP +1");
                dialog_line(9, "^2HEAL EVERY 5 KILLS"); break;
        }
        return;
    }
    if (dialog_is_reward && dialog_kind == PICKUP_RIFT_SIGIL) {
        dialog_lines("^1DUNGEON KEY^0 CLAIMED", "^2NEXT TRIAL^0 AWAKENS",
            "^3SELECT^0 SHOWS PATH");
        return;
    }
    if (dialog_is_reward && dialog_kind == PICKUP_WAYGEAR) {
        if (dialog_topic == 0)
            dialog_lines("A NEW WAY THROUGH", "PASS ^2RUNE BOULDERS",
                "^2ALWAYS ON^0 - WALK");
        else if (dialog_topic == 1)
            dialog_lines("A NEW WAY THROUGH", "CROSS ^2RIVERS/LAKES",
                "^2ALWAYS ON^0 - WALK");
        else if (dialog_topic == 2)
            dialog_lines("A NEW WAY THROUGH", "CROSS ^2HOLES/GAPS",
                "^2ALWAYS ON^0 - WALK");
        else
            dialog_lines("A NEW WAY THROUGH", "^2WAKING / HOLLOW",
                "RIFTWILD: ^3SEL+B");
        return;
    }
    if (dialog_is_reward && dialog_kind == PICKUP_COMPANION) {
        if (dialog_topic == COMPANION_HEARTH)
            dialog_lines("YOUR HEART SUMMONED", "I MEND ^2TWO HALF HP",
                "^3SELECT^0 MAP THEN ^3A");
        else if (dialog_topic == COMPANION_AETHER)
            dialog_lines("YOUR SPARK SUMMONED", "I RESTORE ^2TWO MAGIC",
                "^3SELECT^0 MAP THEN ^3A");
        else
            dialog_lines("THE ROAD CALLED ME", "I REVEAL ^2NEAR PATHS",
                "^3SELECT^0 MAP THEN ^3A");
        return;
    }
    if (dialog_is_reward && dialog_kind == PICKUP_HOLLOW_RELIC) {
        if (dialog_topic == ITEM_ID_BLAST_SEED)
            dialog_lines("HOLLOW RELIC FOUND", "IMPACTS NOW ^2EXPLODE",
                "^4ONLY IN HOLLOW");
        else if (dialog_topic == ITEM_ID_RIFT_LENS)
            dialog_lines("HOLLOW RELIC FOUND", "^3THIRD A:^2 FAT BEAM",
                "^4ONLY IN HOLLOW");
        else
            dialog_lines("HOLLOW RELIC FOUND", "^2REFLECTS^0 ALL SHOTS",
                "^4ONE USE^0 IN ^3PACK");
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
            case PICKUP_VILLAGER: dialog_lines("TOUCH ME FOR REST", "^2HP AND MAGIC^0 REFILL", "BLESSING IS FREE"); break;
            case PICKUP_MERCHANT: shop_write_live_stock(); break;
            case PICKUP_SMITH: dialog_lines("POWER RAISES ATTACK", "^1WEAPONS^0 CHANGE ^3A", "GOLD MEANS STRONG"); break;
            case PICKUP_APOTHECARY: dialog_lines("VAMP HEALS ON KILLS", "RUNES RAISE MAGIC", "SURGE IS ^4TEMPORARY"); break;
            case PICKUP_CARTOGRAPHER: dialog_lines("TOUCH TO SCOUT", "^3SELECT^0 OPENS MAP", "FOG RESETS NEXT STG"); break;
            case PICKUP_WAYKEEPER: dialog_lines("GO NORTH TO LEAVE", "TOWN EACH 3 BOSSES", "SIDE ROADS: SHOPS"); break;
            case PICKUP_LOREKEEPER: dialog_lines("^1SIGIL^0 OPENS GATE", "SECRET ROOMS HIDE", "TRY ORDINARY WALLS"); break;
            default: dialog_lines("ODD WALLS MAY OPEN", "^3SHOOT PUSH OR WALK", "HEAR SECRET CHIME"); break;
        }
    }
}

static void dialog_paint(void) {
    DISPLAY_OFF;
    cls();
    palette_bg_fill_attrs(0);
    if (dialog_is_reward) {
        dialog_line(1, dialog_kind == PICKUP_WAYGEAR ? "^2WAYGEAR ACQUIRED"
            : dialog_kind == PICKUP_COMPANION ? "^2COMPANION JOINED"
            : dialog_kind == PICKUP_RIFT_SIGIL ? "^2KEY CLAIMED"
            : "^2RELIC ACQUIRED");
    }
    gotoxy(1, dialog_is_reward ? 3 : 1); dialog_title();
    VBK_REG = 1;
    {
        u8 col;
        u8 accent = 1;
        for (col = 1; col < 19; ++col)
            set_tiles(col, dialog_is_reward ? 3 : 1, 1, 1,
                (u8 *)0x9800, &accent);
    }
    VBK_REG = 0;
    if (!dialog_is_reward) {
        gotoxy(1, 2); text_write("------------------");
    }
    if (dialog_is_stage) {
        if (dialog_topic < 3)
            dialog_lines("THE WOUND DEEPENS", "STONE ROOT EMBER",
                "ANSWER THE OATH");
        else if (dialog_topic < 6)
            dialog_lines("THE FAR RIFT CALLS", "ICE MIRE AND SHADOW",
                "OLD ROADS REMEMBER");
        else
            dialog_lines("THE LAST SKY OPENS", "SUN MOON AND VOID",
                "CARRY THE FIVE HOME");
    } else if (dialog_kind == PICKUP_WAYFARER) {
        if (dialog_page) wayfarer_advice();
        else wayfarer_lore();
    } else resident_copy();
    if (dialog_is_reward && dialog_kind == PICKUP_WAYGEAR && dialog_topic < 3) {
        dialog_line(11, "^2WILL LIMIT RAISED");
    }
    gotoxy(1, 13);
    if (dialog_is_stage)
        text_write("A/B SKIP  AUTO 5S");
    else if (dialog_is_reward)
        text_write("THE RIFT REMEMBERS.");
    else if (dialog_kind == PICKUP_MERCHANT && dialog_page)
        text_write("TOUCH ICON TO BUY");
    else text_write(dialog_page ? "THE ROAD REMEMBERS." : "... ... ...");
    dialog_line(16, dialog_is_stage ? "^3A/B/START^0 ENTER"
        : dialog_is_reward ? "^3A/B^0 CONTINUE"
        : dialog_page ? "^3A/B^0 RETURN" : "^3A^0 NEXT   ^3B^0 RETURN");
    SHOW_BKG;
    DISPLAY_ON;
    if (dialog_kind == PICKUP_MERCHANT && dialog_page) SHOW_SPRITES;
}

void dialog_prepare(u8 kind, u8 topic) BANKED {
    dialog_kind = kind;
    dialog_topic = topic < 13 ? topic : 12;
    dialog_page = 0;
    dialog_is_reward = 0;
    dialog_is_stage = 0;
}

void dialog_prepare_reward(u8 kind, u8 topic) BANKED {
    dialog_kind = kind;
    dialog_topic = kind == PICKUP_FARFOLD_RELIC
        ? (topic < N_ITEMS ? topic : 12) : (topic < 13 ? topic : 12);
    dialog_page = 0;
    dialog_is_reward = 1;
    dialog_is_stage = 0;
}

void dialog_prepare_stage(u8 stage) BANKED {
    dialog_kind = PICKUP_RIFT_SIGIL;
    dialog_topic = stage < N_STAGES ? stage : (u8)(stage % N_STAGES);
    dialog_page = 0;
    dialog_is_reward = 0;
    dialog_is_stage = 1;
    dialog_stage_ticks = 300;
}

void dialog_enter(void) {
    u8 i;
    DISPLAY_OFF;
    VBK_REG = 0;
    HIDE_SPRITES;
    HIDE_WIN;
    // The room renderer may have occupied every hardware sprite. Dialogue
    // pages own a clean four-icon strip; parking the rest prevents enemies,
    // sale tags, or residents from leaking through when that strip is shown.
    for (i = 0; i < 40; ++i) move_sprite(i, 0, 0);
    palette_bg_load(0, dialog_palette);
    palette_bg_load(7, dialog_palette);
    for (i = 0; i < 4; ++i) palette_bg_load((u8)(i + 1), dialog_accents[i]);
    font_init();
    { font_t f = font_load(font_min); font_set(f); }
    dialog_paint();
}

void dialog_exit(void) {
    u8 i;
    for (i = 0; i < 4; ++i) move_sprite(i, 0, 0);
    HIDE_SPRITES;
}

screen_id_t dialog_tick(u8 keys, u8 pressed) {
    keys;
    if (dialog_is_stage) {
        if (dialog_stage_ticks) dialog_stage_ticks--;
        if (!dialog_stage_ticks || (pressed & (J_A | J_B | J_START))) {
            room_request_resume();
            return SCREEN_ROOM;
        }
        return SCREEN_SELF;
    }
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
