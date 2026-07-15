//! Item definitions: weapons, actives, passives, consumables.

use serde::{Deserialize, Serialize};

use crate::effects::{Effect, ProjectileKind};
use crate::refs::*;

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum Rarity { Common, Uncommon, Rare, Boss }

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum ItemKind {
    Weapon { fire_rate: u8, damage: u8, projectile: ProjectileKind, mp_cost: u8 },
    Active { cooldown_rooms: u8 },
    Passive,
    Consumable { uses: u8 },
}

// Container type with &'static str and &'static [Effect] — no serde.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Item {
    pub id: ItemId,
    pub name: &'static str,                // ≤12 chars
    pub description: &'static str,         // ≤64 chars (4×16)
    pub kind: ItemKind,
    pub icon_sprite: SpriteRef,
    pub palette: PaletteRef,
    pub rarity: Rarity,
    pub effects: &'static [Effect],
}

impl Item {
    pub fn validate(&self) -> Result<(), String> {
        if self.name.is_empty() || self.name.len() > 12 {
            return Err(format!("item {} name length out of range", self.id.raw()));
        }
        if self.description.len() > 64 {
            return Err(format!("item {} description length {} > 64", self.id.raw(), self.description.len()));
        }
        if self.effects.iter().any(|effect| {
            matches!(effect, Effect::StatBoost { delta: 0, .. })
        }) {
            return Err(format!("item {} contains a zero-delta stat boost", self.id.raw()));
        }
        Ok(())
    }
}
