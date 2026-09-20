#pragma bank 13

#include <gb/gb.h>

#include "audio/music.h"
#include "core/types.h"
#include "game/run_state.h"
#include "game/dungeon_director.h"
#include "game/room.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

static u8 return_identity_loaded;

static u8 destination_stage(void) {
    u8 s = run_state.bosses_beaten;
    if (run_state.world_mode) return (s >= 7) ? 6 : (s >= 4) ? 3 : 0;
    // Combat advances bosses_beaten as soon as the Colossus falls, while the
    // champion is still standing in the cleared arena.  Menu resume and the
    // post-fight unseal must retain that arena's art/music identity until the
    // player actually crosses its exit.
    if (run_state_was_cleared_boss()) s--;
    return (s < N_STAGES) ? s : (u8)(s % N_STAGES);
}

void room_load_stage_obj_identity(void) BANKED {
    static const u16 return_palette[4] = {
        BGR555(0, 0, 0), BGR555(9, 3, 15),
        BGR555(23, 11, 26), BGR555(31, 29, 20),
    };
    u8 stage = destination_stage();
    palette_obj_load(6, boss_stage_pal[stage]);
    tiles_load_miniboss(stage);
    tiles_load_boss_big(stage);
    if (room_return_echo_kind >= 4) {
        tiles_load_return_reaper();
        palette_obj_load(6, return_palette);
    }
    return_identity_loaded = room_return_echo_kind >= 4;
}

void room_load_return_identity(void) BANKED {
    if (room_return_echo_kind >= 4 || return_identity_loaded)
        room_load_stage_obj_identity();
}

void room_load_dynamic_fx_identity(void) BANKED {
    u8 stage = destination_stage();
    u8 town = RUN_ROOM_IS_TOWN(run_state.room_counter);
    room_load_return_identity();
    if (!run_state.world_mode && !town) tiles_load_stage_scenery(stage);
    tiles_load_fx_sprites();
    if (!town) {
        switch (stage) {
            case 0: tiles_load_shard_crab_sprite(); break;
            case 1: tiles_load_vine_coil_sprite(); break;
            case 2:
                tiles_load_cinder_kite_sprite();
                tiles_load_cinder_maw_medium_sprite(); break;
            case 3: tiles_load_frost_lancer_sprite(); break;
            case 4: tiles_load_bog_toad_sprite(); break;
            case 5: tiles_load_bramble_sprite(); break;
            case 6: tiles_load_sunwheel_sprite(); break;
            case 7: tiles_load_dusk_midge_sprite(); break;
            default: tiles_load_void_halo_sprite(); break;
        }
        tiles_load_spear_sprite();
    }
    if (!run_state.world_mode && !town && !run_state_is_shop()) {
        tiles_load_dread_bell_sprite();
        tiles_load_rift_warden_sprite();
        tiles_load_prism_skitter_sprite();
        tiles_load_rift_cantor_sprite();
    }
    room_refresh_player_appearance(0);
}

void play_stage_music(void) BANKED {
    u8 stage = destination_stage();
    if (run_state.world_mode) {
        if (RUN_RIFTWILD_IS_HOLLOW()) {
            if (music_track_id != MUSIC_HOLLOW_RIFTWILD)
                music_play_hollow_riftwild();
        } else if (music_track_id != MUSIC_RIFTWILD) music_play_riftwild();
        return;
    }
    if (RUN_ROOM_IS_TOWN(run_state.room_counter)) {
        if (music_track_id != MUSIC_VILLAGE) music_play_village();
        return;
    }
    if (music_track_id == stage) return;
    music_stage_number = stage;
    music_play_stage();
}

void play_boss_music(void) BANKED {
    u8 stage = (u8)(run_state.bosses_beaten % MUSIC_STAGE_COUNT);
    if (music_track_id == (u8)(MUSIC_BOSS_BASE + stage)) return;
    music_stage_number = stage;
    music_play_boss();
}
