#pragma bank 3
#include "audio/sfx.h"
#include "audio/boss_voice.h"
#include "render/large_boss.h"

u8 large_boss_shot_overlap(const entity_t *shot, const entity_t *boss) BANKED;
u8 large_boss_contact(const entity_t *boss) BANKED;
#include "core/rng.h"
#include "core/types.h"
#include "game/combat.h"
#include "game/hexa_boss.h"
#include "game/enemy_ai.h"
#include "game/dungeon_director.h"
#include "game/entity.h"
#include "game/rare_enemy.h"
#include "game/boss_phase.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/projectile.h"
#include "game/room.h"
#include "game/run_state.h"
#include "game/status.h"
#include "game/waygear.h"
#include "game/will.h"
#include "render/tiles.h"
#include "render/hud.h"
#include "content.h"

u8 status_enemy_effective_poise(u8 idx, u8 poise) BANKED;
u8 status_enemy_hit_damage(u8 idx, u8 damage) BANKED;
u8 status_hostile_damage_taken(u8 idx) BANKED;

// Global hit-stop: freezes the room loop for a few frames on impact for weight.
u8 g_hitstop;

// Knock an enemy 3px along a bullet's travel direction, unless it's too poised
// (bosses, heavy enemies). Blocked by walls via enemy_try_step.
static void knockback_enemy(entity_t *e, i8 bvx, i8 bvy, u8 poise) {
    u8 n;
    if (poise >= 3) return;                 // heavy: immovable
    {
        i8 kx = (bvx > 0) ? 1 : (bvx < 0) ? -1 : 0;
        i8 ky = (bvy > 0) ? 1 : (bvy < 0) ? -1 : 0;
        for (n = 0; n < 3; ++n) enemy_try_step(e, kx, ky);
    }
}

static void score_add(u16 points) {
    u16 before = run_state.score;
    run_state.score = (u16)(before + points);
    if (run_state.score < before) run_state.score = 0xFFFF;
}

static u8 combat_has_relic(u8 item_id) {
    u8 k;
    for (k = 0; k < INVENTORY_SLOTS; ++k)
        if (player.inventory[k] == item_id) return 1;
    return 0;
}

static u8 shield_catches_projectile(const entity_t *e) {
    i16 dx = (i16)(FIX8_TO_INT(e->x) + 3) - (i16)(player.x + 8);
    i16 dy = (i16)(FIX8_TO_INT(e->y) + 3) - (i16)(player.y + 8);
    u8 radius = (u8)((player.class_id == 3 ? 14 : 10)
        + (room_appearance_tier << 1));
    if (dx < 0) dx = -dx;
    if (dy < 0) dy = -dy;
    return dx <= radius && dy <= radius;
}

static u8 splash_reaches_enemy(const entity_t *burst, const entity_t *enemy) {
    i16 dx = (FIX8_TO_INT(enemy->x) + 4)
        - (FIX8_TO_INT(burst->x) + 7);
    i16 dy = (FIX8_TO_INT(enemy->y) + 4)
        - (FIX8_TO_INT(burst->y) + 7);
    if (dx < 0) dx = -dx;
    if (dy < 0) dy = -dy;
    return dx <= 18 && dy <= 18;
}

// A bullet-hell kill must leave room for its guaranteed rewards.  Retiring
// hostile shots at the death beat is both a readable clear signal and avoids
// a full 32-slot entity table letting explosion FX crowd out hearts/relics.
static void boss_clear_hostile_projectiles(void) {
    u8 k;
    for (k = 0; k < MAX_ENTITIES; ++k) {
        if ((entities[k].flags & EF_ACTIVE)
            && entities[k].type == ENT_PROJECTILE
            && !(entities[k].flags & EF_PLAYER_PROJ)) {
            entity_kill(k);
        }
    }
}

// Set when a piercing shot splits a Rift Ooze into a later slot. The
// prefiltered enemy list would miss that new body; the caller finishes
// the slot walk with the original pointer scan.
static u8 combat_tail_rescan;

