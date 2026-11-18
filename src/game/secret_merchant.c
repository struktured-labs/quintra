#pragma bank 22

// Secret merchants (docs/superpowers/specs/2026-11-16-secret-merchants.md).
//
// Dungeon: one Veil Trader per stage. A seeded host cell (isolated
// xorshift32, never the room RNG) carries one concealed tell; opening it
// paints the ordinary 16 px secret mouth, and walking in builds the stall
// as procgen's secret overlay (keeper + three shelves, no enemies). The
// keeper is never standing in the host room.
//
// Riftwild: three hidden cave merchants per region, one per two-row band,
// never on a den, the Riftwell, a fixture field or a Hollow relic field.
// The tell is a complete standalone tile in a cleared footprint (no metatile
// fragments); the stall is a compact room at world_screen 48 + cave.
//
// Persistence: run_state.secret_shop / veil_charms / rift_caves (appended).

#include <gb/gb.h>
#include <gbdk/console.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/companion.h"
#include "game/dungeon_director.h"
#include "game/entity.h"
#include "game/mission_graph.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/powerup.h"
#include "game/procgen.h"
#include "game/projectile.h"
#include "game/puzzle.h"
#include "game/riftwild_den.h"
#include "game/riftwild_setpiece.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/secret_merchant.h"
#include "game/stage_event.h"
#include "game/status.h"
#include "game/sun_lattice.h"
#include "game/waygear.h"
#include "input/input.h"
#include "render/hud.h"
#include "render/text.h"
#include "render/tiles.h"
#include "content.h"

u8 secret_merchant_host_here;
u8 secret_merchant_armed;
// Fading-floor warning length (stage_event_hazards). Gloam Lamp and Rime
// Skates add 20 frames.
u8 secret_floor_warn = 60;

static u8 glint_pending;
static u8 cinder_used;
static u8 touch_ticks;
static u8 bell_clock;
static u8 wall_p;       // Veil wall pair origin along its wall
static u8 wall_side;    // 0 = north wall, 1 = west wall

static const u8 veil_kind[9] = {
    SECRET_KIND_BLAST, SECRET_KIND_THICKET, SECRET_KIND_BLAST,
    SECRET_KIND_STONE, SECRET_KIND_STONE, SECRET_KIND_BLAST,
    SECRET_KIND_THICKET, SECRET_KIND_BLAST, SECRET_KIND_THICKET,
};
static const u8 tonic_price[9] = { 16, 18, 18, 16, 20, 20, 24, 18, 20 };
// Phase 1 power-ups shipped (Aegis, Limitless, Mend). Uncommon and rare
// bottles fall back to the Grand Surge stand-in at 24 (spec §5 / §6.4).
static const u8 veil_bottle[9] = {
    SM_BOTTLE_AEGIS, SM_BOTTLE_MEND, SM_BOTTLE_SURGE, SM_BOTTLE_AEGIS,
    SM_BOTTLE_LIMIT, SM_BOTTLE_SURGE, SM_BOTTLE_LIMIT, SM_BOTTLE_SURGE,
    SM_BOTTLE_SURGE,
};
static const u8 charm_price[12] = {
    32, 45, 40, 45, 50, 50, 55, 60, 70,   // Veil signatures, stages 1..9
    40, 45, 55,                           // Wild charms, regions 1..3
};
static const u8 charm_word[12] = {
    NW_LIGHT, NW_COMB, NW_CINDER, NW_SKATES, NW_MASK, NW_LAMP, NW_SEAL,
    NW_PACT, NW_LAST, NW_BELL, NW_LURE, NW_WICK,
};

// ------------------------------------------------------------------ hash

static u32 hs;

static void live_set(u8 x, u8 y, u8 tile, u8 attr);

static u8 next_hash(void) {
    hs ^= hs << 13;
    hs ^= hs >> 17;
    hs ^= hs << 5;
    return (u8)(hs >> 8);
}

static const u32 golden[9] = {
    0x00000000UL, 0x9E3779B9UL, 0x3C6EF372UL, 0xDAA66D2BUL, 0x78DDE6E4UL,
    0x1715609DUL, 0xB54CDA56UL, 0x5384540FUL, 0xF1BBCDC8UL,
};

static void seed_hash(u8 k, u32 tag) {
    hs = run_state.run_seed ^ golden[k] ^ tag;
    if (!hs) hs = 0x2545F491UL;
}

static u8 stage(void) {
    return run_state.bosses_beaten;
}

// ------------------------------------------------------------- Veil host

static u8 host_cache_stage = 0xFF;
static u32 host_cache_seed;
u8 secret_host_cell_cache;   // global: read by the headless tests

static u8 host_legal(u8 cell, u8 size, u8 entry, u8 cache) {
    if (cell == 0 || cell == entry || cell == cache
        || cell + 3 >= size) return 0;
    if (cell == 2 || cell == 5 || cell == 8 || cell == 11
        || cell == 15 || cell == 17 || cell == 23) return 0;
    return mission_graph_cell_is_role(cell) ? 0 : 1;
}

static u8 degree(u8 cell) {
    u8 dir, n = 0;
    for (dir = DIR_N; dir <= DIR_W; ++dir)
        if (run_state_dungeon_cell_neighbor(cell, dir) != 0xFF) n++;
    return n;
}

u8 secret_merchant_host_cell(void) BANKED {
    u8 size, entry, cache, start, i, pass;
    if (run_state.world_mode || stage() >= 9) return 0xFF;
    if (host_cache_stage == stage() && host_cache_seed == run_state.run_seed)
        return secret_host_cell_cache;
    mission_graph_ensure();
    size = run_state_dungeon_size();
    entry = run_state_dungeon_entry_cell();
    cache = run_state_dungeon_cache_cell();
    seed_hash(stage(), 0x5645494CUL);   // 'VEIL'
    start = (u8)(next_hash() % size);
    secret_host_cell_cache = 0xFF;
    // Prefer a dead end (Farfold instinct), then any legal off-role cell.
    for (pass = 0; pass < 2 && secret_host_cell_cache == 0xFF; ++pass) {
        for (i = 0; i < size; ++i) {
            u8 cell = (u8)(start + i);
            if (cell >= size) cell = (u8)(cell - size);
            if (!host_legal(cell, size, entry, cache)) continue;
            if (pass == 0 && degree(cell) != 1) continue;
            secret_host_cell_cache = cell;
            break;
        }
    }
    host_cache_stage = stage();
    host_cache_seed = run_state.run_seed;
    return secret_host_cell_cache;
}

