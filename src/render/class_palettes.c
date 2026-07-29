#pragma bank 7

#include <gb/gb.h>

#include "core/types.h"
#include "render/class_palettes.h"
#include "render/palette.h"

// Sprite art draws body in color 1, details in 2, accents in 3.
const u16 class_obj_palettes[5][4] = {
    // Wolfkin — warm tan / brown
    { BGR555(0,0,0), BGR555(28,22,14), BGR555(14, 8, 4), BGR555(30,28,20) },
    // Sauran — scale green
    { BGR555(0,0,0), BGR555(10,24, 8), BGR555( 4,12, 4), BGR555(24,30,12) },
    // Corvin — violet-black crow
    { BGR555(0,0,0), BGR555(14,10,22), BGR555( 6, 4,12), BGR555(26,24,30) },
    // Picsean — river blue
    { BGR555(0,0,0), BGR555(10,20,28), BGR555( 4, 8,18), BGR555(20,30,30) },
    // Vespine — hornet yellow / amber
    { BGR555(0,0,0), BGR555(30,26, 6), BGR555(12,10, 2), BGR555(30,14, 4) },
};

// Run-earned equipment colors deliberately echo the immediately readable
// Blue Ring / Red Ring language without erasing each vessel's accent color.
// Tier 3 is a shared pearl-gold champion state distinct from the temporary
// full-sprite Spirit Convergence transformation.
const u16 class_obj_upgrade_palettes[5][3][4] = {
    { // Wolfkin: tan accent survives the blue/red armor
        { BGR555(0,0,0), BGR555( 8,17,30), BGR555( 3, 7,17), BGR555(30,23,13) },
        { BGR555(0,0,0), BGR555(29, 8, 7), BGR555(13, 3, 3), BGR555(31,22,10) },
        { BGR555(0,0,0), BGR555(30,30,27), BGR555(18,14, 7), BGR555(31,25, 7) },
    },
    { // Sauran: lime scale accent
        { BGR555(0,0,0), BGR555( 7,18,29), BGR555( 3, 8,16), BGR555(18,30,10) },
        { BGR555(0,0,0), BGR555(28, 7, 6), BGR555(12, 3, 3), BGR555(19,30, 9) },
        { BGR555(0,0,0), BGR555(29,30,25), BGR555(12,18, 7), BGR555(30,25, 6) },
    },
    { // Corvin: violet feather accent
        { BGR555(0,0,0), BGR555( 8,15,28), BGR555( 3, 5,14), BGR555(25,18,31) },
        { BGR555(0,0,0), BGR555(27, 6, 8), BGR555(11, 2, 5), BGR555(26,18,31) },
        { BGR555(0,0,0), BGR555(29,29,31), BGR555(14,10,19), BGR555(31,24, 8) },
    },
    { // Picsean: cyan river accent
        { BGR555(0,0,0), BGR555( 6,17,30), BGR555( 2, 7,17), BGR555(15,30,31) },
        { BGR555(0,0,0), BGR555(28, 7, 8), BGR555(12, 2, 4), BGR555(14,29,31) },
        { BGR555(0,0,0), BGR555(29,31,31), BGR555( 8,15,20), BGR555(31,25, 7) },
    },
    { // Vespine: amber hornet accent
        { BGR555(0,0,0), BGR555( 8,17,29), BGR555( 3, 7,15), BGR555(31,24, 5) },
        { BGR555(0,0,0), BGR555(29, 7, 5), BGR555(13, 3, 2), BGR555(31,23, 4) },
        { BGR555(0,0,0), BGR555(31,30,24), BGR555(17,12, 3), BGR555(31,24, 4) },
    },
};

const u16 weapon_obj_palettes[4][4] = {
    // Spirit/ranged shots
    { BGR555(0,0,0), BGR555(31,24, 0), BGR555(28,16, 0), BGR555(31,31, 4) },
    // Steel blade / natural spike
    { BGR555(0,0,0), BGR555(24,26,29), BGR555( 8,10,14), BGR555(31,31,31) },
    // Rift Flail
    { BGR555(0,0,0), BGR555(24, 8,30), BGR555( 9, 3,15), BGR555(31,19, 5) },
    // Astral Spear
    { BGR555(0,0,0), BGR555( 8,27,31), BGR555( 3,10,18), BGR555(31,27, 8) },
};

void class_palette_load_obj(u8 slot, u8 class_id) BANKED {
    palette_obj_load(slot, class_obj_palettes[class_id < 5 ? class_id : 0]);
}
