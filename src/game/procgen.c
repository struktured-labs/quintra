#pragma bank 255
#include <gb/gb.h>

#include "audio/sfx.h"
#include "core/types.h"
#include "core/rng.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/room.h"
#include "game/run_state.h"
#include "render/tiles.h"
#include "core/types.h"
#include "content.h"

u32 procgen_room_seed(u32 run_seed, u8 biome_id, u8 room_counter) BANKED {
    return run_seed ^ ((u32)biome_id << 16) ^ ((u32)room_counter * 0x9E3779B9UL);
}

// Large boss OBJ tile per stage. Wave B gives each of the 9 stages a distinct
// 32x32 sprite; for now every stage's boss uses the Colossus metasprite.
u8 boss_sprite_for_stage(u8 stage) {
    stage;
    return SPR_BOSS_BIG;
}

// The boss always draws on OBJ palette slot 6; room_enter loads a stage-tinted
// palette into that slot so each stage's boss has its own colour.
u8 boss_palette_for_stage(u8 stage) {
    stage;
    return 0x06;
}

// Place player at the door opposite the one they entered from.
static void place_player_after_entry(void) {
    u8 dir = run_state.entered_from;
    u8 tx, ty;
    if (dir == DIR_N)      { tx = ROOM_W / 2; ty = ROOM_H - 3; }
    else if (dir == DIR_S) { tx = ROOM_W / 2; ty = 2; }
    else if (dir == DIR_E) { tx = 2;          ty = ROOM_H / 2; }
    else if (dir == DIR_W) { tx = ROOM_W - 3; ty = ROOM_H / 2; }
    else                   { tx = ROOM_W / 2; ty = ROOM_H / 2; }
    player.x = (ppos_t)((i16)tx * 8);
    player.y = (ppos_t)((i16)ty * 8);
}

// Weighted pick from this stage's roster (generated stage_pool tables;
// stage wraps with the endless theme cycle). One rng draw per pick.
static u8 pick_enemy_for_stage(u8 stage_raw) {
    u8 st = (u8)(stage_raw % N_STAGES);
    u8 r = rng_range(stage_pool_total[st]);
    u8 k, acc = 0;
    for (k = 0; k < stage_pool_n[st]; ++k) {
        acc = (u8)(acc + stage_pool_w[st][k]);
        if (r < acc) return stage_pool_ids[st][k];
    }
    return stage_pool_ids[st][0];
}