u8 secret_merchant_host_kind(void) BANKED {
    return veil_kind[stage() < 9 ? stage() : 0];
}

static void wall_spot(void) {
    static const u8 north[6] = { 3, 4, 5, 12, 13, 14 };
    static const u8 west[6] = { 3, 4, 5, 11, 12, 13 };
    u8 h;
    seed_hash(stage(), 0x4D4F5554UL);   // 'MOUT'
    h = next_hash();
    wall_side = h & 1;
    wall_p = wall_side ? west[(u8)(h >> 1) % 6] : north[(u8)(h >> 1) % 6];
}

static u8 solid_interior(u8 t) {
    return !room_tile_walkable(t) && t != BGT_WALL && t != BGT_DOOR
        && t != BGT_BLOCK && t != BGT_BLOCK_TR && t != BGT_BLOCK_BL
        && t != BGT_BLOCK_BR;
}

static void clear_cell(u8 x, u8 y) {
    if (x == 0 || y == 0 || x >= ROOM_W - 1 || y >= ROOM_H - 1) return;
    if (solid_interior(room_tilemap[y][x])) room_tilemap[y][x] = BGT_FLOOR;
}

// A walkable 2-wide lane from the tell to the room's central crossing.
static void carve_lane(u8 x0, u8 y0, u8 x1, u8 y1) {
    u8 x, y;
    for (y = y0; y <= y1; ++y)
        for (x = x0; x <= x1; ++x) clear_cell(x, y);
}

static void mouth_coords(u8 kind, u8 *x, u8 *y) {
    if (kind == SECRET_KIND_STONE) { *x = 6; *y = 0; return; }
    if (wall_side) { *x = 0; *y = wall_p; }
    else { *x = wall_p; *y = 0; }
}

static void strip_ordinary(void) {
    u8 i;
    // The host never has two overlay mouths: amber cracks on its border
    // become plain wall (Echo Chime and Cave Light get one target).
    for (i = 0; i < ROOM_W; ++i) {
        if (room_tilemap[0][i] == BGT_WALL_CRACK) room_tilemap[0][i] = BGT_WALL;
        if (room_tilemap[ROOM_H - 1][i] == BGT_WALL_CRACK)
            room_tilemap[ROOM_H - 1][i] = BGT_WALL;
    }
    for (i = 0; i < ROOM_H; ++i) {
        if (room_tilemap[i][0] == BGT_WALL_CRACK) room_tilemap[i][0] = BGT_WALL;
        if (room_tilemap[i][ROOM_W - 1] == BGT_WALL_CRACK)
            room_tilemap[i][ROOM_W - 1] = BGT_WALL;
    }
}

u8 secret_merchant_prepare_host(void) BANKED {
    u8 kind, mx, my, mx2, my2, i;
    secret_merchant_host_here = 0;
    if (run_state_dungeon_local() != secret_merchant_host_cell()) return 0;
    secret_merchant_host_here = 1;
    kind = secret_merchant_host_kind();
    wall_spot();
    strip_ordinary();
    room_hidden_secret_bit = 0;   // Veil discoveries live in secret_shop
    // Lanes keep the tell (and later the mouth) reachable from the centre.
    if (kind == SECRET_KIND_STONE) {
        carve_lane(4, 1, 9, 9);
        carve_lane(9, 8, 10, 9);
    } else if (wall_side) {
        carve_lane(1, wall_p, 10, (u8)(wall_p + 1));
        if (wall_p < 8) carve_lane(9, wall_p, 10, 9);
        else carve_lane(9, 8, 10, (u8)(wall_p + 1));
    } else {
        carve_lane(wall_p, 1, (u8)(wall_p + 1), 9);
        if (wall_p < 9) carve_lane(wall_p, 8, 10, 9);
        else carve_lane(9, 8, (u8)(wall_p + 1), 9);
    }
    mouth_coords(kind, &mx, &my);
    mx2 = my ? mx : (u8)(mx + 1);
    my2 = my ? (u8)(my + 1) : my;
    if (run_state.secret_shop & SECRET_SHOP_MOUTH) {
        // Opened mouths stay enterable after a leave or a suspend.
        room_tilemap[my][mx] = room_tilemap[my2][mx2] = BGT_DOOR;
        secret_door_x = mx; secret_door_y = my;
        secret_door_x2 = mx2; secret_door_y2 = my2;
        room_hidden_secret_kind = HIDDEN_SECRET_NONE;
        return 1;
    }
    if (kind == SECRET_KIND_STONE) {
        // The cairn sits where a shove sends it north; a scrape trail runs
        // from it to the wall that will open.
        for (i = 0; i < MAX_ENTITIES; ++i) {
            if ((entities[i].flags & EF_ACTIVE)
                && entities[i].type == ENT_ENEMY) {
                u8 ex = (u8)((FIX8_TO_INT(entities[i].x) + 8) >> 3);
                u8 ey = (u8)((FIX8_TO_INT(entities[i].y) + 8) >> 3);
                if (ex >= 4 && ex <= 9 && ey >= 4 && ey <= 9) entity_kill(i);
            }
        }
        for (i = 4; i <= 9; ++i) {
            room_tilemap[i][4] = room_tilemap[i][5] = BGT_FLOOR;
            room_tilemap[i][8] = room_tilemap[i][9] = BGT_FLOOR;
            room_tilemap[i][6] = room_tilemap[i][7] = BGT_FLOOR;
        }
        room_hidden_secret_kind = HIDDEN_SECRET_PUSH;
        room_hidden_secret_x = 6; room_hidden_secret_y = 6;
        room_hidden_secret_x2 = 7; room_hidden_secret_y2 = 7;
        room_tilemap[6][6] = BGT_BLOCK;
        room_tilemap[6][7] = BGT_BLOCK_TR;
        room_tilemap[7][6] = BGT_BLOCK_BL;
        room_tilemap[7][7] = BGT_BLOCK_BR;
        room_tilemap[2][6] = room_tilemap[4][7] = BGT_FLOOR2;
        room_tilemap[1][7] = room_tilemap[3][6] = BGT_FLOOR3;
        return 1;
    }
    room_hidden_secret_kind = (kind == SECRET_KIND_BLAST)
        ? HIDDEN_SECRET_SHOT : HIDDEN_SECRET_WALK;
    room_hidden_secret_x = mx; room_hidden_secret_y = my;
    room_hidden_secret_x2 = mx2; room_hidden_secret_y2 = my2;
    room_tilemap[my][mx] = room_tilemap[my2][mx2] = BGT_WALL;
    // The quiet difference sits on the floor in front of an ordinary wall:
    // BLAST = fresh cracks and a chip of rubble at its foot,
    // THICKET = a scattered trail leading straight into it.
    if (wall_side) {
        if (kind == SECRET_KIND_BLAST) {
            room_tilemap[my][1] = room_tilemap[my2][1] = BGT_FLOOR2;
            room_tilemap[my2][2] = BGT_RUBBLE;
        } else {
            room_tilemap[my][2] = room_tilemap[my2][4] = BGT_FLOOR3;
            room_tilemap[my][6] = BGT_FLOOR3;
        }
    } else {
        if (kind == SECRET_KIND_BLAST) {
            room_tilemap[1][mx] = room_tilemap[1][mx2] = BGT_FLOOR2;
            room_tilemap[2][mx2] = BGT_RUBBLE;
        } else {
            room_tilemap[2][mx] = room_tilemap[4][mx2] = BGT_FLOOR3;
            room_tilemap[6][mx] = BGT_FLOOR3;
        }
    }
    return 1;
}

