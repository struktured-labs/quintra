#pragma bank 30
// Pinned to cold bank 30 (next to will_maxfx): autobank (255) placed this
// file in hot banks 1-2 and tripped the bank-1 emergency floor.
// M1 Rime chamber: Rime Pipes (room-local freeze-all) + Stone Jagger
// (invincible lane roamer). Spec: docs/superpowers/specs/
// 2026-11-19-ultima-puzzle-depth.md, M1 + the 2026-11-20 M1 addendum.
//
// The Jagger is a puzzle actor, not an entities[] slot. No player weapon
// path (shots, melee, bombs, Oaths, magic, B items) scans anything but
// entities[], so nothing can damage it, flash it, or kill it, and it never
// counts toward a combat seal or room clear. Player shots that touch it are
// absorbed with a tick. All state here is WRAM rebuilt on room entry: zero
// SRAM, no player_t growth, no new Pack item id. No initialized globals.

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/law_lock.h"
#include "game/mission_graph.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/kite_room.h"
#include "game/lock_room.h"
#include "game/conduit_room.h"
#include "game/rewrite_room.h"
#include "game/rime_room.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/secret_merchant.h"
#include "render/hud.h"
#include "render/rewrite_art.h"
#include "render/rime_art.h"
#include "render/text.h"
#include "render/tiles.h"
#include <gbdk/console.h>
#include "content.h"

extern u8 new_monsters_in_room;

u8 rime_live;
u8 rime_cell;
u8 rime_charge;
u8 room_freeze_beats;
u8 rime_jx, rime_jy;
u8 rime_jagger_hold;
u8 rime_resets;
u8 puzzle_keep_on;
u8 puzzle_keep_x0, puzzle_keep_y0, puzzle_keep_y1;
u8 puzzle_pack_n;
static u8 rime_frame;
static u8 rime_art_ok;
static u8 rime_on_plate;
static u8 rime_inside;
static u8 rime_pace_right;
static i16 rime_safe_x, rime_safe_y;

#define WX(lx) ((u8)(RIME_X0 + (lx)))
#define WY(ly) ((u8)(RIME_Y0 + (ly)))
#define PX(lx) ((u8)(WX(lx) << 3))
#define PY(ly) ((u8)(WY(ly) << 3))
#define LANE_MIN PX(RIME_LANE_X0)
#define LANE_MAX PX(RIME_LANE_X1)
#define LANE_TOP PY(RIME_LANE_Y)
#define LANE_BOT ((u8)(LANE_TOP + 16))

// '#' wall, '.' floor, 'S' goal plate. Pedestals and the reset plate are
// floor drawn over with their own OBJ art (one meaning per graphic).
static const char rime_layout[RIME_H][RIME_W + 1] = {
    "#########",
    "#.......#",   // vault
    "#....SS.#",
    "#.......#",
    "######..#",   // vault gap (6..7)
    "#.......#",   // Jagger lane
    "#.......#",
    "#..######",   // foyer gap (1..2)
    "#.......#",   // foyer
    "........#",   // entrance (west wall, rows 9..10)
    "........#",
    "#.......#",
    "#.......#",
    "#########",
};

static void wset(u8 x, u8 y, u8 t) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = t;
        else room_world_extension[y][(u8)(x - ROOM_W)] = t;
    } else room_world_bottom[(u8)(y - ROOM_H)][x] = t;
}

static void wset_live(u8 x, u8 y, u8 t, u8 attr) {
    wset(x, y, t);
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &t);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &attr);
    VBK_REG = 0;
}

static u8 landmark(u8 c) {
    return (c == 0 || c == 2 || c == 5 || c == 8 || c == 11 || c == 15
        || c == 17 || c == 23) ? 1 : 0;
}

// Deepest legal off-role cell of Verdant Hollow. Mirrored by
// rime_cell() in scripts/quintra_topology.py.
u8 rime_pick_cell(void) BANKED {
    u8 size, entry, cache, host, c;
    // M1 (Verdant Hollow), M2 (Ember Depths), M3 (Frost Vault) share it.
    if (run_state.world_mode || (run_state.bosses_beaten != RIME_STAGE
            && run_state.bosses_beaten != RW_STAGE
            && run_state.bosses_beaten != KT_STAGE
            && run_state.bosses_beaten != LK_STAGE
            && run_state.bosses_beaten != CD_STAGE))
        return 0xFF;
    mission_graph_ensure();
    size = run_state_dungeon_size();
    entry = run_state_dungeon_entry_cell();
    cache = run_state_dungeon_cache_cell();
    host = secret_merchant_host_cell();
    for (c = (u8)(size - 4); c >= 1; --c) {
        if (c == entry || c == cache || c == host || landmark(c)) continue;
        // Every sixth cell may own an ambient Dungeon Law altar.
        if ((c % 6) == 0) continue;
        if (mission_graph_cell_is_role(c)) continue;
        // An ambient Law altar owns this cell: the floor simply has no
        // chamber (never fall through, so the Python mirror stays exact).
        return law_lock_cell_is_altar(c) ? 0xFF : c;
    }
    return 0xFF;
}

