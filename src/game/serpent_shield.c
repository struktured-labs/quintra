#pragma bank 17
// Serpent plated-tail shield: palette telegraph and the shot/blade block.
// Split from enemy_serpent_tail.c, whose bank has no room left. Pinned to
// bank 17 (the roomy art bank) so autobanking does not squeeze bank 7.

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/projectile.h"
#include "render/palette.h"
#include "render/tiles.h"

extern u8 entity_anim_counter;

// Armour clink: a very high, short 12.5%-duty ping over a bright noise tick.
// Blades glance lower and heavier, steel on steel. Distinct from the dry
// SFX_HIT crunch so a block never reads as damage.
static void shield_clink(u8 melee) {
    if (sfx_melody_locked()) return;
    sfx_will_active = 0;
    sfx_claim_channels(8, 8);
    NR10_REG = 0x00;
    NR11_REG = melee ? 0x40 : 0x00;
    NR12_REG = melee ? 0xD2 : 0xC1;
    NR13_REG = melee ? (u8)(1925 & 0xFF) : (u8)(2008 & 0xFF);
    NR14_REG = 0x80 | (melee ? (1925 >> 8) : (2008 >> 8));
    NR42_REG = melee ? 0xB2 : 0x91;
    NR43_REG = melee ? 0x34 : 0x14;
    NR44_REG = 0x80;
}
u8 serpent_tail_flash;
u8 serpent_tail_pal_mode;

// BG slot 6 for the coil: plated (the Verdant boss ramp shared with the
// hood), slack (dull grey: the shield is down), and the white block flash.
static const u16 tail_palettes[3][4] = {
    { 0x0000, 0x3C6A, 0x611B, 0x3BFF },
    { 0x0000, 0x20A6, 0x396D, 0x4A74 },
    { 0x0000, 0x494E, 0x7FFF, 0x63FF },
};

void serpent_tail_shield_tick(entity_t *e) BANKED {
    u8 mode = serpent_tail_flash ? 2 : (e->state == 2 ? 1 : 0);
    if (serpent_tail_flash) serpent_tail_flash--;
    // Re-assert every 32 frames in case a room effect rewrote the slot.
    if (mode != serpent_tail_pal_mode || !(entity_anim_counter & 31)) {
        serpent_tail_pal_mode = mode;
        palette_bg_load(6, tail_palettes[mode]);
    }
}

// Called for each live player shot while the Serpent is in the room.
// Returns 1 when the plated tail stopped it (caller retires the shot).
u8 serpent_tail_blocks(entity_t *shot) BANKED {
    entity_t *h;
    u8 cx, cy, tx, ty, aux;
    if (serpent_head_index >= MAX_ENTITIES) return 0;
    h = &entities[serpent_head_index];
    // Unwinding after a storm charge: plates slack, shots pass to the hood.
    if (h->type != ENT_ENEMY || !(h->flags & EF_ACTIVE) || h->state == 2)
        return 0;
    // Bombs and splash bursts are area damage, not a lane the tail can
    // cover; the hookshot is a tool. Max-Will signatures and Spirit
    // Convergence chords cut straight through the plates.
    aux = shot->ai_data[6];
    if (aux == PROJ_AUX_FUSE_BOMB || aux == PROJ_AUX_SPLASH
        || aux == PROJ_AUX_HOOKSHOT) return 0;
    if (shot->ai_data[3]
        & (PROJ_FLAG_CONVERGENCE | PROJ_FLAG_HOWL | PROJ_FLAG_WILL_WAVE))
        return 0;
    if ((u16)shot->x >= 248 || (u16)shot->y >= 248) return 0;
    cx = (u8)((u8)shot->x + (u8)(shot->hitbox >> 5));
    cy = (u8)((u8)shot->y + (u8)((shot->hitbox & 0x0F) >> 1));
    // The hood is never armour: anything on the drawn 32x24 head goes on
    // to the normal head hit test.
    if ((u8)(cx - (u8)h->x) < 32 && (u8)(cy - (u8)h->y) < 24) return 0;
    tx = cx >> 3;
    ty = cy >> 3;
    if (ty >= 17) return 0;
    if (!(serpent_body_cells[(u8)((ty << 2) + (tx >> 3))] & (u8)(1 << (tx & 7))))
        return 0;
    fx_spawn(SPR_FX_IMPACT, 1, (i16)cx - 4, (i16)cy - 4, 8);
    if (!serpent_tail_flash) shield_clink(shot->ai_data[2]);
    serpent_tail_flash = 6;
    return 1;
}

