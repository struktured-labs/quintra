#include <gbdk/console.h>
#include <stdio.h>

#include "render/text.h"

void text_write(const char *text) {
    while (*text) putchar(*text++);
}

void text_u16(u16 value) {
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

void text_digit(u8 value) {
    putchar((u8)('0' + (value % 10)));
}
