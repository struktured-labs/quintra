#pragma bank 28
// M3 Kite Kennel: the tool-beast chain (spec section 5 pattern / M3).
// Pinned in cold bank 28 (art in bank 31); banks 26 and 30 hold M2 and M1.
#include <gb/gb.h>
#include "audio/sfx.h"
#include "core/types.h"
#include "game/entity.h"
#include "game/enemy_new_ai.h"
#include "game/kite_room.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/puzzle.h"
#include "game/rime_room.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/hud.h"
#include "render/kite_art.h"
#include "render/tiles.h"
#include "content.h"

u8 kt_live;
u8 kt_s1, kt_x, kt_broken;
u8 kt_state, kt_ky, kt_cold, kt_frame;
u8 kt_resets, kt_deaths, kt_refusals, kt_blink, kt_offcam_sfx;
static u8 kt_t;                 // breath / respawn timer
static u8 kt_queue, kt_flash, kt_flash_t, kt_cool, kt_cue, kt_epoch;
static u8 kt_on_l, kt_on_s1, kt_on_s2, kt_on_reset, kt_on_goal;

#define WX(lx) ((u8)(KT_X0 + (lx)))
#define WY(ly) ((u8)(KT_Y0 + (ly)))
#define PX(lx) ((u8)(WX(lx) << 3))
#define PY(ly) ((u8)(WY(ly) << 3))
#define KY_HOME PY(KT_HOME_Y)
#define KY_END  PY(KT_END_Y)
#define KT_COLD_DIE 150
#define KT_RESPAWN  90

// '#' wall, '.' floor, 'G' goal, 'K' kennel floor (stream), 'g' gate,
// 'a'/'b' channel segments, 's' fixed stream, 'L' crystal lock.
static const char kt_layout[KT_H][KT_W + 1] = {
    "############",
    "#R-.....#KK#",   // reset plate (1,1); kennel niche (9..10, 1..2)
    "#--.....#KK#",
    "#.....L-#gg#",   // lever (6,3); kennel gate (9..10, 3..4)
    "#.....--#gg#",
    "#.....1-#aa#",   // stream plate S1 (6,5); segment A (9..10, 5..6)
    "......--#aa#",   // entrance rows 6..7
    "......2-#bb#",   // stream plate S2 (6,7) (linked to the lever); segment B
    "#.....--#bb#",
    "#.......#ss#",   // fixed stream: the stream preview, seen at once
    "#.......#ss#",
    "######LL#ss#",   // crystal lock (6..7, 11..12) plugs the vault door;
    "######LL#ss#",   // the Kite breathes on it from the channel end
    "#..........#",   // vault
    "#..........#",
    "#...GG.....#",
    "#..........#",
    "############",
};

static const u8 reg_x[KT_REGIONS] = { KT_CHAN_X, KT_CHAN_X, KT_CHAN_X, KT_LOCK_X };
static const u8 reg_y[KT_REGIONS] = { 3, 5, 7, KT_LOCK_Y };

static void wset(u8 x, u8 y, u8 t) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = t;
        else room_world_extension[y][(u8)(x - ROOM_W)] = t;
    } else room_world_bottom[(u8)(y - ROOM_H)][x] = t;
}

// Palette: stream glows (crystal ramp), the lock is a door plug (door
// ramp), cairn and bars are wall. All four are solid to the hero.
static u8 tile_attr(u8 t) {
    if (t == KT_T_STREAM) return BGPAL_CRYSTAL;
    if (t == KT_T_LOCK_T || t == KT_T_LOCK_B) return BGPAL_DOOR;
    if (t == BGT_FLOOR) return BGPAL_FLOOR;
    return BGPAL_WALL;
}

static void fill4(u8 *t, u8 v) { t[0] = t[1] = t[2] = t[3] = v; }

static void region_tiles(u8 r, u8 *t) {
    u8 open;
    if (r == 3) {
        if (kt_broken) { fill4(t, BGT_FLOOR); return; }
        t[0] = t[1] = KT_T_LOCK_T; t[2] = t[3] = KT_T_LOCK_B;
        return;
    }
    open = (r == 0) ? kt_x : (r == 1) ? kt_s1 : (u8)!kt_x;
    if (open) { fill4(t, KT_T_STREAM); return; }
    if (r == 0) { fill4(t, KT_T_BARS); return; }
    t[0] = KT_T_CAIRN_TL; t[1] = KT_T_CAIRN_TR;
    t[2] = KT_T_CAIRN_BL; t[3] = KT_T_CAIRN_BR;
}

