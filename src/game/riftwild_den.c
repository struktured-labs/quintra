#pragma bank 18

// Riftwild hidden dens ("dens"): three optional secrets per region, each with
// one subtle field tell, one gate made from verbs that already exist, and a
// short chain of compact rooms ending in a puzzle chest or a keeper.
//
// State costs zero new save bytes:
//   world_screen 36 + den*4 + room   which den room the hero is in
//   world_return_screen low 6 bits   parent field (bit 7 keeps the legacy
//                                    Riftwell flag)
//   (world_seen_xxhi bit 4+d, riftwild_shadow bit 4+d) per den d:
//     (0,0) hidden    (0,1) Echo Chime heard it (dim Compass chest)
//     (1,0) found     (1,1) reward claimed
//   The (0,1) pair is otherwise unreachable, so the Chime costs no bit.
// A new region clears both bytes, so every region brings fresh dens.

#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/dungeon_director.h"
#include "game/entity.h"
#include "game/companion.h"
#include "game/enemy_ai.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/powerup.h"
#include "game/procgen.h"
#include "game/riftwild_den.h"
#include "game/riftwild_phase.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/secret_merchant.h"
#include "game/waygear.h"
#include "input/input.h"
#include "render/hud.h"
#include "render/tiles.h"
#include "content.h"

u8 riftwild_den_armed;

// Per-room transient state. Regenerated on every entry, so leaving a den
// room always resets a half-pushed crate or an unfinished fight.
static u8 den_gate_open;
static u8 den_keeper_up;
static u8 den_touch;
static u8 den_frame;

enum {
    ROLE_ENTRY = 0,
    ROLE_TRIAL,
    ROLE_PUZZLE,
    ROLE_PUZZLE_END,
    ROLE_CHEST_END,
    ROLE_KEEPER_END,
};

// Fixed per-region placement (a seeded layout can replace this table later).
// Every field avoids the discovery, Riftwell, Warden, Waygear grove, gate,
// cave, vault, boss-landmark and Hollow-relic fixtures, and the three dens
// sit in different two-row bands (so in different biomes).
static const u8 den_field[3][RIFT_DEN_COUNT] = {
    { 7, 14, 25 },
    { 4, 20, 28 },
    { 9, 13, 33 },
};
static const u8 den_kind[3][RIFT_DEN_COUNT] = {
    { RIFT_DEN_CAIRN, RIFT_DEN_DROWNED, RIFT_DEN_SCAR },
    { RIFT_DEN_SCAR, RIFT_DEN_CAIRN, RIFT_DEN_DROWNED },
    { RIFT_DEN_DROWNED, RIFT_DEN_SCAR, RIFT_DEN_CAIRN },
};
// One den per region only manifests its stair in the Hollow (the Worldglass
// "night" side). Its Waking tell is a dead ring with no way down.
static const u8 den_hollow_only[3] = { 2, 1, 0 };

static const u8 den_rooms[3] = { 2, 3, 4 };
static const u8 den_role[3][4] = {
    { ROLE_ENTRY, ROLE_PUZZLE_END, 0, 0 },
    { ROLE_ENTRY, ROLE_TRIAL, ROLE_CHEST_END, 0 },
    { ROLE_ENTRY, ROLE_TRIAL, ROLE_PUZZLE, ROLE_KEEPER_END },
};

#define DEN_OPEN_BIT(d)  ((u8)(0x10u << (d)))
#define DEN_CLAIM_BIT(d) ((u8)(0x10u << (d)))

// Puzzle crate and its framed socket (compact tile coordinates).
#define CRATE_X 5
#define CRATE_Y 11
#define SOCKET_X 11
#define SOCKET_Y 4

static u8 region(void) {
    u8 r = run_state.riftwild_region;
    return r < 3 ? r : (u8)(r % 3);
}

static u8 in_den(void) {
    return (run_state.world_mode
        && run_state.world_screen >= RIFT_DEN_SCREEN_BASE) ? 1 : 0;
}

static u8 den_index(void) {
    return (u8)((u8)(run_state.world_screen - RIFT_DEN_SCREEN_BASE) >> 2);
}

static u8 den_room(void) {
    return (u8)((run_state.world_screen - RIFT_DEN_SCREEN_BASE) & 3);
}

static u8 den_found(u8 d) {
    return (run_state.world_seen_xxhi & DEN_OPEN_BIT(d)) ? 1 : 0;
}

