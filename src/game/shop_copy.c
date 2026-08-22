#pragma bank 2

#include <gb/gb.h>
#include <gbdk/console.h>

#include "core/types.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/shop_copy.h"
#include "render/text.h"
#include "content.h"

static const char *effect(u8 ware, u8 item_index) {
    if (ware == WARE_ITEM && item_index < N_ITEMS) {
        switch (items[item_index].id) {
            case 20: return "MAX HP +2";
            case 21: return "SPEED +1";
            case 22: return "ATTACK +1";
            case 23: return "DEFENSE +1";
            case 24: return "LUCK +2";
            case 25: return "MAX MAGIC +2";
            case 26: return "DEF + LUCK";
            case 27: return "ATK + SPEED";
            case 28: return "LUCK +3";
            default: return "KILLS HEAL HP";
        }
    }
    switch (ware) {
        case WARE_HEART: return "HEAL 1 HEART";
        case WARE_BIG: return "MAX HP +2";
        case WARE_FORGE: return "ATTACK +1";
        case WARE_RUNE: return "MAX MAGIC +2";
        case WARE_SURGE: return "15S WEAPON UP";
        case WARE_VAMP: return "KILLS HEAL HP";
        case WARE_CHART: return "REVEAL MAP";
        case WARE_WEAPON: return "ALT A WEAPON";
        case WARE_GLASS: return "HP FOR ATK+SPD";
        case WARE_PHOENIX: return "ONE REVIVE";
        case WARE_ASCEND: return "MP + WEAPON UP";
        case WARE_ECHO: return "4TH A FRACTAL";
        case WARE_RICOCHET: return "BOUNCE A SHOT";
        case WARE_THORN: return "HIT COUNTER";
        case WARE_DRUM: return "5 KILLS: B+MP";
        case WARE_BLAST: return "HITS SPLASH";
        case WARE_BEAM: return "3RD A FAT BEAM";
        default: return "HEARTS TO MP";
    }
}

void shop_write_live_stock(void) BANKED {
    u8 i, row = 5, icon = 0;
    gotoxy(1, 3); text_write("TODAYS WARES / COST");
    for (i = 0; i < MAX_ENTITIES && row <= 11; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)
            || entities[i].type != ENT_PICKUP
            || entities[i].ai_data[0] != PICKUP_SHOP) continue;
        // The dialogue retains the room's OBJ atlas. Reuse the exact shelf
        // silhouette and tint at the left of every row, turning this from a
        // wall of abbreviations into a four-item visual catalog.
        set_sprite_tile(icon, entities[i].sprite_tile);
        set_sprite_prop(icon, entities[i].palette);
        move_sprite(icon, 8, (u8)(row * 8 + 16));
        gotoxy(1, row);
        text_write(effect(entities[i].ai_data[1], entities[i].ai_data[3]));
        gotoxy(15, row); text_u16(entities[i].ai_data[2]); text_write("G");
        icon++;
        row = (u8)(row + 2);
    }
}
