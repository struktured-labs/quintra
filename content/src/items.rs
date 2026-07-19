//! Champion weapons, signature actives, and run-long relics.

use quintra_content::{Effect, Item, ItemKind, ProjectileKind, Rarity, Registry, Stat};

use crate::ids::*;

pub const CLAW_COMBO: Item = Item {
    id:          ITEM_CLAW_COMBO,
    name:        "Claw Combo",
    description: "Fast melee.",
    kind: ItemKind::Weapon {
        fire_rate:  24,    // deliberate no-upgrade cadence; run-earned SPD accelerates it
        damage:     2,
        projectile: ProjectileKind::Spike,
        mp_cost:    0,
    },
    icon_sprite: SPRITE_ITEM_CLAW,
    palette:     OBJ_PAL_ITEM_GOLD,
    rarity:      Rarity::Common,
    effects:     &[],
};

pub const HOWL: Item = Item {
    id:          ITEM_HOWL,
    name:        "Howl",
    description: "8-way burst + brief ward.",
    kind: ItemKind::Active { cooldown_rooms: 2 },
    icon_sprite: SPRITE_ITEM_HOWL,
    palette:     OBJ_PAL_ITEM_GOLD,
    rarity:      Rarity::Rare,
    // B is an immediate eight-spike ring plus a very short activation ward;
    // it is not a room-clear stun or a durable projectile shield.
    effects: &[],
};

// --- Other starter weapons (one per class)

pub const TAIL_SPIKE: Item = Item {
    id:          ITEM_TAIL_SPIKE,
    name:        "Tail Spike",
    description: "Short heavy strike. Bonus damage on hit.",
    kind: ItemKind::Weapon { fire_rate: 28, damage: 4, projectile: ProjectileKind::Spike, mp_cost: 0 },
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Common,
    effects: &[],
};

pub const FEATHER_SHURIKEN: Item = Item {
    id:          ITEM_FEATHER_SHURI,
    name:        "Featherbarb",
    description: "Ranged shuriken. Returns after hit.",
    kind: ItemKind::Weapon { fire_rate: 22, damage: 1, projectile: ProjectileKind::Shuriken, mp_cost: 0 },
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Common,
    effects: &[],
};

pub const BUBBLE_BOLT: Item = Item {
    id:          ITEM_BUBBLE_BOLT,
    name:        "BubbleBolt",
    description: "Slow piercing bubble.",
    kind: ItemKind::Weapon { fire_rate: 30, damage: 2, projectile: ProjectileKind::Bubble, mp_cost: 0 },
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Common,
    effects: &[],
};

pub const STINGER: Item = Item {
    id:          ITEM_STINGER,
    name:        "Stinger",
    description: "Fast strike. High critical chance.",
    kind: ItemKind::Weapon { fire_rate: 20, damage: 2, projectile: ProjectileKind::Spike, mp_cost: 0 },
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Common,
    effects: &[Effect::StatBoost { stat: Stat::Lck, delta: 3 }],
};

// --- Actives

pub const STONESKIN: Item = Item {
    id: ITEM_STONESKIN, name: "Stoneskin",
    description: "Block shots & bodies.",
    kind: ItemKind::Active { cooldown_rooms: 2 },
    icon_sprite: SPRITE_ITEM_HOWL, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Rare,
    effects: &[],
};

pub const MURDER: Item = Item {
    id: ITEM_MURDER, name: "Murder",
    description: "3-way shard burst.",
    kind: ItemKind::Active { cooldown_rooms: 3 },
    icon_sprite: SPRITE_ITEM_HOWL, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Rare,
    // Runtime fires a three-way shuriken spread on B; it does not spawn
    // homing shards after a clear.
    effects: &[],
};

pub const TIDAL_WAVE: Item = Item {
    id: ITEM_TIDAL_WAVE, name: "TidalWave",
    description: "3 bubbles + water guard.",
    kind: ItemKind::Active { cooldown_rooms: 2 },
    icon_sprite: SPRITE_ITEM_HOWL, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Rare,
    effects: &[],
};

pub const SWARM: Item = Item {
    id: ITEM_SWARM, name: "Swarm",
    description: "4-stinger fan + brief ward.",
    kind: ItemKind::Active { cooldown_rooms: 3 },
    icon_sprite: SPRITE_ITEM_HOWL, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Rare,
    effects: &[],
};

// --- Passive stat boosts (dropped from enemies + shops)

pub const IRON_HEART: Item = Item {
    id: ITEM_IRON_HEART, name: "Iron Heart",
    description: "Permanent +2 max HP for this run.",
    kind: ItemKind::Passive,
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Uncommon,
    effects: &[Effect::StatBoost { stat: Stat::Hp, delta: 2 }],
};

pub const SPEED_RING: Item = Item {
    id: ITEM_SPEED_RING, name: "Speed Ring",
    description: "+1 SPD.",
    kind: ItemKind::Passive,
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Uncommon,
    effects: &[Effect::StatBoost { stat: Stat::Spd, delta: 1 }],
};

pub const POWER_STONE: Item = Item {
    id: ITEM_POWER_STONE, name: "PowerStone",
    description: "+1 ATK damage.",
    kind: ItemKind::Passive,
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Uncommon,
    effects: &[Effect::StatBoost { stat: Stat::Atk, delta: 1 }],
};