static u8 den_claimed(u8 d) {
    return (den_found(d)
        && (run_state.riftwild_shadow & DEN_CLAIM_BIT(d))) ? 1 : 0;
}

static u8 den_chimed(u8 d) {
    return (!den_found(d)
        && (run_state.riftwild_shadow & DEN_CLAIM_BIT(d))) ? 1 : 0;
}

// Found: leave the Chime state (0,1) for (1,0).
static void mark_found(u8 d) {
    if (den_found(d)) return;
    run_state.world_seen_xxhi |= DEN_OPEN_BIT(d);
    run_state.riftwild_shadow &= (u8)~DEN_CLAIM_BIT(d);
}

// A Hollow-only den shows its stair only while the Riftwild is Hollow.
static u8 den_manifest(u8 d) {
    return (d != den_hollow_only[region()] || RUN_RIFTWILD_IS_HOLLOW()) ? 1 : 0;
}

static u8 field_den(u8 field) {
    u8 d;
    u8 r = region();
    for (d = 0; d < RIFT_DEN_COUNT; ++d)
        if (den_field[r][d] == field) return d;
    return 0xFF;
}

u8 riftwild_den_field_of(u8 d) BANKED {
    return d < RIFT_DEN_COUNT ? den_field[region()][d] : 0xFF;
}

u8 riftwild_den_in_field(void) BANKED {
    if (!run_state.world_mode || in_den()) return 0;
    return field_den(run_state.world_screen) != 0xFF ? 1 : 0;
}

u8 riftwild_field_screen(void) BANKED {
    if (in_den()) return (u8)(run_state.world_return_screen & 0x3Fu);
    return run_state.world_screen;
}

static void world_set(u8 x, u8 y, u8 tile) {
    if (y < ROOM_H) {
        if (x < ROOM_W) room_tilemap[y][x] = tile;
        else room_world_extension[y][x - ROOM_W] = tile;
    } else room_world_bottom[y - ROOM_H][x] = tile;
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
    u8 zone = (u8)(riftwild_field_screen() / 6);
    if (zone == 0) return BGT_WILD_SNOW;
    if (zone == 4) return BGT_WILD_MUD;
    if (zone == 5) return BGT_WILD_SAND;
    return BGT_GRASS;
}

// Never overwrite authored route fixtures while carving the approach.
static u8 carve_ok(u8 t) {
    return t != BGT_PATH && t != BGT_PORTAL && t != BGT_PILLAR
        && t != BGT_CRYSTAL && t != BGT_SWITCH
        && (t < BGT_GATE_BOULDER || t > BGT_GATE_VENT);
}

static u8 world_get(u8 x, u8 y) {
    if (y < ROOM_H) {
        if (x < ROOM_W) return room_tilemap[y][x];
        return room_world_extension[y][x - ROOM_W];
    }
    return room_world_bottom[y - ROOM_H][x];
}

// Only solid ground is cleared: walkable landmarks, flowers and paths that
// already cross the approach stay exactly as the field generated them.
static void carve(u8 x, u8 y, u8 floor) {
    u8 t = (u8)(world_get(x, y) & 0x7F);
    if (!room_tile_walkable(t) && carve_ok(t)) world_set(x, y, floor);
}

