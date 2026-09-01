#pragma bank 3
#include "audio/sfx.h"
#include "core/rng.h"
#include "core/types.h"
#include "game/combat.h"
#include "game/enemy_ai.h"
#include "game/entity.h"
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

u8 combat_resolve(void) BANKED {
    u8 i, j;
    u8 player_died = 0;
    // One Convergence chord launches eight arcs at once. A giant's 32x32
    // collision body used to overlap every arc in this same sweep, turning a
    // crowd-control crescendo into an accidental eightfold boss delete.
    // This counter is local to the sweep: the chord still hits every ordinary
    // enemy it reaches, while a colossus receives at most four readable
    // hits per cast rather than all eight overlapping arcs.
    u8 convergence_giant_hits = 0;

    // Tick down per-frame timers
    if (player.iframes > 0) player.iframes--;
    if (status_confused_projectiles)
        status_resolve_confused_projectiles();

    // 1) Player-projectile -> enemy collisions
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        if (entities[i].type   != ENT_PROJECTILE) continue;
        if (!(entities[i].flags & EF_PLAYER_PROJ)) continue;
        // Splash arming happens in the next frame's projectile update. It then
        // receives exactly one complete sweep independent of entity slot order.
        if (entities[i].ai_data[6] == PROJ_AUX_SPLASH) {
            if (entities[i].ai_data[7] == 3) {
                entity_kill(i);
                continue;
            }
            if (entities[i].ai_data[7] != 2) continue;
            entities[i].ai_data[7] = 3;
        }
        for (j = 0; j < MAX_ENTITIES; ++j) {
            u8 eid, weakness, poise, dmg;
            u8 shot_spent_for_split = 0;
            u8 boss_retired_for_rewards = 0;
            if (j == i) continue;
            if (!(entities[j].flags & EF_ACTIVE)) continue;
            if (entities[j].type == ENT_ENEMY
                && !(entities[j].flags & EF_ON_SCREEN)) continue;
            // Physical A weapons can cut hostile shots. Reuse the outer
            // player-projectile sweep instead of adding another 32x32 pass:
            // melee gains defensive space without taxing ordinary bullets.
            if (entities[j].type == ENT_PROJECTILE
                && !(entities[j].flags & EF_PLAYER_PROJ)
                && entities[i].ai_data[2]
                && aabb_overlap_ee(&entities[i], &entities[j])) {
                fx_spawn(SPR_FX_IMPACT, 6,
                    FIX8_TO_INT(entities[j].x),
                    FIX8_TO_INT(entities[j].y), 7);
                entity_kill(j);
                sfx_play(SFX_HIT);
                if (entities[i].hp <= 1) {
                    entity_kill(i);
                    break;
                }
                entities[i].hp--;
                continue;
            }
            if (entities[j].type != ENT_ENEMY) continue;
            if (entities[i].ai_data[6] == PROJ_AUX_SPLASH) {
                if (entities[i].ai_data[5] == j
                    || !splash_reaches_enemy(&entities[i], &entities[j]))
                    continue;
            } else if (!aabb_overlap_ee(&entities[i], &entities[j])) continue;

            eid      = entities[j].ai_data[0];
            if (entities[i].ai_data[6] == PROJ_AUX_BOOMERANG) {
                if (!(entities[j].flags & (EF_ELITE | EF_ALPHA))
                    && eid != ENEMY_STONE_SENTINEL
                    && eid != ENEMY_STAGE_REAPER
                    && entities[j].ai_data[2] != ENEMY_AUX_BELLWARDEN
                    && enemy_status_kind[j] != QSTATUS_STOP) {
                    status_enemy_apply(j, QSTATUS_STOP, 14);
                }
                continue;
            }
            // Keep specialist rejection out of this already-large resolver's
            // stack frame. The helper is entered only for authored armor,
            // shell, or projection bodies—not every ordinary contact.
            if (eid == ENEMY_FACET_RAM || eid == ENEMY_FOLD_STAR
                    || (eid < N_ENEMIES
                        && enemies[eid].ai_kind == AI_COUNTER_GUARD)) {
                enemy_special_reject_hit(i, j);
                // Projectile retirement is the authoritative rejection
                // result. Avoid carrying an SDCC banked return byte through
                // the helper's nested visual/audio calls.
                if (!(entities[i].flags & EF_ACTIVE)) break;
            }
            // Fang Forms is a two-body cleave, not two consecutive damage
            // ticks against one overlapping body. Preserve the projectile so
            // it can strike a different enemy farther down the same lane.
            if (entities[i].ai_data[6] == PROJ_AUX_WOLFKIN_FANG
                && entities[i].ai_data[5] == j) continue;
            if (eid == ENEMY_STONE_SENTINEL && entities[j].ai_data[3]
                && (entities[i].ai_data[3] & PROJ_FLAG_CONVERGENCE)) {
                if (convergence_giant_hits >= 4) {
                    // The spectacle has already landed on this colossus;
                    // spend the overlapping duplicate instead of applying
                    // another simultaneous full-damage arc.
                    entity_kill(i);
                    break;
                }
                convergence_giant_hits++;
            }
            if (eid == ENEMY_STONE_SENTINEL && entities[j].ai_data[3]
                && (entities[i].ai_data[3] & PROJ_FLAG_HOWL)) {
                if (will_howl_giant_hits >= WILL_HOWL_GIANT_HIT_CAP) {
                    entity_kill(i);
                    break;
                }
                will_howl_giant_hits++;
                // Each Howl lane may touch this giant only once. It retains
                // its normal pierce value against separate crowd bodies.
                entities[i].hp = 1;
            }
            weakness = (eid < N_ENEMIES) ? enemies[eid].stats.weakness : 0;
            // Large bosses reuse the Stone Sentinel entity definition for
            // storage/AI, but must not inherit its lightning-only weakness.
            // They also deliberately have no elemental weakness: making every
            // boss weak to every champion was an invisible 50% damage bonus
            // and let an untouched starter kit erase early colossi before
            // their patterns could become a fight. Ordinary enemies and
            // mini-bosses retain their authored matchups.
            if (eid == ENEMY_STONE_SENTINEL && entities[j].ai_data[3]) weakness = 0;
            poise    = (eid < N_ENEMIES) ? enemies[eid].stats.poise    : 0;
            poise = status_enemy_effective_poise(j, poise);

            // Per-hit damage: base + elemental x2 (weapon element in
            // projectile ai_data[1]) + crit x2 (LCK * 5% chance).
            // Vespine's venom synergy (perk 5): elemental hits bite +1.
            dmg = entities[i].damage;
            u8 weak = (entities[i].ai_data[1] & weakness) ? 1 : 0;
            if (weak) {
                dmg = (u8)(dmg + ((dmg + 1) >> 1));
                if (player.class_id == 4) dmg++;
            }
            if (rng_range(100)
                < (u8)(status_player_effective_stat(QSTATUS_STAT_LCK) * 5))
                dmg = (u8)(dmg << 1);
            if (player.class_id == 2 && will_corvin_mark_ticks
                && j == will_corvin_mark_slot) {
                dmg = (u8)(dmg + WILL_CORVIN_MARK_BONUS);
            }
            // Last Stand: down to your final heart (the low-HP pulse zone),
            // desperation lends +1 damage — a comeback edge one hit from death.
            if (player.hp <= 2 && player.hp > 0) dmg++;
            if (dmg == 0) dmg = 1;
            dmg = status_enemy_hit_damage(j, dmg);
            if (entities[i].ai_data[6] == PROJ_AUX_WOLFKIN_FANG)
                entities[i].ai_data[5] = j;

            // A fully built run can otherwise erase the one-byte (255 HP)
            // late bosses in a few rapid-fire beats. Ember Depths onward,
            // their Rift Armor turns a huge single projectile into a readable
            // sequence of hits rather than pretending the cartridge can hold
            // ever-larger HP values. That leaves the first three encounters
            // as accessible pattern lessons, while every later Colossus gets
            // time to show its authored phase break. The Void Lord is included
            // now that the controller has a tested, controller-only response
            // to its announced World Collapse pocket; it can no longer be
            // erased before that positional fight happens.
            // This intentionally applies only to giant stage bosses; normal
            // enemies, mini-bosses, and the first two bosses keep their full
            // weapon/elemental payoff.
            if (entities[j].ai_data[0] == ENEMY_STONE_SENTINEL
                && entities[j].ai_data[3]
                && entities[j].ai_data[2] >= 2
                && entities[j].ai_data[2] <= 8) {
                // Easy is the hands-on deep-content mode. Keep the same
                // Colossus HP, patterns, arena, and one-hit damage contract,
                // but let the strengthened tester kit pierce more Rift Armor
                // so a late mechanic can be replayed without every attempt
                // ending a few hits short. Normal retains its authored
                // three-damage endurance cap.
                u8 cap = RUN_IS_EASY() ? 5 : 3;
                if (dmg > cap) dmg = cap;
            }

            // Blast Seed is a true area interaction: the first direct body
            // impact consumes the marker and leaves a one-frame 15x15 burst.
            // Its payload remembers the struck slot so the target never takes
            // both direct and splash damage from the same hit.
            if (entities[i].ai_data[3] & PROJ_FLAG_SPLASH) {
                entities[i].ai_data[3] &= (u8)~PROJ_FLAG_SPLASH;
                projectile_spawn_splash(
                    FIX8_TO_INT(entities[i].x) + 3,
                    FIX8_TO_INT(entities[i].y) + 3,
                    dmg > 1 ? (u8)((dmg + 1) >> 1) : 1, j);
            }

            {
                // Apply damage
                if (entities[j].hp > dmg) {
                    entities[j].hp = (u8)(entities[j].hp - dmg);
                    status_try_player_shot(j, i);
                    entities[j].ai_data[7] = weak ? 7 : 4;  // hit-flash frames
                    knockback_enemy(&entities[j], entities[i].vx, entities[i].vy, poise);
                    if (g_hitstop < (weak ? 2 : 1)) g_hitstop = weak ? 2 : 1;
                    if (weak) {
                        // "Super effective": bright spark at the hit + crystal ping
                        i16 hx = FIX8_TO_INT(entities[j].x) + 4;
                        i16 hy = FIX8_TO_INT(entities[j].y) + 4;
                        fx_spawn(SPR_FX_IMPACT, 3, hx, hy, 10);
                        sfx_play(SFX_WEAK);
                    } else {
                        sfx_play(SFX_HIT);
                    }
                } else {
                    sfx_play(SFX_DEATH);
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
                    // Elites always pay out. Preserve their doubled HP and
                    // damage, but turn the sure reward into a small recovery
                    // when the fight actually cost health. At full health the
                    // same slot remains the established five-coin prize. This
                    // keeps hard Normal encounters dangerous while making an
                    // unlucky early elite a roguelike risk/reward beat instead
                    // of pure run attrition.
                    if (entities[j].flags & (EF_ELITE | EF_ALPHA)) {
                        pickup_spawn((player.hp < player.hp_max)
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
                        }
                    }
                }
                if (shot_spent_for_split) break;
                // Impact FX at bullet position (spawn on every hit, even non-kill)
                fx_spawn(SPR_FX_IMPACT, 2,
                    (i16)FIX8_TO_INT(entities[i].x),
                    (i16)FIX8_TO_INT(entities[i].y), 4);
                // Projectile pierce
                if (entities[i].hp <= 1) {
                    entity_kill(i);
                    break;     // this projectile is dead, move on
                } else {
                    entities[i].hp--;
                }
            }
        }
    }

    // 2) Pickup collisions (always processed; doesn't require iframes)
    pickup_check_player_collision();

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
        for (i = 0; i < MAX_ENTITIES; ++i) {
            u8 hostile;
            if (!(entities[i].flags & EF_ACTIVE)) continue;
            hostile = (entities[i].type == ENT_ENEMY)
                || (entities[i].type == ENT_PROJECTILE
                    && !(entities[i].flags & EF_PLAYER_PROJ));
            if (!hostile) continue;
            // Sleeping field bodies and authored vanish phases share one
            // authoritative collision flag. Compact enemies spawn visible.
            if (entities[i].type == ENT_ENEMY
                && !(entities[i].flags & EF_ON_SCREEN)) continue;
            // An attached Gloam Leech uses its own timed drain; ordinary body
            // collision would double-charge damage every iframe cycle.
            if (entities[i].type == ENT_ENEMY && entities[i].ai_data[0] == ENEMY_GLOAM_LEECH
                && entities[i].ai_data[6]) continue;
            if (aabb_overlap_player(&entities[i])) {
                u8 was_projectile = (entities[i].type == ENT_PROJECTILE);
                if (was_projectile
                    && entities[i].ai_data[6] == PROJ_AUX_MORTAL_SCYTHE) {
                    stage_reaper_mortal_hit(i);
                    break;
                }
                // DEF soaks incoming damage (min 1 half-heart gets through).
                // A giant colossus is already a moving wall inside a dense
                // bullet pattern. Its body is a positioning tax, not a
                // second full-strength projectile: keep contact at one
                // half-heart so close-range champions can trade a lunge for
                // space while the actual bullet-hell damage still escalates.
                u8 taken = status_hostile_damage_taken(i);
                if (entities[i].type == ENT_ENEMY
                    && entities[i].ai_data[0] == ENEMY_STONE_SENTINEL
                    && entities[i].ai_data[3]) taken = 1;
                // Tester Easy deliberately makes every impact legible but
                // inexpensive: one half-heart, regardless of late-game power.
                // Normal reaches this point unchanged.
                if (RUN_IS_EASY()) taken = 1;
                if (player.hp > taken) {
                    player.hp = (u8)(player.hp - taken);
                    // Riftwild is traversal pressure, not a sealed combat
                    // arena. A doubled recovery beat there prevents one
                    // optional body from re-contacting at the exact moment
                    // the normal 30-frame knockback grace expires, while
                    // dungeon and boss hit pacing remains unchanged.
                    {
                        u8 recovery = run_state.world_mode ? 60
                            : (entities[i].type == ENT_ENEMY
                               && entities[i].ai_data[0] == ENEMY_STONE_SENTINEL
                               && entities[i].ai_data[3]) ? 45 : 30;
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
                        i16 sx = FIX8_TO_INT(entities[i].x);
                        i16 sy = FIX8_TO_INT(entities[i].y);
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

    return player_died;
}
