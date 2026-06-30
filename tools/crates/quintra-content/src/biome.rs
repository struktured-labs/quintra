//! Biome definitions — top-level run zones.

use crate::refs::*;

// Container with static slices — no serde.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Biome {
    pub id: BiomeId,
    pub name: &'static str,
    pub depth_range: (u8, u8),                       // inclusive
    pub tileset: TilesetRef,
    pub bg_palettes: [PaletteRef; 4],
    pub music_track: MusicRef,
    pub enemy_pool: &'static [(EnemyId, u8)],        // (id, weight)
    pub room_template_pool: &'static [RoomTemplateId],
    pub min_rooms: u8,
    pub max_rooms: u8,
    pub has_shop: bool,
    pub has_altar: bool,
    pub boss: BossId,
}

impl Biome {
    pub fn validate(&self) -> Result<(), String> {
        if self.min_rooms == 0 || self.max_rooms < self.min_rooms {
            return Err(format!("biome {} room-count range invalid: [{},{}]",
                self.id.raw(), self.min_rooms, self.max_rooms));
        }
        if self.depth_range.0 > self.depth_range.1 {
            return Err(format!("biome {} depth_range inverted", self.id.raw()));
        }
        if self.enemy_pool.is_empty() {
            return Err(format!("biome {} has empty enemy_pool", self.id.raw()));
        }
        if self.room_template_pool.is_empty() {
            return Err(format!("biome {} has empty room_template_pool", self.id.raw()));
        }
        Ok(())
    }
}
