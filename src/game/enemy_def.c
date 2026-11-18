#pragma bank 25

#include <string.h>
#include "content.h"
#include "game/enemy_def.h"

void enemy_load_def(u8 id, enemy_def_t *out) BANKED {
    if (id >= N_ENEMIES) {
        memset(out, 0, sizeof(*out));
        return;
    }
    *out = enemies[id];
}
