#pragma bank 1
// ROOM — top-down gameplay scene. Phase 5: spawns N enemies, supports
// 4-dir movement, 8-dir B-button fire, wall collision, combat resolution.
// Phase 7 wires procgen to fill from biome.room_template_pool.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "audio/audio.h"
#include "audio/music.h"
#include "audio/sfx.h"
#include "core/types.h"
#include "core/rng.h"
#include "game/combat.h"
#include "game/entity.h"
#include "game/enemy_ai.h"
#include "game/loop.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/procgen.h"
#include "game/projectile.h"
#include "game/puzzle.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/sram.h"
#include "render/class_palettes.h"
#include "render/hud.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

BANKREF(room_enter)

u8 room_tilemap[ROOM_H][ROOM_W];
u8 room_world_extension[ROOM_H][ROOM_WIDE_EXT_TILES];
u8 room_world_bottom[ROOM_WIDE_BOTTOM_ROWS][ROOM_WIDE_W_TILES];
u8 room_world_width = ROOM_VIEW_W_PX;
u8 room_world_height = ROOM_VIEW_H_PX;
u8 room_camera_x;
u8 room_camera_y;

static u8 room_paused;
static u8 room_resume_flag;   // set by room_request_resume: skip procgen next enter
// Active VBlanks below one whole second. Keep this across pack/map visits so
// menu tapping cannot erase time; g_vbl_ticks itself is cleared on re-entry so
// time spent reading those screens remains paused.
static u8 run_clock_fraction;
// Secret door opened by shooting a cracked wall this room (0xFF = none)
static u8 secret_door_x = 0xFF;
static u8 secret_door_y = 0xFF;
static u8 secret_door_x2 = 0xFF;   // secret doors open as a 2-tile pair
static u8 secret_door_y2 = 0xFF;   // (the wide feet box needs 16px)
// Block-push state: current lean direction + how long it's been held.
static u8 push_dir = DIR_NONE;
static u8 push_timer;
// Stage-entry reveal: first room of each new stage fades in from dimmed
// palettes over ~half a second. stage_seen tracks the last stage revealed.
static u8 stage_seen = 0xFF;
static u8 stage_fade;

// Room-clear chime: hostiles seen alive this room (reset on every room
// generation so walking into an empty room never false-fires the chime).
static u8 hostiles_prev;
static u8 hostiles_now;
static u8 door_bump_cd;
static u8 boss_threshold_warned;
static u8 shop_offer_visible;
// Cinder's projected furnace face only uploads its two animated tiles when
// the existing wind-up/lunge/recovery state actually changes.
static u8 cinder_projection_state = 0xFF;
// Toxic Mire's BG organism redraws only when the boss changes pulse phase.
// 0xFF forces the first live frame to reconcile VRAM with the entity state.
static u8 mire_projection_state = 0xFF;
// Set once when a room is generated.  Price proximity must never put a
// 32-entity scan on ordinary bullet-hell frames that cannot contain a ware.
static u8 room_has_shop_wares;
// These are run-scoped, not room-scoped: passive trickles should retain their
// partial progress through doors/menus, but player_clear resets them before a
// brand-new champion is initialized.
static u8 mp_regen;
static u16 hp_regen;
u8 room_combat_sealed;
u8 room_sigil_status;

// Screen shake (BG scroll wiggle; the WINDOW HUD stays put). Set by
// combat via room_shake() on boss kills / player hits.
static u8 shake_timer;
static u8 shake_mag;

// Death sequence: frames left in the fall-down beat before GAMEOVER.
static u8 death_timer;

// Dodge dash (double-tap a direction): a fast i-frame lunge on a short
// cooldown. tap_dir/tap_age detect the double-tap; dash_timer runs the
// lunge; dash_cd gates re-use.
static u8 tap_dir;       // last freshly-pressed cardinal ('L'/'R'/'U'/'D')
static u8 tap_age;       // frames since that press
static u8 dash_timer;    // frames left in the current dash
static u8 dash_cd;       // cooldown before the next dash
static i8 dash_dx, dash_dy;
// Wolfkin's A kit is deliberately input-shaped rather than a held-button
// projectile stream: a directed tap stabs, an undirected tap sweeps, and a
// committed hold becomes a cooldown-gated Max Strike dash.
static u8 wolfkin_a_hold;
static u8 wolfkin_max_cd;
// Room transitions grant real invulnerability so a generated arrival cannot
// immediately trade into a hostile. It is safety rather than damage, so it
// must not inherit the alternating invisible damage-flicker.
static u8 arrival_sprite_grace;
// Spirit Convergence lasts 135 eighth-second ticks (~18 seconds). Keeping the
// timer here avoids inflating suspend-save payloads; ordinary room transitions
// do not reset it.
u8 room_transform_ticks;
// Surge Spark lasts 120 eighth-second beats (about 15 seconds). It is room
// runtime state, like Spirit Convergence, rather than permanent save data.
u8 room_weapon_surge_ticks;

// Wolfkin's Howl and Vespine's Swarm are committed close-range burst
// abilities. Their activation ward is deliberately not a shield: it neither
// deletes shots nor lasts through a whole pattern. It merely gives the two
// melee kits a readable beat to spend their MP burst inside a boss body or
// lane without trading the same frame for damage.
static void room_special_guard(u8 frames) {
    if (player.iframes < frames) player.iframes = frames;
}

void room_shake(u8 mag, u8 frames) BANKED {
    shake_mag = mag;
    if (frames > shake_timer) shake_timer = frames;
}

void room_start_weapon_surge(void) BANKED {
    room_weapon_surge_ticks = 120;
    room_shake(1, 10);
    fx_spawn(SPR_SURGE_ORB, 0x06, (i16)player.x + 4, (i16)player.y - 6, 18);
    sfx_play(SFX_ROAR);
}

void room_reset_passive_timers(void) BANKED {
    mp_regen = 0;
    hp_regen = 0;
    wolfkin_a_hold = 0;
    wolfkin_max_cd = 0;
}

void room_request_resume(void) BANKED { room_resume_flag = 1; }

static void room_clock_consume(void) {
    u8 elapsed = g_vbl_ticks;
    g_vbl_ticks = 0;
    run_clock_fraction = (u8)(run_clock_fraction + elapsed);
    while (run_clock_fraction >= 60) {
        run_clock_fraction = (u8)(run_clock_fraction - 60);
        if (run_state.run_timer < 65535) run_state.run_timer++;
    }
}

// Stage themes now live in the Rust content layer (content/src/stages.rs)
// and arrive as generated BGR555 tables: stage_pal / boss_stage_pal /
// stage_pal_crack / stage_names (see src/generated/stages.h). Invalid
// colors or a wrong stage count fail at cargo build, never here.

static u8 room_stage(void) {
    // Endless descent (10th+ boss): the nine themes cycle again —
    // Crystal Caverns at double power, and on down. Stats stay maxed
    // (procgen clamps power separately); this drives look + music.
    u8 s = run_state.bosses_beaten;
    return (s < N_STAGES) ? s : (u8)(s % N_STAGES);
}

// Penta Dragon's memorable giants are arenas as much as sprites. The GBC has
// only 40 hardware sprites and the existing 32x32 weak point already uses 16,
// so all nine authored bosses project larger bodies into the BG plane.
// The body is visual/lore space—only the mobile OBJ core is vulnerable or
// collidable.
// Store availability is a room property, not an every-frame discovery job.
// This is refreshed on both full room entry and the in-place door/portal
// regeneration paths.
static u8 room_state_has_shop_wares(void) {
    return run_state_is_shop()
        // The Cartographer sells a Chart in the arrival square too. Keep all
        // town shelves on the same proximity-HUD path so no paid ware looks
        // like a mysterious loose pickup.
        || RUN_ROOM_IS_TOWN(run_state.room_counter);
}

static void room_refresh_shop_wares(void) {
    room_has_shop_wares = room_state_has_shop_wares();
}

// Slot 125 is intentionally multiplexed: merchant rooms need the proximity
// callout, while all other dungeon rooms may use the Dread Bell silhouette.
// Both full screen entry and in-place door/portal regeneration must come
// through this helper; otherwise a prior room's tile data can leak forward.
static void room_load_dynamic_fx_identity(void) {
    tiles_load_fx_sprites();
    // Slot 79 is phase-safe across stages, but its owner must not be tied to
    // the shop test below: that test is about the sale-callout slots, while
    // a fresh room-entry can still have its shop cache in flight.  Choose the
    // stage specialist first, then let a town resident reclaim its tile in
    // the town-specific loader.
    if (!RUN_ROOM_IS_TOWN(run_state.room_counter)) {
        if (room_stage() == 0) tiles_load_shard_crab_sprite();
        else if (room_stage() == 1) tiles_load_vine_coil_sprite();
        else if (room_stage() == 2) tiles_load_cinder_kite_sprite();
        else if (room_stage() == 3) tiles_load_frost_lancer_sprite();
        else if (room_stage() == 4) tiles_load_bog_toad_sprite();
        else if (room_stage() == 5) tiles_load_bramble_sprite();
        else if (room_stage() == 6) tiles_load_sunwheel_sprite();
        else if (room_stage() == 7) tiles_load_dusk_midge_sprite();
        else tiles_load_void_halo_sprite();
    }
    // Chartwright occupies this slot only in towns. Dungeon rooms reclaim it
    // for Astral Spear; no gameplay population can require both at once.
    if (!RUN_ROOM_IS_TOWN(run_state.room_counter)) tiles_load_spear_sprite();
    // room_state_has_shop_wares() already covers towns as well as dungeon
    // shops, so it is the single exclusion for this combat-only sprite set.
    if (!run_state.world_mode && !room_state_has_shop_wares()) {
        tiles_load_dread_bell_sprite();
        tiles_load_rift_warden_sprite();
        tiles_load_prism_skitter_sprite();
    }
}

static void room_load_town_resident_identity(void) {
    if (!RUN_ROOM_IS_TOWN(run_state.room_counter)) return;
    // The Bellkeeper borrows the apothecary's slot on arrival. Restore the
    // ordinary resident atlas on every town screen first, then apply only
    // the screen-local identities below so a craft-quarter apothecary can
    // never inherit the bell art after a lateral transition.
    tiles_load_pickup_sprites();
    tiles_load_town_waykeeper_sprite();
    if (run_state.world_return_screen == TOWN_ARRIVAL) {
        tiles_load_town_bellkeeper_sprite();
        tiles_load_town_lorekeeper_sprite();
        tiles_load_town_lore_callout_sprite();
    }
}

// Progression fixtures belong to room orchestration, after procgen has fully
// populated combat slots. Keeping them here prevents geometry/encounter code
// from accidentally erasing a required key and makes the invariant testable.
void room_spawn_progression_fixture(void) BANKED {
    u8 i;
    u8 arena_stage = room_apply_world_arena();
    if (arena_stage == 2) cinder_projection_state = 0xFF;
    if (arena_stage == 4) mire_projection_state = 0xFF;
    room_sigil_status = 1;
    if (run_state.world_mode) return;
    room_sigil_status = 2;
    // Each six-room dungeon puts its persistent objective in local room 2.
    // This must be modulo-based: stage two and beyond have their own Sigil,
    // rather than inheriting the opening dungeon's one-time fixture.
    if (run_state_dungeon_local() != 2) return;
    room_sigil_status = 3;
    if (run_state.rift_sigils
        & RUN_STAGE_SIGIL_BIT(run_state.bosses_beaten)) return;
    room_sigil_status = 4;
    // This is normally called by procgen immediately after entity_init_all,
    // before optional enemies/loot can occupy the fixed 32-slot table. The
    // later orchestration calls are intentionally idempotent: never duplicate
    // an unclaimed fixture while a room is redrawn or resumed.
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if ((entities[i].flags & EF_ACTIVE)
            && entities[i].type == ENT_PICKUP
            && entities[i].ai_data[0] == PICKUP_RIFT_SIGIL) {
            room_sigil_status = 5;
            return;
        }
    }
    {
        u8 sigil = pickup_spawn(PICKUP_RIFT_SIGIL, FIX8(80), FIX8(64));
        if (sigil != 0xFF) {
            room_sigil_status = 5;
            entities[sigil].sprite_tile = SPR_ITEM_ORB;
            entities[sigil].palette = 0x06;
            entities[sigil].state_timer = 0;
        }
    }
}

// Stage-specific OBJ identity is independent of the shared enemy/player
// tiles. In-place room transitions must refresh it explicitly; otherwise the
// stage-0 Colossus art and tint remain resident for the entire run.
static void room_load_stage_obj_identity(void) {
    u8 stage = room_stage();
    palette_obj_load(6, boss_stage_pal[stage]);
    tiles_load_miniboss(stage);
    tiles_load_boss_big(stage);
}

