#pragma bank 7

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/dungeon_director.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"
#include "content.h"

u8 room_encounter_kind;
u8 room_encounter_phase;
u16 room_encounter_timer;
u8 room_encounter_complete;
u8 room_objective_dir;
u8 room_encounter_target;

static u8 encounter_spawn_clock;

u8 dungeon_director_pick_stage_enemy(u8 stage_raw) BANKED {
    u8 stage = (u8)(stage_raw % N_STAGES);
    u8 roll = rng_range(stage_pool_total[stage]);
    u8 i, sum = 0;
    for (i = 0; i < stage_pool_n[stage]; ++i) {
        sum = (u8)(sum + stage_pool_w[stage][i]);
        if (roll < sum) return stage_pool_ids[stage][i];
    }
    return stage_pool_ids[stage][0];
}

// The same nine aprons used by initial wide-court placement. Procgen carves
// each one before population, so reinforcement bodies cannot appear inside
// scenery or in the narrow false gaps deliberately closed later.
static const u8 wave_x[9] = { 15, 26, 23, 9, 4, 27, 15, 23, 9 };
static const u8 wave_y[9] = {  8, 25,  6,23, 8,  6, 19, 19,27 };

static u8 spawn_wave(u8 count, u8 make_target) {
    u8 made = 0;
    u8 attempt = 0;
    u8 offset = (u8)((run_state.room_counter + room_encounter_phase * 3) % 9);
    while (made < count && attempt < 18) {
        u8 site = (u8)(offset + attempt);
        u8 tx, ty, idx;
        i16 dx, dy;
        while (site >= 9) site = (u8)(site - 9);
        tx = wave_x[site];
        ty = wave_y[site];
        attempt++;
        dx = (i16)tx * 8 - (i16)player.x;
        dy = (i16)ty * 8 - (i16)player.y;
        if (dx < 0) dx = -dx;
        if (dy < 0) dy = -dy;
        if (dx < 40 && dy < 40) continue;
        idx = enemy_spawn(dungeon_director_pick_stage_enemy(
            run_state.bosses_beaten), tx, ty);
        if (idx == 0xFF) break;
        {
            u8 stage = run_state.bosses_beaten;
            u8 bonus;
            if (stage > 24) stage = 24;
            bonus = (u8)(1 + (stage >> 1));
            if (!RUN_IS_EASY()) bonus++;
            entities[idx].hp = (u8)(entities[idx].hp + bonus);
            // A dynamic target is always visually and mechanically legible.
            if (make_target && made == 0) {
                entities[idx].flags |= EF_ELITE;
                entities[idx].palette = 0x06;
                room_encounter_target = idx;
                if (RUN_IS_EASY())
                    entities[idx].hp = (u8)(entities[idx].hp
                        + ((entities[idx].hp + 1) >> 1));
                else
                    entities[idx].hp = (u8)(entities[idx].hp << 1);
                entities[idx].damage++;
            }
        }
        fx_spawn(SPR_FX_IMPACT, 0x06,
            (i16)tx * 8, (i16)ty * 8, 18);
        made++;
    }
    if (made) {
        sfx_play(SFX_ROAR);
        room_shake(1, 10);
    }
    return made;
}

static u8 target_alive(void) {
    return room_encounter_target < MAX_ENTITIES
        && (entities[room_encounter_target].flags & EF_ACTIVE)
        && entities[room_encounter_target].type == ENT_ENEMY;
}

static void spawn_boon_choice(void) {
    u8 roll = (u8)(run_state.room_counter + (u8)run_state.run_seed
        + player.class_id);
    u8 first = pickup_farfold_relic_for_class(roll);
    u8 second = pickup_farfold_relic_for_class((u8)(roll + 1));
    // Every generated dungeon district owns a guaranteed-open central hall.
    // Two separated orbs make the mutually exclusive choice readable and
    // keep neither reward under the champion at the instant it appears.
    pickup_spawn_choice(first, FIX8(104), FIX8(120));
    pickup_spawn_choice(second, FIX8(136), FIX8(120));
}

static void finish_directive(u8 reward) {
    room_encounter_phase = 2;
    room_encounter_complete = 1;
    if (reward) spawn_boon_choice();
}

void dungeon_director_reset(void) BANKED {
    room_encounter_kind = ENCOUNTER_SKIRMISH;
    room_encounter_phase = 0;
    room_encounter_timer = 0;
    room_encounter_complete = 0;
    room_objective_dir = DIR_NONE;
    room_encounter_target = 0xFF;
    encounter_spawn_clock = 0;
}

void dungeon_director_choose(u8 eligible, u8 was_seen) BANKED {
    u8 signature;
    if (!eligible || was_seen) return;
    signature = (u8)((u8)run_state.run_seed
        + run_state.room_counter
        + (u8)(run_state.bosses_beaten * 3));
    signature &= 7;
    if (signature == 2) room_encounter_kind = ENCOUNTER_TRAP;
    else if (signature == 3) room_encounter_kind = ENCOUNTER_WAVE;
    else if (signature == 5) room_encounter_kind = ENCOUNTER_ELITE;
    else if (signature == 6) room_encounter_kind = ENCOUNTER_HOLD;
    if (room_encounter_kind == ENCOUNTER_TRAP) room_encounter_timer = 50;
    else if (room_encounter_kind == ENCOUNTER_HOLD) {
        room_encounter_timer = RUN_IS_EASY() ? 360 : 480;
        encounter_spawn_clock = 120;
    }
}