u8 combat_defeat_enemy(u8 j, u8 i, u8 weak) BANKED {
    u8 eid=entities[j].ai_data[0];
    u8 boss_retired_for_rewards=0, shot_spent_for_split=0;
    sfx_play(SFX_DEATH);
    if (entities[j].ai_data[0] == ENEMY_STONE_SENTINEL
        && (entities[j].ai_data[3] & 1))
        boss_voice(entities[j].ai_data[2], BOSS_VOICE_DEATH);
    if (weak) {
        fx_spawn(SPR_FX_IMPACT, 3,
                 FIX8_TO_INT(entities[j].x) + 4,
                 FIX8_TO_INT(entities[j].y) + 4, 10);
    }
    if (g_hitstop < 2) g_hitstop = 2;
    {
        if (eid < N_ENEMIES) {
            // Endless descent pays double
            u16 pts = enemies[eid].stats.score;
            if (run_state.bosses_beaten >= BOSSES_TO_WIN) pts = (u16)(pts << 1);
            score_add(pts);
        }
        run_state_record_enemy_kill();
        if (eid == ENEMY_STAGE_REAPER)
            run_state.dungeon_puzzles |= RUN_REAPER_CLEARED_BIT;
        // Vampiric Sigil (item id 29): slow dungeon sustain.
        // Multiple copies keep their stat boosts but do not
        // multiply the heal, avoiding runaway immortality.
        if (!STATUS_PLAYER_HEALING_BLOCKED()
            && (run_state_enemies_killed_total() % 5) == 0
            && player.hp < player.hp_max) {
            u8 vi;
            for (vi = 0; vi < INVENTORY_SLOTS; ++vi) {
                if (player.inventory[vi] == 29) {
                    player.hp++;
                    hud_redraw_hp();
                    sfx_play(SFX_HEART);
                    break;
                }
            }
        }
        // War Drum turns the same five-kill cadence into a
        // class-shaped resource swing: every champion gets
        // B back immediately, while restored MP feeds the
        // separate A+B/Oath magic ladder.
        if ((run_state_enemies_killed_total() % 5) == 0
            && combat_has_relic(ITEM_ID_WAR_DRUM)) {
            player.active_charge = 0;
            if (player.mp < player.mp_max) {
                player.mp++;
                hud_redraw_mp();
            }
            sfx_play(SFX_CLEAR);
        }
        // Enemy id 1 is used by BOTH the large stage boss
        // (giant flag ai_data[3]=1) and the room-3 mini-boss.
        // Only the GIANT advances the stage — a mini-boss kill
        // must not skip the stage boss (bug: it used to).
        if (eid == ENEMY_STONE_SENTINEL && entities[j].ai_data[3]) {
            fix8_t boss_x = entities[j].x;
            fix8_t boss_y = entities[j].y;
            i16 bx = FIX8_TO_INT(entities[j].x) + 12;
            i16 by = FIX8_TO_INT(entities[j].y) + 12;
            g_hitstop = 8;   // boss kill: big freeze
            room_shake(2, 26);   // the colossus hits the floor
            run_state.bosses_beaten++;
            // Campaign order is also the Oath unlock table:
            // this victory grants a permanent new active verb
            // for the current run, selectable in the Pack.
            // Every defeated arena opens before its reward or
            // ending screen. The final boss used to jump
            // straight to Victory with every threshold still
            // sealed, trapping endless descent in the arena.
            run_state.pending_unseal = 1;
            if (run_state.bosses_beaten >= BOSSES_TO_WIN) {
                run_state.victory = 1;
            }
            // The giant and its bullets release their slots
            // before effects. Rewards therefore remain real
            // pickups even in a completely saturated fight.
            entity_kill(j);
            boss_retired_for_rewards = 1;
            boss_link_active = boss_link_pending = 0;
            hud_show_boss_link(3);
            boss_clear_hostile_projectiles();
            // A stage clear is the run's deliberate recovery
            // beat. Grant one visible heart immediately so a
            // player who won the fight at low health enters
            // the next procedurally dangerous room with a
            // buffer, while the two physical heart drops
            // below still reward careful positioning and can
            // be saved at full health. This is sustain, not
            // a boss-fight heal: it happens only after the
            // colossus and its bullet storm are gone.
            if (!STATUS_PLAYER_HEALING_BLOCKED()
                && player.hp < player.hp_max) {
                if (player.hp <= (u8)(player.hp_max - 2))
                    player.hp = (u8)(player.hp + 2);
                else
                    player.hp = player.hp_max;
                hud_redraw_hp();
                sfx_play(SFX_HEART);
            }
            pickup_spawn(PICKUP_HEART_HALF, boss_x - FIX8(8), boss_y);
            pickup_spawn(PICKUP_HEART_HALF, boss_x + FIX8(16), boss_y);
            pickup_spawn(PICKUP_COIN_5, boss_x, boss_y - FIX8(8));
            pickup_spawn(PICKUP_COIN_5, boss_x, boss_y + FIX8(16));
            // Every colossus yields a class-attuned passive
            // item — the run's guaranteed power curve.
            pickup_spawn_item(pickup_boss_relic_for_class(),
                boss_x + FIX8(4), boss_y + FIX8(4));
            // Death explosion: staggered ring of impact FX.
            // These are allowed to drop if a later effect
            // burst fills the table; the rewards are not.
            fx_spawn(SPR_FX_IMPACT, 2, bx - 10, by - 10, 14);
            fx_spawn(SPR_FX_IMPACT, 2, bx + 10, by - 10, 18);
            fx_spawn(SPR_FX_IMPACT, 2, bx - 10, by + 10, 22);
            fx_spawn(SPR_FX_IMPACT, 2, bx + 10, by + 10, 26);
            fx_spawn(SPR_FX_IMPACT, 2, bx,      by,      30);
            // Stage clears themselves advance visible gear;
            // the guaranteed relic can advance it early too.
            room_refresh_player_appearance(1);
        } else if (eid == ENEMY_BOMBER) {
            // Bomber: death detonation — a 4-way revenge
            // burst. Kill it from a diagonal, or eat sparks.
            i16 dx2 = FIX8_TO_INT(entities[j].x);
            i16 dy2 = FIX8_TO_INT(entities[j].y);
            projectile_spawn_enemy(dx2, dy2, 0, -2, entities[j].damage);
            projectile_spawn_enemy(dx2, dy2, 0,  2, entities[j].damage);
            projectile_spawn_enemy(dx2, dy2, -2, 0, entities[j].damage);
            projectile_spawn_enemy(dx2, dy2,  2, 0, entities[j].damage);
        } else if ((eid == ENEMY_STONE_SENTINEL)
                   || (eid == ENEMY_DREAD_BELL
                       && entities[j].ai_data[2] == ENEMY_AUX_BELLWARDEN)) {
            // Mini-boss down: solid reward, no stage advance.
            // Bellwarden is a Dread Bell mechanically, but it
            // is tagged by procgen so it receives this same
            // weapon-orb preparation reward. Ordinary late
            // roster Bells remain ordinary enemy drops.
            u8 world_guard = (run_state.world_mode
                && run_state_riftwild_guard_active(
                    run_state.world_screen));
            // The first Warden is a meaningful stage fixture,
            // not an optional combat room. Its weapon orb is
            // the mechanical boon; this persistent mark tells
            // the sanctuary that the trial was completed.
            if (world_guard) {
                u8 gear = run_state_riftwild_guard_gear(
                    run_state.world_screen);
                run_state_riftwild_clear_guard();
                // First-region Wardens carry the three
                // permanent traversal implements. In later
                // regions the same distant fights remain
                // rewarding through a volatile Wildcard.
                if (gear < WAYGEAR_COUNT
                    && !(player.waygear_owned
                        & WAYGEAR_BIT(gear)))
                    pickup_spawn_waygear(gear,
                        entities[j].x + FIX8(12),
                        entities[j].y);
                else pickup_spawn_wildcard(
                    entities[j].x + FIX8(12),
                    entities[j].y);
            } else if (!run_state.world_mode) {
                u8 local = run_state_dungeon_local();
                if (local == run_state.mission_warden_cell)
                    run_state.dungeon_puzzles |= RUN_WARDEN_BOON_BIT;
                else if (local
                    == run_state.mission_deep_warden_cell)
                    run_state.dungeon_phase |= RUN_DEEP_WARDEN_BIT;
            }
            g_hitstop = 5;
            pickup_spawn(PICKUP_HEART_HALF, entities[j].x, entities[j].y - FIX8(8));
            pickup_spawn(PICKUP_COIN_5,     entities[j].x, entities[j].y + FIX8(8));
            if (!world_guard) {
                u8 w = pickup_weapon_from_roll(
                    rng_range(pickup_weapon_count()));
                if (w == player.starter_weapon)
                    w = pickup_next_weapon(w);
                pickup_spawn_weapon(w,
                    entities[j].x + FIX8(12), entities[j].y);
            }
        }
    }
    // Impact FX at enemy position
    fx_spawn(SPR_FX_IMPACT, 2,
        (i16)FIX8_TO_INT(entities[j].x),
        (i16)FIX8_TO_INT(entities[j].y), 8);
    if (entities[j].flags & (EF_ELITE | EF_ALPHA | EF_RARE)) {
        u8 recovery = (entities[j].flags & EF_ELITE)
            ? player.hp < player.hp_max
            : RUN_IS_EASY() ? player.hp < player.hp_max
            : (u16)player.hp * 2u <= player.hp_max;
        pickup_spawn(recovery
            ? PICKUP_HEART_HALF : PICKUP_COIN_5,
            entities[j].x, entities[j].y);
        score_add((eid < N_ENEMIES) ? enemies[eid].stats.score : 0);
    } else {
        pickup_roll_drop(entities[j].x, entities[j].y);
    }
    {
        // Rift Ooze: the apparent kill is only phase one.
        // Free its slot first so a full entity table still
        // guarantees at least one fragment, then seed two
        // fragile crawlers on opposite sides of the corpse.
        u8 split = (eid == ENEMY_RIFT_OOZE);
        u8 sx = (u8)(FIX8_TO_INT(entities[j].x) >> 3);
        u8 sy = (u8)(FIX8_TO_INT(entities[j].y) >> 3);
        // Boss rewards can occupy the just-freed boss slot.
        // Do not erase that first heart/item in the generic
        // cleanup after the giant has already been retired.
        if (!boss_retired_for_rewards) entity_kill(j);
        if (split) {
            // Generic pierce cleanup happens later, but its
            // lethal shot is the second free slot we need at
            // entity capacity. Retire it before fragment spawn.
            if (entities[i].hp <= 1) {
                entity_kill(i);
                shot_spent_for_split = 1;
            }
            u8 a = enemy_spawn(ENEMY_BLUE_CRAWLER, sx, sy);
            u8 b = enemy_spawn(ENEMY_BLUE_CRAWLER, sx, sy);
            if (a != 0xFF) {
                entities[a].hp = 2;
                entities[a].ai_data[1] = 90; // scatter beat
                entities[a].ai_data[2] = ENEMY_AUX_OOZE_FRAGMENT;
                enemy_try_step(&entities[a], -1, 0);
            }
            if (b != 0xFF) {
                entities[b].hp = 2;
                entities[b].ai_data[1] = 90;
                entities[b].ai_data[2] = ENEMY_AUX_OOZE_FRAGMENT;
                enemy_try_step(&entities[b], 1, 0);
            }
            // A still-piercing shot must see a fragment that landed past j.
            if (!shot_spent_for_split) combat_tail_rescan = 1;
        }
    }
    return shot_spent_for_split;
}