// Hero hurtbox (x+5..x+10, y+9..y+14) against a box.
static u8 hero_hits(u8 bx, u8 by, u8 w, u8 h) {
    i16 hx = (i16)player.x + 5, hy = (i16)player.y + 9;
    if (hx + 6 <= (i16)bx || hx >= (i16)(bx + w)) return 0;
    if (hy + 6 <= (i16)by || hy >= (i16)(by + h)) return 0;
    return 1;
}

// Footprint + apron + the corridor west to the central N-S trail (x9..10),
// the one spine every dungeon field keeps open. Anything carved must be
// swept of loose entities first.
#define RIME_TRAIL_X 11
static u8 in_zone(u8 ex, u8 ey) {
    if (ex >= (u8)(RIME_X0 - 4) && ey >= RIME_Y0
        && ey < (u8)(RIME_Y0 + RIME_H)) return 1;
    return (ex >= RIME_TRAIL_X && ey >= (u8)(WY(RIME_ENTRY_Y) - 1)
        && ey <= (u8)(WY(RIME_ENTRY_Y) + 2)) ? 1 : 0;
}

static void rime_restore(void) {
    rime_jx = PX(RIME_JAGGER_X);
    rime_jy = LANE_TOP;
    rime_charge = 0;
    room_freeze_beats = 0;
    rime_pace_right = 0;
}

u8 rime_prepare(void) BANKED {
    u8 i, x, y;
    rime_live = 0;
    if (!procgen_current_room_is_large || room_world_width < ROOM_WIDE_W_PX
        || room_world_height < ROOM_WIDE_H_PX) return 0;
    // Decline (ordinary room) if something that must persist sits in the
    // footprint or its apron. Loose coins / hearts / MP are swept.
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        u8 ex, ey;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_PICKUP) continue;
        ex = (u8)((e->x + 8) >> 3);
        ey = (u8)((e->y + 8) >> 3);
        if (in_zone(ex, ey)
            && e->ai_data[0] != PICKUP_HEART_HALF
            && e->ai_data[0] != PICKUP_COIN_1
            && e->ai_data[0] != PICKUP_COIN_5
            && e->ai_data[0] != PICKUP_MP) return 0;
    }
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        u8 ex, ey, id;
        if (!(e->flags & EF_ACTIVE)) continue;
        id = e->ai_data[0];
        // Basilisks own the same bank-1 OBJ tiles; never mix them in.
        if (e->type == ENT_ENEMY && (id == ENEMY_LEYBEAM
                || id == ENEMY_SUN_BASILISK || id == ENEMY_NOX_BASILISK)) {
            entity_kill(i);
            continue;
        }
        if (e->type != ENT_ENEMY && e->type != ENT_PICKUP) continue;
        ex = (u8)((e->x + 8) >> 3);
        ey = (u8)((e->y + 8) >> 3);
        if (in_zone(ex, ey)) entity_kill(i);
    }
    for (y = 0; y < RIME_H; ++y)
        for (x = 0; x < RIME_W; ++x) {
            char c = rime_layout[y][x];
            u8 t = (c == '#') ? BGT_WALL : BGT_FLOOR;
            if (c == 'S') t = (run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT)
                ? BGT_SWITCH_PRESSED : BGT_SWITCH;
            wset(WX(x), WY(y), t);
        }
    // Always-open apron west of the entrance, then a two-tile corridor on
    // the entrance rows back to the central trail, so the doorway can never
    // open into a pillar-sealed pocket of the courtyard.
    for (y = (u8)(RIME_ENTRY_Y - 1); y <= (u8)(RIME_ENTRY_Y + 2); ++y)
        for (x = (u8)(RIME_X0 - 4); x < RIME_X0; ++x)
            wset(x, WY(y), BGT_FLOOR);
    for (y = RIME_ENTRY_Y; y <= (u8)(RIME_ENTRY_Y + 1); ++y)
        for (x = RIME_TRAIL_X; x < (u8)(RIME_X0 - 4); ++x)
            wset(x, WY(y), BGT_FLOOR);
    rime_restore();
    rime_jagger_hold = 0;
    rime_resets = 0;
    rime_frame = 0;
    rime_art_ok = 0;
    rime_on_plate = 0;
    rime_inside = 0;
    rime_safe_x = player.x;
    rime_safe_y = player.y;
    puzzle_keep_x0 = (u8)RIME_KEEP_X0;
    puzzle_keep_y0 = (u8)RIME_KEEP_Y0;
    puzzle_keep_y1 = (u8)RIME_KEEP_Y1;
    puzzle_keep_on = 1;
    puzzle_pack_n = 2;
    rime_live = 1;
    new_monsters_in_room = 1;
    return 1;
}

