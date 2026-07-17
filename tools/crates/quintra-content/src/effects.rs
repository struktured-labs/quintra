//! Item Effects and Triggers — the composable hook vocabulary.

use serde::{Deserialize, Serialize};

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum Stat { Hp, Mp, Atk, Def, Spd, Lck }

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum ProjectileKind {
    Bullet,        // straight line, single hit
    Bolt,          // straight line, pierces 2
    Homing,        // tracks nearest enemy
    Wave,          // sine wave
    Spread3,       // 3 bullets in 30° fan
    Spread5,       // 5 bullets in 50° fan
    Boomerang,     // out-and-back
    Bomb,          // arcs, explodes on contact
    Laser,         // instant beam (1-frame)
    Bubble,        // slow, pierces water tiles
    Spike,         // melee range, short forward thrust
    Shuriken,      // homing-lite, returns after hit
    Flail,         // sweeping mid-range physical arc, pierces a small pack
}

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum Status {
    None,
    Burning,       // dot over N ticks
    Frozen,        // can't act
    Poisoned,      // dot
    Stunned,       // can't move
    Cursed,        // 1.5x damage taken
    Marked,        // homing projectiles target
}

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum Effect {
    StatBoost { stat: Stat, delta: i8 },
    OnHit(Trigger),
    OnRoomClear(Trigger),
    OnPickup(Trigger),
    OnDamageTaken(Trigger),
    Dash { iframes: u8, dist: u8 },
    HealHearts(u8),
    GrantMp(u8),
    RevealMap,
    // Extensible
}

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum Trigger {
    SpawnProjectile { kind: ProjectileKind, count: u8 },
    DealDamage     { amount: u8, radius: u8 },
    ApplyStatus    { status: Status, duration_ticks: u8 },
    GiveCoins(u8),
}