static void play_stage_music(void) {
    u8 stage = (u8)(run_state.bosses_beaten % MUSIC_STAGE_COUNT);
    // Doorways within a stage must not reset the exploration loop.  Besides
    // sounding repetitive, the reset made a long room-to-room trek feel like
    // a string of disconnected screens.  A real track change (boss exit,
    // world gate, new stage) still takes effect immediately below.
    if (music_track_id == stage) return;
    music_stage_number = stage;
    music_play_stage();
}

static void play_boss_music(void) {
    u8 stage = (u8)(run_state.bosses_beaten % MUSIC_STAGE_COUNT);
    if (music_track_id == (u8)(MUSIC_BOSS_BASE + stage)) return;
    music_stage_number = stage;
    music_play_boss();
}

// Crawler (enemy) palette — blue, with one accent
static const u16 crawler_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555( 8, 12, 28),
    BGR555( 4,  6, 20),
    BGR555(20, 24, 31),
};

// Skeleton — bone white (OBJ palette 0)
static const u16 skeleton_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(28, 28, 26),
    BGR555(13, 13, 15),
    BGR555(30, 20, 18),
};

// Orc — moss green (OBJ palette 7)
static const u16 orc_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(12, 22,  8),
    BGR555( 5, 10,  4),
    BGR555(27, 13,  6),
};

// Stone Sentinel (mini-boss) palette — granite grey with bright accent
static const u16 sentinel_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(18, 18, 22),
    BGR555( 8,  8, 12),
    BGR555(28, 24, 14),
};

// (Per-stage large-boss palettes now come from the generated stage
// tables — boss_stage_pal in stages.h.)

// Bullet palette — bright gold
static const u16 bullet_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(31, 24,  0),
    BGR555(28, 16,  0),
    BGR555(31, 31,  4),
};

// Heart pickup palette (red). Color 3 is unused by the heart sprite —
// it doubles as the Bomber's lit fuse and the weapon orb's glow core.
static const u16 heart_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(31, 12, 12),
    BGR555(16,  4,  4),
    BGR555(31, 26,  6),
};

// Coin pickup palette (gold)
static const u16 coin_palette[4] = {
    BGR555( 0,  0,  0),
    BGR555(31, 24,  4),
    BGR555(18, 12,  0),
    BGR555(31, 31, 14),
};

static u8 is_walkable_at(i16 px, i16 py) {
    return room_tile_walkable(room_tile_at_px(px, py));
}

// Most scenery deliberately uses a Zelda-style feet collision box, allowing
// the upper sprite to overlap a wall.  Crates and the small stone pillars are
// physical objects, though: entering either through its lower edge looks like
// clipping through it.  Treat their whole visible body as solid.
static u8 is_full_body_obstacle_at(i16 px, i16 py) {
    u8 t = room_tile_at_px(px, py);
    return (t == BGT_PILLAR
         || t == BGT_BLOCK || t == BGT_BLOCK_TR
         || t == BGT_BLOCK_BL || t == BGT_BLOCK_BR);
}

// A 12px-wide collision box can straddle three 8px tiles. Checking only its
// corners lets a one-tile pillar sit invisibly beneath the body's centre:
// the hero can walk through its lower edge and become trapped on the far
// side. Sample the centre column as well as both edges for every move.
static u8 player_feet_blocked_at(i16 x, i16 y) {
    u8 n = 0;
    if (!is_walkable_at(x + 2,  y + 8))  n++;
    if (!is_walkable_at(x + 8,  y + 8))  n++;
    if (!is_walkable_at(x + 13, y + 8))  n++;
    if (!is_walkable_at(x + 2,  y + 15)) n++;
    if (!is_walkable_at(x + 8,  y + 15)) n++;
    if (!is_walkable_at(x + 13, y + 15)) n++;
    return n;
}

static u8 player_body_obstacles_at(i16 x, i16 y) {
    u8 n = 0;
    if (is_full_body_obstacle_at(x + 2,  y))     n++;
    if (is_full_body_obstacle_at(x + 8,  y))     n++;
    if (is_full_body_obstacle_at(x + 13, y))     n++;
    if (is_full_body_obstacle_at(x + 2,  y + 7)) n++;
    if (is_full_body_obstacle_at(x + 8,  y + 7)) n++;
    if (is_full_body_obstacle_at(x + 13, y + 7)) n++;
    return n;
}

static u8 player_feet_walkable_at(i16 x, i16 y) {
    return player_feet_blocked_at(x, y) == 0;
}

// Knockback can put a body a few pixels inside scenery even though ordinary
// input cannot enter it. Permit movement until that exceptional overlap is
// clear; an unobstructed player can still never take the first step into a
// solid tile. Requiring the sampled overlap count to decrease every pixel
// creates another trap when the left/centre/right probes change tile columns.
static u8 player_horizontal_step_allowed(i16 nx, i16 y) {
    u8 next = player_feet_blocked_at(nx, y);
    if (next == 0) return 1;
    {
        u8 current = player_feet_blocked_at(player.x, y);
        return current != 0;
    }
}

static u8 player_vertical_step_allowed(i16 x, i16 ny) {
    u8 next = (u8)(player_feet_blocked_at(x, ny)
        + player_body_obstacles_at(x, ny));
    if (next == 0) return 1;
    {
        u8 current = (u8)(player_feet_blocked_at(x, player.y)
            + player_body_obstacles_at(x, player.y));
        return current != 0;
    }
}

// A spike is a readable positional tax, never a soft-lock. Contact can occur
// after an enemy knockback or at a sub-tile seam where the player's attempted
// escape is still resolving. When an immediately adjacent body position is
// clear of spikes, stumble there with the same one-time hit that started the
// recovery window. Dense spike fields retain their danger—this only prevents
// repeated unavoidable damage while a safe lane is already beside the hero.
static void room_stumble_off_hazard(void) {
    static const i8 dx[4] = { 0, 8, 0, -8 };
    static const i8 dy[4] = { -8, 0, 8, 0 };
    u8 i;
    for (i = 0; i < 4; ++i) {
        ppos_t nx = (ppos_t)(player.x + dx[i]);
        ppos_t ny = (ppos_t)(player.y + dy[i]);
        if (room_tile_at_px(nx + 8, ny + 12) == BGT_SPIKES) continue;
        if (player_feet_walkable_at(nx, ny)) {
            player.x = nx;
            player.y = ny;
            return;
        }
    }
}

static const u16 outdoor_floor_pal[4] = {
    BGR555(2,5,2), BGR555(6,15,6), BGR555(12,23,9), BGR555(22,29,16)
};
static const u16 outdoor_wall_pal[4] = {
    BGR555(1,4,2), BGR555(4,10,4), BGR555(8,18,7), BGR555(18,25,11)
};
static const u16 outdoor_crystal_pal[4] = {
    BGR555(1,5,6), BGR555(4,14,18), BGR555(10,24,29), BGR555(27,31,31)
};
static const u16 outdoor_door_pal[4] = {
    BGR555(4,2,1), BGR555(11,6,2), BGR555(21,13,5), BGR555(31,24,12)
};
static const u16 outdoor_alert_pal[4] = {
    BGR555(4,2,0), BGR555(14,7,1), BGR555(27,16,3), BGR555(31,29,14)
};

static u8 room_is_outdoor(void) {
    return (run_state.world_mode || RUN_ROOM_IS_TOWN(run_state.room_counter)) ? 1 : 0;
}

static void room_load_environment_palettes(void) {
    if (room_is_outdoor()) {
        palette_bg_load(BGPAL_FLOOR, outdoor_floor_pal);
        palette_bg_load(BGPAL_WALL, outdoor_wall_pal);
        palette_bg_load(BGPAL_CRYSTAL, outdoor_crystal_pal);
        palette_bg_load(BGPAL_DOOR, outdoor_door_pal);
        palette_bg_load(BGPAL_CRACK, outdoor_alert_pal);
    } else {
        const u16 (*sp)[4] = stage_pal[room_stage()];
        palette_bg_load(BGPAL_FLOOR, sp[0]);
        palette_bg_load(BGPAL_WALL, sp[1]);
        palette_bg_load(BGPAL_CRYSTAL, sp[2]);
        palette_bg_load(BGPAL_DOOR, sp[3]);
        palette_bg_load(BGPAL_CRACK, stage_pal_crack);
    }
}

// Halve each 5-bit channel: pause-dim without storing dim palettes.
static void palette_bg_load_dimmed(u8 slot, const u16 *pal) {
    u16 tmp[4];
    u8 i;
    for (i = 0; i < 4; ++i) tmp[i] = (u16)((pal[i] >> 1) & 0x3DEF);
    palette_bg_load(slot, tmp);
}

static void room_apply_pause_palettes(u8 dim) {
    const u16 (*sp)[4] = stage_pal[room_stage()];
    if (room_is_outdoor()) {
        if (dim) {
            palette_bg_load_dimmed(BGPAL_FLOOR, outdoor_floor_pal);
            palette_bg_load_dimmed(BGPAL_WALL, outdoor_wall_pal);
            palette_bg_load_dimmed(BGPAL_CRYSTAL, outdoor_crystal_pal);
            palette_bg_load_dimmed(BGPAL_DOOR, outdoor_door_pal);
        } else {
            room_load_environment_palettes();
        }
        return;
    }
    if (dim) {
        palette_bg_load_dimmed(BGPAL_FLOOR,   sp[0]);
        palette_bg_load_dimmed(BGPAL_WALL,    sp[1]);
        palette_bg_load_dimmed(BGPAL_CRYSTAL, sp[2]);
        palette_bg_load_dimmed(BGPAL_DOOR,    sp[3]);
    } else {
        palette_bg_load(BGPAL_FLOOR,   sp[0]);
        palette_bg_load(BGPAL_WALL,    sp[1]);
        palette_bg_load(BGPAL_CRYSTAL, sp[2]);
        palette_bg_load(BGPAL_DOOR,    sp[3]);
    }
}

// Rewrite authored cardinal thresholds after a seal is lifted. Ordinary graph
// cells must not gain fake doors into nonexistent neighbours; a cleared boss
// deliberately opens every edge because any threshold descends to Riftwild.
// Called at the top of vblank so the handful of VRAM writes land safely.
static void room_unseal_doors(void) {
    static const u8 dxs[4][2] = {
        { 9, 10 }, { ROOM_W - 1, ROOM_W - 1 },
        { 9, 10 }, { 0, 0 },
    };
    static const u8 dys[4][2] = {
        { 0, 0 }, { 8, 9 },
        { ROOM_H - 1, ROOM_H - 1 }, { 8, 9 },
    };
    u8 dir, half;
    for (dir = 0; dir < 4; ++dir) {
        if (!run_state_was_cleared_boss()
            && run_state_dungeon_neighbor(dir) == 0xFF) continue;
        if (dir == DIR_E && room_world_width > ROOM_VIEW_W_PX) continue;
        for (half = 0; half < 2; ++half)
            room_tilemap[dys[dir][half]][dxs[dir][half]] = BGT_DOOR;
    }
    wait_vbl_done();
    {
        u8 door = BGT_DOOR, attr = BGPAL_DOOR;
        VBK_REG = 0;
        for (dir = 0; dir < 4; ++dir) {
            if (!run_state_was_cleared_boss()
                && run_state_dungeon_neighbor(dir) == 0xFF) continue;
            if (dir == DIR_E && room_world_width > ROOM_VIEW_W_PX) continue;
            for (half = 0; half < 2; ++half)
                set_bkg_tiles(dxs[dir][half], dys[dir][half], 1, 1, &door);
        }
        VBK_REG = 1;
        for (dir = 0; dir < 4; ++dir) {
            if (!run_state_was_cleared_boss()
                && run_state_dungeon_neighbor(dir) == 0xFF) continue;
            if (dir == DIR_E && room_world_width > ROOM_VIEW_W_PX) continue;
            for (half = 0; half < 2; ++half)
                set_bkg_tiles(dxs[dir][half], dys[dir][half], 1, 1, &attr);
        }
        VBK_REG = 0;
    }
    if (procgen_current_room_is_boss
        && room_world_width > ROOM_VIEW_W_PX)
        tiles_open_crystal_far_exit();
}

// Single-tile rewrite (tile + attr) at the top of vblank.
static void room_set_tile_vbl(u8 tx, u8 ty, u8 t, u8 attr) {
    room_tilemap[ty][tx] = t;
    wait_vbl_done();
    VBK_REG = 0;
    set_bkg_tiles(tx, ty, 1, 1, &t);
    VBK_REG = 1;
    set_bkg_tiles(tx, ty, 1, 1, &attr);
    VBK_REG = 0;
}

void room_break_crystal(u8 tx, u8 ty) BANKED {
    // Shatter a crystal tile: floor it, ~25% of shards hold a +1 MP wisp
    // (crystals are the world's mana nodes).
    if (tx >= ROOM_W || ty >= ROOM_H) return;
    if (room_tilemap[ty][tx] != BGT_CRYSTAL) return;
    room_set_tile_vbl(tx, ty, BGT_FLOOR, BGPAL_FLOOR);
    sfx_play(SFX_HIT);
    if (rng_next_u8() < 64) {
        pickup_spawn_mp(FIX8((i16)tx * 8), FIX8((i16)ty * 8));
    }
}

