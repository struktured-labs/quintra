#ifndef QUINTRA_GAME_DIALOG_H
#define QUINTRA_GAME_DIALOG_H

#include "core/types.h"
#include "game/screen.h"

extern u8 dialog_kind;
extern u8 dialog_topic;
extern u8 dialog_page;

// Select a nearby speaker before entering SCREEN_DIALOG. `topic` is the
// current stage for dungeon wayfarers and zero for civic residents.
void dialog_prepare(u8 kind, u8 topic) BANKED;
void dialog_enter(void);
void dialog_exit(void);
screen_id_t dialog_tick(u8 keys, u8 pressed);
void dialog_draw(void);

#endif
