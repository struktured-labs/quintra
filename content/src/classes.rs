//! Five playable champion vessels and their starting kits.

use quintra_content::{BaseStats, Class, FormTheme, Registry};

use crate::ids::*;

pub const WOLFKIN: Class = Class {
    id:            CLASS_WOLFKIN,
    name:          "Wolfkin",
    form_theme:    FormTheme::Wolfkin,
    palette:       OBJ_PAL_WOLFKIN,
    starter_weapon: ITEM_CLAW_COMBO,
    signature_active: ITEM_HOWL,
    passive_perk:  PERK_MOVE_SPEED_PLUS_20,
    // Claw Combo requires sustained body-range contact. Seven hearts and a
    // four-ATK Fang Stab give the dedicated melee champion one real recovery
    // beat to finish a close boss exchange; Sauran remains the tank through
    // higher DEF and its projectile-breaking Stoneskin, while Vespine retains
    // the faster, harder-hitting fragile pressure role.
    base_stats: BaseStats {
        hp_max: 14,  // 7 hearts
        mp_max: 4,
        atk:    4,
        def:    1,
        spd:    6,
    },
};

pub const SAURAN: Class = Class {
    id:            CLASS_SAURAN,
    name:          "Sauran",
    form_theme:    FormTheme::Sauran,
    palette:       OBJ_PAL_SAURAN,
    starter_weapon: ITEM_TAIL_SPIKE,
    signature_active: ITEM_STONESKIN,
    passive_perk:  PERK_HP_PLUS_2_SLOW_REGEN,
    // Scaled Hide is pre-baked into the starting stats. Eight hearts and a
    // measured five-speed let the tank reset from a boss-body approach; four
    // speed left its long Tail Spike recovery unable to reclaim a safe lane
    // before the next contact cycle. Stoneskin and positioning remain the
    // answer to projectile patterns, not a global enemy-stat concession.
    base_stats: BaseStats { hp_max: 16, mp_max: 3, atk: 2, def: 2, spd: 5 },
};

pub const CORVIN: Class = Class {
    id:            CLASS_CORVIN,
    name:          "Corvin",
    form_theme:    FormTheme::Corvin,
    palette:       OBJ_PAL_CORVIN,
    starter_weapon: ITEM_FEATHER_SHURI,
    signature_active: ITEM_MURDER,
    passive_perk:  PERK_SEE_HP_REVEAL,
    // Featherbarb's returning arc demands sustained positioning time. Seven
    // hearts compensate for low DEF through the first Riftwild crossing
    // without inflating its safe ranged damage.
    base_stats: BaseStats { hp_max: 14, mp_max: 8, atk: 2, def: 1, spd: 5 },
};

pub const PICSEAN: Class = Class {
    id:            CLASS_PICSEAN,
    name:          "Picsean",
    form_theme:    FormTheme::Picsean,
    palette:       OBJ_PAL_PICSEAN,
    starter_weapon: ITEM_BUBBLE_BOLT,
    signature_active: ITEM_TIDAL_WAVE,
    passive_perk:  PERK_MP_REGEN_SWIM,
    // Slow piercing shots require prolonged spacing and carry the roster's
    // lowest ATK. Seven hearts offset its long projectile commitment while
    // low ATK/DEF preserve the fragile control-mage identity.
    base_stats: BaseStats { hp_max: 14, mp_max: 10, atk: 1, def: 1, spd: 5 },
};

pub const VESPINE: Class = Class {
    id:            CLASS_VESPINE,
    name:          "Vespine",
    form_theme:    FormTheme::Vespine,
    palette:       OBJ_PAL_VESPINE,
    starter_weapon: ITEM_STINGER,
    signature_active: ITEM_SWARM,
    passive_perk:  PERK_POISON_SYNERGY,
    // The close-range Stinger exposes Vespine to contact damage despite her
    // speed. Six-and-a-half hearts keeps her below both durable melee
    // vessels while giving Swarm's committed finish window one real exchange
    // instead of asking the player to end an opening boss at one hit.
    base_stats: BaseStats { hp_max: 13, mp_max: 5, atk: 4, def: 1, spd: 7 },
};

pub fn register(r: &mut Registry) {
    r.add_class(WOLFKIN.clone());
    r.add_class(SAURAN.clone());
    r.add_class(CORVIN.clone());
    r.add_class(PICSEAN.clone());
    r.add_class(VESPINE.clone());
}