pub const TOUGH_SKIN: Item = Item {
    id: ITEM_TOUGH_SKIN, name: "Tough Skin",
    description: "+1 DEF — soaks incoming damage.",
    kind: ItemKind::Passive,
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Uncommon,
    effects: &[Effect::StatBoost { stat: Stat::Def, delta: 1 }],
};

pub const LUCKY_COIN: Item = Item {
    id: ITEM_LUCKY_COIN, name: "Lucky Coin",
    description: "+2 LCK. Better drops + crit chance.",
    kind: ItemKind::Passive,
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Rare,
    effects: &[Effect::StatBoost { stat: Stat::Lck, delta: 2 }],
};

pub const MANA_GEM: Item = Item {
    id: ITEM_MANA_GEM, name: "Mana Gem",
    description: "+2 max MP.",
    kind: ItemKind::Passive,
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Uncommon,
    effects: &[Effect::StatBoost { stat: Stat::Mp, delta: 2 }],
};

pub const WARD_CHARM: Item = Item {
    id: ITEM_WARD_CHARM, name: "Ward Charm",
    description: "+1 DEF, +1 LCK.",
    kind: ItemKind::Passive,
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Rare,
    effects: &[
        Effect::StatBoost { stat: Stat::Def, delta: 1 },
        Effect::StatBoost { stat: Stat::Lck, delta: 1 },
    ],
};

pub const SWIFT_FANG: Item = Item {
    id: ITEM_SWIFT_FANG, name: "Swift Fang",
    description: "+1 SPD, +1 ATK.",
    kind: ItemKind::Passive,
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Rare,
    effects: &[
        Effect::StatBoost { stat: Stat::Spd, delta: 1 },
        Effect::StatBoost { stat: Stat::Atk, delta: 1 },
    ],
};

pub const HUNTERS_EYE: Item = Item {
    id: ITEM_HUNTERS_EYE, name: "HuntersEye",
    description: "+3 LCK. Fortune favors the watcher.",
    kind: ItemKind::Passive,
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Rare,
    effects: &[Effect::StatBoost { stat: Stat::Lck, delta: 3 }],
};

pub const BLOOD_SIGIL: Item = Item {
    id: ITEM_BLOOD_SIGIL, name: "VampSigil",
    description: "+1 ATK, +1 max HP. Heal every fifth kill.",
    kind: ItemKind::Passive,
    icon_sprite: SPRITE_ITEM_CLAW, palette: OBJ_PAL_ITEM_GOLD, rarity: Rarity::Rare,
    effects: &[
        Effect::StatBoost { stat: Stat::Atk, delta: 1 },
        Effect::StatBoost { stat: Stat::Hp, delta: 1 },
    ],
};

// A run-changing physical weapon rather than another starter reskin.  It
// swings farther than a claw, cleaves a small pack, and pays for that reach
// with the slowest authored A cadence.  It can appear from miniboss and vault
// weapon orbs for every champion, including the ranged vessels.
pub const RIFT_FLAIL: Item = Item {
    id:          ITEM_RIFT_FLAIL,
    name:        "Rift Flail",
    description: "3-pierce slow sweep.",
    kind: ItemKind::Weapon { fire_rate: 36, damage: 3, projectile: ProjectileKind::Flail, mp_cost: 0 },
    icon_sprite: SPRITE_ITEM_CLAW,
    palette:     OBJ_PAL_ITEM_GOLD,
    rarity:      Rarity::Rare,
    effects:     &[],
};

// A deliberate counterpart to the Flail: it is not a wide crowd-clearer.
// Astral Spear takes a slower, committed thrust down one lane, reaches well
// beyond the Wolfkin claw, and rewards a player who lines up a dangerous
// enemy instead of firing freely into a crowd.
pub const ASTRAL_SPEAR: Item = Item {
    id:          ITEM_ASTRAL_SPEAR,
    name:        "Astral Spear",
    description: "Long precise thrust.",
    kind: ItemKind::Weapon { fire_rate: 42, damage: 4, projectile: ProjectileKind::Spear, mp_cost: 0 },
    icon_sprite: SPRITE_ITEM_CLAW,
    palette:     OBJ_PAL_ITEM_GOLD,
    rarity:      Rarity::Rare,
    effects:     &[],
};

pub fn register(r: &mut Registry) {
    r.add_item(CLAW_COMBO.clone());
    r.add_item(TAIL_SPIKE.clone());
    r.add_item(FEATHER_SHURIKEN.clone());
    r.add_item(BUBBLE_BOLT.clone());
    r.add_item(STINGER.clone());
    r.add_item(HOWL.clone());
    r.add_item(STONESKIN.clone());
    r.add_item(MURDER.clone());
    r.add_item(TIDAL_WAVE.clone());
    r.add_item(SWARM.clone());
    r.add_item(IRON_HEART.clone());
    r.add_item(SPEED_RING.clone());
    r.add_item(POWER_STONE.clone());
    r.add_item(TOUGH_SKIN.clone());
    r.add_item(LUCKY_COIN.clone());
    r.add_item(MANA_GEM.clone());
    r.add_item(WARD_CHARM.clone());
    r.add_item(SWIFT_FANG.clone());
    r.add_item(HUNTERS_EYE.clone());
    r.add_item(BLOOD_SIGIL.clone());
    r.add_item(RIFT_FLAIL.clone());
    r.add_item(ASTRAL_SPEAR.clone());
}
