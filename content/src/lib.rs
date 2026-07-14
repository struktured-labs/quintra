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

use quintra_content::Registry;

pub fn registry() -> Registry {
    let mut r = Registry::new();
    items::register(&mut r);          // items first — classes reference items
    classes::register(&mut r);
    rooms::register(&mut r);          // rooms before biomes (biomes reference rooms)
    enemies::register(&mut r);        // enemies before biomes
    biomes::register(&mut r);
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
        assert_eq!(r.n_items(),         20);   // 5 weapons + 5 actives + 10 passives
        assert_eq!(r.n_enemies(),       15);   // includes stage-2 Cinder Maw
        assert_eq!(r.n_biomes(),         1);
        assert_eq!(r.n_room_templates(), 1);
        assert_eq!(r.n_stages(),         9);   // the whole run, in order
    }

    #[test]
    fn stage_bgr555_encoding_matches_hardware_layout() {
        use quintra_content::Rgb5;
        // BGR555: red in bits 0-4, green 5-9, blue 10-14
        assert_eq!(Rgb5(31, 0, 0).to_bgr555(), 0x001F);
        assert_eq!(Rgb5(0, 31, 0).to_bgr555(), 0x03E0);
        assert_eq!(Rgb5(0, 0, 31).to_bgr555(), 0x7C00);
    }
}
