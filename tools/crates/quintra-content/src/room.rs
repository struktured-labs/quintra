//! Room template definitions — pre-authored layouts with spawn slots.

use serde::{Deserialize, Serialize};

use crate::refs::*;

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum RoomSize {
    Small,    // 10×9 tiles
    Medium,   // 20×18 tiles (full screen)
    Large,    // 40×18 tiles (horizontal scroll)
}

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum RoomKind {
    Combat,
    Treasure,
    Shop,
    Altar,
    Puzzle,
    Boss,
}

/// Door bitmask: bit 0 = N, 1 = E, 2 = S, 3 = W
#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
#[serde(transparent)]
pub struct DoorMask(pub u8);
impl DoorMask {
    pub const N: u8 = 0x1;
    pub const E: u8 = 0x2;
    pub const S: u8 = 0x4;
    pub const W: u8 = 0x8;
    pub const fn empty() -> Self { Self(0) }
    pub const fn raw(self) -> u8 { self.0 }
    pub const fn has(self, dir: u8) -> bool { (self.0 & dir) != 0 }
}

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum SpawnRole {
    Enemy,        // engine picks from biome enemy pool
    Pickup,       // engine drops from biome drop table
    Hazard,
    Decoration,
}

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct SpawnSlot {
    pub x: u8,             // tile coord
    pub y: u8,
    pub role: SpawnRole,
}

// Container with &'static [SpawnSlot] — no serde.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct RoomTemplate {
    pub id: RoomTemplateId,
    pub size: RoomSize,
    pub layout: TilemapId,
    pub doors: DoorMask,
    pub spawn_slots: &'static [SpawnSlot],
    pub kind: RoomKind,
}

impl RoomTemplate {
    pub fn validate(&self) -> Result<(), String> {
        if self.spawn_slots.len() > 16 {
            return Err(format!("room {} has {} spawn_slots (max 16)",
                self.id.raw(), self.spawn_slots.len()));
        }
        Ok(())
    }
}