u8 dungeon_director_adjust_initial_count(u8 proposed) BANKED {
    if (room_encounter_kind == ENCOUNTER_TRAP) return 0;
    if (room_encounter_kind == ENCOUNTER_WAVE)
        return (u8)((proposed + 1) >> 1);
    if (room_encounter_kind == ENCOUNTER_HOLD) {
        u8 cap = RUN_IS_EASY() ? 3 : 4;
        return proposed > cap ? cap : proposed;
    }
    return proposed;
}

void dungeon_director_configure_initial(u8 idx, u8 ordinal) BANKED {
    u8 stage;
    if (idx >= MAX_ENTITIES) return;
    stage = run_state.bosses_beaten;
    if (stage > 24) stage = 24;
    // This is the ordinary room depth curve, moved cold-side so procgen's
    // already-dense bank does not duplicate director-specific branches.
    entities[idx].hp = (u8)(entities[idx].hp + 1 + (stage >> 1));
    if (room_encounter_kind != ENCOUNTER_SKIRMISH && !RUN_IS_EASY())
        entities[idx].hp++;
    if (room_encounter_kind == ENCOUNTER_ELITE && ordinal == 0) {
        entities[idx].flags |= EF_ELITE;
        entities[idx].palette = 0x06;
        room_encounter_target = idx;
        if (RUN_IS_EASY())
            entities[idx].hp = (u8)(entities[idx].hp
                + ((entities[idx].hp + 1) >> 1));
        else
            entities[idx].hp = (u8)(entities[idx].hp << 1);
        entities[idx].damage++;
    }
}

u8 dungeon_director_goal_cell(void) BANKED {
    u8 size = run_state_dungeon_size();
    if (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter))
        return 0xFF;
    if (!(run_state.rift_sigils
            & RUN_STAGE_SIGIL_BIT(run_state.bosses_beaten))) return 2;
    if (!(run_state.dungeon_puzzles & RUN_WARDEN_BOON_BIT)) return 3;
    if (size >= 12
        && !(run_state.dungeon_puzzles & RUN_WAYSTONE_BIT)) return 7;
    if (size >= 14
        && !(run_state.dungeon_phase & RUN_DEEP_WARDEN_BIT)) return 9;
    if (size >= 20
        && !(run_state.dungeon_phase & RUN_DEEP_PHASE_OPEN_BIT)) return 12;
    return (u8)(size - 1);
}

u8 dungeon_director_direction_from(u8 start) BANKED {
    u8 target = dungeon_director_goal_cell();
    u8 parent[MAX_DUNGEON_CELLS];
    u8 queue[MAX_DUNGEON_CELLS];
    u8 head = 0, tail = 0, i;
    if (target == 0xFF || target == start) return DIR_NONE;
    for (i = 0; i < MAX_DUNGEON_CELLS; ++i) parent[i] = 0xFF;
    parent[start] = start;
    queue[tail++] = start;
    while (head < tail) {
        u8 cell = queue[head++];
        u8 dir;
        for (dir = DIR_N; dir <= DIR_W; ++dir) {
            u8 next = run_state_dungeon_cell_neighbor(cell, dir);
            if (next == 0xFF || parent[next] != 0xFF) continue;
            parent[next] = cell;
            if (next == target) {
                u8 step = target;
                while (parent[step] != start) step = parent[step];
                for (dir = DIR_N; dir <= DIR_W; ++dir)
                    if (run_state_dungeon_cell_neighbor(start, dir) == step)
                        return dir;
                return DIR_NONE;
            }
            queue[tail++] = next;
        }
    }
    return DIR_NONE;
}

void dungeon_director_refresh_route(void) BANKED {
    room_objective_dir = dungeon_director_direction_from(
        run_state_dungeon_cell());
}

void dungeon_director_activate(void) BANKED {
    dungeon_director_refresh_route();
    if (room_encounter_kind != ENCOUNTER_SKIRMISH)
        room_combat_sealed = 1;
}

u8 dungeon_director_update(u8 alive) BANKED {
    room_encounter_complete = 0;
    if (room_encounter_kind == ENCOUNTER_SKIRMISH
        || room_encounter_phase == 2) return alive;

    if (room_encounter_kind == ENCOUNTER_TRAP) {
        if (room_encounter_timer) {
            room_encounter_timer--;
            if (room_encounter_timer == 24) sfx_play(SFX_TICK);
            if (room_encounter_timer == 0) {
                alive = spawn_wave((u8)(RUN_IS_EASY() ? 3
                    : 4 + (run_state.bosses_beaten >= 3)), 0);
                room_encounter_phase = 1;
            }
        } else if (room_encounter_phase == 1 && alive == 0) {
            finish_directive(0);
        }
    } else if (room_encounter_kind == ENCOUNTER_WAVE) {
        if (alive == 0 && room_encounter_phase == 0) {
            room_encounter_phase = 1;
            alive = spawn_wave((u8)(RUN_IS_EASY() ? 2
                : 3 + (run_state.bosses_beaten >= 4)), 0);
        } else if (alive == 0 && room_encounter_phase == 1) {
            finish_directive(0);
        }
    } else if (room_encounter_kind == ENCOUNTER_ELITE) {
        if (!target_alive()) finish_directive(1);
    } else if (room_encounter_kind == ENCOUNTER_HOLD) {
        if (room_encounter_timer) room_encounter_timer--;
        if (encounter_spawn_clock) encounter_spawn_clock--;
        if (room_encounter_timer && encounter_spawn_clock == 0 && alive < 7) {
            alive = (u8)(alive + spawn_wave(1, 0));
            encounter_spawn_clock = 120;
        }
        if (room_encounter_timer == 0) {
            sfx_play(SFX_CLEAR);
            finish_directive(1);
        }
    }
    return alive;
}
