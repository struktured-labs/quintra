#ifndef QUINTRA_GAME_WOLFKIN_SWORD_H
#define QUINTRA_GAME_WOLFKIN_SWORD_H

#include <gb/gb.h>
#include "core/types.h"
#include "game/entity.h"

// Claw Sword tiles: RESERVED bank-1 OBJ window 144..159. Nothing else may
// write bank-1 OBJ 144..159 (scripts/test_wolfkin_longsword.py checks it
// after Pack, room changes, bombs, spells and Will MAX). It used to sit at
// 160..175, which is also the spell art window (MAGIC_TILE): every room
// entry or Pack resume overwrote the blade with spell glyphs. Bank 0 owns
// other art at the same indices, so every sword sprite sets the VRAM-bank bit.
#define SPR_SWORD_BASE 144
#define SPR_SWORD_TILES 16
#define SPR_SWORD_PROP  0x0A /* OBJ pal 2 (steel) | VRAM bank 1 */
#define SPR_CLAW_H        (SPR_SWORD_BASE + 0)  /* E: pommel, guard, blade, fang tip */
#define SPR_CLAW_V        (SPR_SWORD_BASE + 4)  /* N: hand .. tip */
#define SPR_CLAW_DIAG     (SPR_SWORD_BASE + 8)  /* NE: hilt, blade, tip (6 px steps) */
#define SPR_CLAW_SMEAR_A  (SPR_SWORD_BASE + 11) /* spin trail, NNE half-heading */
#define SPR_CLAW_SMEAR_B  (SPR_SWORD_BASE + 12) /* spin trail, ENE half-heading */
#define SPR_CLAW_BLANK    (SPR_SWORD_BASE + 13)
#define SPR_SWORD_BEAM_TILE (SPR_SWORD_BASE + 15)

// Beam / power-up aux tags stay below PROJ_AUX_HOOKSHOT (0xF5) so they
// do not enter the hookshot/morningstar update and draw path.
#ifndef PROJ_AUX_SWORD_BEAM
#define PROJ_AUX_SWORD_BEAM 0xEE
#define PROJ_AUX_SWORD_PU   0xED
#endif

void wolfkin_sword_load(void) BANKED;
// Fire a slash (slash!=0) or stab in dir 0..7. Returns the first segment
// slot, or 0xFF if none spawned. Also fires the full-heart beam and
// projection power-up beams.
u8   wolfkin_sword_fire(u8 dir, u8 slash, u8 damage) BANKED;
void wolfkin_sword_try_fire(u8 keys, u8 atk, u8 weapon_dmg,
    u8 weapon_rate, u8 muted) BANKED;
void wolfkin_sword_update(entity_t *e) BANKED;
u8   wolfkin_sword_already_hit(u8 enemy_idx) BANKED;
void wolfkin_sword_mark_hit(u8 enemy_idx) BANKED;
u8   wolfkin_sword_live(const entity_t *e) BANKED;
u8   wolfkin_beam_spawn(i16 x, i16 y, u8 dir, u8 dmg, u8 ttl, u8 aux) BANKED;

#endif
