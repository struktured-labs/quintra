#ifndef QUINTRA_TEXT_H
#define QUINTRA_TEXT_H

#include <gb/gb.h>

#include "core/types.h"

// Tiny console helpers for the handful of non-gameplay screens.  Keeping
// formatted I/O out of the cartridge avoids pulling the full stdio formatter
// into always-mapped ROM bank 0.
void text_write(const char *text);
void text_u16(u16 value);
void text_digit(u8 value);

#endif