// Moved from room.c (bank 1 floor). The Veil host's mouth persists.
void room_open_secret(u8 tx, u8 ty) BANKED {
    u8 tx2 = tx, ty2 = ty, t = BGT_DOOR, a = BGPAL_DOOR, i;
    if (tx >= ROOM_W || ty >= ROOM_H) return;
    // Open a second tile along the wall so the doorway is 16px wide
    // (cracks spawn at 2..N-3, so the +1 neighbor is never a corner).
    if (ty == 0 || ty == ROOM_H - 1) tx2 = (u8)(tx + 1);
    else                             ty2 = (u8)(ty + 1);
    for (i = 0; i < 2; ++i) {
        u8 x = i ? tx2 : tx, y = i ? ty2 : ty;
        room_tilemap[y][x] = t;
        wait_vbl_done();
        VBK_REG = 0;
        set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &t);
        VBK_REG = 1;
        set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &a);
        VBK_REG = 0;
    }
    secret_door_x = tx;   secret_door_y = ty;
    secret_door_x2 = tx2; secret_door_y2 = ty2;
    if (secret_merchant_host_here && !run_state.world_mode)
        run_state.secret_shop |= SECRET_SHOP_MOUTH;
    sfx_play(SFX_DOOR);
}

// ---------------------------------------------------------------- shelves

static void paint_price(u8 tx, u8 ty, u8 price) {
    room_tilemap[ty][tx]     = HUD_COIN;
    room_tilemap[ty][tx + 1] = (price >= 10) ? (u8)(HUD_DIGIT_0 + price / 10) : HUD_BLANK;
    room_tilemap[ty][tx + 2] = (u8)(HUD_DIGIT_0 + price % 10);
}

static void shelf(u8 px, u8 py, u8 code, u8 price) {
    u8 idx = pickup_spawn(PICKUP_SHOP, FIX8(px), FIX8(py));
    u8 sprite, pal;
    if (idx == 0xFF) return;
    entities[idx].ai_data[0] = PICKUP_SHOP;
    entities[idx].ai_data[1] = WARE_SECRET;
    entities[idx].ai_data[2] = price;
    entities[idx].ai_data[3] = code;
    if (code <= SM_TONIC_RIFT) { sprite = SPR_ITEM_FLASK; pal = 0x06; }
    else if (code <= SM_BOTTLE_SURGE) {
        sprite = (code == SM_BOTTLE_SURGE) ? SPR_ITEM_SURGE : SPR_ITEM_ASCEND;
        pal = 0x05;
    } else if (code < SM_BOMB_BAG) { sprite = SPR_ITEM_WARD_CHARM; pal = 0x06; }
    else if (code == SM_BOMB_BAG) { sprite = SPR_ITEM_BOMB_BAG; pal = 0x04; }
    else if (code == SM_RIFT_BOMB) { sprite = SPR_ITEM_RIFT_BOMB; pal = 0x04; }
    else if (code == SM_ECHO_CHIME) { sprite = SPR_ITEM_ECHO_CHIME; pal = 0x06; }
    else { sprite = SPR_ITEM_RIFT_SIGIL; pal = 0x06; }
    entities[idx].sprite_tile = sprite;
    entities[idx].palette = pal;
    {
        u8 tag = pickup_spawn_shop_tag(FIX8(px), FIX8((i16)py - 12));
        if (tag != 0xFF) entities[tag].ai_data[1] = idx;
    }
    paint_price((u8)((px >> 3) - 1), (u8)((py >> 3) + 2), price);
}

static void keeper(u8 px, u8 py, u8 pal) {
    u8 idx = pickup_spawn_merchant(FIX8(px), FIX8(py));
    // Veil (violet dusk) and cave (travel cloak) keepers are kin to the
    // public merchant, not twins.
    if (idx != 0xFF) entities[idx].palette = pal;
}

u8 secret_merchant_build_stall(void) BANKED {
    u8 s = stage(), x, y;
    if (run_state.world_mode || s >= 9) return 0;
    if (run_state_dungeon_local() != secret_merchant_host_cell()) return 0;
    run_state.secret_shop |= SECRET_SHOP_FOUND | SECRET_SHOP_MOUTH;
    // Quiet cave vault: bare floor, two crystal lamps, the return mouth
    // procgen already authored on the border.
    for (y = 1; y < ROOM_H - 1; ++y)
        for (x = 1; x < ROOM_W - 1; ++x)
            room_tilemap[y][x] = ((u8)(x * 5 + y * 3) & 7) == 0
                ? BGT_FLOOR2 : BGT_FLOOR;
    room_tilemap[3][3] = room_tilemap[3][16] = BGT_CRYSTAL;
    room_tilemap[13][3] = room_tilemap[13][16] = BGT_CRYSTAL;
    keeper(80, 40, 0x06);
    shelf(56, 64, (u8)(SM_TONIC_VEIL + s), tonic_price[s]);
    if (!(run_state.secret_shop & SECRET_SHOP_B_BOUGHT))
        shelf(80, 64, veil_bottle[s], 24);
    if (!(run_state.secret_shop & SECRET_SHOP_C_BOUGHT) && !VEIL_HAS(s))
        shelf(104, 64, (u8)(SM_CHARM + s), charm_price[s]);
    sfx_play(SFX_CLEAR);
    player.iframes = 60;
    return 1;
}

