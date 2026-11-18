#pragma bank 17

// Cold counter-refusal copy. Kept out of the pickup (5) and shop (7) banks,
// which sit near their emergency floors.

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/antidote.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/status.h"
#include "render/hud.h"
#include "game/curse.h"
#include "render/tiles.h"
#include "content.h"

// Compact six-cell pickup words. Every letter is one of the room-safe HUD
// glyphs (area signage + S C B U X + - ) so no font load happens mid-fight.
// Lives here (bank 17) because the notice renderer's bank 14 is full.
#define N_A BGT_AREA_A
#define N_D BGT_AREA_D
#define N_E BGT_AREA_E
#define N_F BGT_AREA_F
#define N_H BGT_AREA_H
#define N_I BGT_AREA_I
#define N_K BGT_AREA_K
#define N_L BGT_AREA_L
#define N_M BGT_AREA_M
#define N_N BGT_AREA_N
#define N_O BGT_AREA_O
#define N_P BGT_AREA_P
#define N_R BGT_AREA_R
#define N_T BGT_AREA_T
#define N_V BGT_AREA_V
#define N_W BGT_AREA_W
#define N_S HUD_STATUS_S
#define N_C HUD_STATUS_C
#define N_B HUD_STATUS_B
#define N_U HUD_STATUS_U
#define N_X HUD_STATUS_X
#define N__ HUD_BLANK
#define N_1 (HUD_DIGIT_0 + 1)
#define N_3 (HUD_DIGIT_0 + 3)
#define N_G BGT_AREA_G
static const u8 notice_words[NW_COUNT][6] = {
    { N_R,N_E,N_V,N_I,N_V,N_E },          // NW_REVIVE   Phoenix Thread
    { N_F,N_O,N_R,N_K,N__,N__ },          // NW_FORK     Echo Prism
    { N_B,N_O,N_U,N_N,N_C,N_E },          // NW_BOUNCE   Ricochet Rune
    { N_T,N_H,N_O,N_R,N_N,N_S },          // NW_THORNS   Thorn Crown
    { N_D,N_R,N_U,N_M,N__,N__ },          // NW_DRUM     War Drum
    { N_F,N_L,N_A,N_S,N_K,N__ },          // NW_FLASK    Moon Flask
    { N_B,N_L,N_A,N_S,N_T,N__ },          // NW_BLAST    Blast Seed
    { N_B,N_E,N_A,N_M,N__,N__ },          // NW_BEAM     Rift Lens
    { N_V,N_A,N_M,N_P,N__,N__ },          // NW_VAMP     Vampiric Sigil
    { N_W,N_A,N_R,N_D,N__,N__ },          // NW_WARD     Ward Charm
    { N_C,N_H,N_A,N_R,N_T,N__ },          // NW_CHART    Cartographer's Chart
    { N_W,N_E,N_A,N_P,N_O,N_N },          // NW_WEAPON   new A weapon
    { N_H,N_E,N_A,N_L,N_E,N_D },          // NW_HEALED   full restore
    { N_S,N_C,N_O,N_U,N_T,N__ },          // NW_SCOUT    Cartographer blessing
    { N_C,N_L,N_E,N_A,N_N,N__ },          // NW_CLEAN    curse cleansed
    { N_B,N_U,N_R,N_S,N_T,N__ },          // NW_BURST    Rift Bomb tool
    { N_C,N_H,N_I,N_M,N_E,N__ },          // NW_CHIME    Echo Chime tool
    { N_M,N_I,N_R,N_R,N_O,N_R },          // NW_MIRROR   Mirror Shard tool
    { N_C,N_U,N_R,N_E,HUD_STATUS_PLUS,N_1 }, // NW_CURE1 Antidote carried
    { N_H,N_U,N_R,N_T,HUD_STATUS_PLUS,N_1 }, // NW_HURT1 Frail curse
    { HUD_COIN,N_M,N_A,N_X,N__,N__ },     // NW_COINMAX  purse full
    { N_O,N_W,N_N,N_E,N_D,N__ },          // NW_OWNED    unique already carried
    { N_N,N_O,N_R,N_O,N_O,N_M },          // NW_NOROOM   Pack / pouch full
    { N_K,N_N,N_O,N_W,N_N,N__ },          // NW_KNOWN    route already charted
    { HUD_HEART_FULL,N_L,N_O,N_W,N__,N__ }, // NW_LOWHP  pact needs max HP
    { N_A,N__,N_S,N_W,N_A,N_P },          // NW_ASWAP    press A to trade
    { N_W,N_A,N_R,N_D,N_E,N_D },          // NW_WARDED   curse blocked
    { N_A,N_R,N_M,N_E,N_D,N__ },          // NW_ARMED    bottle waits for a fight
    { N_R,N_E,N_A,N_R,N_M,N__ },          // NW_REARM    Riftwell re-armed
    { N_L,N_I,N_G,N_H,N_T,N__ },          // NW_LIGHT    Cave Light
    { N_C,N_O,N_M,N_B,N__,N__ },          // NW_COMB     Honeycomb Charm
    { N_C,N_I,N_N,N_D,N_E,N_R },          // NW_CINDER   Cinder Veil
    { N_S,N_K,N_A,N_T,N_E,N_S },          // NW_SKATES   Rime Skates
    { N_M,N_A,N_S,N_K,N__,N__ },          // NW_MASK     Filter Mask
    { N_L,N_A,N_M,N_P,N__,N__ },          // NW_LAMP     Gloam Lamp
    { N_S,N_E,N_A,N_L,N__,N__ },          // NW_SEAL     Sun Seal
    { N_P,N_A,N_C,N_T,N__,N__ },          // NW_PACT     Crimson Pact
    { N_L,N_A,N_S,N_T,N__,N__ },          // NW_LAST     Last Light
    { N_B,N_E,N_L,N_L,N__,N__ },          // NW_BELL     Wayfarer's Bell
    { N_L,N_U,N_R,N_E,N__,N__ },          // NW_LURE     Cache Lure
    { N_W,N_I,N_C,N_K,N__,N__ },          // NW_WICK     Hollow Wick
    { N_A,N_E,N_G,N_I,N_S,N__ },          // NW_AEGIS    power-up: shield
    { N_B,N_L,N_O,N_C,N_K,N_3 },          // NW_BLOCK3   absorbs three hits
    { N_L,N_I,N_M,N_I,N_T,N__ },          // NW_LIMIT    power-up: Limitless
    { N_F,N_R,N_E,N_E,N_M,N_P },          // NW_FREEMP   Oaths/Bombs cost no MP
    { N_M,N_E,N_N,N_D,N__,N__ },          // NW_MEND     power-up: regen
    { N_R,N_E,N_G,N_E,N_N,N__ },          // NW_REGEN    heals over time
    { N_E,N_N,N_D,N_E,N_D,N__ },          // NW_ENDED    power-up expired
};
// 0 gold, 1 violet, 2 green, 6 MP blue, 7 HUD red.
static const u8 notice_word_pal[NW_COUNT] = {
    0, 1, 1, 7, 0, 6, 7, 1, 7, 1,
    6, 0, 2, 6, 2, 7, 6, 1, 2, 7,
    7, 7, 7, 7, 7, 0, 1,
    0, 2, 0, 0, 7, 6, 2, 1, 0, 7, 1, 0, 0, 1,
    0, 0, 6, 6, 2, 2, 7,
};