// Write one 2x2 block (world arrays + BG map + attributes); caller syncs.
static void block_put(u8 r, u8 flash) {
    u8 t[4], a[4], i, x = WX(reg_x[r]), y = WY(reg_y[r]);
    region_tiles(r, t);
    for (i = 0; i < 4; ++i) a[i] = flash ? BGPAL_DOOR : tile_attr(t[i]);
    if (r == 3 && !kt_broken) { a[1] |= 0x20; a[3] |= 0x20; }   // mirror
    wset(x, y, t[0]); wset((u8)(x + 1), y, t[1]);
    wset(x, (u8)(y + 1), t[2]); wset((u8)(x + 1), (u8)(y + 1), t[3]);
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 2, 2, t);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 2, 2, a);
    VBK_REG = 0;
}

static void region_paint(u8 r, u8 flash) {
    wait_vbl_done();
    block_put(r, flash);
}

static u8 region_in_view(u8 r) {
    u8 cx = (u8)(room_camera_x >> 3), cy = (u8)(room_camera_y >> 3);
    u8 x = WX(reg_x[r]), y = WY(reg_y[r]);
    return ((u8)(x + 2) > cx && x < (u8)(cx + 20)
        && (u8)(y + 2) > cy && y < (u8)(cy + 17)) ? 1 : 0;
}

static u8 foot_on(u8 lx, u8 ly) {
    u8 fx = (u8)((player.x + 8) >> 3), fy = (u8)((player.y + 12) >> 3);
    return ((u8)(fx - WX(lx)) < 2 && (u8)(fy - WY(ly)) < 2) ? 1 : 0;
}

// Kite's full 16x16 box against region rows (r, r+1) of the channel.
static u8 kite_over(u8 r) {
    u8 top = PY(reg_y[r]);
    if (kt_state == KT_DEAD) return 0;
    return (kt_ky < (u8)(top + 16) && (u8)(kt_ky + 16) > top) ? 1 : 0;
}

// Can the Kite's leading edge enter pixel row py (world px)?
static u8 row_open(u8 py) {
    u8 lr = (u8)((py >> 3) - KT_Y0);
    if (lr <= 2) return 1;                  // kennel
    if (lr <= 4) return kt_x;               // gate
    if (lr <= 6) return kt_s1;              // segment A
    if (lr <= 8) return (u8)!kt_x;          // segment B
    return 1;                               // fixed stream to the end
}

static void refuse(void) {
    kt_refusals++;
    sfx_play(SFX_REFUSE);
    kt_cool = 20;
}

static void commit(u8 mask) {
    kt_queue |= mask;
    kt_cue = 0;
    kt_cool = 20;
    sfx_play(SFX_DOOR);
}

static void press_s1(void) {
    if (kite_over(1)) { refuse(); return; }
    kt_s1 ^= 1;
    commit(1 << 1);
}

// Lever and S2 are one switch: gate open <=> segment B closed.
static void press_link(void) {
    if (kite_over(0) || kite_over(2)) { refuse(); return; }
    kt_x ^= 1;
    commit((1 << 0) | (1 << 2));
}

static void evict_enemies(void) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 cx, cy;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_ENEMY) continue;
        cx = e->x + 8; cy = e->y + 8;
        if (cx < (i16)puzzle_keep_x0 || cy < (i16)puzzle_keep_y0) continue;
        e->x = (i16)PX(-4);
        e->y = (i16)PY(KT_ENTRY_Y);
    }
}

static u8 in_zone(u8 ex, u8 ey) {
    if (ex >= (u8)(KT_X0 - 4) && ey >= KT_Y0 && ey < (u8)(KT_Y0 + KT_H)) return 1;
    return (ex >= 11 && ey >= (u8)(WY(KT_ENTRY_Y) - 1)
        && ey <= (u8)(WY(KT_ENTRY_Y) + 2)) ? 1 : 0;
}

static void kite_home(void) {
    kt_state = KT_HOME;
    kt_ky = KY_HOME;
    kt_cold = 0;
    kt_t = 0;
}