// The shot box is invariant across one sweep. Absolute WRAM loads stay
// cheaper than stack slots, and the damage body lives in its own function
// so a miss does not spill those temps on every entity.
static i16 shot_sx, shot_sy, shot_right, shot_bottom;
static u8 shot_sx_b, shot_sy_b, shot_right_b, shot_bottom_b, shot_box_wide;
static u8 shot_targets[MAX_ENTITIES];
static u8 shot_list_n;
static u8 shot_list_ready;

#define SHOT_MISSES(ej) ( \
    shot_right <= (ej)->x \
    || (i16)((ej)->x + (u8)((ej)->hitbox >> 4)) <= shot_sx \
    || shot_bottom <= (ej)->y \
    || (i16)((ej)->y + (u8)((ej)->hitbox & 0x0F)) <= shot_sy)

static void combat_load_shot_box(const entity_t *shot) {
    shot_sx = shot->x;
    shot_sy = shot->y;
    shot_right = (i16)(shot_sx + (u8)(shot->hitbox >> 4));
    shot_bottom = (i16)(shot_sy + (u8)(shot->hitbox & 0x0F));
    shot_sx_b = (u8)shot_sx;
    shot_sy_b = (u8)shot_sy;
    shot_right_b = (u8)shot_right;
    shot_bottom_b = (u8)shot_bottom;
    shot_box_wide = (u8)((u8)((u16)shot_sx >> 8) | (u8)((u16)shot_sy >> 8)
        | (u8)((u16)shot_right >> 8) | (u8)((u16)shot_bottom >> 8));
}