u8 hud_notice_word_fill(u8 word, u8 *row) BANKED {
    u8 i;
    if (word >= NW_COUNT) word = NW_NOROOM;
    for (i = 0; i < 6; ++i) row[i] = notice_words[word][i];
    return notice_word_pal[word];
}

void hud_show_word(u8 word) BANKED {
    if (word < NW_COUNT) hud_notice_pair(HUD_NOTICE_WORD, word);
}

void hud_show_heal(u8 n) BANKED { if (n) hud_notice_pair(HUD_NOTICE_HEAL, n); }
void hud_show_mana(u8 n) BANKED { if (n) hud_notice_pair(HUD_NOTICE_MANA, n); }
void hud_show_coins(u8 n) BANKED { if (n) hud_notice_pair(HUD_NOTICE_COIN, n); }
void hud_show_need(u8 price) BANKED { hud_notice_pair(HUD_NOTICE_NEED, price); }

void hud_show_stat_loss(u8 stat, u8 n) BANKED {
    if (n) hud_notice_pair(HUD_NOTICE_LOSS, (u8)((stat << 4) | (n & 0x0F)));
}

// Presence relics and Pack tools have no stat line; name what they do.
void hud_show_item(u8 item_id) BANKED {
    static const u8 ids[14] = {
        ITEM_ID_PHOENIX_THREAD, ITEM_ID_ECHO_PRISM, ITEM_ID_RICOCHET_RUNE,
        ITEM_ID_THORN_CROWN, ITEM_ID_WAR_DRUM, ITEM_ID_MOON_FLASK,
        ITEM_ID_BLAST_SEED, ITEM_ID_RIFT_LENS, ITEM_ID_BLOOD_SIGIL,
        ITEM_ID_WARD_CHARM, ITEM_ID_RIFT_BOMB, ITEM_ID_ECHO_CHIME,
        ITEM_ID_MIRROR_SHARD, ITEM_ID_ANTIDOTE,
    };
    static const u8 words[14] = {
        NW_REVIVE, NW_FORK, NW_BOUNCE, NW_THORNS, NW_DRUM, NW_FLASK,
        NW_BLAST, NW_BEAM, NW_VAMP, NW_WARD, NW_BURST, NW_CHIME,
        NW_MIRROR, NW_CURE1,
    };
    u8 i;
    for (i = 0; i < 14; ++i)
        if (ids[i] == item_id) { hud_show_word(words[i]); return; }
}