void room_break_pot(u8 tx, u8 ty) BANKED {
    // Smash a pot: floor it and roll a drop (heart / coin / nothing).
    if (tx >= ROOM_W || ty >= ROOM_H) return;
    if (room_tilemap[ty][tx] != BGT_POT) return;
    room_set_tile_vbl(tx, ty, BGT_FLOOR, BGPAL_FLOOR);
    sfx_play(SFX_HIT);
    {
        u8 r = rng_next_u8();
        if (r < 0x50)      pickup_spawn(PICKUP_HEART_HALF,
                               FIX8((i16)tx * 8), FIX8((i16)ty * 8));   // 31%
        else if (r < 0xC0) pickup_spawn(PICKUP_COIN_1,
                               FIX8((i16)tx * 8), FIX8((i16)ty * 8));   // 44%
        // else nothing (25%)
    }
}

void room_open_secret(u8 tx, u8 ty) BANKED {
    u8 tx2 = tx, ty2 = ty;
    if (tx >= ROOM_W || ty >= ROOM_H) return;
    // Open a second tile along the wall so the doorway is 16px wide
    // (cracks spawn at 2..N-3, so the +1 neighbor is never a corner).
    if (ty == 0 || ty == ROOM_H - 1) tx2 = (u8)(tx + 1);
    else                             ty2 = (u8)(ty + 1);
    room_set_tile_vbl(tx, ty, BGT_DOOR, BGPAL_DOOR);
    room_set_tile_vbl(tx2, ty2, BGT_DOOR, BGPAL_DOOR);
    secret_door_x = tx;   secret_door_y = ty;
    secret_door_x2 = tx2; secret_door_y2 = ty2;
    sfx_play(SFX_DOOR);
}

// CGB palette attribute per tile id
static u8 attr_for_tile(u8 t) {
    switch (t) {
        case BGT_WALL:
        case BGT_PILLAR:
        case BGT_ROOF:
        case BGT_FENCE:
        case BGT_TREE:
        case BGT_WILD_STONE: return BGPAL_WALL;
        case BGT_WALL_CRACK:
        case BGT_SPIKES:
        case BGT_BOSS_GATE_L:
        case BGT_BOSS_GATE_R:
        case BGT_BOSS_GATE_TOP:
        case BGT_BOSS_GATE_BOTTOM:
            return BGPAL_CRACK;   // amber danger signal
        case BGT_BLOCK:
        case BGT_BLOCK_TR:
        case BGT_BLOCK_BL:
        case BGT_BLOCK_BR:
            return BGPAL_WALL;      // secret cairns blend into the landscape
        case BGT_POT:
        case BGT_SWITCH:  return BGPAL_DOOR;      // gold-ish, reads as interactive
        case BGT_CRYSTAL:
        case BGT_PORTAL:
        case BGT_WILD_FLOWER:
        case BGT_WILD_WATER: return BGPAL_CRYSTAL;
        case BGT_WILD_STUMP: return BGPAL_DOOR;
        case BGT_DOOR:    return (room_combat_sealed || room_puzzle_locked)
                                  ? BGPAL_CRACK : BGPAL_DOOR;
        case BGT_GRASS:
        case BGT_PATH:    return BGPAL_FLOOR;
        case BGT_COLOSSUS_SCALE:
        case BGT_COLOSSUS_EDGE_L:
        case BGT_COLOSSUS_EDGE_R:
        case BGT_COLOSSUS_HORN:
            return BGPAL_WALL;
        case BGT_COLOSSUS_VOID:
        case BGT_COLOSSUS_RUNE:
        case BGT_COLOSSUS_MAW:
            return BGPAL_CRYSTAL;
        case BGT_COLOSSUS_EYE:
        case BGT_COLOSSUS_FANG:
            return BGPAL_CRACK;
        default:
            // Shop price tags glow amber (crack palette) for readability
            if (t == HUD_COIN || (t >= HUD_DIGIT_0 && t <= HUD_DIGIT_0 + 9)) {
                return BGPAL_CRACK;
            }
            return BGPAL_FLOOR;
    }
}

static u8 room_door_direction(u8 x, u8 y) {
    if (y == 0) return DIR_N;
    if (x == ROOM_W - 1) return DIR_E;
    if (y == ROOM_H - 1) return DIR_S;
    if (x == 0) return DIR_W;
    return DIR_NONE;
}

static void room_hold_at_door(u8 dir, u8 sound, u8 shake_frames) {
    if (dir == DIR_N) player.y = 0;
    else if (dir == DIR_S) player.y = (ppos_t)(room_world_height - 16);
    else if (dir == DIR_W) player.x = 0;
    else player.x = (ppos_t)(room_world_width - 16);
    if (door_bump_cd == 0) {
        door_bump_cd = 20;
        sfx_play(sound);
        room_shake(1, shake_frames);
    }
}

static u8 is_forward_boss_door(u8 x, u8 y, u8 tile) {
    u8 dir;
    if (tile != BGT_DOOR || run_state.world_mode
        || RUN_ROOM_IS_TOWN(run_state.room_counter)) return 0;
    dir = room_door_direction(x, y);
    if (dir == DIR_NONE) return 0;
    return run_state_dungeon_neighbor(dir)
        == run_state_boss_room(run_state.bosses_beaten);
}

static u8 attr_for_room_tile(u8 x, u8 y, u8 tile) {
    // The paired phase gate uses ordinary pillar/floor geometry with a
    // persistent dungeon color. This keeps collision simple while making a
    // switch in one room visibly raise/lower the wall in the next.
    if (room_puzzle_kind == PUZZLE_PHASE_GATE
        && y == room_puzzle_visual_y && x >= 2 && x < ROOM_W - 2)
        return (run_state.dungeon_phase & RUN_PHASE_OPEN_BIT)
            ? BGPAL_CRYSTAL : BGPAL_CRACK;
    return attr_for_tile(tile);
}

// One-shot puzzle payoff shared by hero-pressed and crate-pressed plates.
// The pressure plates are deliberately placed at x=7 or x=12 by procgen:
// opening the matching two-wide north-wall gap therefore never overlaps the
// centered progression door. The result is a real Zelda-style discovery --
// a side passage to the generated secret cache -- instead of a loose coin
// that makes the nearby cairn read as an arbitrary movable prop.
static void activate_switch(u8 tx, u8 ty) {
    // A cairn already occupies the plate when the legitimate solve arrives;
    // do not punch an invisible floor quadrant through its freshly moved art.
    if (room_tilemap[ty][tx] == BGT_SWITCH)
        room_set_tile_vbl(tx, ty, BGT_FLOOR, BGPAL_FLOOR);
    room_open_secret(tx, 0);
    sfx_play(SFX_PUZZLE);
}

static void draw_room_tilemap(void) {
    u8 x, y;
    u8 attr_row[ROOM_W];
    u8 tile_row[ROOM_W];
    for (y = 0; y < ROOM_H; ++y) {
        // Tile indices (VRAM bank 0)
        for (x = 0; x < ROOM_W; ++x)
            tile_row[x] = room_tilemap[y][x];
        VBK_REG = 0;
        set_bkg_tiles(0, y, ROOM_W, 1, tile_row);
        // Palette attributes (VRAM bank 1)
        for (x = 0; x < ROOM_W; ++x)
            attr_row[x] = attr_for_room_tile(x, y, room_tilemap[y][x]);
        VBK_REG = 1;
        set_bkg_tiles(0, y, ROOM_W, 1, attr_row);
    }
    // The banked renderer scans only the four edges once, then projects the
    // 16x16 seal over every forward threshold. Keeping presentation code out
    // of this crowded bank preserves the cartridge headroom floor.
    tiles_draw_boss_cue(run_state.entered_from);
    // Colossal arenas may breathe through a bounded 0..3px camera drift.
    // Populate the first offscreen column and row with wall art so Crystal,
    // Serpent, and Void never expose stale streamed-room VRAM at the right or
    // bottom edge. Keeping this common to every boss also makes future
    // stage-specific camera choreography safe by construction.
    if (run_state.world_mode) {
        tiles_prepare_riftwild_wide_field();
    } else if (procgen_current_room_is_boss && room_world_width > ROOM_VIEW_W_PX) {
        tiles_prepare_crystal_wide_arena();
    } else if (procgen_current_room_is_boss) {
        tiles_prepare_colossal_edges();
    }
    VBK_REG = 0;
    // Compose the outdoor identity after ordinary terrain. It remains a
    // display-only overlay: room_tilemap still owns grass/path collision.
    if (run_state.world_mode) tiles_draw_area_label(1);
    else if (RUN_ROOM_IS_TOWN(run_state.room_counter))
        tiles_draw_area_label((u8)(2 + run_state.world_return_screen));
}

// A 20-tile room is wider than half the 32-tile BG map, so two complete
// screens cannot simply sit side by side. For an eastward slide, stage the
// first 12 destination columns at map x=20..31; once the first 8 source
// columns have scrolled offscreen, recycle x=0..7 for the remaining columns.
// This is the same streamed-map trick used by hardware-era room scrollers.
// Both axes share the same hidden destination staging: LCD-off writes are
// safe at any time and avoid spending one VBlank per row before the motion.
static void room_stage_columns(u8 dst_x, u8 src_x, u8 width) {
    u8 y, x, attrs[12];
    DISPLAY_OFF;
    for (y = 0; y < ROOM_H; ++y) {
        for (x = 0; x < width; ++x)
            attrs[x] = attr_for_room_tile((u8)(src_x + x), y,
                room_tilemap[y][(u8)(src_x + x)]);
        VBK_REG = 0; set_bkg_tiles(dst_x, y, width, 1, &room_tilemap[y][src_x]);
        VBK_REG = 1; set_bkg_tiles(dst_x, y, width, 1, attrs);
    }
    VBK_REG = 0;
    DISPLAY_ON;
}

static void room_stage_rows(u8 dst_y, u8 src_y, u8 height) {
    u8 row, x, attrs[ROOM_W];
    DISPLAY_OFF;
    for (row = 0; row < height; ++row) {
        u8 y = (u8)(src_y + row);
        for (x = 0; x < ROOM_W; ++x)
            attrs[x] = attr_for_room_tile(x, y, room_tilemap[y][x]);
        VBK_REG = 0; set_bkg_tiles(0, (u8)(dst_y + row), ROOM_W, 1, room_tilemap[y]);
        VBK_REG = 1; set_bkg_tiles(0, (u8)(dst_y + row), ROOM_W, 1, attrs);
    }
    VBK_REG = 0;
    DISPLAY_ON;
}

// Slides are blocking room-code loops, so the outer game loop cannot reach
// audio_tick() while they run. Advance the sequencers on each real VBlank;
// otherwise CH2/CH3 sustain one stale note for the entire transition.
static void room_transition_vbl(void) {
    wait_vbl_done();
    audio_tick();
}

static void room_slide_east(void) {
    u8 y, x, step;
    u8 attrs[12];
    room_stage_columns(20, 0, 12);
    for (step = 1; step <= 20; ++step) {
        if (step == 8) {
            for (y = 0; y < ROOM_H; ++y) {
                for (x = 0; x < 8; ++x)
                    attrs[x] = attr_for_room_tile((u8)(x + 12), y, room_tilemap[y][x + 12]);
                VBK_REG = 0; set_bkg_tiles(0, y, 8, 1, &room_tilemap[y][12]);
                VBK_REG = 1; set_bkg_tiles(0, y, 8, 1, attrs);
            }
            VBK_REG = 0;
        }
        room_transition_vbl();
        SCX_REG = (u8)(step << 3);
    }
    // Normalize the streamed map while blanked so gameplay updates retain
    // their straightforward x=0..19 coordinate system after the slide.
    DISPLAY_OFF;
    SCX_REG = room_camera_x;
    draw_room_tilemap();
}

// Mirrored westward streamer. Destination columns 8..19 live at x=20..31
// until the camera has moved 96px left; source x=12..19 are then safely
// behind the viewport and become destination columns 0..7.
static void room_slide_west(void) {
    u8 y, x, step;
    u8 attrs[12];
    room_stage_columns(20, 8, 12);
    for (step = 1; step <= 20; ++step) {
        if (step == 12) {
            for (y = 0; y < ROOM_H; ++y) {
                for (x = 0; x < 8; ++x)
                    attrs[x] = attr_for_room_tile(x, y, room_tilemap[y][x]);
                VBK_REG = 0; set_bkg_tiles(12, y, 8, 1, room_tilemap[y]);
                VBK_REG = 1; set_bkg_tiles(12, y, 8, 1, attrs);
            }
            VBK_REG = 0;
        }
        room_transition_vbl();
        SCX_REG = (u8)(0 - (i16)(step << 3));
    }
    DISPLAY_OFF;
    SCX_REG = room_camera_x;
    draw_room_tilemap();
}