// In-room bodies fit in unsigned bytes. The signed fallback stays for a box
// that crosses 255 or goes negative, where a byte compare would wrap.
static u8 combat_shot_misses(entity_t *ej) {
    u8 ex, ey, hb;
    if (shot_box_wide) return SHOT_MISSES(ej);
    ex = (u8)ej->x;
    ey = (u8)ej->y;
    if ((u8)((u16)ej->x >> 8) | (u8)((u16)ej->y >> 8) || ex > 240 || ey > 240)
        return SHOT_MISSES(ej);
    hb = ej->hitbox;
    if (shot_right_b <= ex) return 1;
    if ((u8)(ex + (hb >> 4)) <= shot_sx_b) return 1;
    if (shot_bottom_b <= ey) return 1;
    if ((u8)(ey + (hb & 0x0F)) <= shot_sy_b) return 1;
    return 0;
}

static void combat_collect_targets(void) {
    u8 n = 0;
    u8 j;
    entity_t *ej = entities;
    for (j = 0; j < MAX_ENTITIES; ++j, ++ej) {
        u8 flags = ej->flags;
        if ((flags & (EF_ACTIVE | EF_ON_SCREEN)) != (EF_ACTIVE | EF_ON_SCREEN))
            continue;
        if (ej->type != ENT_ENEMY) continue;
        shot_targets[n++] = j;
    }
    shot_list_n = n;
    shot_list_ready = 1;
}

