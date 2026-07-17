//! Quintra game content — hand-authored entries assembled into a Registry
//! at codegen time. The build's source of truth for all classes, items,
//! enemies, biomes, and room templates.
//!
//! Add a new entry by:
//!   1. Defining the `Class` / `Item` / `Enemy` / `Biome` / `RoomTemplate`
//!      const in the corresponding module
//!   2. Adding it to that module's `register(reg)` function
//!   3. `cargo run -p quintra-codegen` — validation runs first

#![forbid(unsafe_code)]

pub mod ids;
pub mod classes;
pub mod items;
pub mod enemies;
pub mod biomes;
pub mod rooms;
pub mod stages;
pub mod zelda_overworld;

use quintra_content::Registry;

pub fn registry() -> Registry {
    let mut r = Registry::new();
    items::register(&mut r);          // items first — classes reference items
    classes::register(&mut r);
    rooms::register(&mut r);          // rooms before biomes (biomes reference rooms)
    enemies::register(&mut r);        // enemies before biomes
    biomes::register(&mut r);
    zelda_overworld::register(&mut r);
    stages::register(&mut r);         // the 9 themed stages (order = progression)
    r
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn registry_validates() {
        let r = registry();
        if let Err(errs) = r.validate() {
            panic!("content validation failed:\n  {}", errs.join("\n  "));
        }
    }

    #[test]
    fn registry_counts() {
        let r = registry();
        assert_eq!(r.n_classes(),        5);   // Wolfkin/Sauran/Corvin/Picsean/Vespine
        assert_eq!(r.n_items(),         21);   // 6 weapons + 5 actives + 10 passives
        assert_eq!(r.n_enemies(),       22);   // adds Dread Bell + Rift Warden lane breaker
        assert_eq!(r.n_biomes(),         1);
        assert_eq!(r.n_zelda_overworlds(), 1);
        assert_eq!(r.n_room_templates(), 1);
        assert_eq!(r.n_stages(),         9);   // the whole run, in order
    }

    #[test]
    fn enemy_machine_symbols_are_unique_and_validated() {
        let mut r = registry();
        r.enemies[1].symbol = r.enemies[0].symbol;
        let errors = r.validate().expect_err("duplicate enemy symbol was accepted");
        assert!(errors.iter().any(|e| e.contains("duplicate enemy symbol")));
    }

    #[test]
    fn enemy_runtime_identity_respects_obj_hardware_ranges() {
        use quintra_content::{PaletteRef, SpriteRef};
        let mut bad_tile = registry();
        bad_tile.enemies[0].sprite_set = SpriteRef::new(128);
        let errors = bad_tile.validate().expect_err("out-of-range OBJ tile was accepted");
        assert!(errors.iter().any(|e| e.contains("OBJ tile is outside")));

        let mut bad_palette = registry();
        bad_palette.enemies[0].palette = PaletteRef::new(8);
        let errors = bad_palette.validate().expect_err("out-of-range OBJ palette was accepted");
        assert!(errors.iter().any(|e| e.contains("OBJ palette is outside")));
    }

    #[test]
    fn sauran_scaled_hide_includes_promised_hp_bonus() {
        // player.c defines the passive contract as pre-baked into a
        // 12-half-heart base; keep authored content from silently drifting.
        assert_eq!(classes::SAURAN.base_stats.hp_max, 12);
    }

    #[test]
    fn champion_endurance_survival_floors_do_not_drift() {
        assert_eq!(classes::WOLFKIN.base_stats.hp_max, 10); // five hearts, true melee
        assert_eq!(classes::CORVIN.base_stats.hp_max, 12);  // six hearts
        assert_eq!(classes::PICSEAN.base_stats.hp_max, 14); // seven hearts, defensive caster
        assert_eq!(classes::VESPINE.base_stats.hp_max, 11); // five and a half hearts
    }

    #[test]
    fn stage_bgr555_encoding_matches_hardware_layout() {
        use quintra_content::Rgb5;
        // BGR555: red in bits 0-4, green 5-9, blue 10-14
        assert_eq!(Rgb5(31, 0, 0).to_bgr555(), 0x001F);
        assert_eq!(Rgb5(0, 31, 0).to_bgr555(), 0x03E0);
        assert_eq!(Rgb5(0, 0, 31).to_bgr555(), 0x7C00);
    }

    #[test]
    fn frost_vault_authors_the_mirror_moth_without_weight_inflation() {
        let frost = &stages::STAGES[3];
        assert!(frost.enemy_pool.iter().any(|&(id, _)| id == 16));
        assert_eq!(frost.enemy_pool.iter().map(|&(_, w)| w as u16).sum::<u16>(), 100);
    }

    #[test]
    fn toxic_mire_authors_the_mire_spore_without_weight_inflation() {
        let mire = &stages::STAGES[4];
        assert!(mire.enemy_pool.iter().any(|&(id, _)| id == 17));
        assert_eq!(mire.enemy_pool.iter().map(|&(_, w)| w as u16).sum::<u16>(), 100);
        assert_eq!(enemies::MIRE_SPORE.ai_script,
            quintra_content::AiScriptId::SporeMine { trigger_radius: 40, fuse_ticks: 36 });
    }

    #[test]
    fn golden_temple_authors_the_echo_guard_without_weight_inflation() {
        let temple = &stages::STAGES[6];
        assert!(temple.enemy_pool.iter().any(|&(id, _)| id == 18));
        assert_eq!(temple.enemy_pool.iter().map(|&(_, w)| w as u16).sum::<u16>(), 100);
        assert_eq!(enemies::ECHO_GUARD.ai_script,
            quintra_content::AiScriptId::CounterGuard { guard_cooldown: 100, rush_ticks: 24 });
    }

    #[test]
    fn late_stages_author_the_dread_bell_without_weight_inflation() {
        for stage in [&stages::STAGES[6], &stages::STAGES[7], &stages::STAGES[8]] {
            assert!(stage.enemy_pool.iter().any(|&(id, _)| id == 20));
            assert_eq!(stage.enemy_pool.iter().map(|&(_, w)| w as u16).sum::<u16>(), 100);
        }
        assert_eq!(enemies::DREAD_BELL.ai_script,
            quintra_content::AiScriptId::Shooter {
                fire_rate: 108,
                projectile: quintra_content::ProjectileKind::Bullet,
                pattern: quintra_content::ShotPattern::Ring(8),
            });
    }

    #[test]
    fn rift_warden_adds_late_fan_pressure_without_weight_inflation() {
        for stage in [&stages::STAGES[6], &stages::STAGES[7], &stages::STAGES[8]] {
            assert!(stage.enemy_pool.iter().any(|&(id, _)| id == 21));
            assert_eq!(stage.enemy_pool.iter().map(|&(_, w)| w as u16).sum::<u16>(), 100);
        }
        assert_eq!(enemies::RIFT_WARDEN.ai_script,
            quintra_content::AiScriptId::Shooter {
                fire_rate: 92,
                projectile: quintra_content::ProjectileKind::Bullet,
                pattern: quintra_content::ShotPattern::Fan(5),
            });
    }

    #[test]
    fn shadow_and_void_author_the_rune_lantern_without_weight_inflation() {
        for stage in [&stages::STAGES[5], &stages::STAGES[8]] {
            assert!(stage.enemy_pool.iter().any(|&(id, _)| id == 19));
            assert_eq!(stage.enemy_pool.iter().map(|&(_, w)| w as u16).sum::<u16>(), 100);
        }
        assert_eq!(enemies::RUNE_LANTERN.ai_script,
            quintra_content::AiScriptId::Shooter {
                fire_rate: 84,
                projectile: quintra_content::ProjectileKind::Bullet,
                pattern: quintra_content::ShotPattern::Ring(4),
            });
    }

    #[test]
    fn frost_vault_authors_the_stationary_sentry_without_weight_inflation() {
        let stage = &stages::STAGES[3];
        assert!(stage.enemy_pool.iter().any(|&(id, _)| id == 10));
        assert_eq!(stage.enemy_pool.iter().map(|&(_, w)| w as u16).sum::<u16>(), 100);
        assert_eq!(enemies::SENTRY.ai_script,
            quintra_content::AiScriptId::Turret { rotation: 1, fire_rate: 70 });
    }

    #[test]
    fn every_non_boss_enemy_is_reachable_from_a_procedural_stage_pool() {
        let r = registry();
        let pooled = |id| stages::STAGES.iter()
            .any(|stage| stage.enemy_pool.iter().any(|&(enemy, _)| enemy == id));
        for enemy in &r.enemies {
            let id = enemy.id.raw();
            if id != ids::ENEMY_STONE_SENTINEL.raw() {
                assert!(pooled(id), "enemy {} ({}) is unreachable from every stage pool",
                    id, enemy.name);
            }
        }
    }
}