void rime_use_pipes(void) BANKED {
    if (!rime_live || !rime_charge) {
        sfx_play(SFX_REFUSE);
        return;
    }
    rime_charge = 0;
    room_freeze_beats = RUN_IS_EASY() ? RIME_FREEZE_EASY : RIME_FREEZE_NORMAL;
    sfx_play(SFX_WEAK);
    room_shake(1, 6);
}

void rime_reset(void) BANKED {
    if (!rime_live) return;
    rime_restore();
    // Puzzle state only: HP, MP and run-long Pack charges are untouched.
    player.x = (i16)PX(1);
    player.y = (i16)PY(RIME_ENTRY_Y);
    if (player.iframes < 45) player.iframes = 45;
    rime_safe_x = player.x;
    rime_safe_y = player.y;
    rime_jagger_hold = 30;
    rime_on_plate = 0;
    rime_resets++;
    sfx_play(SFX_PORTAL);
    room_shake(1, 10);
}

static void solve(void) {
    run_state.dungeon_puzzles |= RUN_RIME_SOLVED_BIT;
    wset_live(WX(RIME_GOAL_X), WY(RIME_GOAL_Y), BGT_SWITCH_PRESSED, BGPAL_DOOR);
    wset_live(WX(RIME_GOAL_X + 1), WY(RIME_GOAL_Y), BGT_SWITCH_PRESSED,
        BGPAL_DOOR);
    sfx_play(SFX_PUZZLE);
    room_shake(1, 18);
    // Same reward as a mandatory puzzle: one physical Pack tool charge.
    pickup_spawn_item((u8)(22 + ((u8)run_state.run_seed + rime_cell) % 3),
        player.x, player.y);
}

static void jagger_step(u8 inside) {
    u8 target;
    if (rime_jagger_hold) { rime_jagger_hold--; return; }
    if (room_freeze_beats) return;
    // Easy: three steps in four.
    if (RUN_IS_EASY() && (rime_frame & 3) == 3) return;
    if (inside) {
        i16 hx = player.x;
        target = (hx < (i16)LANE_MIN) ? LANE_MIN
            : (hx > (i16)LANE_MAX) ? LANE_MAX : (u8)hx;
    } else {
        // Idle: a slow pace along the lane while the hero is away.
        if (rime_frame & 1) return;
        if (rime_jx >= LANE_MAX) rime_pace_right = 0;
        else if (rime_jx <= LANE_MIN) rime_pace_right = 1;
        target = rime_pace_right ? LANE_MAX : LANE_MIN;
    }
    if (rime_jx < target) rime_jx++;
    else if (rime_jx > target) rime_jx--;
}

// Anything that reached the chamber by another movement path (knockback,
// a chase) is set back on the open apron outside the doorway.
static void evict_enemies(void) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 cx, cy;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        cx = e->x + 8; cy = e->y + 8;
        if (cx < RIME_KEEP_X0 || cy < RIME_KEEP_Y0 || cy >= RIME_KEEP_Y1)
            continue;
        e->x = (i16)PX(-4);
        e->y = (i16)PY(RIME_ENTRY_Y);
    }
}

static void absorb_shots(void) {
    u8 i, hit = 0;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 sx, sy;
        u8 w, h;
        if ((e->flags & (EF_ACTIVE | EF_PLAYER_PROJ))
            != (EF_ACTIVE | EF_PLAYER_PROJ) || e->type != ENT_PROJECTILE)
            continue;
        sx = e->x; sy = e->y;
        w = (u8)(e->hitbox >> 4); h = (u8)(e->hitbox & 0x0F);
        if (sx + w <= (i16)rime_jx + 1 || sx >= (i16)rime_jx + 15) continue;
        if (sy + h <= (i16)rime_jy + 1 || sy >= (i16)rime_jy + 16) continue;
        entity_kill(i);
        hit = 1;
    }
    if (hit) sfx_play(SFX_TICK);
}

