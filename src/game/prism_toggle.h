#ifndef QUINTRA_GAME_PRISM_TOGGLE_H
#define QUINTRA_GAME_PRISM_TOGGLE_H

#include <gb/gb.h>
#include "core/types.h"

// Prism Toggle: a crystal-switch chamber laid over the compact 20x17 court.
// Two barrier colours (amber, azure); striking any prism orb raises one set
// and lowers the other. Templates and the solver live in the Rust mirror
// tools/crates/quintra-procgen/src/prism_toggle.rs.
#define PRISM_X0 4
#define PRISM_Y0 3
#define PRISM_W 12
#define PRISM_H 11

#define PRISM_CLASS_NONE  0
#define PRISM_CLASS_AMBER 1   // barrier of colour 0
#define PRISM_CLASS_AZURE 2   // barrier of colour 1
#define PRISM_CLASS_ORB   3
#define PRISM_CLASS_GOAL  4

// Per-chamber-tile class, written by prism_prepare. Render paths read it
// inline (no far call per tile) through PRISM_ATTR below.
extern u8 prism_class[PRISM_H][PRISM_W];
// Colour currently raised: 0 amber, 1 azure.
extern u8 prism_raised;

// Palette for one chamber tile, or 0xFF when the tile is ordinary terrain.
// Barriers keep their colour whether raised (pillar) or lowered (floor), so
// both sets stay readable; an orb glows in the colour that is up right now.
#define PRISM_IN(x, y) ((u8)((u8)(x) - PRISM_X0) < PRISM_W \
    && (u8)((u8)(y) - PRISM_Y0) < PRISM_H)
#define PRISM_CLASS(x, y) (PRISM_IN(x, y) \
    ? prism_class[(u8)((u8)(y) - PRISM_Y0)][(u8)((u8)(x) - PRISM_X0)] \
    : PRISM_CLASS_NONE)
#define PRISM_ATTR_OF(c) ((c) == PRISM_CLASS_AMBER ? BGPAL_CRACK \
    : (c) == PRISM_CLASS_AZURE ? BGPAL_CRYSTAL \
    : (c) == PRISM_CLASS_ORB ? (prism_raised ? BGPAL_CRYSTAL : BGPAL_CRACK) \
    : (c) == PRISM_CLASS_GOAL ? BGPAL_DOOR : 0xFF)
#define PRISM_ATTR_AT(x, y) PRISM_ATTR_OF(PRISM_CLASS(x, y))
#define PRISM_IS_ORB(x, y) (PRISM_CLASS(x, y) == PRISM_CLASS_ORB)

void prism_prepare(u32 seed, u8 bosses_beaten, u8 solved) BANKED;
// A player strike landed on (tx, ty). Returns 1 when it hit a prism orb.
u8 prism_strike(u8 tx, u8 ty) BANKED;
// A player shot stopped on tile t at (tx, ty): Sun Lattice vane (pillar) or
// Prism Toggle orb (crystal). Keeps both dispatches out of bank 3.
void prism_shot_tile(u8 t, u8 tx, u8 ty) BANKED;
// Per-frame: strike cooldown, deferred barrier raises, goal check.
// Returns 1 on the frame the goal plate is reached.
u8 prism_tick(void) BANKED;

#endif