static u8 inventory_count(u8 id) {
    u8 i, n = 0;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == id) n++;
    return n;
}

static u8 inventory_add(u8 id) {
    u8 i;
    for (i = 0; i < INVENTORY_SLOTS; ++i)
        if (player.inventory[i] == 0xFF) {
            player.inventory[i] = id;
            hud_show_item(id);
            return 1;
        }
    return 0;
}

static u8 in_cave(void) {
    return (run_state.world_mode
        && run_state.world_screen >= SECRET_CAVE_SCREEN_BASE
        && run_state.world_screen < SECRET_CAVE_SCREEN_BASE + SECRET_CAVE_COUNT)
        ? 1 : 0;
}

static u8 tonic_kind(u8 code) {
    // 0 heart+1MP, 1 heart+cure Poison, 2 heart+cure Burn, 3 cure+heart,
    // 4 heart+2MP, 5 full MP, 6 heart+cure Bleed.
    static const u8 kind[10] = { 0, 1, 2, 0, 3, 4, 5, 6, 4, 0 };
    return kind[code];
}

static u8 tonic_cures(u8 k) {
    u8 s = player_status_kind;
    if (k == 1) return s == QSTATUS_POISON;
    if (k == 2) return s == QSTATUS_BURN;
    if (k == 3) return STATUS_PLAYER_DOT();
    if (k == 6) return s == QSTATUS_BLEED;
    return 0;
}

static u8 tonic_mp(u8 k) {
    return k == 0 ? 1 : k == 4 ? 2 : k == 5 ? 20 : 0;
}

// 0 = sellable, else a refusal (1 HP full, 2 bottle armed, 3 owned,
// 4 no room, 5 healing blocked).
static u8 refuse(u8 code) {
    if (code <= SM_TONIC_RIFT) {
        u8 k = tonic_kind(code);
        u8 heal = (k != 5 && player.hp < player.hp_max
            && !STATUS_PLAYER_HEALING_BLOCKED());
        if (heal || tonic_cures(k)
            || (tonic_mp(k) && player.mp < player.mp_max)) return 0;
        return (k != 5 && player.hp < player.hp_max) ? 5 : 1;
    }
    if (code <= SM_BOTTLE_SURGE)
        return ((run_state.secret_shop & SECRET_SHOP_ARMED)
            || (run_state.rift_caves & RIFT_CAVE_ARMED)) ? 2 : 0;
    if (code < SM_BOMB_BAG)
        return VEIL_HAS(code - SM_CHARM) ? 3 : 0;
    if (code == SM_BOMB_BAG && inventory_count(ITEM_ID_BOMBS)) return 3;
    if (code == SM_REARM_WELL) return RUN_RIFTWELL_USED() ? 0 : 3;
    return inventory_count(0xFF) ? 0 : 4;
}

static void drink(u8 code) {
    u8 k = tonic_kind(code), mp = tonic_mp(k);
    if (k != 5 && !STATUS_PLAYER_HEALING_BLOCKED()) {
        player.hp = (u8)(player.hp + 2);
        if (player.hp > player.hp_max) player.hp = player.hp_max;
        hud_redraw_hp();
        hud_show_heal(2);
    }
    if (tonic_cures(k)) { status_player_cure(); hud_show_cured(); }
    if (mp) {
        player.mp = (u8)(player.mp + mp);
        if (player.mp > player.mp_max) player.mp = player.mp_max;
        hud_redraw_mp();
        if (k != 5) hud_show_mana(mp);
    }
}

static void deliver(u8 code) {
    u8 cave = (u8)(run_state.world_screen - SECRET_CAVE_SCREEN_BASE);
    u8 wild = in_cave();
    if (code <= SM_TONIC_RIFT) { drink(code); return; }
    if (code <= SM_BOTTLE_SURGE) {
        // Arms at the counter; uncorks on the next combat-room entry.
        if (wild) {
            run_state.rift_caves |= RIFT_CAVE_B(cave) | RIFT_CAVE_ARMED;
            run_state.rift_caves &= ~((u32)3u << RIFT_CAVE_FROM_SHIFT);
            run_state.rift_caves |= (u32)cave << RIFT_CAVE_FROM_SHIFT;
        } else run_state.secret_shop |= SECRET_SHOP_B_BOUGHT | SECRET_SHOP_ARMED;
        hud_show_word(NW_ARMED);
        return;
    }
    if (wild) run_state.rift_caves |= RIFT_CAVE_C(cave);
    else run_state.secret_shop |= SECRET_SHOP_C_BOUGHT;
    if (code < SM_BOMB_BAG) {
        u8 c = (u8)(code - SM_CHARM);
        run_state.veil_charms |= VEIL_CHARM_BIT(c);
        hud_show_word(charm_word[c]);
        secret_merchant_armed = 1;
        glint_pending = 1;
        return;
    }
    if (code == SM_BOMB_BAG) {
        inventory_add(ITEM_ID_BOMBS);
        projectile_sync_player_relics();
        hud_show_secondary(1);
    } else if (code == SM_RIFT_BOMB) inventory_add(ITEM_ID_RIFT_BOMB);
    else if (code == SM_ECHO_CHIME) inventory_add(ITEM_ID_ECHO_CHIME);
    else {
        run_state.riftwild_flags &= (u8)~RIFT_REGION_WELL_USED_BIT;
        run_state.world_return_screen &= (u8)~RIFTWELL_USED_FLAG;
        hud_show_word(NW_REARM);
    }
}

static u8 cue(u8 i) {
    if (entities[i].ai_data[4]) return 0;
    entities[i].ai_data[4] = 90;
    sfx_play(SFX_REFUSE);
    return 1;
}

void secret_merchant_touch(u8 i) BANKED {
    u8 code = entities[i].ai_data[3];
    u8 price = entities[i].ai_data[2];
    u8 why;
    if (code >= SM_CODE_COUNT) return;
    why = refuse(code);
    if (why) {
        if (cue(i)) {
            if (why == 1) hud_show_hp_full();
            else if (why == 5) hud_show_healing_blocked();
            else if (why == 2) hud_show_word(NW_ARMED);
            else if (why == 3) hud_show_word(NW_OWNED);
            else hud_show_word(NW_NOROOM);
        }
        return;
    }
    if (player.coins < price) {
        if (cue(i)) hud_show_need(price);
        return;
    }
    player.coins = (u16)(player.coins - price);
    hud_redraw_coins();
    sfx_play_reward(SFX_REWARD_PURCHASE);
    deliver(code);
    // Tonics restock like the public Antidote: wait for a fresh contact.
    if (code <= SM_TONIC_RIFT) entities[i].ai_data[4] = 0xFF;
    else {
        // Sold out: lift the painted price with the ware.
        u8 tx = (u8)((u8)(FIX8_TO_INT(entities[i].x) >> 3) - 1);
        u8 ty = (u8)((u8)(FIX8_TO_INT(entities[i].y) >> 3) + 2);
        u8 k;
        entity_kill(i);
        for (k = 0; k < 3; ++k)
            if ((u8)(tx + k) < ROOM_W - 1 && ty < ROOM_H - 1)
                live_set((u8)(tx + k), ty, BGT_FLOOR, BGPAL_FLOOR);
    }
}

