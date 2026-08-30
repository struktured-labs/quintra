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
// Major dungeon objectives reuse the readable conversation screen but have a
// one-page claim layout, a raised-artifact tableau, and no speaker identity.
void dialog_prepare_reward(u8 kind, u8 topic) BANKED;
// Riftwild gate arrivals pause on an authored stage card for up to five
// seconds; A/B/START skips immediately into the already-generated room.
void dialog_prepare_stage(u8 stage) BANKED;
void dialog_enter(void);
void dialog_exit(void);
screen_id_t dialog_tick(u8 keys, u8 pressed);
void dialog_draw(void);

#endif
