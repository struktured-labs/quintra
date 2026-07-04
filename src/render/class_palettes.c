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