void riftwild_den_stamp_field(void) BANKED {
    u8 x, y, d, kind, floor, stair;
    riftwild_den_armed &= 0x02;   // keep the secret-merchant tick bit
    if (!run_state.world_mode || in_den()) return;
    // Cave-merchant fields never hold a den (secret_merchant.c).
    if (secret_cave_stamp_field()) return;
    d = field_den(run_state.world_screen);
    if (d == 0xFF) return;
    kind = den_kind[region()][d];
    floor = field_floor();
    // A walkable approach from the trail cross to the den. The route is
    // always open; only the tell itself is gated.
    for (y = 10; y <= 22; ++y) { carve(9, y, floor); carve(10, y, floor); }
    for (x = 9; x <= 20; ++x) { carve(x, 21, floor); carve(x, 22, floor); }
    // Climate features around the den (stone outcrops, lakes, reeds) stay;
    // only the den's own 7x7 footprint is rewritten below.
    if (kind == RIFT_DEN_CAIRN)
        for (y = 19; y <= 25; ++y)
            for (x = 21; x <= 27; ++x) carve(x, y, floor);
    stair = (den_found(d) || kind != RIFT_DEN_CAIRN) && den_manifest(d)
        ? BGT_PORTAL : BGT_WILD_STONE;
    if (kind == RIFT_DEN_CAIRN) {
        // Four field menhirs frame one more standing stone; a short line of
        // the field's flowers points at it. Nothing glows.
        world_set(22, 20, BGT_WILD_STONE);
        world_set(26, 20, BGT_WILD_STONE);
        world_set(22, 24, BGT_WILD_STONE);
        world_set(26, 24, BGT_WILD_STONE);
        world_set(24, 24, BGT_WILD_FLOWER);
        world_set(24, 25, BGT_WILD_FLOWER);
        world_set(24, 26, BGT_WILD_FLOWER);
    } else {
        // DROWNED: a pond with a 3x3 island. SCAR: a ring of sinkholes with
        // a lone pillar on the island. The stair is visible but unreachable
        // without the matching verb (classic Zelda island stair).
        u8 moat = kind == RIFT_DEN_DROWNED ? BGT_WILD_WATER : BGT_WILD_HOLE;
        for (y = 19; y <= 25; ++y)
            for (x = 21; x <= 27; ++x)
                world_set(x, y, (x >= 23 && x <= 25 && y >= 21 && y <= 23)
                    ? floor : moat);
        if (kind == RIFT_DEN_SCAR) world_set(23, 21, BGT_PILLAR);
        else world_set(25, 21, BGT_WILD_REEDS);
        // A dead Hollow-only island keeps a standing stone where the stair
        // will manifest, so the Waking tell still reads as "something here".
    }
    world_set(RIFT_DEN_TELL_X, RIFT_DEN_TELL_Y, stair);
    riftwild_den_armed |= 1;
}

static void open_cairn(u8 d) {
    mark_found(d);
    live_set(RIFT_DEN_TELL_X, RIFT_DEN_TELL_Y, BGT_PORTAL, BGPAL_FLOOR);
    room_shake(1, 10);
    sfx_play(SFX_PUZZLE);
}

static u8 field_cairn_closed(void) {
    u8 d;
    if (!run_state.world_mode || in_den()) return 0xFF;
    d = field_den(run_state.world_screen);
    if (d == 0xFF || den_kind[region()][d] != RIFT_DEN_CAIRN
        || den_found(d)) return 0xFF;
    return d;
}

u8 riftwild_den_strike(u8 tx, u8 ty) BANKED {
    u8 d;
    if (secret_cave_strike(tx, ty)) return 1;
    if (tx != RIFT_DEN_TELL_X || ty != RIFT_DEN_TELL_Y) return 0;
    d = field_cairn_closed();
    if (d == 0xFF) return 0;
    if (!den_manifest(d)) {
        // The Waking side of a Hollow den answers with a hollow knock only.
        sfx_play(SFX_TICK);
        return 1;
    }
    open_cairn(d);
    return 1;
}

u8 riftwild_den_portal(u8 tx, u8 ty) BANKED {
    u8 d;
    if (!run_state.world_mode) return 0;
    if (in_den()) {
        // Every den stair (entry or the one-way end stair) climbs back to
        // the parent field; procgen's centre arrival keeps that safe.
        run_state.world_screen = (u8)(run_state.world_return_screen & 0x3Fu);
        return 1;
    }
    if (tx != RIFT_DEN_TELL_X || ty != RIFT_DEN_TELL_Y) return 0;
    d = field_den(run_state.world_screen);
    if (d == 0xFF || !den_manifest(d)) return 0;
    mark_found(d);
    run_state.world_return_screen = (u8)(run_state.world_screen
        | (run_state.world_return_screen & RIFTWELL_USED_FLAG));
    run_state.world_screen = (u8)(RIFT_DEN_SCREEN_BASE + (d << 2));
    return 1;
}

// Bit 7 of the result asks the Compass for the dim (unopened) palette.
u8 riftwild_den_map_icon(u8 cell, u8 icon) BANKED {
    u8 d = field_den(cell);
    if (d == 0xFF || icon == BGT_MAP_HERE) return icon;
    if (den_chimed(d)) return (u8)(BGT_MAP_CACHE | 0x80u);
    if (!den_found(d) || den_claimed(d)) return icon;
    return BGT_MAP_CACHE;
}

