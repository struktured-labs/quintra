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
#include "render/tiles.h"
#include "render/hud.h"
#include "content.h"

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

    // 1) Player-projectile -> enemy collisions
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        if (entities[i].type   != ENT_PROJECTILE) continue;
        if (!(entities[i].flags & EF_PLAYER_PROJ)) continue;
        for (j = 0; j < MAX_ENTITIES; ++j) {
            u8 eid, weakness, poise, dmg;
            u8 shot_spent_for_split = 0;
            u8 boss_retired_for_rewards = 0;
            if (j == i) continue;
            if (!(entities[j].flags & EF_ACTIVE)) continue;
            if (entities[j].type != ENT_ENEMY) continue;
            if (!aabb_overlap_ee(&entities[i], &entities[j])) continue;

            eid      = entities[j].ai_data[0];
            // Echo Guard: the first hit is a readable shield parry. It spends
            // the projectile, launches a short rush, then exposes the guard
            // for the remainder of its authored cooldown.
            if (eid == ENEMY_ECHO_GUARD && entities[j].state == 0) {
                entities[j].state = 1;
                entities[j].state_timer = enemies[eid].ai_p1;
                entities[j].ai_data[6] = enemies[eid].ai_p0;
                entities[j].palette = 4;
                entities[j].ai_data[7] = 10;
                fx_spawn(SPR_FX_IMPACT, 3,
                    FIX8_TO_INT(entities[i].x), FIX8_TO_INT(entities[i].y), 8);
                sfx_play(SFX_WEAK);
                entity_kill(i);
                break;
            }
            // Folding Star: expanded geometry is an invulnerable projection.
            // Shots still burst on contact, teaching the player to wait for
            // the bright contracted core rather than passing through it.
            if (eid == ENEMY_FOLD_STAR && entities[j].state != 0) {
                sfx_play(SFX_HIT);
                fx_spawn(SPR_FX_IMPACT, 0,
                    FIX8_TO_INT(entities[i].x), FIX8_TO_INT(entities[i].y), 5);
                entity_kill(i);
                break;
            }
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

            // Per-hit damage: base + elemental x2 (weapon element in
            // projectile ai_data[1]) + crit x2 (LCK * 5% chance).
            // Vespine's venom synergy (perk 5): elemental hits bite +1.
            dmg = entities[i].damage;
            u8 weak = (entities[i].ai_data[1] & weakness) ? 1 : 0;
            if (weak) {
                dmg = (u8)(dmg + ((dmg + 1) >> 1));
                if (player.class_id == 4) dmg++;
            }
            if (rng_range(100) < (u8)(player.lck * 5)) dmg = (u8)(dmg << 1);
            // Last Stand: down to your final heart (the low-HP pulse zone),
            // desperation lends +1 damage — a comeback edge one hit from death.
            if (player.hp <= 2 && player.hp > 0) dmg++;
            if (dmg == 0) dmg = 1;

            // A fully built run can otherwise erase the one-byte (255 HP)
            // late bosses in a few rapid-fire beats.  Golden Temple onward,
            // their Rift Armor turns a huge single projectile into a readable
            // sequence of hits rather than pretending the cartridge can hold
            // ever-larger HP values. Golden Temple and Bloodmoon receive the
            // 3-damage cap. The Void Lord is included now that the controller
            // has a tested, controller-only response to its announced World
            // Collapse pocket; it can no longer be erased before that
            // positional fight happens.
            // This intentionally applies only to giant stage bosses; normal
            // enemies, mini-bosses, and the first six bosses keep their full
            // weapon/elemental payoff.
            if (entities[j].ai_data[0] == ENEMY_STONE_SENTINEL
                && entities[j].ai_data[3]
                && entities[j].ai_data[2] >= 6
                && entities[j].ai_data[2] <= 8) {
                u8 cap = 3;
                if (dmg > cap) dmg = cap;
            }

            {
                // Apply damage
                if (entities[j].hp > dmg) {
                    entities[j].hp = (u8)(entities[j].hp - dmg);
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
                        run_state.enemies_killed++;
                        // Vampiric Sigil (item id 29): slow dungeon sustain.
                        // Multiple copies keep their stat boosts but do not
                        // multiply the heal, avoiding runaway immortality.
                        if ((run_state.enemies_killed % 5) == 0
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
                            if (run_state.bosses_beaten >= BOSSES_TO_WIN) {
                                run_state.victory = 1;
                            } else {
                                run_state.pending_unseal = 1;
                            }
                            // The giant and its bullets release their slots
                            // before effects. Rewards therefore remain real
                            // pickups even in a completely saturated fight.
                            entity_kill(j);
                            boss_retired_for_rewards = 1;
                            boss_clear_hostile_projectiles();
                            pickup_spawn(PICKUP_HEART_HALF, boss_x - FIX8(8), boss_y);
                            pickup_spawn(PICKUP_HEART_HALF, boss_x + FIX8(16), boss_y);
                            pickup_spawn(PICKUP_COIN_5, boss_x, boss_y - FIX8(8));
                            pickup_spawn(PICKUP_COIN_5, boss_x, boss_y + FIX8(16));
                            // Every colossus yields a passive item — the
                            // run's guaranteed power curve (indices 10..19).
                            pickup_spawn_item((u8)(10 + rng_range(10)),
                                boss_x + FIX8(4), boss_y + FIX8(4));
                            // Death explosion: staggered ring of impact FX.
                            // These are allowed to drop if a later effect
                            // burst fills the table; the rewards are not.
                            fx_spawn(SPR_FX_IMPACT, 2, bx - 10, by - 10, 14);
                            fx_spawn(SPR_FX_IMPACT, 2, bx + 10, by - 10, 18);
                            fx_spawn(SPR_FX_IMPACT, 2, bx - 10, by + 10, 22);
                            fx_spawn(SPR_FX_IMPACT, 2, bx + 10, by + 10, 26);
                            fx_spawn(SPR_FX_IMPACT, 2, bx,      by,      30);
                        } else if (eid == ENEMY_BOMBER) {
                            // Bomber: death detonation — a 4-way revenge
                            // burst. Kill it from a diagonal, or eat sparks.
                            i16 dx2 = FIX8_TO_INT(entities[j].x);
                            i16 dy2 = FIX8_TO_INT(entities[j].y);
                            projectile_spawn_enemy(dx2, dy2, 0, -2, entities[j].damage);
                            projectile_spawn_enemy(dx2, dy2, 0,  2, entities[j].damage);
                            projectile_spawn_enemy(dx2, dy2, -2, 0, entities[j].damage);
                            projectile_spawn_enemy(dx2, dy2,  2, 0, entities[j].damage);
                        } else if (eid == ENEMY_STONE_SENTINEL) {
                            // Mini-boss down: solid reward, no stage advance.
                            // Always drops a weapon orb you don't hold —
                            // the run's main way to change your A-weapon.
                            u8 w = pickup_weapon_from_roll(rng_range(pickup_weapon_count()));
                            if (w == player.starter_weapon) w = pickup_next_weapon(w);
                            g_hitstop = 5;
                            pickup_spawn(PICKUP_HEART_HALF, entities[j].x, entities[j].y - FIX8(8));
                            pickup_spawn(PICKUP_COIN_5,     entities[j].x, entities[j].y + FIX8(8));
                            pickup_spawn_weapon(w, entities[j].x + FIX8(12), entities[j].y);
                        }
                    }
                    // Impact FX at enemy position
                    fx_spawn(SPR_FX_IMPACT, 2,
                        (i16)FIX8_TO_INT(entities[j].x),
                        (i16)FIX8_TO_INT(entities[j].y), 8);
                    // Elites always pay out
                    if (entities[j].flags & EF_ELITE) {
                        pickup_spawn(PICKUP_COIN_5, entities[j].x, entities[j].y);
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
                                enemy_try_step(&entities[a], -1, 0);
                            }
                            if (b != 0xFF) {
                                entities[b].hp = 2;
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
                && aabb_overlap_player_wide(&entities[i])) {
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
            // An attached Gloam Leech uses its own timed drain; ordinary body
            // collision would double-charge damage every iframe cycle.
            if (entities[i].type == ENT_ENEMY && entities[i].ai_data[0] == ENEMY_GLOAM_LEECH
                && entities[i].ai_data[6]) continue;
            if (aabb_overlap_player(&entities[i])) {
                u8 was_projectile = (entities[i].type == ENT_PROJECTILE);
                // DEF soaks incoming damage (min 1 half-heart gets through).
                // A giant colossus is already a moving wall inside a dense
                // bullet pattern. Its body is a positioning tax, not a
                // second full-strength projectile: keep contact at one
                // half-heart so close-range champions can trade a lunge for
                // space while the actual bullet-hell damage still escalates.
                u8 taken = (entities[i].damage > player.def)
                    ? (u8)(entities[i].damage - player.def) : 1;
                if (entities[i].type == ENT_ENEMY
                    && entities[i].ai_data[0] == ENEMY_STONE_SENTINEL
                    && entities[i].ai_data[3]) taken = 1;
                if (player.hp > taken) {
                    player.hp = (u8)(player.hp - taken);
                    player.iframes = 30;
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
                            if (!room_tile_walkable(room_tile_at_px(nx + 2,  ny + 8))
                                || !room_tile_walkable(room_tile_at_px(nx + 13, ny + 8))
                                || !room_tile_walkable(room_tile_at_px(nx + 2,  ny + 15))
                                || !room_tile_walkable(room_tile_at_px(nx + 13, ny + 15))) {
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
                if (was_projectile) entity_kill(i);   // bullet spent
                break;   // one hit per frame
            }
        }
    }

    return player_died;
}