u8 kt_prepare(void) BANKED {
    u8 i, x, y;
    kt_live = 0;
    if (!procgen_current_room_is_large || room_world_width < ROOM_WIDE_W_PX
        || room_world_height < ROOM_WIDE_H_PX) return 0;
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
    kt_s1 = kt_x = kt_broken = 0;
    for (y = 0; y < KT_H; ++y)
        for (x = 0; x < KT_W; ++x) {
            char c = kt_layout[y][x];
            u8 t = BGT_FLOOR;
            if (c == '#') t = BGT_WALL;
            else if (c == 'K' || c == 's') t = KT_T_STREAM;
            else if (c == 'G') t = (run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT)
                ? BGT_SWITCH_PRESSED : BGT_SWITCH;
            wset(WX(x), WY(y), t);
        }
    for (i = 0; i < KT_REGIONS; ++i) {
        u8 t[4];
        region_tiles(i, t);
        x = WX(reg_x[i]); y = WY(reg_y[i]);
        wset(x, y, t[0]); wset((u8)(x + 1), y, t[1]);
        wset(x, (u8)(y + 1), t[2]); wset((u8)(x + 1), (u8)(y + 1), t[3]);
    }
    for (y = (u8)(KT_ENTRY_Y - 1); y <= (u8)(KT_ENTRY_Y + 2); ++y)
        for (x = (u8)(KT_X0 - 4); x < KT_X0; ++x)
            wset(x, WY(y), BGT_FLOOR);
    for (y = KT_ENTRY_Y; y <= (u8)(KT_ENTRY_Y + 1); ++y)
        for (x = 11; x < (u8)(KT_X0 - 4); ++x)
            wset(x, WY(y), BGT_FLOOR);
    kite_home();
    kt_queue = kt_blink = kt_flash = kt_flash_t = kt_cool = 0;
    kt_on_l = kt_on_s1 = kt_on_s2 = kt_on_reset = kt_on_goal = 0;
    kt_resets = kt_deaths = kt_refusals = kt_offcam_sfx = 0;
    kt_cue = 1;
    kt_epoch = (u8)(tiles_bg_epoch - 1);
    puzzle_keep_x0 = (u8)((KT_X0 - 1) * 8);
    puzzle_keep_y0 = (u8)(KT_Y0 * 8);
    puzzle_keep_y1 = (u8)((KT_Y0 + KT_H) * 8);
    puzzle_keep_on = 1;
    puzzle_pack_n = 1;
    kt_live = 1;
    new_monsters_in_room = 1;
    return 1;
}

void kt_reset(void) BANKED {
    if (!kt_live) return;
    // Warp first, then re-lock: the hero is never sealed in the vault.
    player.x = (i16)PX(1);
    player.y = (i16)PY(KT_ENTRY_Y - 1);
    if (player.iframes < 45) player.iframes = 45;
    kt_s1 = kt_x = kt_broken = 0;
    kite_home();
    kt_queue = (1 << KT_REGIONS) - 1;
    kt_cue = 1;                 // a reset is its own cue (portal SFX)
    kt_blink = 0;
    kt_flash = kt_flash_t = 0;
    kt_on_reset = kt_on_l = kt_on_s1 = kt_on_s2 = 1;
    kt_cool = 20;
    kt_resets++;
    sfx_play(SFX_PORTAL);
    room_shake(1, 10);
}

static void solve(void) {
    u8 t[2] = { BGT_SWITCH_PRESSED, BGT_SWITCH_PRESSED };
    u8 a[2] = { BGPAL_DOOR, BGPAL_DOOR };
    run_state.dungeon_puzzles |= RUN_RIME_SOLVED_BIT;
    wset(WX(KT_GOAL_X), WY(KT_GOAL_Y), BGT_SWITCH_PRESSED);
    wset(WX(KT_GOAL_X + 1), WY(KT_GOAL_Y), BGT_SWITCH_PRESSED);
    wait_vbl_done();
    set_bkg_tiles(ROOM_BG_MAP_X(WX(KT_GOAL_X)), ROOM_BG_MAP_Y(WY(KT_GOAL_Y)), 2, 1, t);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(WX(KT_GOAL_X)), ROOM_BG_MAP_Y(WY(KT_GOAL_Y)), 2, 1, a);
    VBK_REG = 0;
    sfx_play(SFX_PUZZLE);
    room_shake(1, 18);
    pickup_spawn_item((u8)(22 + ((u8)run_state.run_seed + rime_cell) % 3),
        player.x, player.y);
}

static void paint_step(void) {
    u8 r;
    for (r = 0; r < KT_REGIONS; ++r) {
        if (!(kt_queue & (1 << r))) continue;
        kt_queue &= (u8)~(1 << r);
        if (kt_flash & (1 << r)) { kt_flash = 0; kt_flash_t = 0; }
        if (!region_in_view(r)) {
            // Off camera: one distinct cue per press, then a blink on arrival.
            kt_blink |= (u8)(1 << r);
            if (!kt_cue) {
                kt_cue = 1;
                kt_offcam_sfx++;
                sfx_play(SFX_DISTRICT);
            }
        } else kt_blink &= (u8)~(1 << r);
        region_paint(r, 0);
        return;                         // amortized: one 2x2 per frame
    }
}

static void blink_step(void) {
    u8 r;
    if (kt_flash_t) {
        if (--kt_flash_t == 0) {
            for (r = 0; r < KT_REGIONS; ++r)
                if (kt_flash & (1 << r)) region_paint(r, 0);
            kt_flash = 0;
        }
        return;
    }
    for (r = 0; r < KT_REGIONS; ++r) {
        if (!(kt_blink & (1 << r)) || !region_in_view(r)) continue;
        kt_blink &= (u8)~(1 << r);
        kt_flash = (u8)(1 << r);
        kt_flash_t = 16;
        region_paint(r, 1);
        return;
    }
}