void procgen_generate_current_room(void) BANKED {
    const biome_def_t *bio = &biomes[run_state.biome_id];
    u32 seed = procgen_room_seed(run_state.run_seed, run_state.biome_id, run_state.room_counter);
    // A boss guards every Nth room until BOSSES_TO_WIN are down. Computed
    // once at function scope so door-drawing, the secret-room guard, and
    // enemy spawning all agree (a mismatch here soft-locked boss rooms).
    u8 is_boss_room = (run_state.room_counter > 0
        && (run_state.room_counter % BOSS_EVERY_N_ROOMS) == 0
        && (u8)(run_state.room_counter / BOSS_EVERY_N_ROOMS) > run_state.bosses_beaten) ? 1 : 0;
    rng_seed(seed);

    bio;
    {
        u8 x, y;

        // Base: border walls + textured floor (plain / cracked / pebbled mix)
        for (y = 0; y < ROOM_H; ++y) {
            for (x = 0; x < ROOM_W; ++x) {
                if (y == 0 || y == ROOM_H - 1 || x == 0 || x == ROOM_W - 1) {
                    room_tilemap[y][x] = BGT_WALL;
                } else {
                    u8 r = rng_next_u8();
                    room_tilemap[y][x] =
                        (r < 38) ? BGT_FLOOR2 :        // ~15% cracked
                        (r < 64) ? BGT_FLOOR3 :        // ~10% pebbled
                                   BGT_FLOOR;
                }
            }
        }

        if (!is_boss_room) {
            room_tilemap[0][ROOM_W / 2]            = BGT_DOOR;
            room_tilemap[ROOM_H - 1][ROOM_W / 2]   = BGT_DOOR;
            room_tilemap[ROOM_H / 2][0]            = BGT_DOOR;
            room_tilemap[ROOM_H / 2][ROOM_W - 1]   = BGT_DOOR;

            // Interior obstacles. Door lanes stay clear (cols 9-11 for the
            // N/S door at col 10; rows 7-9 for the E/W door at row 8) so
            // every door remains reachable regardless of pattern.
            {
                u8 shape = (u8)(rng_next_u8() & 0x07);
                if (shape == 1) {
                    // Four pillars at quarter points
                    room_tilemap[4][4]   = BGT_PILLAR;
                    room_tilemap[4][15]  = BGT_PILLAR;
                    room_tilemap[13][4]  = BGT_PILLAR;
                    room_tilemap[13][15] = BGT_PILLAR;
                } else if (shape == 2) {
                    // Crystal clusters — up to 4, lanes + border excluded
                    u8 placed = 0, tries = 12;
                    while (placed < 4 && tries--) {
                        u8 cx = (u8)(2 + rng_range(ROOM_W - 4));
                        u8 cy = (u8)(2 + rng_range(ROOM_H - 4));
                        if (cx >= 9 && cx <= 11) continue;
                        if (cy >= 7 && cy <= 9)  continue;
                        room_tilemap[cy][cx] = BGT_CRYSTAL;
                        placed++;
                    }
                } else if (shape == 3) {
                    // Chunky pillar pairs in the corners
                    room_tilemap[4][4]   = BGT_PILLAR; room_tilemap[4][5]   = BGT_PILLAR;
                    room_tilemap[4][14]  = BGT_PILLAR; room_tilemap[4][15]  = BGT_PILLAR;
                    room_tilemap[13][4]  = BGT_PILLAR; room_tilemap[13][5]  = BGT_PILLAR;
                    room_tilemap[13][14] = BGT_PILLAR; room_tilemap[13][15] = BGT_PILLAR;
                } else if (shape == 4) {
                    // Inner vault: pillar ring at x 4-15 / y 4-12, with
                    // lane-wide gaps where the door lanes cross it.
                    u8 i;
                    for (i = 4; i <= 15; ++i) {
                        if (i >= 9 && i <= 11) continue;      // N/S lane gap
                        room_tilemap[4][i]  = BGT_PILLAR;
                        room_tilemap[12][i] = BGT_PILLAR;
                    }
                    for (i = 4; i <= 12; ++i) {
                        if (i >= 7 && i <= 9) continue;       // E/W lane gap
                        room_tilemap[i][4]  = BGT_PILLAR;
                        room_tilemap[i][15] = BGT_PILLAR;
                    }
                } else if (shape == 5) {
                    // Twin walls: vertical pillar runs at x=5 and x=14,
                    // broken at the E/W lane — three linked chambers.
                    u8 i;
                    for (i = 2; i <= 14; ++i) {
                        if (i >= 7 && i <= 9) continue;
                        room_tilemap[i][5]  = BGT_PILLAR;
                        room_tilemap[i][14] = BGT_PILLAR;
                    }
                } else if (shape == 6) {
                    // Diagonal crystal spurs from each corner (shootable)
                    room_tilemap[3][3]   = BGT_CRYSTAL; room_tilemap[4][4]   = BGT_CRYSTAL;
                    room_tilemap[5][5]   = BGT_CRYSTAL;
                    room_tilemap[3][16]  = BGT_CRYSTAL; room_tilemap[4][15]  = BGT_CRYSTAL;
                    room_tilemap[5][14]  = BGT_CRYSTAL;
                    room_tilemap[13][3]  = BGT_CRYSTAL; room_tilemap[12][4]  = BGT_CRYSTAL;
                    room_tilemap[11][5]  = BGT_CRYSTAL;
                    room_tilemap[13][16] = BGT_CRYSTAL; room_tilemap[12][15] = BGT_CRYSTAL;
                    room_tilemap[11][14] = BGT_CRYSTAL;
                } else if (shape == 7) {
                    // Colonnade: two pillar rows flanking the E/W lane —
                    // a great hall with cover to duck behind.
                    static const u8 col_x[6] = { 3, 5, 7, 13, 15, 17 };
                    u8 i;
                    for (i = 0; i < 6; ++i) {
                        room_tilemap[5][col_x[i]]  = BGT_PILLAR;
                        room_tilemap[11][col_x[i]] = BGT_PILLAR;
                    }
                }
                // shape 0: open room (now 1-in-8 — variety rules)
            }

            // Rubble decoration (walkable) — 3 scatter spots
            {
                u8 i;
                for (i = 0; i < 3; ++i) {
                    u8 rx = (u8)(2 + rng_range(ROOM_W - 4));
                    u8 ry = (u8)(2 + rng_range(ROOM_H - 4));
                    if (room_tilemap[ry][rx] == BGT_FLOOR) {
                        room_tilemap[ry][rx] = BGT_RUBBLE;
                    }
                }
            }

            // Pushable blocks — 0-2 per room, kept in the interior away from
            // the door lanes so they can always be walked around or shoved.
            {
                u8 nb = (u8)(rng_next_u8() % 3);
                u8 i;
                for (i = 0; i < nb; ++i) {
                    u8 bx = (u8)(3 + rng_range(ROOM_W - 6));
                    u8 by = (u8)(3 + rng_range(ROOM_H - 6));
                    if (bx >= 9 && bx <= 11) continue;   // clear N/S door lane
                    if (by >= 7 && by <= 9)  continue;   // clear E/W door lane
                    if (room_tilemap[by][bx] == BGT_FLOOR) {
                        room_tilemap[by][bx] = BGT_BLOCK;
                    }
                }
            }


            // Secret cracked wall — ~half of rooms hide one on a border
            // (never on a door or the E/W door row). Rendered on its own
            // glowing palette so it's obviously shootable.
            if ((rng_next_u8() & 0x01) == 0) {
                u8 side = (u8)(rng_next_u8() & 0x03);
                u8 pos;
                if (side == 0) {          // north wall
                    pos = (u8)(2 + rng_range(ROOM_W - 4));
                    if (pos != ROOM_W / 2) room_tilemap[0][pos] = BGT_WALL_CRACK;
                } else if (side == 1) {   // south wall
                    pos = (u8)(2 + rng_range(ROOM_W - 4));
                    if (pos != ROOM_W / 2) room_tilemap[ROOM_H - 1][pos] = BGT_WALL_CRACK;
                } else if (side == 2) {   // west wall
                    pos = (u8)(2 + rng_range(ROOM_H - 4));
                    if (pos != ROOM_H / 2) room_tilemap[pos][0] = BGT_WALL_CRACK;
                } else {                  // east wall
                    pos = (u8)(2 + rng_range(ROOM_H - 4));
                    if (pos != ROOM_H / 2) room_tilemap[pos][ROOM_W - 1] = BGT_WALL_CRACK;
                }
            }
        }
    }

    // Clear entity table — fresh enemies per room
    entity_init_all();

    // Player position FIRST so spawn-avoidance checks the real tile
    place_player_after_entry();

    // Debug markers (HRAM)
    *(volatile u8*)0xFFFE = run_state.room_counter;
    *(volatile u8*)0xFFFD = run_state.victory;

    // Secret treasure room: no enemies, loot piled in the middle. Always
    // clear the flag (else it leaks into every future room). Only take the
    // early-return when this is NOT also a boss room — otherwise the sealed,
    // door-less boss layout would have no boss to spawn = unrecoverable.
    if (run_state.secret_pending) {
        run_state.secret_pending = 0;
        if (!is_boss_room) {
            u8 i;
            *(volatile u8*)0xFFFC = 0x00;
            // The vault: a shootable crystal ring guards the hoard —
            // crack it open or slip around the corner gaps.
            for (i = 7; i <= 12; ++i) {
                room_tilemap[5][i]  = BGT_CRYSTAL;
                room_tilemap[11][i] = BGT_CRYSTAL;
            }
            room_tilemap[7][6]  = BGT_CRYSTAL; room_tilemap[9][6]  = BGT_CRYSTAL;
            room_tilemap[7][13] = BGT_CRYSTAL; room_tilemap[9][13] = BGT_CRYSTAL;
            // The hoard: hearts, a stat item, a coin shower, and a
            // 50% chance of a weapon orb to reroute the build.
            pickup_spawn(PICKUP_HEART_HALF, FIX8(72), FIX8(56));
            pickup_spawn(PICKUP_HEART_HALF, FIX8(88), FIX8(56));
            pickup_spawn(PICKUP_COIN_5,     FIX8(72), FIX8(72));
            pickup_spawn(PICKUP_COIN_5,     FIX8(88), FIX8(72));
            pickup_spawn(PICKUP_COIN_1,     FIX8(64), FIX8(64));
            pickup_spawn(PICKUP_COIN_1,     FIX8(96), FIX8(64));
            pickup_spawn(PICKUP_COIN_1,     FIX8(80), FIX8(48));
            pickup_spawn_item((u8)(10 + rng_range(10)), FIX8(80), FIX8(64));
            if (rng_next_u8() & 1) {
                u8 w = (u8)rng_range(5);
                if (w == player.starter_weapon) w = (u8)((w + 1) % 5);
                pickup_spawn_weapon(w, FIX8(80), FIX8(80));
            }
            sfx_play(SFX_CLEAR);   // secret-found fanfare
            player.iframes = 60;
            return;
        }
        // Boss room: fall through to spawn the boss below.
    }

    {
        u8 is_miniboss = (!is_boss_room && (run_state.room_counter % ROOMS_PER_STAGE) == 3) ? 1 : 0;
        u8 is_shop     = (!is_boss_room && !is_miniboss
                          && (run_state.room_counter % ROOMS_PER_STAGE) == 4) ? 1 : 0;
        // Sanctuary: the room right before every stage boss. No enemies —
        // a shrine, two hearts, and a full MP blessing. Breathe, then go.
        u8 is_rest     = (!is_boss_room
                          && (run_state.room_counter % ROOMS_PER_STAGE) == 5) ? 1 : 0;

        if (is_rest) {
            *(volatile u8*)0xFFFC = 0x00;
            // Crystal shrine: four pylons around the room's heart, all
            // outside the door lanes (cols 9-11 / rows 7-9 stay clear)
            room_tilemap[6][7]   = BGT_CRYSTAL; room_tilemap[6][12]  = BGT_CRYSTAL;
            room_tilemap[10][7]  = BGT_CRYSTAL; room_tilemap[10][12] = BGT_CRYSTAL;
            pickup_spawn(PICKUP_HEART_HALF, FIX8(68), FIX8(64));
            pickup_spawn(PICKUP_HEART_HALF, FIX8(92), FIX8(64));
            player.mp = player.mp_max;   // the shrine's blessing
            player.iframes = 60;
            return;
        }

        if (is_boss_room) {
            // EVERY stage ends with a LARGE (32x32) boss. Power clamps at
            // stage 8 (40 + 9*22 would overflow u8 -> a 4 HP boss); the
            // SKIN cycles all nine colossi forever in endless descent.
            u8 stage = run_state.bosses_beaten;
            u8 pow  = (stage < 9) ? stage : 8;
            u8 skin = (u8)(stage % 9);
            *(volatile u8*)0xFFFC = 0xBB;
            {
                u8 idx = enemy_spawn(1, (ROOM_W / 2) - 2, (ROOM_H / 2) - 2);
                if (idx != 0xFF) {
                    entities[idx].sprite_tile = boss_sprite_for_stage(skin);
                    entities[idx].palette     = boss_palette_for_stage(skin);
                    entities[idx].hitbox      = (15 << 4) | 15;
                    entities[idx].ai_data[3]  = 1;              // giant flag
                    entities[idx].ai_data[2]  = skin;          // boss attack pattern
                    entities[idx].hp = (u8)(entities[idx].hp
                        + stage_boss_hp[pow]);
                    entities[idx].damage = (u8)(entities[idx].damage
                        + stage_boss_dmg[pow]);
                }
            }
        } else if (is_miniboss) {
            // MINI-BOSS: a beefed 16x16 Sentinel + a small escort. Tougher than
            // a normal room, a step below the stage boss.
            u8 stage = run_state.bosses_beaten;
            *(volatile u8*)0xFFFC = 0x00;
            {
                u8 idx = enemy_spawn(1, (ROOM_W / 2) - 1, 3);
                if (idx != 0xFF) {
                    // Silhouette comes from the generated stage table —
                    // ONE source shared with tiles_load_miniboss, so art and
                    // palette can't drift apart. HP power clamps (u8 overflow).
                    static const u8 mb_pal[3] = { 0x06, 0x07, 0x00 };
                    u8 mb_pow = (stage < 9) ? stage : 8;
                    entities[idx].sprite_tile = SPR_BOSS;
                    entities[idx].palette     = mb_pal[stage_mb_variant[stage % 9]];
                    entities[idx].hitbox      = (14 << 4) | 14;
                    entities[idx].hp = (u8)(entities[idx].hp + (u8)(mb_pow * 12));
                }
            }
            // two escorts drawn from the stage roster
            {
                u8 e;
                for (e = 0; e < 2; ++e) {
                    u8 eid = pick_enemy_for_stage(stage);
                    enemy_spawn(eid, (u8)(4 + e * 11), (u8)(ROOM_H - 4));
                }
            }
        } else if (is_shop) {
            // MERCHANT room: three wares, no enemies. Walk into a ware
            // with enough coins to buy (heart 10 / stat item 25 / +2 max HP 40).
            *(volatile u8*)0xFFFC = 0x00;
            {
                u8 s0 = pickup_spawn(PICKUP_SHOP, FIX8(56),  FIX8(64));
                u8 s1 = pickup_spawn(PICKUP_SHOP, FIX8(80),  FIX8(64));
                u8 s2 = pickup_spawn(PICKUP_SHOP, FIX8(104), FIX8(64));
                if (s0 != 0xFF) {
                    entities[s0].ai_data[0] = PICKUP_SHOP;
                    entities[s0].ai_data[1] = WARE_HEART;
                    entities[s0].ai_data[2] = 10;
                    entities[s0].sprite_tile = SPR_HEART;
                    entities[s0].palette = 0x04;
                }
                if (s1 != 0xFF) {
                    entities[s1].ai_data[0] = PICKUP_SHOP;
                    entities[s1].ai_data[1] = WARE_ITEM;
                    entities[s1].ai_data[2] = 25;
                    entities[s1].sprite_tile = SPR_ITEM_ORB;
                    entities[s1].palette = 0x05;
                }
                if (s2 != 0xFF) {
                    entities[s2].ai_data[0] = PICKUP_SHOP;
                    entities[s2].ai_data[1] = WARE_BIG;
                    entities[s2].ai_data[2] = 40;
                    entities[s2].sprite_tile = SPR_ITEM_ORB;
                    entities[s2].palette = 0x04;
                }
                // Price tags painted on the floor under each ware:
                // [coin][d][d], amber, walkable. Wares sit at tile y=8;
                // tags at y=10 leave a step of space.
                room_tilemap[10][6]  = HUD_COIN;
                room_tilemap[10][7]  = (u8)(HUD_DIGIT_0 + 1);
                room_tilemap[10][8]  = (u8)(HUD_DIGIT_0 + 0);
                room_tilemap[10][9]  = HUD_COIN;
                room_tilemap[10][10] = (u8)(HUD_DIGIT_0 + 2);
                room_tilemap[10][11] = (u8)(HUD_DIGIT_0 + 5);
                room_tilemap[10][12] = HUD_COIN;
                room_tilemap[10][13] = (u8)(HUD_DIGIT_0 + 4);
                room_tilemap[10][14] = (u8)(HUD_DIGIT_0 + 0);
            }
        } else {
            *(volatile u8*)0xFFFC = 0x00;
            // Enemy count scales with depth (1-4 early, up to 6 deep)
            u8 depth_bonus = (u8)(run_state.room_counter / 6);
            u8 enemy_count = (u8)(1 + rng_range(4) + (depth_bonus > 2 ? 2 : depth_bonus));
            u8 ptx = (u8)(player.x >> 3);
            u8 pty = (u8)(player.y >> 3);
            u8 i;
            for (i = 0; i < enemy_count; ++i) {
                u8 tx = (u8)(2 + rng_range(ROOM_W - 4));
                u8 ty = (u8)(2 + rng_range(ROOM_H - 4));
                if (!room_tile_walkable(room_tilemap[ty][tx])) continue;
                {
                    u8 dx = (tx > ptx) ? (u8)(tx - ptx) : (u8)(ptx - tx);
                    u8 dy = (ty > pty) ? (u8)(ty - pty) : (u8)(pty - ty);
                    if (dx < 3 && dy < 3) continue;
                }
                {
                    // Roster comes from the generated per-stage pool —
                    // designed in content/src/stages.rs, not hard-coded here.
                    u8 eid = pick_enemy_for_stage(run_state.bosses_beaten);
                    {
                        u8 idx = enemy_spawn(eid, tx, ty);
                        // ~12% spawn ELITE: boss-palette glow, double HP,
                        // +1 damage, EF_ELITE flag (combat pays the bonus).
                        if (idx != 0xFF && rng_next_u8() < 31) {
                            entities[idx].flags  |= EF_ELITE;
                            entities[idx].palette = 0x06;
                            entities[idx].hp      = (u8)(entities[idx].hp << 1);
                            entities[idx].damage  = (u8)(entities[idx].damage + 1);
                        }
                    }
                }
            }
        }
    }

    player.iframes = 60;    // brief invuln on room entry
}