void secret_merchant_write_effect(u8 code) BANKED {
    static const char *const text[SM_CODE_COUNT] = {
        "HEART + 1 MP", "HEART + NO PSN", "HEART+NO BURN", "HEART + 1 MP",
        "CURE + HEART", "HEART + 2 MP", "FULL MAGIC", "HEART+NO BLEED",
        "HEART + 2 MP", "HEART + 1 MP",
        "ARM: AEGIS", "ARM: MEND", "ARM: LIMITLESS", "ARM: 20S SURGE",
        "CAVE LIGHT", "HONEYCOMB", "CINDER VEIL", "RIME SKATES",
        "FILTER MASK", "GLOAM LAMP", "SUN SEAL", "CRIMSON PACT",
        "LAST LIGHT", "WAYFARER BELL", "CACHE LURE", "HOLLOW WICK",
        "B: BOMB / 1 MP", "TOOL: BOMB", "TOOL: CHIME", "REARM RIFTWELL",
    };
    if (code < SM_CODE_COUNT) text_write(text[code]);
}

// ------------------------------------------------------------ room hooks

static void uncork(u8 code) {
    if (code == SM_BOTTLE_AEGIS) powerup_collect(POWERUP_AEGIS);
    else if (code == SM_BOTTLE_MEND) powerup_collect(POWERUP_MEND);
    else if (code == SM_BOTTLE_LIMIT) powerup_collect(POWERUP_LIMITLESS);
    else {
        room_start_weapon_surge();
        room_weapon_surge_ticks = 160;   // Grand Surge: 20 s, not 15
    }
}

static u8 cave_bottle(u8 cave) {
    u8 kind = secret_cave_kind(cave);
    if (kind != SECRET_KIND_STONE) return SM_BOTTLE_SURGE;
    return (run_state.run_seed & 0x10) ? SM_BOTTLE_MEND : SM_BOTTLE_AEGIS;
}

void secret_merchant_room_ready(void) BANKED {
    u8 armed = 0;
    secret_merchant_host_here = 0;
    cinder_used = 0;
    touch_ticks = 0;
    secret_floor_warn = 60;
    if (VEIL_HAS(VEIL_GLOAM_LAMP)) secret_floor_warn += 20;
    if (VEIL_HAS(VEIL_RIME_SKATES)) secret_floor_warn += 20;
    // A dungeon bottle never follows the champion out into Riftwild.
    if (run_state.world_mode) run_state.secret_shop &= (u8)~SECRET_SHOP_ARMED;
    if (entity_enemy_count && !run_state.secret_pending && !in_cave()) {
        if (run_state.secret_shop & SECRET_SHOP_ARMED) {
            run_state.secret_shop &= (u8)~SECRET_SHOP_ARMED;
            uncork(veil_bottle[stage() < 9 ? stage() : 0]);
        } else if (run_state.rift_caves & RIFT_CAVE_ARMED) {
            u8 from = (u8)(run_state.rift_caves >> RIFT_CAVE_FROM_SHIFT) & 3;
            run_state.rift_caves &= ~(RIFT_CAVE_ARMED
                | ((u32)3u << RIFT_CAVE_FROM_SHIFT));
            uncork(cave_bottle(from < 3 ? from : 0));
        }
    }
    if (run_state.veil_charms & (VEIL_CHARM_BIT(VEIL_CAVE_LIGHT)
            | VEIL_CHARM_BIT(VEIL_HONEYCOMB) | VEIL_CHARM_BIT(VEIL_SUN_SEAL)
            | VEIL_CHARM_BIT(VEIL_CRIMSON_PACT)
            | VEIL_CHARM_BIT(VEIL_WAYFARER_BELL)
            | VEIL_CHARM_BIT(VEIL_CACHE_LURE)
            | VEIL_CHARM_BIT(VEIL_HOLLOW_WICK))
        || (run_state.veil_charms & VEIL_CRIMSON_APPLIED)) armed = 1;
    if (run_state.world_mode && run_state.world_screen < 36
        && secret_cave_field_index(run_state.world_screen) != 0xFF) armed = 1;
    secret_merchant_armed = armed;
    glint_pending = armed;
}

static void glint(u8 tx, u8 ty) {
    fx_spawn(SPR_FX_IMPACT, 0x06, (i16)((u16)tx << 3) - 4,
        (i16)((u16)ty << 3) - 4, 40);
}

static void do_glints(void) {
    u8 i;
    if (!run_state.world_mode) {
        if (VEIL_HAS(VEIL_CAVE_LIGHT)) {
            // Cracked walls and Veil/hidden tells glint once per room.
            u8 n = 0;
            if (room_hidden_secret_kind != HIDDEN_SECRET_NONE) {
                glint(room_hidden_secret_x, room_hidden_secret_y);
                n++;
            }
            for (i = 1; i < ROOM_W - 1 && n < 3; ++i) {
                if (room_tilemap[0][i] == BGT_WALL_CRACK) { glint(i, 0); n++; }
                if (room_tilemap[ROOM_H - 1][i] == BGT_WALL_CRACK) {
                    glint(i, ROOM_H - 1); n++;
                }
            }
            for (i = 1; i < ROOM_H - 1 && n < 3; ++i) {
                if (room_tilemap[i][0] == BGT_WALL_CRACK) { glint(0, i); n++; }
                if (room_tilemap[i][ROOM_W - 1] == BGT_WALL_CRACK) {
                    glint(ROOM_W - 1, i); n++;
                }
            }
            if (n) sfx_play(SFX_TICK);
        }
        if (VEIL_HAS(VEIL_SUN_SEAL) && room_puzzle_kind == PUZZLE_SUN_LATTICE
            && room_puzzle_locked) {
            // The next correct vane glints once when the puzzle goes live.
            for (i = 0; i < sl_n; ++i)
                if (sl_kind[i] == SLK_VANE && sl_ang[i] != sl_solved_ang[i]) {
                    glint(sl_x[i], sl_y[i]);
                    break;
                }
        }
        return;
    }
    if (run_state.world_screen >= 36) return;
    if (VEIL_HAS(VEIL_CACHE_LURE) && riftwild_cache_x != 0xFF)
        glint(riftwild_cache_x, riftwild_cache_y);
    if (VEIL_HAS(VEIL_HOLLOW_WICK) && RUN_RIFTWILD_IS_HOLLOW()) {
        if (riftwild_cache_x != 0xFF) glint(riftwild_cache_x, riftwild_cache_y);
        if (riftwild_den_in_field())
            glint(RIFT_DEN_TELL_X, RIFT_DEN_TELL_Y);
    }
}