void rime_tick(void) BANKED {
    u8 ftx, fty, inside, on_plate, in_lane;
    if (!rime_live) return;
    if (!rime_art_ok) { rime_art_load(); rime_art_ok = 1; }
    new_monsters_in_room = 1;
    rime_frame++;
    if (room_freeze_beats && !(rime_frame & 3)) room_freeze_beats--;

    ftx = (u8)((player.x + 8) >> 3);
    fty = (u8)((player.y + 12) >> 3);
    inside = (ftx >= RIME_X0 && ftx < (u8)(RIME_X0 + RIME_W)
        && fty >= RIME_Y0 && fty < (u8)(RIME_Y0 + RIME_H)) ? 1 : 0;
    // Walking out of the entrance drops the floor-local charge, like a
    // reset; the Jagger only ever shadows the hero, so its spot is not state.
    if (rime_inside && !inside) rime_charge = 0;
    rime_inside = inside;

    on_plate = (inside && (u8)(ftx - WX(RIME_PLATE_X)) < 2
        && (u8)(fty - WY(RIME_PLATE_Y)) < 2) ? 1 : 0;
    if (on_plate && !rime_on_plate) {
        rime_reset();
        rime_on_plate = 1;
        return;
    }
    rime_on_plate = on_plate;

    if (inside && !rime_charge && !room_freeze_beats
        && (hero_hits(PX(RIME_PED_FOYER_X), PY(RIME_PED_FOYER_Y), 16, 16)
            || hero_hits(PX(RIME_PED_VAULT_X), PY(RIME_PED_VAULT_Y), 16, 16))) {
        rime_charge = 1;
        sfx_play(SFX_COIN);
    }

    if (inside && fty == WY(RIME_GOAL_Y)
        && (u8)(ftx - WX(RIME_GOAL_X)) < 2
        && !(run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT)) solve();

    jagger_step(inside);
    absorb_shots();
    if (!(rime_frame & 7)) evict_enemies();

    in_lane = (inside && (i16)player.y + 15 > (i16)LANE_TOP
        && (i16)player.y + 9 < (i16)LANE_BOT) ? 1 : 0;
    if (!in_lane) { rime_safe_x = player.x; rime_safe_y = player.y; }
    // A frozen Jagger is a harmless statue the hero may walk through.
    if (!room_freeze_beats && !player.iframes && !player.shield_timer
        && hero_hits((u8)(rime_jx + 2), (u8)(rime_jy + 2), 12, 14)) {
        // One heart, never lethal, and a shove back to where the hero
        // last stood outside the lane.
        if (player.hp > 2) player.hp = (u8)(player.hp - 2);
        else if (player.hp > 1) player.hp = 1;
        player.iframes = 60;
        player.x = rime_safe_x;
        player.y = rime_safe_y;
        sfx_play(SFX_HURT);
        hud_redraw_hp();
    }
}

// Pack TOOL row entries, drawn and confirmed here so the hot Pack bank only
// pays two far calls. Returns 2 to close the Pack and apply on resume.
void rime_pack_draw(u8 pipes) BANKED {
    gotoxy(3, 15);
    if (pipes) {
        text_write("TOOL PIPES x");
        text_u16(rime_charge);
    } else text_write("TOOL RESET ROOM");
    set_sprite_tile(8, pipes ? RIME_TILE_PIP
        : (rw_live || kt_live) ? RW_TILE_PLATE : RIME_TILE_GLYPH);
    set_sprite_prop(8, pipes ? (3 | 0x08) : (5 | 0x08));
    move_sprite(8, 16, 135);
}

u8 rime_pack_a(u8 pipes) BANKED {
    if (pipes && !rime_charge) {
        sfx_play(SFX_HURT);
        return 1;
    }
    sfx_play(SFX_CLEAR);
    return 2;
}

// Pack TOOL entries past the four physical tools. M1: PIPES, RESET ROOM.
// M2 / M3: RESET ROOM.
void puzzle_pack_draw(u8 idx) BANKED {
    if (cd_live) { cd_pack_draw(idx); return; }
    if (lk_live) { lk_pack_draw(idx); return; }
    rime_pack_draw((rime_live && idx == 0) ? 1 : 0);
}

u8 puzzle_pack_a(u8 idx) BANKED {
    if (cd_live) return cd_pack_a(idx);
    if (lk_live) return lk_pack_a(idx);
    return rime_pack_a((rime_live && idx == 0) ? 1 : 0);
}

void puzzle_pack_apply(u8 idx) BANKED {
    if (cd_live) cd_pack_apply(idx);
    else if (lk_live) lk_pack_apply(idx);
    else if (kt_live) kt_reset();
    else if (rw_live) rw_reset();
    else if (idx == 0) rime_use_pipes();
    else rime_reset();
}
