#pragma bank 17

#include <gb/gb.h>

#include "core/types.h"
#include "game/riftwild_density.h"
#include "game/run_state.h"

// The Riftwild used the dungeon room band (12..16 on Normal), so every one of
// the 36 fields opened with about a dozen hostiles. That is an arena, not a
// journey. Zelda 1 and FF Adventure put a handful of foes on a screen and
// leave some screens empty. Each field now gets a seed-stable band from all
// 32 seed bits: about one field in four is quiet, the rest hold 3..6 (2..5
// on Easy), with one more in the third region. The Worldglass Hollow stays
// the deliberately dangerous counterpart at 5..8 with no quiet fields.

static u8 field_hash(void) {
    u16 h = (u16)run_state.run_seed
        ^ (u16)(run_state.run_seed >> 16)
        ^ (u16)((u16)run_state.world_screen * 0x9E37u)
        ^ (u16)((u16)run_state.riftwild_region * 0x7F4Bu);
    h ^= h << 7;
    h ^= h >> 9;
    h ^= h << 8;
    return (u8)(h ^ (h >> 8));
}

u8 riftwild_field_is_quiet(void) BANKED {
    if (!run_state.world_mode || RUN_RIFTWILD_IS_HOLLOW()) return 0;
    return (field_hash() & 0xC0) == 0 ? 1 : 0;
}

u8 riftwild_field_enemy_count(u8 rolled) BANKED {
    u8 h = field_hash();
    u8 band;
    if (RUN_RIFTWILD_IS_HOLLOW()) {
        band = (u8)((RUN_IS_EASY() ? 4 : 5) + (h & 3));
    } else {
        if ((h & 0xC0) == 0) return 0;
        band = (u8)((RUN_IS_EASY() ? 2 : 3) + (h & 3));
        if (run_state.riftwild_region >= 2) band++;
    }
    return band < rolled ? band : rolled;
}