// Returns 1 when this shot is finished and the slot walk must stop.
u8 combat_apply_player_shot_hit(entity_t *shot, u8 i, entity_t *ej,
                                       u8 j, u8 *giant_hits) BANKED;

static u8 combat_cut_hostile_shot(entity_t *shot, u8 i, entity_t *ej, u8 j) {
    if (ej->type != ENT_PROJECTILE) return 0;
    if (ej->flags & EF_PLAYER_PROJ) return 0;
    if (!shot->ai_data[2]) return 0;
    if (combat_shot_misses(ej)) return 0;
    fx_spawn(SPR_FX_IMPACT, 6,
        FIX8_TO_INT(ej->x),
        FIX8_TO_INT(ej->y), 7);
    entity_kill(j);
    sfx_play(SFX_HIT);
    if (shot->hp <= 1) {
        entity_kill(i);
        return 1;
    }
    shot->hp--;
    return 0;
}

// Full slot walk used by melee, splash, and the tail after an ooze split.
// Returns 1 when the shot is spent.
static u8 combat_scan_slots(entity_t *shot, u8 i, u8 start, u8 *giant_hits) {
    u8 j;
    entity_t *ej = &entities[start];
    u8 splash = (u8)(shot->ai_data[6] == PROJ_AUX_SPLASH);
    for (j = start; j < MAX_ENTITIES; ++j, ++ej) {
        u8 flags;
        if (j == i) continue;
        flags = ej->flags;
        if (!(flags & EF_ACTIVE)) continue;
        if (ej->type == ENT_ENEMY && !(flags & EF_ON_SCREEN)) continue;
        if (combat_cut_hostile_shot(shot, i, ej, j)) return 1;
        if (ej->type != ENT_ENEMY) continue;
        if (splash) {
            if (shot->ai_data[5] == j || !splash_reaches_enemy(shot, ej))
                continue;
        } else if (hexa_boss_active && j == hexa_core_entity) {
            if (!hexa_shot_overlap(shot)) continue;
        } else if (j == large_boss_index) {
            if (!large_boss_shot_overlap(shot, ej)) continue;
        } else if (combat_shot_misses(ej)) continue;
        if (combat_apply_player_shot_hit(shot, i, ej, j, giant_hits)) return 1;
        if (combat_tail_rescan) {
            combat_tail_rescan = 0;
            // The fragment is already in a later slot of this same walk.
        }
    }
    return 0;
}

