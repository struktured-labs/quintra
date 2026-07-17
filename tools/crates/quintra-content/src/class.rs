//! Class definitions. 5 monster-human starters.

use serde::{Deserialize, Serialize};

use crate::refs::*;
use crate::stats::BaseStats;

// FormTheme is a value enum (no static refs) so it can keep serde for future RON.

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum FormTheme {
    Wolfkin,    // canine, speed
    Sauran,     // reptile, tank
    Corvin,     // avian, ranged witch
    Picsean,    // aquatic, mage
    Vespine,    // insectoid, duelist
}

// Container type with &'static str — no serde (hand-authored Rust consts only).
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Class {
    pub id: ClassId,
    pub name: &'static str,                // ≤8 chars (HUD constraint)
    pub form_theme: FormTheme,
    pub palette: PaletteRef,               // OBJ palette index
    // Player art is not content data: the renderer owns three fixed,
    // class-indexed atlases (idle, walk, ascended) so it can change poses
    // without duplicating tile-slot knowledge in every class declaration.
    pub starter_weapon: ItemId,            // bound to B, can't drop
    pub signature_active: ItemId,          // bound to A, 1-slot, recharges
    pub passive_perk: PerkId,
    pub base_stats: BaseStats,
}

impl Class {
    pub fn validate(&self) -> Result<(), String> {
        if self.name.is_empty() || self.name.len() > 8 {
            return Err(format!("class {} name length {} out of range [1,8]", self.id.raw(), self.name.len()));
        }
        self.base_stats.validate().map_err(|e| format!("class {} stats: {}", self.id.raw(), e))?;
        Ok(())
    }
}