static void honeycomb(void) {
    u8 i;
    for (i = 0; i < MAX_ENTITIES; ++i) {
        entity_t *e = &entities[i];
        i16 dx, dy;
        u8 k;
        if (!(e->flags & EF_ACTIVE) || e->type != ENT_PICKUP) continue;
        k = e->ai_data[0];
        if (k != PICKUP_HEART_HALF && k != PICKUP_COIN_1 && k != PICKUP_COIN_5)
            continue;
        // Entity coordinates are FIX8; the hero's are whole pixels.
        dx = (i16)player.x - (i16)FIX8_TO_INT(e->x);
        dy = (i16)player.y - (i16)FIX8_TO_INT(e->y);
        if (dx > 24 || dx < -24 || dy > 24 || dy < -24) continue;
        if (dx > 1) e->x += FIX8(1); else if (dx < -1) e->x -= FIX8(1);
        if (dy > 1) e->y += FIX8(1); else if (dy < -1) e->y -= FIX8(1);
    }
}

static void crimson(void) {
    u8 want = VEIL_HAS(VEIL_CRIMSON_PACT)
        && (u8)(player.hp << 1) <= player.hp_max && player.hp;
    if (want && !(run_state.veil_charms & VEIL_CRIMSON_APPLIED)) {
        if (player.atk >= 15) return;
        player.atk++;
        run_state.veil_charms |= VEIL_CRIMSON_APPLIED;
        fx_spawn(SPR_FX_IMPACT, 0x04, (i16)player.x, (i16)player.y - 4, 16);
    } else if (!want && (run_state.veil_charms & VEIL_CRIMSON_APPLIED)) {
        if (player.atk) player.atk--;
        run_state.veil_charms &= (u16)~VEIL_CRIMSON_APPLIED;
    }
}

static void cave_field_tick(void);

void secret_merchant_tick(void) BANKED {
    if (glint_pending) { glint_pending = 0; do_glints(); }
    if (VEIL_HAS(VEIL_HONEYCOMB)) honeycomb();
    crimson();
    if (run_state.world_mode && run_state.world_screen < 36) cave_field_tick();
}

u8 secret_merchant_chime(void) BANKED {
    if (!secret_merchant_host_here
        || room_hidden_secret_kind == HIDDEN_SECRET_NONE) return 0;
    // The Chime answers the Veil tell without opening it, and the Compass
    // remembers the cell (dim small coin) until the stall is found.
    if (!(run_state.secret_shop & SECRET_SHOP_FOUND))
        run_state.secret_shop |= SECRET_SHOP_CHIMED;
    glint(room_hidden_secret_x, room_hidden_secret_y);
    glint(room_hidden_secret_x2, room_hidden_secret_y2);
    hud_show_word(NW_SCOUT);
    return 1;
}

u8 secret_merchant_map_cell(void) BANKED {
    u8 cell = secret_merchant_host_cell();
    if (cell == 0xFF) return 0xFF;
    if (run_state.secret_shop & SECRET_SHOP_FOUND) return cell;
    if (run_state.secret_shop & SECRET_SHOP_CHIMED) return (u8)(cell | 0x80);
    return 0xFF;
}

#define VEIL_LAST_LIGHT_SPENT 0x4000u
u8 secret_merchant_last_light(void) BANKED {
    if (!VEIL_HAS(VEIL_LAST_LIGHT)
        || (run_state.veil_charms & VEIL_LAST_LIGHT_SPENT)) return 0;
    run_state.veil_charms |= VEIL_LAST_LIGHT_SPENT;
    player.hp = 1;
    player.iframes = 120;
    hud_redraw_hp();
    hud_show_word(NW_LAST);
    room_shake(2, 12);
    sfx_play(SFX_CLEAR);
    return 1;
}

u8 secret_merchant_block_status(u8 kind) BANKED {
    if (kind == QSTATUS_BURN && VEIL_HAS(VEIL_CINDER_VEIL) && !cinder_used) {
        cinder_used = 1;
        return 1;
    }
    if (kind == QSTATUS_SLOW && VEIL_HAS(VEIL_RIME_SKATES)) return 1;
    return 0;
}

// ------------------------------------------------------- Riftwild caves

static u8 cave_cache_region = 0xFF;
static u32 cave_cache_seed;
u8 secret_cave_fields[SECRET_CAVE_COUNT];   // global: read by the headless tests
u8 secret_cave_kinds[SECRET_CAVE_COUNT];

static u8 region(void) {
    u8 r = run_state.riftwild_region;
    return r < 3 ? r : (u8)(r % 3);
}

static u8 cave_candidate(u8 f) {
    switch (f) {
        // Discovery, Riftwell, Warden groves, cave, gates, class groves,
        // boss landmark, vault, and the Hollow relic fields.
        case 0: case 1: case 3: case 5: case 8: case 16: case 17: case 21:
        case 22: case 23: case 27: case 29: case 30: case 32: case 34:
        case 35:
            return 0;
    }
    return 1;
}

static void caves_ensure(void) {
    static const u8 perm[6][3] = {
        { 0, 1, 2 }, { 0, 2, 1 }, { 1, 0, 2 },
        { 1, 2, 0 }, { 2, 0, 1 }, { 2, 1, 0 },
    };
    u8 r = region(), b, f, n, pick, p;
    u8 list[12];
    if (cave_cache_region == r && cave_cache_seed == run_state.run_seed) return;
    seed_hash(r, 0x43415645UL);   // 'CAVE'
    for (b = 0; b < SECRET_CAVE_COUNT; ++b) {
        u8 den = riftwild_den_field_of(b);
        n = 0;
        for (f = (u8)(b * 12); f < (u8)(b * 12 + 12); ++f)
            if (cave_candidate(f) && f != den) list[n++] = f;
        pick = next_hash();
        secret_cave_fields[b] = n ? list[pick % n] : 0xFF;
    }
    p = (u8)(next_hash() % 6);
    for (b = 0; b < SECRET_CAVE_COUNT; ++b) secret_cave_kinds[b] = perm[p][b];
    cave_cache_region = r;
    cave_cache_seed = run_state.run_seed;
}