// Echo Chime rung in a field that hides an unfound den: the tell answers
// and the Compass remembers the field (dim chest) until it is opened.
void riftwild_den_chime(void) BANKED {
    u8 d;
    if (!run_state.world_mode || in_den()) return;
    if (secret_cave_chime()) return;
    d = field_den(run_state.world_screen);
    if (d == 0xFF || den_found(d)) return;
    run_state.riftwild_shadow |= DEN_CLAIM_BIT(d);
    hud_show_word(NW_SCOUT);
}

// ---------------------------------------------------------------- rooms

static void paint_shell(u8 role, u8 room, u8 last) {
    u8 x, y;
    for (y = 0; y < ROOM_H; ++y)
        for (x = 0; x < ROOM_W; ++x)
            room_tilemap[y][x] = (y == 0 || y == ROOM_H - 1
                || x == 0 || x == ROOM_W - 1) ? BGT_WALL
                : ((u8)(x * 5 + y * 3 + room) & 7) == 0 ? BGT_FLOOR2
                : BGT_FLOOR;
    if (room) room_tilemap[8][0] = room_tilemap[9][0] = BGT_DOOR;
    if (!last) room_tilemap[8][ROOM_W - 1] = room_tilemap[9][ROOM_W - 1] =
        (role == ROLE_ENTRY || den_gate_open) ? BGT_DOOR : BGT_PILLAR;
}

static u8 enemy_count(void) {
    u8 i, n = 0;
    for (i = 0; i < MAX_ENTITIES; ++i)
        if ((entities[i].flags & EF_ACTIVE) && entities[i].type == ENT_ENEMY)
            n++;
    return n;
}

static void mark(u8 idx) {
    if (idx != 0xFF) pickup_mark_persistent(idx);
}

static void full_heal(void) {
    player.hp = player.hp_max;
    player.mp = player.mp_max;
    hud_redraw_all();
}

// Wild Chart: the next dungeon's complete layout, OR-ed into any chart the
// village already queued (never a dud overwrite).
static u8 wild_chart(void) {
    if ((run_state.next_dungeon_reveal & run_state.next_dungeon_reveal_hi
            & run_state.next_dungeon_reveal_xhi) == 0xFF) return 0;
    run_state.next_dungeon_reveal = 0xFF;
    run_state.next_dungeon_reveal_hi = 0xFF;
    run_state.next_dungeon_reveal_xhi = 0xFF;
    run_state.next_dungeon_reveal_xxhi = 0x3F;
    hud_show_word(NW_CHART);
    return 1;
}

// Rewards never include a permanent stat item (no cap is ever involved).
// They follow the Riftwild vault rule: the claim bit is set the moment they
// appear, so re-entering a den never refills it.
//   CAIRN   tier 1: a dungeon tool, full restore, coins.
//   DROWNED tier 2: Wild Chart (or a second tool), Riftwell re-arm when the
//                   well is spent, a tool, coins.
//   SCAR    tier 3: keeper boon choice between two curated rare relics.
static void grant_reward(u8 d, u8 px, u8 py) {
    u8 kind = den_kind[region()][d];
    u8 r = region();
    if (den_claimed(d)) return;
    run_state.riftwild_shadow |= DEN_CLAIM_BIT(d);
    if (kind == RIFT_DEN_CAIRN) {
        mark(pickup_spawn_item((u8)(22 + r), FIX8(px), FIX8(py)));
        mark(pickup_spawn(PICKUP_COIN_5, FIX8(px - 16), FIX8(py + 8)));
        mark(pickup_spawn(PICKUP_COIN_5, FIX8(px + 16), FIX8(py + 8)));
        full_heal();
    } else if (kind == RIFT_DEN_DROWNED) {
        mark(pickup_spawn_item((u8)(22 + r), FIX8(px - 12), FIX8(py)));
        if (!wild_chart())
            mark(pickup_spawn_item((u8)(22 + (r == 2 ? 0 : r + 1)),
                FIX8(px + 12), FIX8(py)));
        if (RUN_RIFTWELL_USED()) {
            run_state.riftwild_flags &= (u8)~RIFT_REGION_WELL_USED_BIT;
            run_state.world_return_screen &= (u8)~RIFTWELL_USED_FLAG;
        }
        mark(pickup_spawn(PICKUP_COIN_5, FIX8(px), FIX8(py + 16)));
        full_heal();
    } else {
        // Blast Seed or Rift Lens, against the returning Boomerang.
        pickup_spawn_choice((u8)(25 + ((u8)run_state.run_seed & 1)),
            FIX8(px - 16), FIX8(py));
        pickup_spawn_choice(27, FIX8(px + 16), FIX8(py));
        mark(pickup_spawn(PICKUP_COIN_5, FIX8(px), FIX8(py + 16)));
        full_heal();
    }
    sfx_play(SFX_CLEAR);
}

