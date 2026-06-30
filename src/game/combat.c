#include "core/types.h"
#include "game/combat.h"
#include "game/entity.h"
#include "game/pickup.h"
#include "game/player.h"

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
                } else {
                    // Drop pickup at enemy position before killing
                    pickup_roll_drop(entities[j].x, entities[j].y);
                    entity_kill(j);
                }
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

    // 3) Enemy -> player contact (respects iframes)
    if (player.iframes == 0) {
        for (i = 0; i < MAX_ENTITIES; ++i) {
            if (!(entities[i].flags & EF_ACTIVE)) continue;
            if (entities[i].type != ENT_ENEMY)    continue;
            if (aabb_overlap_player(&entities[i])) {
                if (player.hp > entities[i].damage) {
                    player.hp = (u8)(player.hp - entities[i].damage);
                    player.iframes = 30;
                } else {
                    player.hp = 0;
                    player_died = 1;
                }
                break;   // one hit per frame
            }
        }
    }

    return player_died;
}