u8 secret_cave_field_index(u8 field) BANKED {
    u8 i;
    caves_ensure();
    for (i = 0; i < SECRET_CAVE_COUNT; ++i)
        if (secret_cave_fields[i] == field) return i;
    return 0xFF;
}

u8 secret_cave_kind(u8 cave) BANKED {
    caves_ensure();
    return cave < SECRET_CAVE_COUNT ? secret_cave_kinds[cave] : 0;
}

static u8 cave_open(u8 i) {
    return (run_state.rift_caves & RIFT_CAVE_MOUTH(i)) ? 1 : 0;
}

static void world_set(u8 x, u8 y, u8 tile) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = tile;
        else room_world_extension[y][x - ROOM_W] = tile;
    } else room_world_bottom[y - ROOM_H][x] = tile;
}

static u8 world_get(u8 x, u8 y) {
    if (y < ROOM_H) {
        if (x < ROOM_W) return room_tilemap[y][x];
        return room_world_extension[y][x - ROOM_W];
    }
    return room_world_bottom[y - ROOM_H][x];
}

static void live_set(u8 x, u8 y, u8 tile, u8 attr) {
    world_set(x, y, tile);
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &tile);
    VBK_REG = 1;
    set_bkg_tiles(ROOM_BG_MAP_X(x), ROOM_BG_MAP_Y(y), 1, 1, &attr);
    VBK_REG = 0;
}

static u8 field_floor(void) {
    u8 zone = (u8)(run_state.world_screen / 6);
    if (zone == 0) return BGT_WILD_SNOW;
    if (zone == 4) return BGT_WILD_MUD;
    if (zone == 5) return BGT_WILD_SAND;
    return BGT_GRASS;
}

static u8 keep_tile(u8 t) {
    return t == BGT_PATH || t == BGT_PORTAL || t == BGT_SWITCH
        || (t >= BGT_GATE_BOULDER && t <= BGT_GATE_VENT);
}

#define TX SECRET_CAVE_TELL_X
#define TY SECRET_CAVE_TELL_Y

// Field post-pass (inside riftwild_den_stamp_field, before the metatile
// scan): a cleared 7x6 footprint east of the trail cross, an always-open
// approach, and one concealed mouth made of whole standalone tiles.
u8 secret_cave_stamp_field(void) BANKED {
    u8 i, x, y, kind, floor;
    if (!run_state.world_mode || run_state.world_screen >= 36) return 0;
    i = secret_cave_field_index(run_state.world_screen);
    if (i == 0xFF) return 0;
    kind = secret_cave_kinds[i];
    floor = field_floor();
    for (y = 11; y <= 16; ++y)
        for (x = 13; x <= 19; ++x)
            if (!keep_tile((u8)(world_get(x, y) & 0x7F))) world_set(x, y, floor);
    for (y = 10; y <= 14; ++y)
        for (x = 9; x <= 10; ++x) {
            u8 t = (u8)(world_get(x, y) & 0x7F);
            if (!room_tile_walkable(t) && !keep_tile(t)) world_set(x, y, floor);
        }
    for (x = 9; x <= 13; ++x)
        for (y = 13; y <= 14; ++y) {
            u8 t = (u8)(world_get(x, y) & 0x7F);
            if (!room_tile_walkable(t) && !keep_tile(t)) world_set(x, y, floor);
        }
    if (kind == SECRET_KIND_STONE) {
        // A lone field rock one tile off a worn socket.
        if (cave_open(i)) {
            world_set(TX, TY, BGT_PORTAL);
            world_set(TX + 1, TY, BGT_WILD_STONE);
        } else {
            world_set(TX, TY, BGT_WILD_STONE);
            world_set(TX + 1, TY, BGT_PATH);
        }
    } else if (kind == SECRET_KIND_BLAST) {
        // A self-contained bluff with one plugged face at the end of a
        // short accent line. Single crag cells draw as standalone tiles.
        world_set(TX - 1, TY - 1, BGT_WILD_MOUNTAIN);
        world_set(TX, TY - 1, BGT_WILD_MOUNTAIN);
        world_set(TX + 1, TY - 1, BGT_WILD_MOUNTAIN);
        world_set(TX - 1, TY, BGT_WILD_MOUNTAIN);
        world_set(TX + 1, TY, BGT_WILD_MOUNTAIN);
        world_set(TX, TY, cave_open(i) ? BGT_PORTAL : BGT_WILD_STONE);
        world_set(TX, TY + 1, BGT_PATH);
        world_set(TX, TY + 2, BGT_PATH);
        world_set(TX, TY + 3, BGT_PATH);
    } else {
        // A tree curtain; the one odd leaf tile is the way in.
        for (x = TX - 2; x <= TX + 2; ++x) world_set(x, TY - 1, BGT_TREE);
        world_set(TX - 2, TY, BGT_TREE);
        world_set(TX + 2, TY, BGT_TREE);
        world_set(TX, TY, cave_open(i) ? BGT_PORTAL : BGT_WILD_REEDS);
        world_set(TX, TY + 2, BGT_WILD_FLOWER);
        world_set(TX - 1, TY + 3, BGT_WILD_FLOWER);
    }
    return 1;
}

static u8 field_cave_closed(void) {
    u8 i;
    if (!run_state.world_mode || run_state.world_screen >= 36) return 0xFF;
    i = secret_cave_field_index(run_state.world_screen);
    if (i == 0xFF || cave_open(i)) return 0xFF;
    return i;
}

static void open_cave(u8 i) {
    run_state.rift_caves |= RIFT_CAVE_MOUTH(i);
    if (secret_cave_kinds[i] == SECRET_KIND_STONE)
        live_set(TX + 1, TY, BGT_WILD_STONE, BGPAL_WALL);
    live_set(TX, TY, BGT_PORTAL, BGPAL_FLOOR);
    room_shake(1, 10);
    sfx_play(SFX_PUZZLE);
}