static void paint_room(u8 d, u8 room, u8 role, u8 last) {
    u8 x, y;
    u8 claimed = den_claimed(d);
    paint_shell(role, room, last);
    if (role == ROLE_ENTRY) {
        // Stair back up, flanked by two cave pillars.
        room_tilemap[4][4] = BGT_PORTAL;
        room_tilemap[3][3] = room_tilemap[3][5] = BGT_PILLAR;
        room_tilemap[12][14] = room_tilemap[12][5] = BGT_PILLAR;
        room_tilemap[4][14] = BGT_PILLAR;
    } else if (role == ROLE_TRIAL) {
        room_tilemap[4][6] = room_tilemap[4][13] = BGT_PILLAR;
        room_tilemap[12][6] = room_tilemap[12][13] = BGT_PILLAR;
        room_tilemap[8][10] = BGT_CRYSTAL;
    } else if (role == ROLE_PUZZLE || role == ROLE_PUZZLE_END) {
        // Push the crate into the framed socket.
        for (y = SOCKET_Y; y <= SOCKET_Y + 1; ++y)
            for (x = SOCKET_X; x <= SOCKET_X + 1; ++x)
                room_tilemap[y][x] = BGT_FLOOR3;
        room_tilemap[SOCKET_Y - 1][SOCKET_X - 1] = BGT_PILLAR;
        room_tilemap[SOCKET_Y - 1][SOCKET_X + 2] = BGT_PILLAR;
        room_tilemap[SOCKET_Y + 2][SOCKET_X - 1] = BGT_PILLAR;
        room_tilemap[SOCKET_Y + 2][SOCKET_X + 2] = BGT_PILLAR;
        // Keep the crate's column and row lanes plain floor.
        for (y = SOCKET_Y; y <= CRATE_Y + 1; ++y)
            room_tilemap[y][CRATE_X] = room_tilemap[y][CRATE_X + 1] = BGT_FLOOR;
        for (x = 3; x < SOCKET_X; ++x)
            room_tilemap[SOCKET_Y][x] = room_tilemap[SOCKET_Y + 1][x] = BGT_FLOOR;
        if (den_gate_open || claimed) {
            room_tilemap[SOCKET_Y][SOCKET_X] = BGT_BLOCK;
            room_tilemap[SOCKET_Y][SOCKET_X + 1] = BGT_BLOCK_TR;
            room_tilemap[SOCKET_Y + 1][SOCKET_X] = BGT_BLOCK_BL;
            room_tilemap[SOCKET_Y + 1][SOCKET_X + 1] = BGT_BLOCK_BR;
        } else {
            room_tilemap[CRATE_Y][CRATE_X] = BGT_BLOCK;
            room_tilemap[CRATE_Y][CRATE_X + 1] = BGT_BLOCK_TR;
            room_tilemap[CRATE_Y + 1][CRATE_X] = BGT_BLOCK_BL;
            room_tilemap[CRATE_Y + 1][CRATE_X + 1] = BGT_BLOCK_BR;
        }
        if (role == ROLE_PUZZLE_END) {
            // Treasure alcove behind a pillar screen in the east.
            for (y = 1; y < ROOM_H - 1; ++y)
                room_tilemap[y][15] = (y >= 7 && y <= 10)
                    ? (claimed ? BGT_FLOOR : BGT_PILLAR) : BGT_WALL;
            if (claimed) room_tilemap[12][17] = BGT_PORTAL;
        }
    } else {
        // Chest or keeper hall: four crystal lamps.
        room_tilemap[3][3] = room_tilemap[3][16] = BGT_CRYSTAL;
        room_tilemap[13][3] = room_tilemap[13][16] = BGT_CRYSTAL;
        if (claimed) room_tilemap[12][15] = BGT_PORTAL;
    }
}

