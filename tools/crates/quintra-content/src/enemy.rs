//! Enemy definitions + AI script vocabulary.

use serde::{Deserialize, Serialize};

use crate::effects::ProjectileKind;
use crate::refs::*;

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct EnemyStats {
    pub hp:       u8,    // 1-250
    pub damage:   u8,    // contact damage in half-hearts
    pub speed:    u8,    // px/tick fixed point
    pub score:    u8,    // points on kill
    pub weakness: u8,    // element bitmask: 1=Fire 2=Ice 4=Lightning 8=Shadow 16=Poison
    pub poise:    u8,    // hits before flinching (boss armor)
}

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum ShotPattern {
    Single,                 // one shot toward player
    Fan(u8),                // N shots in fan
    Ring(u8),               // N shots in ring
    Burst(u8),              // N rapid shots
    Spiral { steps: u8 },   // rotating
}

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum AiScriptId {
    Walker,                                                                  // straight line, ignores player
    Chaser,                                                                  // pathfind 4-dir
    Charger  { telegraph_ticks: u8, charge_speed: u8 },
    Shooter  { fire_rate: u8, projectile: ProjectileKind, pattern: ShotPattern },
    Spinner  { radius: u8, fire_rate: u8 },
    Turret   { rotation: u8, fire_rate: u8 },
    // Penta DNA — bullet-hell flavors:
    SprayPattern { angles: u8, fire_rate: u8 },
    AimedBurst   { burst_size: u8, recovery_ticks: u8 },
    /// Vanish, reappear near the player, strike-window, repeat.
    Teleporter   { blink_rate: u8, appear_dist: u8 },
}

// Container with &'static str and &'static [BiomeId] — no serde.
#[derive(Clone, PartialEq, Eq, Debug)]
pub struct Enemy {
    pub id: EnemyId,
    pub name: &'static str,
    pub sprite_set: SpriteRef,
    pub palette: PaletteRef,
    pub stats: EnemyStats,
    pub ai_script: AiScriptId,
    pub drop_table: DropTableId,
    pub biomes: &'static [BiomeId],
}

impl Enemy {
    pub fn validate(&self) -> Result<(), String> {
        if self.name.is_empty() || self.name.len() > 12 {
            return Err(format!("enemy {} name length out of range", self.id.raw()));
        }
        if self.stats.hp == 0 {
            return Err(format!("enemy {} hp is 0", self.id.raw()));
        }
        Ok(())
    }
}
