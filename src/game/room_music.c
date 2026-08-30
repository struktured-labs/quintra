#pragma bank 13

#include <gb/gb.h>

#include "audio/music.h"
#include "core/types.h"
#include "game/run_state.h"
#include "render/palette.h"
#include "render/tiles.h"
#include "content.h"

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
    u8 stage = destination_stage();
    palette_obj_load(6, boss_stage_pal[stage]);
    tiles_load_miniboss(stage);
    tiles_load_boss_big(stage);
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