// A run curse names itself and then its concrete cost.
void hud_show_curse(u8 kind) BANKED {
    if (kind & CURSE_HUNGER) { hud_show_hunger_curse(); return; }
    hud_show_status(QSTATUS_CURSE);
    if (kind & CURSE_FRAIL) hud_show_word(NW_HURT1);
    if (kind & CURSE_MISFORTUNE) hud_show_stat_loss(STAT_LCK, 2);
    if (kind & CURSE_DULL) hud_show_stat_loss(STAT_ATK, 1);
}

static u8 carries(u8 id) {
    u8 i;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == id) return 1;
    return 0;
}

// The counter refusal used to be a bare buzz for every case below.
void shop_refuse_explain(u8 ware) BANKED {
    static const u8 unique[12] = {
        WARE_PHOENIX, ITEM_ID_PHOENIX_THREAD, WARE_ECHO, ITEM_ID_ECHO_PRISM,
        WARE_RICOCHET, ITEM_ID_RICOCHET_RUNE, WARE_THORN, ITEM_ID_THORN_CROWN,
        WARE_DRUM, ITEM_ID_WAR_DRUM, WARE_FLASK, ITEM_ID_MOON_FLASK,
    };
    static const u8 unique2[10] = {
        WARE_BLAST, ITEM_ID_BLAST_SEED, WARE_BOOMERANG, ITEM_ID_BOOMERANG,
        WARE_HOOKSHOT, ITEM_ID_HOOKSHOT, WARE_MORNINGSTAR, ITEM_ID_MORNINGSTAR,
        WARE_BOMBS, ITEM_ID_BOMBS,
    };
    u8 i;
    for (i = 0; i < 12; i += 2)
        if (unique[i] == ware && carries(unique[i + 1])) {
            hud_show_word(NW_OWNED); return;
        }
    for (i = 0; i < 10; i += 2)
        if (unique2[i] == ware && carries(unique2[i + 1])) {
            hud_show_word(NW_OWNED); return;
        }
    if (ware == WARE_GLASS && player.hp_max <= 2) {
        hud_show_word(NW_LOWHP); return;
    }
    if (ware == WARE_CHART) { hud_show_word(NW_KNOWN); return; }
    if (ware == WARE_VAMP && carries(0xFF)) {
        hud_show_stat_max(STAT_ATK); return;
    }
    hud_show_word(NW_NOROOM);   // full Pack or a full Antidote pouch
}

// Iron Heart at the max-HP cap: still a heart, so if the champion is hurt
// it mends two HP instead of sitting on the floor as a dead white heart.
// Lives here because the pickup bank (5) sits at its emergency floor.
u8 pickup_iron_heart_overflow(u8 item_idx) BANKED {
    u8 hp;
    if (item_idx >= N_ITEMS || items[item_idx].id != ITEM_ID_IRON_HEART
        || player.hp_max < HP_CAP || player.hp >= player.hp_max
        || STATUS_PLAYER_HEALING_BLOCKED()) return 0;
    hp = (u8)(player.hp + 2);
    player.hp = hp > player.hp_max ? player.hp_max : hp;
    hud_redraw_hp();
    hud_show_stat_max(STAT_HP);
    hud_show_heal(2);
    sfx_play(SFX_HEART);
    return 1;
}
