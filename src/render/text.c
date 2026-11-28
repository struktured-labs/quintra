#pragma bank 14

#include <gbdk/console.h>
#include <stdio.h>

#include "render/text.h"
#include "render/tiles.h"

// GBDK's font_min has letters, digits and a little punctuation but no '+',
// which printed as a blank: "SEL+B" read "SEL B" (#280). Draw one from a
// scratch BG tile at the console cursor and step the cursor past it.
// The scratch tile is the first shop-offer HUD glyph: every return to play
// reloads the HUD atlas, which also restores the hearts the font overwrote.
#define TEXT_PLUS_TILE HUD_OFFER_HEAL

void text_plus(void) BANKED {
    static const u8 plus[16] = {
        0x00,0x00, 0x18,0x18, 0x18,0x18, 0x7E,0x7E,
        0x7E,0x7E, 0x18,0x18, 0x18,0x18, 0x00,0x00
    };
    u8 tile = TEXT_PLUS_TILE;
    u8 x = posx(), y = posy();
    set_bkg_data(TEXT_PLUS_TILE, 1, plus);
    set_bkg_tiles(x, y, 1, 1, &tile);
    gotoxy((u8)(x + 1), y);
}

void text_putc(char c) NONBANKED {
    if (c == '+') text_plus();
    else putchar(c);
}

void text_write(const char *text) NONBANKED {
    while (*text) text_putc(*text++);
}

void text_u16(u16 value) BANKED {
    u16 place = 10000;
    u8 emitted = 0;
    while (place > 1) {
        u8 digit = (u8)(value / place);
        if (digit || emitted) {
            putchar((u8)('0' + digit));
            emitted = 1;
        }
        value = (u16)(value % place);
        place /= 10;
    }
    putchar((u8)('0' + value));
}

void text_digit(u8 value) BANKED {
    putchar((u8)('0' + (value % 10)));
}
