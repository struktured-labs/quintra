#!/usr/bin/env bash
# Shared schema for the controller balance matrix and its input-replay test.
# Keep this in one place: a stale duplicate header can produce rows that look
# valid to a shell script but no longer line up with the Lua observer output.

quintra_balance_csv_header() {
  printf '%s\n' 'run,class,seed,frames,max_room,rooms_seen,rooms_cleared,kills,bosses,damage,giant_overlap_damage,giant_close_frames,min_hp,final_x,final_y,world_mode,world_screen,room_frames,max_combat_frames,max_combat_room,max_combat_enemy,max_target_stall_frames,max_target_stall_room,max_target_stall_enemy,max_route_frames,max_route_room,hostiles,last_enemy,death_source,towns,world_hops,victory,ui_screen,dodges,shop_visits,purchases,enemy_mask,min_giant_hp,b_uses,boss_attempts,boss_attempt_frames,boss_clear_frames,town_market_visits,town_quarter_visits,boss_clear_durations,death_room,death_bosses,death_giant,death_giant_overlap,boss_relics_seen,boss_relics_collected,boss_relics_missed,final_weapon,weapon_swaps,final_hp_max,final_mp_max,final_atk,final_def,final_spd,final_lck'
}