// The keeper is this stage's mini-boss (its GPT art is already resident),
// configured exactly like procgen's Warden/Sentinel path.
static void configure_keeper(u8 idx) {
    static const u8 mb_pal[5] = { 0x06, 0x07, 0x00, 0x04, 0x03 };
    u8 stage = run_state.bosses_beaten;
    u8 mb_pow = (stage < 9) ? stage : 8;
    u8 mb_var = stage_mb_variant[stage % 9];
    entities[idx].sprite_tile = SPR_BOSS;
    entities[idx].palette     = mb_pal[mb_var];
    entities[idx].hitbox      = (u8)0xEE;
    entities[idx].ai_data[2]  = mb_var;
    entities[idx].hp = (u8)(entities[idx].hp + 25u + (u8)(mb_pow * 14));
    entities[idx].damage++;
    if (RUN_IS_EASY()) entities[idx].hp = (u8)((entities[idx].hp + 1) >> 1);
}

void riftwild_den_build_room(void) BANKED {
    u8 d = den_index();
    u8 room = den_room();
    u8 kind, rooms, role, last, claimed;
    if (d >= RIFT_DEN_COUNT) {
        // Corrupt suspend: fall back to the parent field.
        run_state.world_screen = (u8)(run_state.world_return_screen & 0x3Fu);
        d = 0;
    }
    kind = den_kind[region()][d];
    rooms = den_rooms[kind];
    if (room >= rooms) room = (u8)(rooms - 1);
    role = den_role[kind][room];
    last = (u8)(room + 1 == rooms);
    claimed = den_claimed(d);
    procgen_current_room_is_boss = 0;
    procgen_current_room_is_large = 0;
    dungeon_director_reset();
    room_district_label_ticks = 0;
    den_gate_open = claimed ? 1 : 0;
    den_keeper_up = 0;
    den_touch = 0;
    rng_seed(procgen_room_seed(run_state.run_seed, run_state.biome_id,
        (u8)(0xC0u ^ run_state.world_screen
            ^ (u8)(run_state.riftwild_region * 0x35u))));
    mark_found(d);
    paint_room(d, room, role, last);
    entity_init_room();
    companion_spawn_current();
    room_spawn_progression_fixture();
    if (!claimed) {
        if (role == ROLE_TRIAL) {
            static const u8 sx[5] = { 14, 15, 11, 15, 8 };
            static const u8 sy[5] = { 3, 12, 6, 8, 12 };
            u8 i, n = (u8)(3 + (kind == RIFT_DEN_SCAR ? 1 : 0)
                + (run_state.riftwild_region ? 1 : 0));
            for (i = 0; i < n; ++i) {
                u8 idx = enemy_spawn(dungeon_director_pick_stage_enemy(
                    run_state.bosses_beaten), sx[i], sy[i]);
                riftwild_harden_enemy(idx, i);
            }
        } else if (role == ROLE_CHEST_END) {
            grant_reward(d, 80, 56);
            room_tilemap[12][15] = BGT_PORTAL;
            den_gate_open = 1;
        } else if (role == ROLE_KEEPER_END) {
            u8 idx = enemy_spawn(ENEMY_STONE_SENTINEL, (ROOM_W / 2) - 1, 3);
            if (idx != 0xFF) {
                configure_keeper(idx);
                // Ordinal 0 keeps the variant palette in the Hollow.
                riftwild_harden_enemy(idx, 0);
                den_keeper_up = 1;
            }
        }
    }
    riftwild_den_armed |= 1;
    player.iframes = 60;
}

static void open_east_door(void) {
    live_set(ROOM_W - 1, 8, BGT_DOOR, BGPAL_DOOR);
    live_set(ROOM_W - 1, 9, BGT_DOOR, BGPAL_DOOR);
}

static void den_room_tick(void) {
    u8 d = den_index();
    u8 kind, room, role;
    if (d >= RIFT_DEN_COUNT || den_gate_open) return;
    kind = den_kind[region()][d];
    room = den_room();
    role = den_role[kind][room];
    if (role == ROLE_TRIAL) {
        if (enemy_count()) return;
        den_gate_open = 1;
        open_east_door();
        sfx_play(SFX_CLEAR);
    } else if (role == ROLE_PUZZLE || role == ROLE_PUZZLE_END) {
        if (room_tilemap[SOCKET_Y][SOCKET_X] != BGT_BLOCK) return;
        den_gate_open = 1;
        sfx_play(SFX_PUZZLE);
        room_shake(1, 8);
        if (role == ROLE_PUZZLE) {
            open_east_door();
        } else {
            u8 y;
            for (y = 7; y <= 10; ++y) live_set(15, y, BGT_FLOOR, BGPAL_FLOOR);
            grant_reward(d, 136, 56);
            live_set(17, 12, BGT_PORTAL, BGPAL_CRYSTAL);
        }
    } else if (role == ROLE_KEEPER_END) {
        if (!den_keeper_up || enemy_count()) return;
        den_gate_open = 1;
        grant_reward(d, 80, 56);
        live_set(15, 12, BGT_PORTAL, BGPAL_CRYSTAL);
    }
}