// Re-dress after any dungeon BG reload: art and every region as it stands.
static void redress(void) {
    u8 r;
    kt_flash = kt_flash_t = 0;
    for (r = 0; r < KT_REGIONS; ++r) region_paint(r, 0);
    // Fixed stream and kennel floor carry the renderer's palette; repaint.
    {
        u8 t[2] = { KT_T_STREAM, KT_T_STREAM }, a[2] = { BGPAL_CRYSTAL, BGPAL_CRYSTAL };
        u8 ly;
        static const u8 rows[6] = { 1, 2, 9, 10, 11, 12 };
        wait_vbl_done();
        for (ly = 0; ly < 6; ++ly) {
            u8 y = WY(rows[ly]);
            VBK_REG = 1;
            set_bkg_tiles(ROOM_BG_MAP_X(WX(KT_CHAN_X)), ROOM_BG_MAP_Y(y), 2, 1, a);
            VBK_REG = 0;
            set_bkg_tiles(ROOM_BG_MAP_X(WX(KT_CHAN_X)), ROOM_BG_MAP_Y(y), 2, 1, t);
        }
    }
}

static void kite_step(void) {
    switch (kt_state) {
    case KT_HOME:
        if (kt_x) { kt_state = KT_DOWN; kt_cold = 0; }
        break;
    case KT_DOWN:
        if (kt_ky >= KY_END) {
            kt_state = KT_BREATH;
            kt_t = 0;
            sfx_play(SFX_FIRE);
        } else if (kt_ky == KY_HOME && !kt_x) {
            kt_state = KT_HOME;         // gate shut before it left
        } else if (row_open((u8)(kt_ky + 16))) {
            kt_ky++;
            kt_cold = 0;
        } else if (++kt_cold >= KT_COLD_DIE) {
            // The Frost Vault cold douses a Kite left waiting.
            kt_state = KT_DEAD;
            kt_t = 0;
            kt_deaths++;
            sfx_play(SFX_DEATH);
        }
        break;
    case KT_BREATH:
        if (++kt_t >= 24) {
            if (!kt_broken) {
                kt_broken = 1;
                kt_queue |= 1 << 3;
                kt_cue = 0;
                sfx_play(SFX_PUZZLE);
                room_shake(1, 12);
            }
            kt_state = KT_RETURN;
        }
        break;
    case KT_RETURN:
        // Aerial: flies straight home over anything, then shuts the gate.
        if (kt_ky <= (u8)(KY_HOME + 2)) {
            kite_home();
            if (kt_x) { kt_x = 0; kt_queue |= (1 << 0) | (1 << 2); kt_cue = 0; }
        } else kt_ky -= 2;
        break;
    default:                            // KT_DEAD: re-forms in the kennel
        if (++kt_t >= KT_RESPAWN) {
            kite_home();
            if (kt_x) { kt_x = 0; kt_queue |= (1 << 0) | (1 << 2); kt_cue = 0; }
            sfx_play(SFX_HEART);
        }
        break;
    }
}

void kt_tick(void) BANKED {
    u8 on, ok;
    if (!kt_live) return;
    if (kt_epoch != tiles_bg_epoch) {
        // Room entry or Pack resume reloaded the dungeon set: re-dress.
        kt_bg_art_load();
        kt_art_load();
        redress();
        kt_epoch = tiles_bg_epoch;
    }
    new_monsters_in_room = 1;
    kt_frame++;
    if (kt_cool) kt_cool--;
    paint_step();
    blink_step();
    kite_step();

    on = foot_on(KT_RESET_X, KT_RESET_Y);
    if (on && !kt_on_reset) { kt_reset(); return; }
    kt_on_reset = on;

    // Edges sampled every frame; cooldown/queue only gate the press.
    ok = (!kt_cool && !kt_queue) ? 1 : 0;
    on = foot_on(KT_LEVER_X, KT_LEVER_Y);
    if (ok && on && !kt_on_l) { press_link(); ok = 0; }
    kt_on_l = on;
    on = foot_on(KT_S1_X, KT_S1_Y);
    if (ok && on && !kt_on_s1) { press_s1(); ok = 0; }
    kt_on_s1 = on;
    on = foot_on(KT_S2_X, KT_S2_Y);
    if (ok && on && !kt_on_s2) press_link();
    kt_on_s2 = on;

    on = (foot_on(KT_GOAL_X, KT_GOAL_Y) && ((player.y + 12) >> 3) == WY(KT_GOAL_Y)) ? 1 : 0;
    if (on && !kt_on_goal && !(run_state.dungeon_puzzles & RUN_RIME_SOLVED_BIT))
        solve();
    kt_on_goal = on;
    if (!(kt_frame & 7)) evict_enemies();
}