// Ordinary bullets only overlap on-screen enemies. Build that slot list
// once, in ascending order, and test the box inline. A split re-enters
// the full walk so a new fragment is not skipped.
static void combat_resolve_ordinary(entity_t *shot, u8 i, u8 *giant_hits) {
    u8 j, k;
    entity_t *ej;
    combat_load_shot_box(shot);
    combat_tail_rescan = 0;
    if (!shot_list_ready) combat_collect_targets();
    for (k = 0; k < shot_list_n; ++k) {
        j = shot_targets[k];
        ej = &entities[j];
        if (!(ej->flags & EF_ACTIVE)) continue;
        if (hexa_boss_active && j == hexa_core_entity) {
            if (!hexa_shot_overlap(shot)) continue;
        } else if (j == large_boss_index) {
            if (!large_boss_shot_overlap(shot, ej)) continue;
        } else if (combat_shot_misses(ej)) continue;
        if (combat_apply_player_shot_hit(shot, i, ej, j, giant_hits)) return;
        if (combat_tail_rescan) {
            combat_tail_rescan = 0;
            shot_list_ready = 0;
            combat_scan_slots(shot, i, (u8)(j + 1), giant_hits);
            return;
        }
    }
}

static void combat_resolve_player_shot(entity_t *shot, u8 i, u8 *giant_hits) {
    combat_load_shot_box(shot);
    combat_tail_rescan = 0;
    combat_scan_slots(shot, i, 0, giant_hits);
    shot_list_ready = 0;
}

static void combat_player_shots(void) {
    u8 i;
    entity_t *shot=entities;
    // One chord may hit a giant at most four times in this sweep.
    u8 convergence_giant_hits = 0;
    shot_list_ready = 0;
    // 1) Player-projectile -> enemy collisions
    for (i = 0; i < MAX_ENTITIES; ++i,++shot) {
        if (!(shot->flags & EF_ACTIVE)) continue;
        if (shot->type == ENT_PICKUP) {
            entity_pickup_pending = 1;
            continue;
        }
        if (shot->type != ENT_PROJECTILE) continue;
        if (!(shot->flags & EF_PLAYER_PROJ)) continue;
        // Splash arming happens in the next frame's projectile update. It then
        // receives exactly one complete sweep independent of entity slot order.
        if (shot->ai_data[6] == PROJ_AUX_SPLASH) {
            if (shot->ai_data[7] == 3) {
                entity_kill(i);
                continue;
            }
            if (shot->ai_data[7] != 2) continue;
            shot->ai_data[7] = 3;
        }
        // Melee that cuts shots, and splash bursts, still walk every slot.
        // Ordinary bullets only test the on-screen enemy list.
        if (shot->ai_data[2] || shot->ai_data[6] == PROJ_AUX_SPLASH)
            combat_resolve_player_shot(shot, i, &convergence_giant_hits);
        else
            combat_resolve_ordinary(shot, i, &convergence_giant_hits);
    }
}


