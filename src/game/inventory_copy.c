#pragma bank 2

#include <gb/gb.h>

#include "core/types.h"
#include "game/inventory_copy.h"
#include "render/text.h"

void inventory_write_weapon_tip(u8 index) BANKED {
    static const char *const tips[7] = {
        "STAB SLASH MAX", "HEAVY HIT MAX", "RETURNING MAX",
        "PIERCE BUBBLE MAX", "FAST CRIT MAX", "SLOW SWEEP MAX",
        "LONG STAB MAX",
    };
    if (index < 5) {
        text_write(tips[index]);
        return;
    }
    // Generated item slots 20/21 are the two run-found melee weapons.
    if (index >= 20 && index <= 21) {
        text_write(tips[index - 15]);
        return;
    }
    text_write("PRIMARY ATTACK");
}
