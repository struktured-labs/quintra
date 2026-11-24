#ifndef QUINTRA_GAME_CLASS_SELECT_H
#define QUINTRA_GAME_CLASS_SELECT_H


#include <gb/gb.h>
#include "core/types.h"
#include "game/screen.h"
#include "game/sram.h"

// CLASS_SELECT BG palettes. Shared by enter, crown blit, and VBlank attrs.
#define CS_PAL_BODY      0
#define CS_PAL_GOLD      1
#define CS_PAL_ACCENT    2
#define CS_PAL_LAVENDER  3
#define CS_PAL_ROYAL     4

extern u8 class_select_cursor;   // 0..N_CLASSES-1
extern u8 class_select_easy_mode;
// VBlank work queue: attribute jobs 1..6, then palette half-bursts.
// class_select_vbl_work is nonzero while either remains.
extern u8 class_select_attr_phase;
extern u8 class_select_pal_steps;
extern u8 class_select_vbl_work;
// Selected hero's name length, cached by render() for the name row.
extern u8 class_select_name_len;
// Lifetime trophies, snapshotted on enter so render/attr skip SRAM I/O.
extern u8 class_select_hero_wins[HERO_TROPHY_SLOTS];
extern u8 class_select_hero_tier[HERO_TROPHY_SLOTS];

// One bounded job per frame, called at the top of class_select_tick
// (right after loop_run's input_poll) while LY is still in VBlank.
void        class_select_vblank_step(void) BANKED;
// Build the page-dependent attribute rows (name, stats) after render().
void        class_select_attr_prepare(void) BANKED;
// Attribute rows filled by class_select_attr_prepare (bank 27).
extern u8   cs_row_names[HERO_TROPHY_SLOTS][20];
extern u8   cs_row_stats[20];
void        class_select_enter(void);
void        class_select_exit(void);
screen_id_t class_select_tick(u8 keys, u8 pressed);
void        class_select_draw(void);

#endif