// Vertical rooms are 17 tiles high, leaving 15 free map rows. Stage those
// first, then recycle the two source rows once the scroll has carried them
// offscreen. The HUD is a WINDOW layer, so it remains fixed during the slide.
static void room_slide_south(void) {
    u8 y, x, step, attrs[ROOM_W];
    room_stage_rows(17, 0, 15);
    for (step = 1; step <= 17; ++step) {
        if (step == 2) {
            for (y = 15; y < 17; ++y) {
                for (x = 0; x < ROOM_W; ++x)
                    attrs[x] = attr_for_room_tile(x, y, room_tilemap[y][x]);
                VBK_REG = 0; set_bkg_tiles(0, (u8)(y - 15), ROOM_W, 1, room_tilemap[y]);
                VBK_REG = 1; set_bkg_tiles(0, (u8)(y - 15), ROOM_W, 1, attrs);
            }
            VBK_REG = 0;
        }
        room_transition_vbl();
        SCY_REG = (u8)(step << 3);
    }
    DISPLAY_OFF; SCX_REG = room_camera_x; SCY_REG = room_camera_y; draw_room_tilemap();
}

static void room_slide_north(void) {
    u8 y, x, step, attrs[ROOM_W];
    room_stage_rows(17, 2, 15);
    for (step = 1; step <= 17; ++step) {
        if (step == 2) {
            for (y = 0; y < 2; ++y) {
                for (x = 0; x < ROOM_W; ++x)
                    attrs[x] = attr_for_room_tile(x, y, room_tilemap[y][x]);
                VBK_REG = 0; set_bkg_tiles(0, (u8)(y + 15), ROOM_W, 1, room_tilemap[y]);
                VBK_REG = 1; set_bkg_tiles(0, (u8)(y + 15), ROOM_W, 1, attrs);
            }
            VBK_REG = 0;
        }
        room_transition_vbl();
        SCY_REG = (u8)(0 - (i16)(step << 3));
    }
    DISPLAY_OFF; SCX_REG = room_camera_x; SCY_REG = room_camera_y; draw_room_tilemap();
}

static void place_player_sprite(void) {
    // 16x16 player metasprite — 4 OAM slots, anchored at (x+8, y+16) per GBDK
    if (arrival_sprite_grace == 0 && player.iframes > 0
        && (player.iframes & 0x04)) {
        move_sprite(0, 0, 0);
        move_sprite(1, 0, 0);
        move_sprite(2, 0, 0);
        move_sprite(3, 0, 0);
    } else {
        u8 sx = (u8)((i16)player.x - room_camera_x + 8);
        u8 sy = (u8)((i16)player.y - room_camera_y + 16);
        u8 class_id = (player.class_id < 5) ? player.class_id : 0;
        u8 step = (player.anim_frame & 0x04) ? 1 : 0;
        u8 pose_base = room_transform_ticks ? SPR_CLASS_ASCENDED_BASE
            : (step ? SPR_CLASS_WALK_BASE : SPR_CLASS_BASE);
        u8 base = (u8)(pose_base
                       + (u8)(class_id * SPR_CLASS_STRIDE));
        set_sprite_tile(0, (u8)(base + 0));
        set_sprite_tile(1, (u8)(base + 1));
        set_sprite_prop(0, 0x01);
        set_sprite_prop(1, 0x01);
        move_sprite(0, sx,         sy);
        move_sprite(1, (u8)(sx+8), sy);
        set_sprite_tile(2, (u8)(base + 2));
        set_sprite_tile(3, (u8)(base + 3));
        set_sprite_prop(2, 0x01);
        set_sprite_prop(3, 0x01);
        move_sprite(2, sx,         (u8)(sy+8));
        move_sprite(3, (u8)(sx+8), (u8)(sy+8));
    }
}

// Get the 8-dir index from current/pressed input. Returns 0..7 or 0xFF if none.
static u8 input_to_dir8(u8 keys) {
    u8 d = 0xFF;
    if (keys & J_UP) {
        if      (keys & J_RIGHT) d = 1;   // NE
        else if (keys & J_LEFT)  d = 7;   // NW
        else                     d = 0;   // N
    } else if (keys & J_DOWN) {
        if      (keys & J_RIGHT) d = 3;   // SE
        else if (keys & J_LEFT)  d = 5;   // SW
        else                     d = 4;   // S
    } else if (keys & J_RIGHT) {
        d = 2;
    } else if (keys & J_LEFT) {
        d = 6;
    }
    return d;
}

// Map 4-dir facing to 8-dir for fallback when no D-pad pressed at fire time
static u8 facing_to_dir8(u8 facing) {
    switch (facing) {
        case FACE_N: return 0;
        case FACE_E: return 2;
        case FACE_S: return 4;
        case FACE_W: return 6;
        default:     return 4;
    }
}

void room_enter(void) {
    g_vbl_ticks = 0;   // run clock: don't count time spent off-room
    DISPLAY_OFF;
    room_paused = 0;

    room_load_environment_palettes();
    palette_obj_load(0, skeleton_palette);
    palette_obj_load(1, class_obj_palettes[player.class_id < 5 ? player.class_id : 0]);
    palette_obj_load(2, bullet_palette);
    palette_obj_load(3, crawler_palette);
    palette_obj_load(4, heart_palette);
    palette_obj_load(5, coin_palette);
    palette_obj_load(7, orc_palette);

    tiles_load_dungeon_bg();              // authored dungeon tileset (slot 0 = void)
    tiles_load_boss_cue_bg();             // unmistakable sanctuary threshold
    if (room_is_outdoor())
        tiles_load_area_labels();         // live Riftwild/village identifiers
    tiles_load_colossus_bg(room_stage()); // phase-specific BG projection atlas
    tiles_load_pickup_sprites();
    tiles_load_all_class_sprites();       // 5 × 16x16 player metasprites (slots 0..19)
    tiles_load_all_enemy_sprites();       // small, specialist, and bruiser art
    if (RUN_ROOM_IS_TOWN(run_state.room_counter)) {
        room_load_town_resident_identity();
    }

    hud_init();
    hud_show();
    shop_offer_visible = 0;
    room_has_shop_wares = 0;
    hud_clear_offer();

    // Player metasprite — 4 tiles starting at class-specific base
    {
        u8 base = (u8)(SPR_CLASS_BASE + (u8)(player.class_id * SPR_CLASS_STRIDE));
        set_sprite_tile(0, (u8)(base + 0));    // TL
        set_sprite_tile(1, (u8)(base + 1));    // TR
        set_sprite_tile(2, (u8)(base + 2));    // BL
        set_sprite_tile(3, (u8)(base + 3));    // BR
        set_sprite_prop(0, 0x01);
        set_sprite_prop(1, 0x01);
        set_sprite_prop(2, 0x01);
        set_sprite_prop(3, 0x01);
    }
    player.facing        = FACE_S;
    player.fire_cooldown = 0;

    if (room_resume_flag) {
        // Returning from the pack screen: keep the existing tilemap, entities
        // and player position — just redraw. Do NOT regenerate or restart music.
        room_resume_flag = 0;
        room_refresh_shop_wares();
        room_load_dynamic_fx_identity();
        draw_room_tilemap();
        entity_draw_all_world();
        place_player_sprite();
        SCX_REG = room_camera_x;
        SCY_REG = room_camera_y;
        // Music kept running through the pack screen (room_exit no longer stops
        // it), so there's nothing to restart here — resume is seamless.
        SHOW_SPRITES;
        SHOW_BKG;
        DISPLAY_ON;
        return;
    }

    // A brand-new run owns a brand-new fractional clock. Normal room changes
    // retain it so transition screens cannot shave partial seconds either.
    if (run_state.room_counter == 0 && run_state.run_timer == 0)
        run_clock_fraction = 0;

    player.iframes       = 0;

    // Select audio before the banked generator. The destination counter is
    // already authoritative, while post-bcall audio calls are unreliable on
    // this SDCC build (and previously collapsed later stages to track 0).
    if (run_state_is_boss_room()) {
        play_boss_music();
    } else {
        play_stage_music();
    }

    // Procgen builds the tilemap + spawns enemies + positions player
    procgen_generate_current_room();
    arrival_sprite_grace = 60;
    room_refresh_shop_wares();
    room_load_dynamic_fx_identity();
    room_spawn_progression_fixture();
    puzzle_prepare_room_role();
    boss_threshold_warned = 0;
    room_load_environment_palettes();
    draw_room_tilemap();
    place_player_sprite();

    secret_door_x = secret_door_y = 0xFF;
    secret_door_x2 = secret_door_y2 = 0xFF;
    if (procgen_current_room_is_boss) {
        sfx_play(SFX_ROAR);
        // Entry drama: the arena starts dark and trembling, then the
        // light pops as the fight begins.
        room_apply_pause_palettes(1);
        stage_fade = 30;
        room_shake(1, 24);
    }

    hostiles_prev = 0;   // fresh room: re-arm the clear chime
    hostiles_now = 0;
    door_bump_cd = 0;

    // Stage-entry reveal: first room of a new stage (or of a fresh run)
    // starts with dimmed palettes and pops to full ~0.4s in.
    if (run_state.room_counter == 0) stage_seen = 0xFF;
    if (room_stage() != stage_seen) {
        stage_seen = room_stage();
        room_load_stage_obj_identity();
        // The stage upload changes several multiplexed OBJ ranges. Restore
        // the current combat identity afterward so a streamed stage boundary
        // cannot retain the previous stage's slot-79 specialist (or a town
        // callout) for the first room of the new dungeon.
        room_load_dynamic_fx_identity();
        stage_fade = 26;
        room_apply_pause_palettes(1);   // start dimmed
    }

    // Suspend save: every room entry snapshots the run (battery SRAM).
    sram_save_run();

    SHOW_SPRITES;
    SHOW_BKG;
    DISPLAY_ON;
}

void room_exit(void) {
    HIDE_SPRITES;
    hud_hide();
    // Settle any in-flight shake so the next screen isn't skewed
    shake_timer = 0;
    SCX_REG = 0;
    SCY_REG = 0;
    // NOTE: do NOT wipe entities or stop music here. Opening the pack screen
    // (START) exits the room and returns via the resume path, which expects
    // the room's entities/player/music to be intact. Real room changes
    // re-init entities in procgen_generate_current_room(). Leaving music
    // running also avoids a restart blip every time the pack is toggled.
}