static void field_tick(void) {
    u8 d = field_cairn_closed();
    u8 fx, fy;
    if (d == 0xFF) { riftwild_den_armed &= 0x02; return; }
    // Titan Glove (or a Sauran's grip) heaves the stone aside: stand
    // beside it and push into it for a moment.
    if (!(player.class_id == 1
            || (player.waygear_owned & WAYGEAR_BIT(WAYGEAR_GLOVE)))
        || !den_manifest(d)) return;
    fx = (u8)((player.x + 8) >> 3);
    fy = (u8)((player.y + 12) >> 3);
    if (fx + 1 >= RIFT_DEN_TELL_X && fx <= RIFT_DEN_TELL_X + 1
        && fy + 1 >= RIFT_DEN_TELL_Y && fy <= RIFT_DEN_TELL_Y + 1
        && (input_keys & (J_LEFT | J_RIGHT | J_UP | J_DOWN))) {
        if (++den_touch >= 12) {   // ~0.5 s of game ticks
            den_touch = 0;
            open_cairn(d);
        }
    } else den_touch = 0;
}

// Bit 1 rides the same room_tick guard for the secret-merchant charms
// (secret_merchant.c), so ordinary rooms pay no extra per-frame check.
void riftwild_den_tick(void) BANKED {
    if (riftwild_den_armed & 0x02) secret_merchant_tick();
    if (!(riftwild_den_armed & 0x01)) return;
    if (!run_state.world_mode) { riftwild_den_armed &= 0x02; return; }
    if (in_den()) {
        if ((++den_frame & 7) == 0) den_room_tick();
        return;
    }
    field_tick();
}

// Rift Bomb: the burst covers seven tiles around the hero.
void riftwild_den_burst(u8 tx, u8 ty) BANKED {
    if (!run_state.world_mode || in_den()) return;
    secret_cave_burst(tx, ty);
    if (tx + 3 >= RIFT_DEN_TELL_X && tx <= RIFT_DEN_TELL_X + 3
        && ty + 3 >= RIFT_DEN_TELL_Y && ty <= RIFT_DEN_TELL_Y + 3)
        riftwild_den_strike(RIFT_DEN_TELL_X, RIFT_DEN_TELL_Y);
}

// Every Riftwild portal tile: a den stair first, then the authored arch,
// vault, and cave staircase fixtures (moved here from bank 1 unchanged).
void riftwild_take_portal(u8 tx, u8 ty) BANKED {
    const zelda_screen_t *cell;
    if (secret_cave_portal(tx, ty)) return;
    if (riftwild_den_portal(tx, ty)) return;
    cell = &zelda_overworlds[0].screen_grid[run_state.world_screen];
    if (cell->kind == ZELDA_CELL_DUNGEON_ENTRANCE) {
        run_state_enter_from_world();
    } else if (cell->kind == ZELDA_CELL_VAULT) {
        run_state.world_screen =
            (u8)(run_state.world_return_screen & 0x3Fu);
    } else if (cell->stairs != ID_NONE_U8) {
        run_state.world_return_screen = (u8)(run_state.world_screen
            | (run_state.world_return_screen & RIFTWELL_USED_FLAG));
        run_state.world_screen = cell->stairs;
    }
}

// Room-generation entry point: dens build their own compact cave; every other
// room (dungeon, town, Riftwild field) runs the shared procgen body.
void procgen_generate_current_room(void) BANKED {
    if (run_state.world_mode
        && run_state.world_screen >= SECRET_CAVE_SCREEN_BASE)
        secret_cave_build_room();
    else if (RUN_IN_RIFT_DEN()) riftwild_den_build_room();
    else procgen_generate_room_body();
    // After the room body (or a den/cave) so bank 4 does not pay for the
    // banked call. The function no-ops unless this is the shrine cell.
    powerup_place_room_shrine();
}