u8 secret_cave_strike(u8 tx, u8 ty) BANKED {
    u8 i;
    if (tx != TX || ty != TY) return 0;
    i = field_cave_closed();
    if (i == 0xFF || secret_cave_kinds[i] != SECRET_KIND_BLAST) return 0;
    open_cave(i);
    return 1;
}

void secret_cave_burst(u8 tx, u8 ty) BANKED {
    if (tx + 3 >= TX && tx <= TX + 3 && ty + 3 >= TY && ty <= TY + 3)
        secret_cave_strike(TX, TY);
}

u8 secret_cave_portal(u8 tx, u8 ty) BANKED {
    u8 i;
    if (!run_state.world_mode || run_state.world_screen >= 36) return 0;
    if (tx != TX || ty != TY) return 0;
    i = secret_cave_field_index(run_state.world_screen);
    if (i == 0xFF || !cave_open(i)) return 0;
    run_state.rift_caves |= RIFT_CAVE_FOUND(i);
    run_state.world_return_screen = (u8)(run_state.world_screen
        | (run_state.world_return_screen & RIFTWELL_USED_FLAG));
    run_state.world_screen = (u8)(SECRET_CAVE_SCREEN_BASE + i);
    return 1;
}

static void cave_field_tick(void) {
    u8 i = field_cave_closed();
    u8 fx, fy, kind, near;
    if (i == 0xFF) return;
    kind = secret_cave_kinds[i];
    fx = (u8)((player.x + 8) >> 3);
    fy = (u8)((player.y + 12) >> 3);
    // The hero must press *into* the tell from its open face: STONE from
    // the west toward its socket (never from the socket, which the rock
    // lands on), BLAST and THICKET from the approach below.
    if (kind == SECRET_KIND_STONE)
        near = (fx == TX - 1 && fy == TY && (input_keys & J_RIGHT));
    else
        near = (fx == TX && (fy == TY + 1 || fy == TY)
            && (input_keys & J_UP));
    if (VEIL_HAS(VEIL_WAYFARER_BELL)
        && fx + 3 >= TX && fx <= TX + 3 && fy + 3 >= TY && fy <= TY + 3
        && !(++bell_clock & 31)) sfx_play(SFX_TICK);
    if (!near) {
        touch_ticks = 0;
        return;
    }
    // STONE: a shove from the west slides the rock into its socket. BLAST: only the
    // Titan Glove / a Sauran's grip tears the plug out by hand. THICKET:
    // walking into the odd leaf parts the curtain.
    if (kind == SECRET_KIND_BLAST && !(player.class_id == 1
            || (player.waygear_owned & WAYGEAR_BIT(WAYGEAR_GLOVE)))) return;
    if (++touch_ticks >= (kind == SECRET_KIND_THICKET ? 8 : 12)) {
        touch_ticks = 0;
        open_cave(i);
    }
}

void secret_cave_build_room(void) BANKED {
    u8 i = (u8)(run_state.world_screen - SECRET_CAVE_SCREEN_BASE);
    u8 x, y, kind, r = region();
    if (i >= SECRET_CAVE_COUNT) i = 0;
    kind = secret_cave_kind(i);
    procgen_current_room_is_boss = 0;
    procgen_current_room_is_large = 0;
    dungeon_director_reset();
    room_district_label_ticks = 0;
    run_state.rift_caves |= RIFT_CAVE_FOUND(i) | RIFT_CAVE_MOUTH(i);
    for (y = 0; y < ROOM_H; ++y)
        for (x = 0; x < ROOM_W; ++x)
            room_tilemap[y][x] = (y == 0 || y == ROOM_H - 1
                || x == 0 || x == ROOM_W - 1) ? BGT_WALL
                : ((u8)(x * 5 + y * 3 + i) & 7) == 0 ? BGT_FLOOR2
                : BGT_FLOOR;
    room_tilemap[12][3] = BGT_PORTAL;    // stair back up
    room_tilemap[11][2] = room_tilemap[11][4] = BGT_PILLAR;
    room_tilemap[3][3] = room_tilemap[3][16] = BGT_CRYSTAL;
    entity_init_room();
    companion_spawn_current();
    room_spawn_progression_fixture();
    keeper(80, 24, 0x05);
    riftwild_den_armed = 0;
    shelf(48, 56, SM_TONIC_RIFT, 16);
    if (!(run_state.rift_caves & RIFT_CAVE_B(i)))
        shelf(80, 56, cave_bottle(i), 24);
    if (!(run_state.rift_caves & RIFT_CAVE_C(i))) {
        if (kind == SECRET_KIND_STONE) {
            if (!VEIL_HAS(VEIL_WAYFARER_BELL + r))
                shelf(112, 56, (u8)(SM_CHARM + VEIL_WAYFARER_BELL + r),
                    charm_price[VEIL_WAYFARER_BELL + r]);
        } else if (kind == SECRET_KIND_BLAST) {
            if (inventory_count(ITEM_ID_BOMBS)) shelf(112, 56, SM_RIFT_BOMB, 20);
            else shelf(112, 56, SM_BOMB_BAG, 30);
        } else {
            if (!inventory_count(ITEM_ID_ECHO_CHIME))
                shelf(112, 56, SM_ECHO_CHIME, 20);
            else if (RUN_RIFTWELL_USED()) shelf(112, 56, SM_REARM_WELL, 25);
        }
    }
    secret_merchant_armed = 0;
    // Arrive beside the stair, clear of the shelves (the generic portal
    // arrival at 72,60 would step straight onto the bottle).
    player.x = 40;
    player.y = 88;
    player.iframes = 60;
}

u8 secret_cave_chime(void) BANKED {
    u8 i;
    if (!run_state.world_mode || run_state.world_screen >= 36) return 0;
    i = secret_cave_field_index(run_state.world_screen);
    if (i == 0xFF || (run_state.rift_caves & RIFT_CAVE_FOUND(i))) return 0;
    run_state.rift_caves |= RIFT_CAVE_CHIMED(i);
    glint(TX, TY);
    hud_show_word(NW_SCOUT);
    return 1;
}

u8 secret_cave_map_icon(u8 cell, u8 icon) BANKED {
    u8 i;
    if (icon == BGT_MAP_HERE || cell >= 36) return icon;
    i = secret_cave_field_index(cell);
    if (i == 0xFF) return icon;
    if (run_state.rift_caves & RIFT_CAVE_FOUND(i)) return BGT_MAP_SHOP;
    if (run_state.rift_caves & RIFT_CAVE_CHIMED(i))
        return (u8)(BGT_MAP_SHOP | 0x80u);
    return icon;
}