screen_id_t room_tick(u8 keys, u8 pressed) {
    if (door_bump_cd) door_bump_cd--;
    if (arrival_sprite_grace) arrival_sprite_grace--;
    // Consume active-room wall time before any route can leave this screen.
    // This preserves the fraction earned before START/SELECT was pressed.
    room_clock_consume();
    // ---- START opens PACK; SELECT opens the generated field compass.
    if (pressed & J_START) {
        return SCREEN_INVENTORY;
    }
    if (pressed & J_SELECT) {
        return SCREEN_MAP;
    }
    // Entering the amber threshold's approach gives one low roar and tremor.
    // The room itself is a full-heal sanctuary, so this is a fair commitment
    // warning rather than an ambush or an extra confirmation dialog.
    if (!boss_threshold_warned && !procgen_current_room_is_boss
        && !run_state.world_mode
        && !RUN_ROOM_IS_TOWN(run_state.room_counter)) {
        u8 near_n = (player.y <= 16) && is_forward_boss_door(
            (u8)((player.x + 8) >> 3), 0, room_tilemap[0][(player.x + 8) >> 3]);
        u8 near_s = (player.y >= 104) && is_forward_boss_door(
            (u8)((player.x + 8) >> 3), ROOM_H - 1,
            room_tilemap[ROOM_H - 1][(player.x + 8) >> 3]);
        u8 near_w = (player.x <= 16) && is_forward_boss_door(
            0, (u8)((player.y + 12) >> 3), room_tilemap[(player.y + 12) >> 3][0]);
        u8 near_e = (player.x >= 128) && is_forward_boss_door(
            ROOM_W - 1, (u8)((player.y + 12) >> 3),
            room_tilemap[(player.y + 12) >> 3][ROOM_W - 1]);
        if (near_n || near_s || near_w || near_e) {
            boss_threshold_warned = 1;
            sfx_play(SFX_ROAR);
            room_shake(1, 12);
        }
    }
    if (room_paused) return SCREEN_SELF;
    // ---- Death beat: the world keeps animating (bullets fly, bursts
    // pop, screen shakes) but the hero is done — then GAMEOVER.
    if (death_timer) {
        if (--death_timer == 0) return SCREEN_GAMEOVER;
        if (player.iframes) player.iframes--;   // drives the flicker
        entity_update_all(0, 0);
        place_player_sprite();
        entity_draw_all_world();
        return SCREEN_SELF;
    }

    // ---- Stage-entry reveal: hold dimmed palettes briefly, then pop to
    // full brightness — a beat of "emerging into somewhere new".
    if (stage_fade) {
        if (--stage_fade == 0) room_apply_pause_palettes(0);
    }

    // ---- Low-HP danger: at one heart the HUD hearts pulse white-hot
    // and a soft heartbeat blip sounds in the quiet between shots.
    {
        static u8 lowhp_t;
        if (player.hp <= 2 && player.hp > 0) {
            lowhp_t++;
            hud_low_hp_pulse((u8)((lowhp_t & 0x10) ? 1 : 0));
            if (lowhp_t >= 96) { lowhp_t = 0; sfx_play(SFX_LOWHP); }
        } else if (lowhp_t) {
            lowhp_t = 0;
            hud_low_hp_pulse(0);
        }
    }

    // ---- Hit-stop: freeze the world a few frames on impact for weight,
    // but keep drawing so the flash/knockback is visible.
    if (g_hitstop) {
        g_hitstop--;
        place_player_sprite();
        entity_draw_all_world();
        return SCREEN_SELF;
    }

    // ---- Movement: SPD-scaled sub-pixel accumulator.
    // acc += spd; each 5 accumulated = 1 px step. spd 5 = 1.0 px/f,
    // Sauran 4 = 0.8, Wolfkin 6 = 1.2, Vespine 7 = 1.4.
    {
        u8 moved = 0;
        i8 dx = 0, dy = 0;
        u8 steps;

        if (keys & J_LEFT)  { dx = -1; player.facing = FACE_W; moved = 1; }
        if (keys & J_RIGHT) { dx = +1; player.facing = FACE_E; moved = 1; }
        if (keys & J_UP)    { dy = -1; player.facing = FACE_N; moved = 1; }
        if (keys & J_DOWN)  { dy = +1; player.facing = FACE_S; moved = 1; }

        if (moved) {
            player.move_acc = (u8)(player.move_acc + player.spd);
        }

        // ---- Dodge dash: double-tap a cardinal within ~12 frames to lunge
        // fast in that direction with brief i-frames, then a short cooldown.
        {
            u8 td = (pressed & J_LEFT)  ? (u8)'L'
                  : (pressed & J_RIGHT) ? (u8)'R'
                  : (pressed & J_UP)    ? (u8)'U'
                  : (pressed & J_DOWN)  ? (u8)'D' : 0;
            if (td) {
                if (td == tap_dir && tap_age <= 12
                    && dash_cd == 0 && dash_timer == 0) {
                    dash_timer = 7;
                    dash_cd    = 30;
                    if (player.iframes < 14) player.iframes = 14;
                    dash_dx = (td == 'L') ? -1 : (td == 'R') ? 1 : 0;
                    dash_dy = (td == 'U') ? -1 : (td == 'D') ? 1 : 0;
                    sfx_play(SFX_DOOR);   // whoosh
                    tap_dir = 0;
                } else {
                    tap_dir = td;
                    tap_age = 0;
                }
            }
            if (tap_age < 255) tap_age++;
            if (dash_cd) dash_cd--;
        }

        // While dashing, override player control with a fast wall-checked
        // lunge (3 px/frame). The rest of room_tick still runs — enemies
        // and bullets keep moving so the dash actually dodges them; the
        // dash's i-frames keep you safe. Normal movement + block-push are
        // neutralized below via moved/move_acc = 0.
        if (dash_timer) {
            u8 s;
            dash_timer--;
            for (s = 0; s < 3; ++s) {
                if (dash_dx) {
                    ppos_t nx = (ppos_t)(player.x + dash_dx);
                    if (player_horizontal_step_allowed(nx, player.y))
                        player.x = nx;
                }
                if (dash_dy) {
                    ppos_t ny = (ppos_t)(player.y + dash_dy);
                    if (player_vertical_step_allowed(player.x, ny))
                        player.y = ny;
                }
            }
            dx = 0; dy = 0; moved = 0; player.move_acc = 0;
        }

        // --- Pushable blocks: press against a block (cardinal move) and,
        //     if the tile behind it is open floor, it slides one tile.
        //     Detection probes the player's LEADING EDGE corners (not the
        //     center tile), so contact counts whenever you're actually
        //     grinding on the block, at any off-axis alignment. Input
        //     noise (a 1-frame diagonal brush) DECAYS the hold instead of
        //     restarting it — d-pads are messy. ---
        {
            u8 qualified = 0;
            u8 fx = 0, fy = 0, cur = 0;
            if (moved && ((dx != 0) != (dy != 0))) {
                // Leading-edge probes: 1px beyond the 1..6 collision box
                // on the facing side, at both cross-axis corners. When
                // flush against a block, these land inside its tile.
                i16 p1x, p1y, p2x, p2y;
                if (dx) {
                    i16 ex = (i16)(player.x + ((dx > 0) ? 14 : 1));
                    p1x = ex; p1y = (i16)(player.y + 9);
                    p2x = ex; p2y = (i16)(player.y + 14);
                } else {
                    // Crates own a full-body north face. Walls remain
                    // feet-anchored, but approaching a crate from below must
                    // probe just above the visible head rather than waiting
                    // for the feet box to overlap half its sprite.
                    i16 ey = (i16)(player.y + ((dy > 0) ? 16 : -1));
                    p1x = (i16)(player.x + 3); p1y = ey;
                    p2x = (i16)(player.x + 12); p2y = ey;
                }
                cur = (u8)((dy != 0) ? ((dy < 0) ? DIR_N : DIR_S)
                                     : ((dx < 0) ? DIR_W : DIR_E));
                {
                    u8 q1 = room_tile_at_px(p1x, p1y);
                    u8 q2 = room_tile_at_px(p2x, p2y);
                    if (q1 == BGT_BLOCK || q1 == BGT_BLOCK_TR
                        || q1 == BGT_BLOCK_BL || q1 == BGT_BLOCK_BR) {
                        fx = (u8)(p1x >> 3); fy = (u8)(p1y >> 3); qualified = 1;
                    } else if (q2 == BGT_BLOCK || q2 == BGT_BLOCK_TR
                        || q2 == BGT_BLOCK_BL || q2 == BGT_BLOCK_BR) {
                        fx = (u8)(p2x >> 3); fy = (u8)(p2y >> 3); qualified = 1;
                    }
                }
            }
            if (qualified) {
                // Resolve the crate's ORIGIN (top-left) from whichever
                // quadrant the probe touched.
                u8 ox = fx, oy = fy;
                {
                    u8 q = room_tilemap[fy][fx];
                    if (q == BGT_BLOCK_TR)      { ox = (u8)(fx - 1); }
                    else if (q == BGT_BLOCK_BL) { oy = (u8)(fy - 1); }
                    else if (q == BGT_BLOCK_BR) { ox = (u8)(fx - 1); oy = (u8)(fy - 1); }
                }
                {
                // Leading edge after an 8px slide: two cells to check
                u8 t1x, t1y, t2x, t2y;
                u8 open;
                u8 nox = (u8)(ox + dx), noy = (u8)(oy + dy);
                if (dx > 0)      { t1x = (u8)(ox + 2); t1y = oy; t2x = t1x; t2y = (u8)(oy + 1); }
                else if (dx < 0) { t1x = (u8)(ox - 1); t1y = oy; t2x = t1x; t2y = (u8)(oy + 1); }
                else if (dy > 0) { t1x = ox; t1y = (u8)(oy + 2); t2x = (u8)(ox + 1); t2y = t1y; }
                else             { t1x = ox; t1y = (u8)(oy - 1); t2x = (u8)(ox + 1); t2y = t1y; }
                open = (t1x < ROOM_W && t1y < ROOM_H && t2x < ROOM_W && t2y < ROOM_H);
                if (open) {
                    u8 a = room_tilemap[t1y][t1x], b = room_tilemap[t2y][t2x];
                    open = (a == BGT_FLOOR || a == BGT_FLOOR2 || a == BGT_FLOOR3
                            || a == BGT_SWITCH)
                        && (b == BGT_FLOOR || b == BGT_FLOOR2 || b == BGT_FLOOR3
                            || b == BGT_SWITCH);
                }
                // A 2x2 cairn needs two clear body tiles between it and a
                // threshold. Otherwise a legal shove can leave the visible
                // gold frame open but reduce its approach to an impassable
                // eight-pixel slit.
                if (open
                    && ((((nox <= 3 || nox >= 15)
                            && noy <= 10 && (u8)(noy + 1) >= 7))
                        || (((noy <= 3 || noy >= 12)
                            && nox <= 12 && (u8)(nox + 1) >= 7)))) {
                    open = 0;
                }
                // Never entomb a live enemy under the sliding crate
                if (open) {
                    u8 k;
                    for (k = 0; k < MAX_ENTITIES; ++k) {
                        u8 etx, ety;
                        if (!(entities[k].flags & EF_ACTIVE)
                            || entities[k].type != ENT_ENEMY) continue;
                        etx = (u8)((FIX8_TO_INT(entities[k].x) + 4) >> 3);
                        ety = (u8)((FIX8_TO_INT(entities[k].y) + 4) >> 3);
                        if ((etx == t1x && ety == t1y) || (etx == t2x && ety == t2y)) {
                            open = 0;
                            break;
                        }
                    }
                }
                if (open) {
                    if (push_dir == cur) push_timer++;
                    else { push_dir = cur; push_timer = 1; }
                    if (push_timer >= 10) {
                        u8 pressed_switch = (u8)(room_tilemap[t1y][t1x] == BGT_SWITCH
                                              || room_tilemap[t2y][t2x] == BGT_SWITCH);
                        u8 switch_x = (room_tilemap[t1y][t1x] == BGT_SWITCH) ? t1x : t2x;
                        u8 switch_y = (room_tilemap[t1y][t1x] == BGT_SWITCH) ? t1y : t2y;
                        // One vblank, eight tile writes: clear the old
                        // 2x2, draw the crate at its new origin.
                        room_tilemap[oy][ox]         = BGT_FLOOR;
                        room_tilemap[oy][ox + 1]     = BGT_FLOOR;
                        room_tilemap[oy + 1][ox]     = BGT_FLOOR;
                        room_tilemap[oy + 1][ox + 1] = BGT_FLOOR;
                        room_tilemap[noy][nox]         = BGT_BLOCK;
                        room_tilemap[noy][nox + 1]     = BGT_BLOCK_TR;
                        room_tilemap[noy + 1][nox]     = BGT_BLOCK_BL;
                        room_tilemap[noy + 1][nox + 1] = BGT_BLOCK_BR;
                        wait_vbl_done();
                        {
                            u8 yy, xx;
                            u8 x0 = (dx < 0) ? nox : ox;
                            u8 y0 = (dy < 0) ? noy : oy;
                            VBK_REG = 0;
                            for (yy = 0; yy < 3; ++yy)
                                for (xx = 0; xx < 3; ++xx)
                                    set_bkg_tiles((u8)(x0 + xx), (u8)(y0 + yy),
                                        1, 1, &room_tilemap[y0 + yy][x0 + xx]);
                            VBK_REG = 1;
                            for (yy = 0; yy < 3; ++yy)
                                for (xx = 0; xx < 3; ++xx) {
                                    u8 at = attr_for_room_tile((u8)(x0 + xx),
                                        (u8)(y0 + yy), room_tilemap[y0 + yy][x0 + xx]);
                                    set_bkg_tiles((u8)(x0 + xx), (u8)(y0 + yy),
                                        1, 1, &at);
                                }
                            VBK_REG = 0;
                        }
                        sfx_play(SFX_DOOR);
                        if (pressed_switch) activate_switch(switch_x, switch_y);
                        if (puzzle_on_block_moved(ox, oy)) room_unseal_doors();
                        push_timer = 0;
                    }
                } else if (push_timer) {
                    push_timer--;
                }
                }
            } else if (push_timer) {
                push_timer--;              // noise decays, never hard-resets
                if (push_timer == 0) push_dir = DIR_NONE;
            }
        }

        steps = 0;
        while (player.move_acc >= 5) { player.move_acc -= 5; steps++; }

        while (steps--) {
            // Feet-anchored wall box (Zelda convention): x+2..x+13 wide,
            // y+8..y+15 — the bottom half of the 16x16 body. The head
            // overhangs walls above; the body never buries into terrain.
            if (dx) {
                ppos_t nx = (ppos_t)(player.x + dx);
                if (player_horizontal_step_allowed(nx, player.y)) {
                    player.x = nx;
                }
            }
            if (dy) {
                ppos_t ny = (ppos_t)(player.y + dy);
                if (player_vertical_step_allowed(player.x, ny)) {
                    player.y = ny;
                }
            }
        }

        if (moved) {
            player.anim_frame = (u8)((player.anim_frame + 1) & 0x07);
        }
    }

    // ---- Weapons. Starter comes from the generated items[] entry
    // (p0=fire_rate, p1=damage, p2=projectile kind). Starter ids 0-4 map
    // to array indices 0-4 by content authoring; guarded by N_ITEMS.
    // Per-class elemental identity: Wolfkin fire, Sauran lightning,
    // Corvin shadow, Picsean ice, Vespine poison (1/4/8/2/16).
    {
        static const u8 class_element[5] = { 1, 4, 8, 2, 16 };
        const item_def_t *w =
            &items[player.starter_weapon < N_ITEMS ? player.starter_weapon : 0];
        g_shot_element = class_element[player.class_id < 5 ? player.class_id : 0];

        // A+B at full MP: SPIRIT CONVERGENCE. This is deliberately shared
        // across all five vessels—the common oath underneath their different
        // kits. Full-meter requirement prevents accidental chord activation.
        if ((pressed & (J_A | J_B)) == (J_A | J_B)
            && player.mp == player.mp_max && player.active_charge == 0) {
            u8 sd;
            for (sd = 0; sd < 8; ++sd) {
                u8 shot = projectile_spawn_player(dir8_dx[sd], dir8_dy[sd],
                    (u8)(w->p1 + player.atk + 2), PROJ_SPIKE);
                if (shot != 0xFF) {
                    entities[shot].ai_data[3] |= PROJ_FLAG_CONVERGENCE;
                }
            }
            player.mp = 0;
            player.iframes = 45;
            player.active_charge = 180;
            room_transform_ticks = 135; // 135 * 8 frames = 18 seconds at 60 Hz
            room_shake(1, 18);
            sfx_play(SFX_ROAR);
            hud_redraw_mp();
        }

        // Wolfkin is a true contact kit, not the same held-A fire stream as
        // the ranged champions. A directed tap is the precise Fang Stab;
        // neutral A is a wider two-target Sweep. Holding through the tell
        // commits to a Max Strike dash, then settles into a deliberately
        // slower combo cadence so turbo/held play never requires button
        // mashing. Weapon swaps keep their authored projectile behaviour.
        if (player.class_id == 0
            && player.starter_weapon == classes[0].starter_weapon
            && w->p2 == PROJ_SPIKE && !(keys & J_B)) {
            u8 dir = input_to_dir8(keys);
            if (dir == 0xFF) dir = facing_to_dir8(player.facing);
            if (wolfkin_max_cd) wolfkin_max_cd--;
            if (keys & J_A) {
                if (wolfkin_a_hold < 255) wolfkin_a_hold++;
                if (wolfkin_a_hold == 20 && wolfkin_max_cd == 0) {
                    // The dash is the hero's committed FF-style lane break:
                    // a visible spear-like thrust travels with the body, not
                    // a permanent replacement for their contact weapon.
                    projectile_spawn_player(dir8_dx[dir], dir8_dy[dir],
                        (u8)(w->p1 + player.atk + 3), PROJ_SPEAR);
                    dash_timer = 11;
                    dash_cd = 45;
                    dash_dx = dir8_dx[dir];
                    dash_dy = dir8_dy[dir];
                    if (player.iframes < 18) player.iframes = 18;
                    wolfkin_max_cd = 150;
                    room_shake(1, 8);
                    sfx_play(SFX_ROAR);
                }
            } else {
                wolfkin_a_hold = 0;
            }

            // A held A is a deliberate physical combo, not a button-mashing
            // tax: one contact arc every 24 frames (2.5/sec). That is slower
            // than the old 16-frame tap rate; the 20-frame hold still layers
            // the distinct Max Strike dash into the same sustained action.
            if ((keys & J_A) && player.fire_cooldown == 0) {
                u8 dmg = (u8)(w->p1 + player.atk);
                u8 shot;
                if (room_weapon_surge_ticks) dmg++;
                shot = projectile_spawn_player(dir8_dx[dir], dir8_dy[dir],
                    dmg, PROJ_SPIKE);
                // Wolfkin takes the true-melee branch above, so its
                // class-shaped Surge expression must live here rather than
                // only in the ranged/shared branch below. The base claw
                // already cleaves two bodies; Razor Surge deliberately adds
                // exactly one more without widening the physical arc or
                // changing permanent weapon stats.
                if (room_weapon_surge_ticks && shot != 0xFF)
                    entities[shot].hp++;
                if (shot != 0xFF && !(keys & (J_LEFT | J_RIGHT | J_UP | J_DOWN))) {
                    // Neutral A sweeps a noticeably wider close arc. It is
                    // still one hitbox, so a boss cannot be blendered by
                    // several overlapping pseudo-projectiles in one frame.
                    entities[shot].hitbox = 0xBB;
                }
                player.fire_cooldown = 24;
            }
        } else if ((keys & J_A) && !(keys & J_B) && player.fire_cooldown == 0) {
            u8 dir = input_to_dir8(keys);
            u8 dmg = (u8)(w->p1 + player.atk);
            u8 cooldown = player_fire_delay(w->p0);
            if (room_weapon_surge_ticks) {
                // Surge Spark is an earned short burst, not a permanent stat:
                // it makes every class's actual A weapon hit harder and cycle
                // four frames faster without changing their geometry or B kit.
                dmg++;
                cooldown = (cooldown > 10) ? (u8)(cooldown - 4) : 6;
            }
            if (dir == 0xFF) dir = facing_to_dir8(player.facing);
            {
                u8 shot = projectile_spawn_player(dir8_dx[dir], dir8_dy[dir], dmg, w->p2);
                if (room_weapon_surge_ticks && shot != 0xFF) {
                    // Surge is one purchasable/drop-based power window, but
                    // it should amplify the shape of the vessel's actual A
                    // weapon rather than make five champions feel identical.
                    // The shared +damage/+cadence above stays deliberately
                    // modest; these are short 15-second expressions of the
                    // kits, not permanent build inflation.
                    switch (player.class_id) {
                        case 0: // Wolfkin: Razor Surge cleaves one more body.
                            entities[shot].hp++;
                            break;
                        case 1: // Sauran: Longtail Surge adds 16px of reach.
                            entities[shot].state_timer = (u8)(entities[shot].state_timer + 4);
                            break;
                        case 2: // Corvin: Gale Surge opens a second feather lane.
                            projectile_spawn_player(dir8_dx[(u8)((dir + 1) & 7)],
                                dir8_dy[(u8)((dir + 1) & 7)], dmg, PROJ_SHURIKEN);
                            break;
                        case 3: // Picsean: Tide Surge makes the bubble broader and deeper.
                            entities[shot].hp++;
                            entities[shot].hitbox = 0x99;
                            break;
                        default: // Vespine: Thorn Surge pierces a second target.
                            entities[shot].hp++;
                            break;
                    }
                }
            }
            player.fire_cooldown = cooldown;
        }
        if (player.fire_cooldown) player.fire_cooldown--;

        // ---- Weapon 2 (B, edge): class signature move. Costs MP_COST_B
        // magic on top of the ~2.3s cooldown; no MP -> error beep.
        #define MP_COST_B 2
        if ((pressed & J_B) && !(keys & J_A) && player.active_charge == 0
            && player.mp < MP_COST_B) {
            sfx_play(SFX_HURT);   // out of magic
        }
        if ((pressed & J_B) && !(keys & J_A) && player.active_charge == 0
            && player.mp >= MP_COST_B) {
            u8 dir = input_to_dir8(keys);
            u8 dmg = (u8)(w->p1 + 1 + player.atk);
            u8 d;
            if (dir == 0xFF) dir = facing_to_dir8(player.facing);
            switch (player.class_id) {
                case 0:   // Wolfkin HOWL: 8-way spike ring
                    for (d = 0; d < 8; ++d) {
                        projectile_spawn_player(dir8_dx[d], dir8_dy[d], dmg, PROJ_SPIKE);
                    }
                    // This remains an activation ward rather than a shield:
                    // half a second carries the committed burst through a
                    // dense boss lane, but cannot erase a whole volley.
                    room_special_guard(30);
                    break;
                case 1:   // Sauran STONESKIN: brief, timed shot/body shield
                    player.shield_timer = 60;
                    player.iframes = 8; // cover the raising animation
                    break;
                case 2:   // Corvin MURDER: 3-way shuriken spread
                    projectile_spawn_player(dir8_dx[dir], dir8_dy[dir], dmg, PROJ_SHURIKEN);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 1) & 7)],
                        dir8_dy[(u8)((dir + 1) & 7)], dmg, PROJ_SHURIKEN);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 7) & 7)],
                        dir8_dy[(u8)((dir + 7) & 7)], dmg, PROJ_SHURIKEN);
                    break;
                case 3:   // Picsean TIDAL WAVE: 3-lane bubble wall
                    projectile_spawn_player(dir8_dx[dir], dir8_dy[dir], dmg, PROJ_BUBBLE);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 2) & 7)],
                        dir8_dy[(u8)((dir + 2) & 7)], dmg, PROJ_BUBBLE);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 6) & 7)],
                        dir8_dy[(u8)((dir + 6) & 7)], dmg, PROJ_BUBBLE);
                    // Undertow guard: the wave wraps its caster in a brief
                    // water barrier, paid for by the normal MP/cooldown. It
                    // blocks bodies and destroys shots like other barriers.
                    if (player.shield_timer < 100) player.shield_timer = 100;
                    if (player.iframes < 8) player.iframes = 8;
                    break;
                default:  // Vespine SWARM: 4-stinger fan burst
                    projectile_spawn_player(dir8_dx[dir], dir8_dy[dir], dmg, PROJ_SPIKE);
                    projectile_spawn_player(dir8_dx[dir], dir8_dy[dir], dmg, PROJ_BULLET);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 1) & 7)],
                        dir8_dy[(u8)((dir + 1) & 7)], dmg, PROJ_BULLET);
                    projectile_spawn_player(dir8_dx[(u8)((dir + 7) & 7)],
                        dir8_dy[(u8)((dir + 7) & 7)], dmg, PROJ_BULLET);
                    room_special_guard(18);
                    break;
            }
            sfx_play(SFX_ROAR);
            player.active_charge = 140;
            player.mp = (u8)(player.mp - MP_COST_B);
            hud_redraw_mp();
        }
        if (player.active_charge > 0) player.active_charge--;
        if (room_transform_ticks > 0 && (run_clock_fraction & 7) == 0)
            room_transform_ticks--;
        if (room_weapon_surge_ticks > 0 && (run_clock_fraction & 7) == 0) {
            room_weapon_surge_ticks--;
            if ((room_weapon_surge_ticks & 0x0F) == 0)
                fx_spawn(SPR_FX_IMPACT, 0x06, (i16)player.x + 4,
                    (i16)player.y + 2, 12);
        }
        if (player.shield_timer > 0) {
            player.shield_timer--;
            if ((player.shield_timer & 7) == 0)
                fx_spawn(SPR_SHIELD_AURA, 1,
                    (i16)player.x + ((player.shield_timer & 8) ? 12 : -4),
                    (i16)player.y + ((player.shield_timer & 16) ? 12 : -4), 8);
        }

        // MP trickle: +1 every ~3.2s while below max — Picsean's
        // MP-attuned passive (perk 4) regenerates twice as fast.
        if (player.mp < player.mp_max) {
            u8 thresh = (player.class_id == 3) ? 96 : 192;
            if (++mp_regen >= thresh) {
                mp_regen = 0;
                player.mp++;
                hud_redraw_mp();
            }
        }

        // Sauran's scaled hide (perk 2): slow HP regen, one half-heart
        // per ~30s of active play.
        if (player.class_id == 1 && player.hp < player.hp_max) {
            if (++hp_regen >= 1800) {
                hp_regen = 0;
                player.hp++;
                hud_redraw_hp();
                sfx_play(SFX_HEART);
            }
        }
    }

    // ---- Entity updates
    entity_update_all(keys, pressed);

    // ---- Combat
    if (combat_resolve() || player.hp == 0) {
        // Player died: don't hard-cut — a beat of shake, bursts, and a
        // flickering hero falling before the GAMEOVER screen takes over.
        death_timer = 50;
        player.iframes = 50;             // reuse the iframe flicker
        sfx_play(SFX_DEATH);
        music_stop();
        room_shake(2, 30);
        fx_spawn(SPR_FX_IMPACT, 2, (i16)player.x,     (i16)player.y,     16);
        fx_spawn(SPR_FX_IMPACT, 2, (i16)player.x - 8, (i16)player.y - 8, 24);
        fx_spawn(SPR_FX_IMPACT, 2, (i16)player.x + 8, (i16)player.y + 8, 32);
        hud_redraw_hp();                 // show the empty hearts
        return SCREEN_SELF;
    }

    // ---- Boss HP bar + room-clear detection in one entity sweep.
    // HUD helper caches segments so polling only writes VRAM on change.
    {
        u8 i, found = 0, alive = 0, corvin_i = 0xFF;
        for (i = 0; i < MAX_ENTITIES; ++i) {
            if (!(entities[i].flags & EF_ACTIVE)) continue;
            if (entities[i].type != ENT_ENEMY)    continue;
            alive++;
            if (corvin_i == 0xFF) corvin_i = i;
            if (!found && entities[i].ai_data[0] == ENEMY_STONE_SENTINEL) {
                // ai_data[6] = remembered max HP (set on first boss tick);
                // fall back to current hp for the very first frame.
                u8 max = entities[i].ai_data[6];
                if (max == 0) max = entities[i].hp;
                hud_redraw_boss(entities[i].hp, max);
                found = 1;
            }
        }
        // Corvin's raven sight (perk 3): with no boss around, the bar
        // reads a regular enemy's real spawn HP. The old content-table value
        // ignored procgen's regular-room stage bonus, making a fully healthy
        // late enemy look already chipped and delaying each bar segment's
        // visible loss by several true hits.
        if (!found && player.class_id == 2 && corvin_i != 0xFF) {
            u8 eid = entities[corvin_i].ai_data[0];
            u8 max = (eid < N_ENEMIES) ? enemies[eid].stats.hp : 0;
            if (max) {
                if (!run_state.world_mode
                    && run_state_dungeon_local() < 3) {
                    u8 st = run_state.bosses_beaten;
                    if (st > 24) st = 24;
                    max = (u8)(max + 1 + (u8)(st >> 1));
                }
                // Elites carry doubled HP — double the reference too
                if (entities[corvin_i].flags & EF_ELITE) max = (u8)(max << 1);
                hud_redraw_boss(entities[corvin_i].hp, max);
                found = 1;
            }
        }
        if (!found) {
            u8 ware, price;
            hud_redraw_boss(0, 0);
            if (room_has_shop_wares && pickup_nearby_shop_offer(&ware, &price)) {
                hud_show_offer(ware, price);
                shop_offer_visible = 1;
            } else if (shop_offer_visible) {
                hud_clear_offer();
                shop_offer_visible = 0;
            }
            // The contextual four-slot lane is otherwise empty. Wolfkin's
            // Max Strike uses it as a filling cooldown bar: full means the
            // held-A dash is ready, empty means it has just been spent.
            if (!room_has_shop_wares && player.class_id == 0
                && player.starter_weapon == classes[0].starter_weapon) {
                hud_redraw_action_charge((u8)(150 - wolfkin_max_cd), 150);
            }
        }

        // Last hostile down → rising chime + 1 MP back. Boss kills keep
        // their own fanfare (roar/explosion), so skip when one just landed.
        if (alive == 0 && hostiles_prev != 0
            && !run_state.pending_unseal && !run_state.victory) {
            sfx_play(SFX_CLEAR);
            if (room_combat_sealed) {
                room_combat_sealed = 0;
                room_unseal_doors();
            }
            if (run_state.rooms_cleared < 255) run_state.rooms_cleared++;
            if (player.mp < player.mp_max) {
                player.mp++;
                hud_redraw_mp();
            }
        }
        hostiles_now = alive;
        hostiles_prev = alive;
    }

    // ---- Boss beaten (non-final): lift the door seal, run continues,
    // and the fight music yields back to the exploration theme.
    if (run_state.pending_unseal) {
        run_state.pending_unseal = 0;
        room_unseal_doors();
        play_stage_music();
    }

    // ---- Final victory: all bosses down
    if (run_state.victory) {
        return SCREEN_VICTORY;
    }

    // Puzzle rooms replace the ordinary extermination seal. Ordered runes
    // and paired dungeon switches react to feet contact; a completed seal
    // releases every forward threshold immediately.
    if (room_puzzle_kind != PUZZLE_NONE && puzzle_update_player())
        room_unseal_doors();

    // ---- Rubble poking: walking over rubble kicks it apart (Zelda bush-cut).
    // Pressure plates deliberately do not activate under the hero: their
    // oversized cairn and clear push lane communicate the actual solution.
    {
        u8 rtx = (u8)((player.x + 8) >> 3);
        u8 rty = (u8)((player.y + 12) >> 3);
        if (rtx < ROOM_W && rty < ROOM_H
            && room_tilemap[rty][rtx] == BGT_RUBBLE) {
            room_set_tile_vbl(rtx, rty, BGT_FLOOR, BGPAL_FLOOR);
            sfx_play(SFX_HIT);
            if (rng_next_u8() < 100) {   // ~40%: hidden coin
                pickup_spawn(PICKUP_COIN_1,
                    FIX8((i16)rtx * 8), FIX8((i16)rty * 8));
            }
        }
        else if (rtx < ROOM_W && rty < ROOM_H
            && room_tilemap[rty][rtx] == BGT_PORTAL) {
            if (run_state.world_mode) {
                const zelda_screen_t *cell =
                    &zelda_overworlds[0].screen_grid[run_state.world_screen & 15];
                if (cell->kind == ZELDA_CELL_DUNGEON_ENTRANCE) {
                    run_state_begin_dungeon();
                    run_state.room_counter++;
                } else if (cell->kind == ZELDA_CELL_VAULT) {
                    run_state.world_screen = (u8)(run_state.world_return_screen & 15);
                } else if (cell->stairs != ID_NONE_U8) {
                    run_state.world_return_screen = (u8)(run_state.world_screen
                        | (run_state.world_return_screen & RIFTWELL_USED_FLAG));
                    run_state.world_screen = cell->stairs;
                }
            } else {
                u8 base = run_state_stage_start(run_state.bosses_beaten);
                u8 local = run_state_dungeon_local();
                run_state.room_counter = (u8)(base + ((local == 2) ? 8 : 2));
            }
            // A rift/stair is not a cardinal doorway. Pretending it came
            // through a random edge can spawn the hero on a destination's
            // non-existent east/south exit (notably vault 15), where the
            // sprite appears to vanish into the tree line. DIR_NONE makes
            // procgen use its safe center arrival, clear of the portal tile
            // and valid regardless of the destination's authored edges.
            run_state.entered_from = DIR_NONE;
            sfx_play(SFX_DOOR);
            // Select before the banked generator. On hardware/SDCC the
            // post-bcall path could skip the later selector, leaving every
            // Riftwild dungeon entrance on stage 0 music.
            play_stage_music();
            DISPLAY_OFF;
            procgen_generate_current_room();
            arrival_sprite_grace = 60;
            room_refresh_shop_wares();
            room_load_dynamic_fx_identity();
            // A post-region Riftwild gate can land directly in a village.
            // Cardinal town transitions already restore resident-only OBJ
            // slots; the portal path must do the same or the Waykeeper and
            // Bellkeeper inherit stale combat sprites.
            room_load_town_resident_identity();
            room_spawn_progression_fixture();
            puzzle_prepare_room_role();
            boss_threshold_warned = 0;
            room_load_environment_palettes();
            draw_room_tilemap();
            place_player_sprite();
            hud_redraw_all();
            DISPLAY_ON;
            hostiles_prev = 0;
            sram_save_run();
            return SCREEN_SELF;
        }
        // ---- Hazard floor: walkable but bites when the feet-box center
        // rests on it. Picsean's swim passive crosses Toxic Mire pools safely;
        // other stages remain dangerous to every vessel.
        else if (rtx < ROOM_W && rty < ROOM_H
            && room_tilemap[rty][rtx] == BGT_SPIKES
            && !(player.class_id == 3 && room_stage() == 4)
            && player.iframes == 0) {
            if (player.hp > 1) {
                player.hp--;
                player.iframes = 40;
                room_stumble_off_hazard();
                g_hitstop = 2;
                room_shake(1, 6);
                sfx_play(SFX_HURT);
                hud_redraw_hp();
            } else {
                player.hp = 0;
                return SCREEN_GAMEOVER;
            }
        }
    }

    // ---- Door detection. Near (N/W) boundaries cannot be reached by the
    // feet-box CENTER without putting part of the body outside the map, so
    // detect all four sides symmetrically from the body's leading edge.
    {
        u8 tx = 0xFF, ty = 0xFF;
        u8 dir = DIR_NONE;
        u8 source_was_wide = (room_world_width > ROOM_VIEW_W_PX
            || room_world_height > ROOM_VIEW_H_PX);
        if (player.y <= 0) {
            dir = DIR_N; tx = (u8)((player.x + 8) >> 3); ty = 0;
        } else if (player.y >= (ppos_t)(room_world_height - 16)) {
            dir = DIR_S; tx = (u8)((player.x + 8) >> 3);
            ty = (u8)((room_world_height >> 3) - 1);
        } else if (player.x <= 0) {
            dir = DIR_W; tx = 0; ty = (u8)((player.y + 12) >> 3);
        } else if (player.x >= (ppos_t)(room_world_width - 16)) {
            dir = DIR_E; tx = (u8)((room_world_width >> 3) - 1);
            ty = (u8)((player.y + 12) >> 3);
        }

        if (dir != DIR_NONE && ty < (u8)(room_world_height >> 3)
            && room_tile_at_px((i16)tx << 3, (i16)ty << 3) == BGT_DOOR) {
            u8 back_dir = (u8)((run_state.entered_from + 2) & 3);
                // The sanctuary's forward threshold rejects the hero until
                // this dungeon's route fixtures are recovered. Twelve-cell
                // stages add the local-room-7 Waystone; fourteen-cell stages
                // also require the existing local-room-9 deep Warden. The
                // return door remains open, guaranteeing a route back to
                // every visible objective.
                if (is_forward_boss_door(tx, ty, BGT_DOOR)
                    && (!(run_state.rift_sigils
                            & RUN_STAGE_SIGIL_BIT(run_state.bosses_beaten))
                        || !(run_state.dungeon_puzzles
                            & RUN_WARDEN_BOON_BIT)
                        || (run_state_dungeon_size() >= 12
                            && !(run_state.dungeon_puzzles
                                & RUN_WAYSTONE_BIT))
                        || (run_state_dungeon_size() >= 14
                            && !(run_state.dungeon_phase
                                & RUN_DEEP_WARDEN_BIT)))) {
                    room_hold_at_door(dir, SFX_HURT, 6);
                    return SCREEN_SELF;
                }
                // A discovered cache is an overlay attached to its parent
                // graph cell, not another campaign node. Its only exit is the
                // threshold back to that parent.
                if (run_state.secret_pending == 2
                    && !(run_state.entered_from != DIR_NONE && dir == back_dir)) {
                    room_hold_at_door(dir, SFX_TICK, 4);
                    return SCREEN_SELF;
                }
                // Procedural puzzle rooms preserve the return route but hold
                // every unexplored exit until their landscape interaction is
                // solved. This is independent of enemy count: these rooms are
                // alternatives to the ordinary kill-everything seal.
                if (room_puzzle_locked
                    && !(run_state.entered_from != DIR_NONE && dir == back_dir)) {
                    room_hold_at_door(dir, SFX_TICK, 4);
                    return SCREEN_SELF;
                }
                // Dungeon combat rooms gate unexplored exits. Riftwild is an
                // overworld, not a chain of arenas: its fights are optional
                // and every authored graph exit remains fleeable.
                if (room_combat_sealed && hostiles_now != 0
                    && !(run_state.entered_from != DIR_NONE && dir == back_dir)) {
                    // A locked doorway is still walkable terrain so the hero
                    // can cross it after a clear. Hold the signed position at
                    // the legal room edge while combat keeps it locked;
                    // otherwise repeated input can drift to -8/152 offscreen
                    // and leave every remaining enemy impossible to hit.
                    room_hold_at_door(dir, SFX_HIT, 4);
                    return SCREEN_SELF;
                }
                // Leaving through a shot-open secret door → treasure room
                if ((tx == secret_door_x && ty == secret_door_y)
                    || (tx == secret_door_x2 && ty == secret_door_y2)) {
                    run_state.secret_pending = 1;
                }
                secret_door_x = secret_door_y = 0xFF;
                secret_door_x2 = secret_door_y2 = 0xFF;
                // Sticky dungeon: room layout is a pure function of room_counter,
                // so treat the counter as a position on a corridor. Leaving
                // through the door we came in (opposite of entered_from) walks
                // BACK to the previous room — regenerating its identical layout;
                // any other door advances. entered_from = exit dir works for
                // both (the player spawns at the opposite door either way).
                {
                    if (run_state.world_mode) {
                        if (dir == DIR_N) run_state.world_screen -= 4;
                        else if (dir == DIR_E) run_state.world_screen++;
                        else if (dir == DIR_S) run_state.world_screen += 4;
                        else run_state.world_screen--;
                    } else if (RUN_ROOM_IS_TOWN(run_state.room_counter)) {
                        if (run_state.world_return_screen == TOWN_ARRIVAL) {
                            if (dir == DIR_E) run_state.world_return_screen = TOWN_MARKET;
                            else if (dir == DIR_W) run_state.world_return_screen = TOWN_QUARTER;
                            else {
                                // Town route knowledge is queued separately
                                // from the current compass. Entering north is
                                // a genuine dungeon transition, so consume it
                                // here just as Riftwild cave gates do.
                                run_state_begin_dungeon();
                                run_state.room_counter++;
                            }
                        } else {
                            run_state.world_return_screen = TOWN_ARRIVAL;
                        }
                    } else if (run_state_was_cleared_boss()) {
                        // A defeated dungeon opens into a nonlinear overworld;
                        // locate its authored dungeon gate to begin the next.
                        run_state_begin_world();
                    } else if (run_state.secret_pending == 1) {
                        // Generate the cache over the current graph cell.
                        // procgen promotes state 1 to persistent state 2.
                    } else if (run_state.secret_pending == 2) {
                        // Return from that overlay to the same stable cell.
                        run_state.secret_pending = 0;
                    } else {
                        u8 neighbor = run_state_dungeon_neighbor(dir);
                        if (neighbor != 0xFF)
                            run_state.room_counter = neighbor;
                    }
                }
                run_state.entered_from = dir;
                sfx_play(SFX_DOOR);
                if (run_state_is_boss_room()) {
                    play_boss_music();
                } else {
                    play_stage_music();
                }
                // Regenerate room in-place (skip full screen exit/enter).
                // Any same-stage outdoor or dungeon seam gets the streamed
                // Zelda-like slide. Palette-changing boss/world/town
                // boundaries retain the safe blanked rebuild path.
                procgen_generate_current_room();
                boss_threshold_warned = 0;
                arrival_sprite_grace = 60;
                room_refresh_shop_wares();
                // Town arrivals own two resident-only OBJ tiles. Unlike a
                // streamed dungeon step, blank briefly before changing them.
                if (RUN_ROOM_IS_TOWN(run_state.room_counter)) DISPLAY_OFF;
                // draw_room_tilemap and the compass use CGB VRAM bank 1 for
                // attributes. Sprite uploads always belong in bank 0; without
                // this reset a streamed town entry can create its residents
                // correctly while leaving their visible OBJ tile unchanged.
                VBK_REG = 0;
                room_load_dynamic_fx_identity();
                room_load_town_resident_identity();
                room_spawn_progression_fixture();
                puzzle_prepare_room_role();
                // A 224px source already occupies BG columns 0..27; the
                // 20-column streamer would overwrite eight still-visible
                // source columns while staging its destination at 20..31.
                // Wide fields therefore use the shorter blanked rebuild.
                // Their internal 64px camera travel removes far more loading
                // than the obsolete one-screen-per-cell cadence, and entering
                // from the east now starts at SCX 64 with the hero visible.
                if (!source_was_wide
                    && room_world_width <= ROOM_VIEW_W_PX
                    && room_world_height <= ROOM_VIEW_H_PX
                    && !RUN_ROOM_IS_TOWN(run_state.room_counter) && dir == DIR_E
                    && !procgen_current_room_is_boss
                    && room_stage() == stage_seen) {
                    HIDE_SPRITES;
                    room_slide_east();
                } else if (!source_was_wide
                    && room_world_width <= ROOM_VIEW_W_PX
                    && room_world_height <= ROOM_VIEW_H_PX
                    && !RUN_ROOM_IS_TOWN(run_state.room_counter) && dir == DIR_W
                    && !procgen_current_room_is_boss
                    && room_stage() == stage_seen) {
                    HIDE_SPRITES;
                    room_slide_west();
                } else if (!source_was_wide
                    && room_world_width <= ROOM_VIEW_W_PX
                    && room_world_height <= ROOM_VIEW_H_PX
                    && !RUN_ROOM_IS_TOWN(run_state.room_counter) && dir == DIR_S
                    && !procgen_current_room_is_boss
                    && room_stage() == stage_seen) {
                    HIDE_SPRITES;
                    room_slide_south();
                } else if (!source_was_wide
                    && room_world_width <= ROOM_VIEW_W_PX
                    && room_world_height <= ROOM_VIEW_H_PX
                    && !RUN_ROOM_IS_TOWN(run_state.room_counter) && dir == DIR_N
                    && !procgen_current_room_is_boss
                    && room_stage() == stage_seen) {
                    HIDE_SPRITES;
                    room_slide_north();
                } else {
                    DISPLAY_OFF;
                    // Reuse this path's existing blanking window for the tiny
                    // outdoor atlas. Boss projections loaded below reclaim the
                    // same combat-unused slots; Riftwild/towns retain them.
                    tiles_load_area_labels();
                    if (procgen_current_room_is_boss)
                        tiles_load_colossus_bg(room_stage());
                    draw_room_tilemap();
                }
                room_load_environment_palettes();
                place_player_sprite();
                hud_redraw_all();
                // The Zelda-style slide hides OBJ for the scroll so neither
                // room's actors float across the seam. Restore it before the
                // rebuilt room is shown; otherwise the player state is live
                // but the entire sprite layer remains disabled after a door.
                SHOW_SPRITES;
                DISPLAY_ON;
                if (procgen_current_room_is_boss) {
                    sfx_play(SFX_ROAR);
                    // Entry drama: dark, trembling, then the light pops
                    room_apply_pause_palettes(1);
                    stage_fade = 30;
                    room_shake(1, 24);
                }
                hostiles_prev = 0;   // fresh room: re-arm the clear chime
                // Stage-entry reveal (door path — stage changes land here
                // after a boss kill, not via room_enter)
                if (room_stage() != stage_seen) {
                    stage_seen = room_stage();
                    room_load_stage_obj_identity();
                    // Stage art is uploaded after the ordinary room refresh
                    // on this path. Reapply the phase-safe enemy/callout
                    // identity so it always wins the final OBJ write.
                    room_load_dynamic_fx_identity();
                    stage_fade = 26;
                    room_apply_pause_palettes(1);
                }
                sram_save_run();   // suspend save on every room entry
                return SCREEN_SELF;
        }
    }

    return SCREEN_SELF;
}

