// Lore intro (SCREEN_INTRO) and title attract mode.
// Spec: docs/superpowers/specs/2026-11-16-intro-and-stage-vignettes.md §1 and
// the 2026-11-17 attract addendum.
#ifndef QUINTRA_GAME_ATTRACT_H
#define QUINTRA_GAME_ATTRACT_H

#include <gb/gb.h>
#include "core/types.h"
#include "game/screen.h"

// Title frames with no key held before attract starts (12 s at 60 Hz).
#define ATTRACT_TITLE_IDLE 720u

// Set by headless harnesses (scripts/quintra_sitecustomize): no boot intro
// and no title-idle attract, so fixed-frame boot scripts keep their timing.
extern u8 attract_mute;
// 1 while a demo run owns the joypad. SRAM writers return early while set:
// the demo never touches the suspend save, records, or unlock flags.
extern u8 attract_demo;

void intro_enter(void);
void intro_exit(void);
screen_id_t intro_tick(u8 keys, u8 pressed);

// Title idle timeout fired: returns SCREEN_INTRO or the demo's first screen.
screen_id_t attract_begin(void) BANKED;
// Called by input_poll() each frame while attract_demo is set.
// Replaces the joypad with the recorded demo input; returns SCREEN_TITLE
// when a real button is pressed or the demo ends, else SCREEN_SELF.
screen_id_t attract_demo_frame(void) BANKED;

#endif
