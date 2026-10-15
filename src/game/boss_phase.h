#ifndef QUINTRA_BOSS_PHASE_H
#define QUINTRA_BOSS_PHASE_H
#include <gb/gb.h>
#include "game/entity.h"
#define PROJ_PRELINK 0x40
extern u8 boss_phase, boss_phase_clock, boss_link_active;
extern u8 boss_link_pending;
u8 boss_phase_tick(entity_t *e) BANKED;
u8 boss_phase_motion(entity_t *e) BANKED;
u8 boss_link_reflect(entity_t *boss, entity_t *shot, u8 damage) BANKED;
void boss_link_share(u8 source, u8 damage) BANKED;
#endif