void room_draw(void) {
    if (procgen_current_room_is_boss && room_stage() == 2) {
        u8 i;
        for (i = 0; i < MAX_ENTITIES; ++i) {
            entity_t *e = &entities[i];
            if ((e->flags & EF_ACTIVE) && e->type == ENT_ENEMY
                && e->ai_data[0] == ENEMY_STONE_SENTINEL
                && (e->ai_data[3] & 1) && e->ai_data[2] == 2) {
                // State 0 breathes, state 1 lunges, state 2 recovers.
                u8 active = e->state != 2;
                if (active != cinder_projection_state) {
                    tiles_animate_cinder_bg(active);
                    cinder_projection_state = active;
                }
                break;
            }
        }
    }
    if (procgen_current_room_is_boss && room_stage() == 4) {
        u8 i;
        for (i = 0; i < MAX_ENTITIES; ++i) {
            entity_t *e = &entities[i];
            if ((e->flags & EF_ACTIVE) && e->type == ENT_ENEMY
                && e->ai_data[0] == ENEMY_STONE_SENTINEL
                && (e->ai_data[3] & 1) && e->ai_data[2] == 4) {
                u8 phase = (u8)(e->state & 1);
                if (phase != mire_projection_state) {
                    tiles_paint_mire_projection(phase, 1);
                    mire_projection_state = phase;
                }
                break;
            }
        }
    }
    room_camera_x = (room_world_width > ROOM_VIEW_W_PX)
        ? tiles_world_camera_step(room_camera_x, player.x,
            room_world_width, ROOM_VIEW_W_PX) : 0;
    room_camera_y = (room_world_height > ROOM_VIEW_H_PX)
        ? tiles_world_camera_step(room_camera_y, player.y,
            room_world_height, ROOM_VIEW_H_PX) : 0;
    place_player_sprite();
    if (room_world_height > ROOM_VIEW_H_PX) entity_draw_all_world();
    else entity_draw_all();

    if (procgen_current_room_is_boss && room_stage() == 1
        && (loop_frame_counter & 0x0F) == 0) {
        // One shared BG tile makes charge visibly travel through the huge
        // coil while the existing OBJ head owns all combat behavior.
        tiles_animate_serpent_bg((loop_frame_counter & 0x20) != 0);
    }

    if (procgen_current_room_is_boss && room_stage() == 3
        && (loop_frame_counter & 0x0F) == 0) {
        // The web and paired eyes pulse together; the OBJ weak point's live
        // warning/blink remains authoritative combat timing.
        tiles_animate_spider_bg((loop_frame_counter & 0x20) != 0);
    }

    if (procgen_current_room_is_boss && room_stage() == 5
        && (loop_frame_counter & 0x0F) == 0) {
        tiles_animate_reaper_bg((loop_frame_counter & 0x20) != 0);
    }

    if (procgen_current_room_is_boss && room_stage() == 6
        && (loop_frame_counter & 0x0F) == 0) {
        // A brief stone sleep makes the paired sun-rune wake-up readable;
        // projectile timing still comes entirely from the existing boss AI.
        tiles_animate_golem_bg((loop_frame_counter & 0x7F) >= 0x60);
    }

    if (procgen_current_room_is_boss && room_stage() == 7
        && (loop_frame_counter & 0x0F) == 0) {
        // Side heads and centre head alternate their open breath posture. The
        // existing five-stream volley remains authoritative combat timing.
        tiles_animate_hydra_bg((loop_frame_counter & 0x20) != 0);
    }

    if (procgen_current_room_is_boss && room_stage() == 8
        && (loop_frame_counter & 0x0F) == 0) {
        // Brief synchronized blink: the background creature is alive, while
        // the OBJ core remains the only vulnerable body.
        tiles_animate_colossus_bg((loop_frame_counter & 0x7F) >= 0x70);
    }

    // Impact shake is added to the real camera rather than replacing it.
    if (shake_timer) {
        shake_timer--;
        if (shake_timer == 0) {
            SCX_REG = room_camera_x;
            SCY_REG = room_camera_y;
        } else {
            if (shake_timer & 2) {
                u8 max_camera = (u8)(room_world_width - ROOM_VIEW_W_PX);
                SCX_REG = (room_camera_x + shake_mag > max_camera)
                    ? max_camera : (u8)(room_camera_x + shake_mag);
            } else {
                SCX_REG = (room_camera_x > shake_mag)
                    ? (u8)(room_camera_x - shake_mag) : 0;
            }
            if (room_world_height > ROOM_VIEW_H_PX) {
                u8 max_camera_y = (u8)(room_world_height - ROOM_VIEW_H_PX);
                if (shake_timer & 4)
                    SCY_REG = (room_camera_y + shake_mag > max_camera_y)
                        ? max_camera_y : (u8)(room_camera_y + shake_mag);
                else
                    SCY_REG = (room_camera_y > shake_mag)
                        ? (u8)(room_camera_y - shake_mag) : 0;
            } else {
                SCY_REG = (room_world_width > ROOM_VIEW_W_PX)
                    ? 0 : ((shake_timer & 4) ? 1 : 0xFF);
            }
        }
    } else if (room_world_width > ROOM_VIEW_W_PX
        || room_world_height > ROOM_VIEW_H_PX) {
        // Crystal and every Riftwild cell share the real world camera.
        SCX_REG = room_camera_x;
        SCY_REG = room_camera_y;
    } else if (procgen_current_room_is_boss && room_stage() == 1) {
        // Preserve Verdant's original inline timing: a banked call here costs
        // enough cycles to perturb fixed controller replays in dense fights.
        u8 phase = (u8)((loop_frame_counter >> 3) & 7);
        SCX_REG = (phase < 4) ? phase : (u8)(7 - phase);
        SCY_REG = (phase & 2) ? 1 : 0;
    } else if (procgen_current_room_is_boss && room_stage() == 4) {
        // Mire Heart is an expanding organism, so let its whole arena breathe
        // on a slower eight-beat loop. This is the Penta-style camera language
        // of Ted/Cameo rather than extra collision: the WINDOW HUD and the
        // mobile OBJ heart stay authoritative while the huge BG body shifts
        // by at most three horizontal pixels.
        u8 phase = (u8)((loop_frame_counter >> 4) & 7);
        SCX_REG = (phase < 4) ? phase : (u8)(7 - phase);
        SCY_REG = 0;
    } else if (procgen_current_room_is_boss && room_stage() == 7) {
        // Blood Hydra is the late Faze-like moving arena: its three-head coil
        // drifts around the independently weaving weak point. The second half
        // of the 16-beat loop mirrors the vertical phase so this does not read
        // as a copy of Verdant's faster eight-beat Serpent sway.
        u8 phase = (u8)((loop_frame_counter >> 3) & 15);
        u8 arc = (u8)(phase & 7);
        SCX_REG = (arc < 4) ? arc : (u8)(7 - arc);
        SCY_REG = 0;
    } else if (procgen_current_room_is_boss && room_stage() == 8) {
        u8 phase = (u8)((loop_frame_counter >> 4) & 7);
        SCX_REG = (phase < 4) ? phase : (u8)(7 - phase);
        SCY_REG = 0;
    } else {
        SCX_REG = 0;
        SCY_REG = 0;
    }
}