u8 combat_resolve(void) BANKED {
    u8 i, j;
    u8 player_died = 0;

    if (!player.hp) {
        boss_link_pending = 0;
        return 1;
    }
    entity_pickup_pending = 0;

    // Tick down per-frame timers
    if (player.iframes > 0) player.iframes--;
    if (status_confused_projectiles)
        status_resolve_confused_projectiles();

    combat_player_shots();

    // Pickups are noted by the slot walk above, or by entity_spawn when a
    // drop appears during that walk. An empty field skips the banked scan.
    if (entity_pickup_pending) pickup_check_player_collision();

    // Sauran shield catches hostile shots; contact bodies are harmless while
    // it is raised. active_charge supplies the post-use cooldown.
    if (player.shield_timer > 0) {
        for (i = 0; i < MAX_ENTITIES; ++i) {
            if ((entities[i].flags & EF_ACTIVE)
                && entities[i].type == ENT_PROJECTILE
                && !(entities[i].flags & EF_PLAYER_PROJ)
                && shield_catches_projectile(&entities[i])) {
                fx_spawn(SPR_FX_IMPACT, 1,
                    FIX8_TO_INT(entities[i].x), FIX8_TO_INT(entities[i].y), 7);
                entity_kill(i);
                sfx_play(SFX_HIT);
            }
        }
    }

    // 3) Enemy bodies AND enemy projectiles -> player
    if (player.iframes == 0 && player.shield_timer == 0) {
        entity_t *hostile_entity=entities;
        for (i = 0; i < MAX_ENTITIES; ++i,++hostile_entity) {
            u8 hostile, touching;
            if (!(hostile_entity->flags & EF_ACTIVE)) continue;
            hostile = (hostile_entity->type == ENT_ENEMY)
                || (hostile_entity->type == ENT_PROJECTILE
                    && !(hostile_entity->flags & EF_PLAYER_PROJ));
            if (!hostile) continue;
            // Sleeping field bodies and authored vanish phases share one
            // authoritative collision flag. Compact enemies spawn visible.
            if (hostile_entity->type == ENT_ENEMY
                && !(hostile_entity->flags & EF_ON_SCREEN)) continue;
            // An attached Gloam Leech uses its own timed drain; ordinary body
            // collision would double-charge damage every iframe cycle.
            if (hostile_entity->type == ENT_ENEMY && hostile_entity->ai_data[0] == ENEMY_GLOAM_LEECH
                && hostile_entity->ai_data[6]) continue;
            if (i == large_boss_index) touching=large_boss_contact(hostile_entity);
            else if (hexa_boss_active && i == hexa_core_entity)
                touching = hexa_touches_player();
            else touching=aabb_overlap_player(hostile_entity);
            if (touching) {
                u8 was_projectile = (hostile_entity->type == ENT_PROJECTILE);
                if (was_projectile
                    && hostile_entity->ai_data[6] == PROJ_AUX_MORTAL_SCYTHE) {
                    stage_reaper_mortal_hit(i);
                    break;
                }
                // DEF soaks incoming damage (min 1 half-heart gets through).
                // A giant colossus is already a moving wall inside a dense
                // bullet pattern. Its body is a positioning tax, not a
                // second full-strength projectile.
                u8 taken = status_hostile_damage_taken(i);
                if (hostile_entity->type == ENT_ENEMY
                    && hostile_entity->ai_data[0] == ENEMY_STONE_SENTINEL
                    && hostile_entity->ai_data[3]) {
                    // Boss body contact is half its computed hit (round up,
                    // min 1): a real cost that scales with the stage without
                    // turning the body into a second full-strength bullet.
                    taken = (u8)((taken + 1) >> 1);
                    if (!taken) taken = 1;
                }
                // Tester Easy deliberately makes every impact legible but
                // inexpensive: one half-heart, regardless of late-game power.
                // Normal reaches this point unchanged.
                if (RUN_IS_EASY()) taken = 1;
                if (boss_link_active) boss_link_share(i,taken);
                if (player.hp > taken) {
                    player.hp = (u8)(player.hp - taken);
                    // Riftwild is traversal pressure, not a sealed combat
                    // arena. A doubled recovery beat there prevents one
                    // optional body from re-contacting at the exact moment
                    // the normal 30-frame knockback grace expires, while
                    // dungeon and boss hit pacing remains unchanged.
                    {
                        u8 recovery = run_state.world_mode ? 60
                            : (hostile_entity->type == ENT_ENEMY
                               && hostile_entity->ai_data[0] == ENEMY_STONE_SENTINEL
                               && hostile_entity->ai_data[3]) ? 45 : 30;
                        // Easy is a deliberately coarse deep-test assist, not
                        // a separately authored encounter table. The extended
                        // post-hit read/reposition beat keeps late bullet hell
                        // observable while Normal retains its exact cadence.
                        if (RUN_IS_EASY()) {
                            recovery = (u8)(recovery * EASY_IFRAME_MULTIPLIER);
                        }
                        player.iframes = recovery;
                    }
                    // Thorn Crown makes a risky contact build tangible: the
                    // hit still costs full health, then four modest player
                    // shots answer on the next combat sweep. Keeping it
                    // cardinal avoids filling the 32-entity pool with an
                    // eight-way burst during already-dense boss patterns.
                    if (combat_has_relic(ITEM_ID_THORN_CROWN)) {
                        u8 counter_atk = status_player_effective_stat(
                            QSTATUS_STAT_ATK);
                        u8 counter = (u8)(1 + (counter_atk >> 1));
                        g_shot_element = 0;
                        projectile_spawn_player(0, -1, counter, PROJ_BULLET);
                        projectile_spawn_player(1, 0, counter, PROJ_BULLET);
                        projectile_spawn_player(0, 1, counter, PROJ_BULLET);
                        projectile_spawn_player(-1, 0, counter, PROJ_BULLET);
                    }
                    g_hitstop = 3;
                    room_shake(1, 6);   // small jolt: that one hurt
                    sfx_play(SFX_HURT);
                    // Knockback: shove the player up to 6px away from the
                    // source, one wall-checked pixel at a time (Zelda feel +
                    // breaks contact so iframes aren't instantly re-spent).
                    {
                        i16 sx = FIX8_TO_INT(hostile_entity->x);
                        i16 sy = FIX8_TO_INT(hostile_entity->y);
                        i8 kx = ((i16)player.x > sx) ? 1 : ((i16)player.x < sx) ? -1 : 0;
                        i8 ky = ((i16)player.y > sy) ? 1 : ((i16)player.y < sy) ? -1 : 0;
                        u8 n;
                        for (n = 0; n < 6; ++n) {
                            i16 nx = (i16)(player.x + kx);
                            i16 ny = (i16)(player.y + ky);
                            if (!room_player_position_clear(nx, ny)) {
                                break;
                            }
                            player.x = (ppos_t)nx;
                            player.y = (ppos_t)ny;
                        }
                    }
                } else {
                    player.hp = 0;
                    player_died = 1;
                }
                // HP mutation and its visible contract belong to the same hit.
                // Without this, ordinary contact/projectile damage stayed on
                // the old heart row until a later pickup or room redraw.
                hud_redraw_hp();
                status_try_hostile_hit(i);
                if (was_projectile) entity_kill(i);   // bullet spent
                break;   // one hit per frame
            }
        }
    }

    if (boss_link_pending) {
        // Finish the source hit before retiring its boss and projectile slots.
        j = boss_link_pending - 1;
        boss_link_pending = 0;
        if (player.hp && entities[j].type == ENT_ENEMY
            && (entities[j].flags & EF_ACTIVE) && !entities[j].hp
            && entities[j].ai_data[0] == ENEMY_STONE_SENTINEL
            && (entities[j].ai_data[3] & 1) && entities[j].ai_data[2] == 5)
            combat_defeat_enemy(j,0xFF,0);
    }
    if (!player.hp) player_died = 1;
    return player_died;
}
