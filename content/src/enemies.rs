//! Enemy roster and stage-pool combat parameters.

use quintra_content::{AiScriptId, Enemy, EnemyStats, ProjectileKind, Registry, ShotPattern};

use crate::ids::*;

pub const BLUE_CRAWLER: Enemy = Enemy {
    id:         ENEMY_BLUE_CRAWLER,
    name:       "B. Crawler",
    sprite_set: SPRITE_CRAWLER,
    palette:    OBJ_PAL_CRAWLER,
    stats: EnemyStats {
        hp:       3,
        damage:   1,
        speed:    64,     // 0.25 px/tick (fixed point)
        score:    10,
        weakness: 0x01,   // Fire bit
        poise:    0,
    },
    ai_script:  AiScriptId::Walker,
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const STONE_SENTINEL: Enemy = Enemy {
    id:         ENEMY_STONE_SENTINEL,
    name:       "S.Sentinel",
    sprite_set: SPRITE_SENTINEL,
    palette:    OBJ_PAL_SENTINEL,
    stats: EnemyStats {
        hp:       50,
        damage:   2,
        speed:    32,
        score:    200,
        weakness: 0x04,   // Lightning
        poise:    8,
    },
    ai_script:  AiScriptId::Walker,
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const HORNET: Enemy = Enemy {
    id:         ENEMY_HORNET,
    name:       "Hornet",
    sprite_set: SPRITE_CRAWLER,
    palette:    OBJ_PAL_CRAWLER,
    stats: EnemyStats { hp: 2, damage: 1, speed: 96, score: 15, weakness: 0x02, poise: 0 },
    ai_script:  AiScriptId::Chaser,
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const SKELETON: Enemy = Enemy {
    id:         ENEMY_SKELETON,
    name:       "Skeleton",
    sprite_set: SPRITE_CRAWLER,
    palette:    OBJ_PAL_CRAWLER,
    stats: EnemyStats { hp: 5, damage: 1, speed: 64, score: 20, weakness: 0x08, poise: 1 },
    ai_script:  AiScriptId::Chaser,
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const ORC: Enemy = Enemy {
    id:         ENEMY_ORC,
    name:       "Orc",
    sprite_set: SPRITE_CRAWLER,
    palette:    OBJ_PAL_CRAWLER,
    stats: EnemyStats { hp: 10, damage: 2, speed: 48, score: 40, weakness: 0x11, poise: 3 },  // fire + poison
    ai_script:  AiScriptId::Charger { telegraph_ticks: 30, charge_speed: 96 },
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const WISP: Enemy = Enemy {
    id:         ENEMY_WISP,
    name:       "Wisp",
    sprite_set: SPRITE_CRAWLER,
    palette:    OBJ_PAL_CRAWLER,
    stats: EnemyStats { hp: 2, damage: 1, speed: 32, score: 25, weakness: 0x04, poise: 0 },
    ai_script:  AiScriptId::Shooter {
        fire_rate: 90,
        projectile: ProjectileKind::Bullet,
        pattern: ShotPattern::Single,
    },
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const BOMBER: Enemy = Enemy {
    id:         ENEMY_BOMBER,
    name:       "Bomber",
    sprite_set: SPRITE_CRAWLER,
    palette:    OBJ_PAL_CRAWLER,
    // Chunky slow walker. The real threat is the death detonation —
    // combat.c fires a 4-way revenge burst when it dies.
    stats: EnemyStats { hp: 4, damage: 2, speed: 40, score: 35, weakness: 0x02, poise: 2 },
    ai_script:  AiScriptId::Walker,
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const SHADE: Enemy = Enemy {
    id:         ENEMY_SHADE,
    name:       "Shade",
    sprite_set: SPRITE_CRAWLER,
    palette:    OBJ_PAL_CRAWLER,
    // Fragile ambusher: vanishes, reappears beside you, strikes. Weak to
    // shadow (Corvin unmakes what hides in the dark).
    stats: EnemyStats { hp: 3, damage: 2, speed: 48, score: 45, weakness: 0x08, poise: 0 },
    ai_script:  AiScriptId::Teleporter { blink_rate: 110, appear_dist: 28 },
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const WARLOCK: Enemy = Enemy {
    id:         ENEMY_WARLOCK,
    name:       "Warlock",
    sprite_set: SPRITE_CRAWLER,
    palette:    OBJ_PAL_CRAWLER,
    // Deep-stage caster: slow drift, three-way fanned volleys. The first
    // enemy to exercise the content ShotPattern beyond Single.
    stats: EnemyStats { hp: 5, damage: 2, speed: 32, score: 55, weakness: 0x04, poise: 1 },
    ai_script:  AiScriptId::Shooter {
        fire_rate: 100,
        projectile: ProjectileKind::Bullet,
        pattern: ShotPattern::Fan(3),
    },
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const ROPE: Enemy = Enemy {
    id:         ENEMY_ROPE,
    name:       "Rope",
    sprite_set: SPRITE_CRAWLER,
    palette:    OBJ_PAL_CRAWLER,
    // Classic Zelda snake: slithers idly, then bee-lines straight at you
    // when you share its row or column. Pure contact damage, no shots.
    // Fragile but fast on the charge — a short telegraph keeps it fair.
    stats: EnemyStats { hp: 3, damage: 2, speed: 64, score: 20, weakness: 0x01, poise: 0 },
    ai_script:  AiScriptId::Charger { telegraph_ticks: 14, charge_speed: 96 },
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const SENTRY: Enemy = Enemy {
    id:         ENEMY_SENTRY,
    name:       "Sentry",
    sprite_set: SPRITE_CRAWLER,
    palette:    OBJ_PAL_CRAWLER,
    // Stationary turret: never moves, fires a rotating 4-way cross that
    // sweeps the room. Deny-space zoner; lightning-weak, moderate HP so
    // it's a persistent hazard you route around or burn down.
    stats: EnemyStats { hp: 6, damage: 2, speed: 0, score: 40, weakness: 0x04, poise: 4 },
    ai_script:  AiScriptId::Turret { rotation: 1, fire_rate: 55 },
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const FOLDING_STAR: Enemy = Enemy {
    id:         ENEMY_FOLDING_STAR,
    name:       "Fold Star",
    sprite_set: SPRITE_CRAWLER,
    palette:    OBJ_PAL_CRAWLER,
    // A spatial timing enemy: it blooms into untouchable diagonal echoes in
    // a deliberately lopsided rhythm, then contracts for a brief damage
    // window. Shadow cuts through its false geometry most effectively.
    stats: EnemyStats { hp: 7, damage: 2, speed: 56, score: 60, weakness: 0x08, poise: 2 },
    // One full second contracted gives slow melee champions a real punish
    // window after reading the 83-frame bloom; damage is still rejected for
    // the entire expanded phase.
    ai_script:  AiScriptId::Replicator { open_ticks: 83, closed_ticks: 60 },
    drop_table: DROP_SMALL_COIN,
    biomes:     &[BIOME_CRYSTAL_CAVERNS],
};

pub const FLUTTERBAT: Enemy = Enemy {
    id: ENEMY_FLUTTERBAT, name: "Flutterbat", sprite_set: SPRITE_CRAWLER,
    palette: OBJ_PAL_CRAWLER,
    stats: EnemyStats { hp: 2, damage: 1, speed: 80, score: 18, weakness: 0x04, poise: 0 },
    ai_script: AiScriptId::Walker, drop_table: DROP_SMALL_COIN,
    biomes: &[BIOME_CRYSTAL_CAVERNS],
};

pub const GLOAM_LEECH: Enemy = Enemy {
    id: ENEMY_GLOAM_LEECH, name: "GloomLeech", sprite_set: SPRITE_CRAWLER,
    palette: OBJ_PAL_CRAWLER,
    stats: EnemyStats { hp: 4, damage: 1, speed: 72, score: 35, weakness: 0x02, poise: 0 },
    ai_script: AiScriptId::Chaser, drop_table: DROP_SMALL_COIN,
    biomes: &[BIOME_CRYSTAL_CAVERNS],
};

pub const CINDER_MAW: Enemy = Enemy {
    id: ENEMY_CINDER_MAW, name: "CinderMaw", sprite_set: SPRITE_CRAWLER,
    palette: OBJ_PAL_CRAWLER,
    // Stage-2 specialist: a durable, slow caster whose three-way volleys
    // turn Ember Depths into a routing problem without adding contact speed.
    stats: EnemyStats { hp: 6, damage: 2, speed: 24, score: 50, weakness: 0x02, poise: 2 },
    ai_script: AiScriptId::Shooter {
        fire_rate: 105,
        projectile: ProjectileKind::Bullet,
        pattern: ShotPattern::Fan(3),
    },
    drop_table: DROP_SMALL_COIN,
    biomes: &[BIOME_CRYSTAL_CAVERNS],
};

pub const RIFT_OOZE: Enemy = Enemy {
    id: ENEMY_RIFT_OOZE, name: "Rift Ooze", sprite_set: SPRITE_CRAWLER,
    palette: OBJ_PAL_CRAWLER,
    // A modest body with a dangerous second beat: combat.c cracks it into
    // two 2-HP crawler fragments on death. Its low contact damage keeps the
    // surprise readable instead of turning one kill into unavoidable burst.
    stats: EnemyStats { hp: 6, damage: 1, speed: 40, score: 45, weakness: 0x01, poise: 2 },
    ai_script: AiScriptId::Walker, drop_table: DROP_SMALL_COIN,
    biomes: &[BIOME_CRYSTAL_CAVERNS],
};

pub fn register(r: &mut Registry) {
    r.add_enemy(BLUE_CRAWLER.clone());
    r.add_enemy(STONE_SENTINEL.clone());
    r.add_enemy(HORNET.clone());
    r.add_enemy(SKELETON.clone());
    r.add_enemy(ORC.clone());
    r.add_enemy(WISP.clone());
    r.add_enemy(BOMBER.clone());
    r.add_enemy(SHADE.clone());
    r.add_enemy(WARLOCK.clone());
    r.add_enemy(ROPE.clone());
    r.add_enemy(SENTRY.clone());
    r.add_enemy(FOLDING_STAR.clone());
    r.add_enemy(FLUTTERBAT.clone());
    r.add_enemy(GLOAM_LEECH.clone());
    r.add_enemy(CINDER_MAW.clone());
    r.add_enemy(RIFT_OOZE.clone());
}
