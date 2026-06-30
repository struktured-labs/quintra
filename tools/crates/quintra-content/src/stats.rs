//! Per-class base stats. See spec §6.

use serde::{Deserialize, Serialize};

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct BaseStats {
    pub hp_max: u8,   // half-hearts, 1-24
    pub mp_max: u8,   // 0-20
    pub atk:    u8,   // 1-15
    pub def:    u8,   // 0-10
    pub spd:    u8,   // 1-8 (px/tick fixed point)
}

impl BaseStats {
    pub const fn validate(&self) -> Result<(), &'static str> {
        if self.hp_max == 0 || self.hp_max > 24 { return Err("hp_max out of range [1,24]"); }
        if self.mp_max > 20                      { return Err("mp_max out of range [0,20]"); }
        if self.atk == 0 || self.atk > 15        { return Err("atk out of range [1,15]"); }
        if self.def > 10                         { return Err("def out of range [0,10]"); }
        if self.spd == 0 || self.spd > 8         { return Err("spd out of range [1,8]"); }
        Ok(())
    }
}
