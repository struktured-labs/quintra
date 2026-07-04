#include "audio/sfx.h"
#include "core/types.h"
#include "game/combat.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"
#include "game/run_state.h"
#include "render/tiles.h"
#include "content.h"

u8 combat_resolve(void) {
    u8 i, j;
    u8 player_died = 0;

    // Tick down per-frame timers
    if (player.iframes > 0)        player.iframes--;
    if (player.active_charge > 0)  /* room-based charge stays */;

    // 1) Player-projectile -> enemy collisions
    for (i = 0; i < MAX_ENTITIES; ++i) {
        if (!(entities[i].flags & EF_ACTIVE)) continue;
        if (entities[i].type   != ENT_PROJECTILE) continue;
        if (!(entities[i].flags & EF_PLAYER_PROJ)) continue;
        for (j = 0; j < MAX_ENTITIES; ++j) {
            if (j == i) continue;
            if (!(entities[j].flags & EF_ACTIVE)) continue;
            if (entities[j].type != ENT_ENEMY) continue;
            if (aabb_overlap_ee(&entities[i], &entities[j])) {
                // Apply damage
                if (entities[j].hp > entities[i].damage) {
                    entities[j].hp = (u8)(entities[j].hp - entities[i].damage);
                    sfx_play(SFX_HIT);
                } else {
                    sfx_play(SFX_DEATH);
                    {
                        u8 eid = entities[j].ai_data[0];
                        if (eid < N_ENEMIES) {
                            u16 s = run_state.score + (u16)enemies[eid].stats.score;
                            run_state.score = s;
                        }
                        run_state.enemies_killed++;
                        if (eid == 1) {
                            // Boss down: reward burst + unseal, or final victory
                            run_state.bosses_beaten++;
                            if (run_state.bosses_beaten >= BOSSES_TO_WIN) {
                                run_state.victory = 1;
                            } else {
                                run_state.pending_unseal = 1;
                            }
                            pickup_spawn(PICKUP_HEART_HALF, entities[j].x - FIX8(8), entities[j].y);
                            pickup_spawn(PICKUP_HEART_HALF, entities[j].x + FIX8(16), entities[j].y);
                            pickup_spawn(PICKUP_COIN_5, entities[j].x, entities[j].y - FIX8(8));
                            pickup_spawn(PICKUP_COIN_5, entities[j].x, entities[j].y + FIX8(16));
                        }
                    }
                    // Impact FX at enemy position
                    fx_spawn(SPR_FX_IMPACT, 2,
                        (i16)FIX8_TO_INT(entities[j].x),
                        (i16)FIX8_TO_INT(entities[j].y), 8);
                    pickup_roll_drop(entities[j].x, entities[j].y);
                    entity_kill(j);
                }
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

    // 3) Enemy bodies AND enemy projectiles -> player (respects iframes)
    if (player.iframes == 0) {
        for (i = 0; i < MAX_ENTITIES; ++i) {
            u8 hostile;
            if (!(entities[i].flags & EF_ACTIVE)) continue;
            hostile = (entities[i].type == ENT_ENEMY)
                || (entities[i].type == ENT_PROJECTILE
                    && !(entities[i].flags & EF_PLAYER_PROJ));
            if (!hostile) continue;
            if (aabb_overlap_player(&entities[i])) {
                u8 was_projectile = (entities[i].type == ENT_PROJECTILE);
                if (player.hp > entities[i].damage) {
                    player.hp = (u8)(player.hp - entities[i].damage);
                    player.iframes = 30;
                    sfx_play(SFX_HURT);
                } else {
                    player.hp = 0;
                    player_died = 1;
                }
                if (was_projectile) entity_kill(i);   // bullet spent
                break;   // one hit per frame
            }
        }
    }

    return player_died;
}
