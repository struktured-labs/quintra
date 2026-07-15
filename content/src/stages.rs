//! The nine stage themes — palettes + names, ported verbatim from the
//! hand-authored C tables that used to live in room.c / inventory.c.
//! Order matters: stage id == position == run progression.

use quintra_content::{Registry, Rgb5, StageTheme};

const fn c(r: u8, g: u8, b: u8) -> Rgb5 { Rgb5(r, g, b) }

pub const STAGES: [StageTheme; 9] = [
    // 0 — Crystal Caverns (cool blue)
    StageTheme {
        id: 0, name: "CRYSTAL CAVERNS",
        floor:   [c( 4, 3, 6), c(11,10,15), c(17,16,22), c(23,22,28)],
        wall:    [c( 1, 1, 3), c( 5, 5,11), c( 9,10,17), c(16,18,26)],
        crystal: [c( 2, 0, 5), c(16, 5,22), c(10,22,29), c(31,30,31)],
        door:    [c( 1, 1, 2), c(10, 7, 2), c(18,13, 3), c(28,21, 6)],
        boss:    [c(0,0,0), c(10,13,22), c( 2, 3, 8), c(22,29,31)],
        boss_hp_bonus: 40, boss_dmg_bonus: 1, mb_variant: 0, room_archetype: 0,
        enemy_pool: &[(0, 35), (12, 30), (9, 20), (13, 15)],
    },
    // 1 — Verdant Hollow (mossy green)
    StageTheme {
        id: 1, name: "VERDANT HOLLOW",
        floor:   [c( 3, 6, 3), c( 8,14, 7), c(13,20,11), c(20,26,16)],
        wall:    [c( 1, 3, 1), c( 4, 9, 3), c( 7,14, 6), c(13,22,11)],
        crystal: [c( 1, 4, 0), c( 8,24, 4), c(18,31,10), c(30,31,22)],
        door:    [c( 2, 2, 1), c(11, 8, 2), c(20,14, 3), c(30,24, 8)],
        boss:    [c(0,0,0), c( 9,19, 7), c( 2, 6, 2), c(26,31,14)],
        boss_hp_bonus: 62, boss_dmg_bonus: 1, mb_variant: 1, room_archetype: 1,
        enemy_pool: &[(12, 30), (4, 30), (9, 20), (13, 20)],
    },
    // 2 — Ember Depths (molten red/orange)
    StageTheme {
        id: 2, name: "EMBER DEPTHS",
        floor:   [c( 7, 2, 2), c(16, 7, 5), c(23,12, 7), c(30,20,12)],
        wall:    [c( 3, 0, 0), c(11, 3, 2), c(17, 6, 3), c(26,12, 6)],
        crystal: [c( 5, 1, 0), c(28,10, 2), c(31,22, 4), c(31,31,20)],
        door:    [c( 2, 1, 0), c(12, 8, 2), c(22,15, 3), c(31,26, 8)],
        boss:    [c(0,0,0), c(22, 9, 4), c( 6, 2, 1), c(31,27,10)],
        boss_hp_bonus: 84, boss_dmg_bonus: 2, mb_variant: 2, room_archetype: 2,
        enemy_pool: &[(3, 20), (6, 30), (4, 25), (14, 25)],
    },
    // 3 — Frost Vault (icy cyan/white)
    StageTheme {
        id: 3, name: "FROST VAULT",
        floor:   [c( 6, 9,12), c(14,19,23), c(20,26,29), c(27,31,31)],
        wall:    [c( 3, 5, 8), c( 8,13,18), c(13,20,25), c(20,27,31)],
        crystal: [c( 4, 8,12), c(12,26,31), c(22,31,31), c(31,31,31)],
        door:    [c( 2, 3, 4), c(10, 9, 4), c(20,16, 6), c(30,26,12)],
        boss:    [c(0,0,0), c(12,18,24), c( 3, 5, 9), c(31,31,31)],
        boss_hp_bonus: 106, boss_dmg_bonus: 2, mb_variant: 3, room_archetype: 3,
        enemy_pool: &[(5, 35), (3, 35), (6, 30)],
    },
    // 4 — Toxic Mire (sickly yellow-green)
    StageTheme {
        id: 4, name: "TOXIC MIRE",
        floor:   [c( 5, 6, 1), c(12,14, 3), c(18,20, 6), c(24,26,10)],
        wall:    [c( 2, 3, 0), c( 7, 8, 1), c(11,13, 3), c(17,19, 6)],
        crystal: [c( 3, 5, 0), c(16,26, 2), c(26,31, 6), c(31,31,18)],
        door:    [c( 2, 2, 0), c(11, 9, 2), c(20,16, 4), c(29,25, 9)],
        boss:    [c(0,0,0), c(16,20, 4), c( 4, 6, 1), c(31,31,14)],
        boss_hp_bonus: 128, boss_dmg_bonus: 3, mb_variant: 4, room_archetype: 4,
        enemy_pool: &[(12, 20), (5, 20), (6, 25), (15, 35)],
    },
    // 5 — Shadow Keep (cold grey/violet)
    StageTheme {
        id: 5, name: "SHADOW KEEP",
        floor:   [c( 4, 4, 6), c(10,10,13), c(15,15,19), c(21,21,26)],
        wall:    [c( 2, 2, 3), c( 6, 6, 9), c(10,10,14), c(16,16,22)],
        crystal: [c( 3, 1, 5), c(14, 8,22), c(22,16,30), c(30,28,31)],
        door:    [c( 2, 2, 3), c(10, 8, 6), c(19,15, 8), c(28,24,14)],
        boss:    [c(0,0,0), c(13,11,20), c( 3, 3, 6), c(28,22,31)],
        boss_hp_bonus: 150, boss_dmg_bonus: 3, mb_variant: 2, room_archetype: 5,
        enemy_pool: &[(7, 30), (3, 25), (5, 25), (11, 20)],
    },
    // 6 — Golden Temple (warm gold/sand)
    StageTheme {
        id: 6, name: "GOLDEN TEMPLE",
        floor:   [c( 8, 6, 2), c(18,14, 6), c(25,20, 9), c(31,27,15)],
        wall:    [c( 4, 3, 1), c(12, 9, 3), c(18,14, 5), c(26,21, 9)],
        crystal: [c( 6, 4, 0), c(28,22, 4), c(31,29, 8), c(31,31,22)],
        door:    [c( 3, 2, 0), c(14,11, 2), c(24,19, 4), c(31,28,10)],
        boss:    [c(0,0,0), c(22,17, 5), c( 6, 4, 1), c(31,30,18)],
        boss_hp_bonus: 172, boss_dmg_bonus: 4, mb_variant: 3, room_archetype: 6,
        enemy_pool: &[(4, 30), (6, 25), (7, 25), (10, 20)],
    },
    // 7 — Bloodmoon (crimson/black)
    StageTheme {
        id: 7, name: "BLOODMOON",
        floor:   [c( 6, 1, 2), c(13, 3, 5), c(19, 5, 8), c(26,10,12)],
        wall:    [c( 3, 0, 1), c( 8, 1, 2), c(13, 2, 4), c(20, 6, 8)],
        crystal: [c( 5, 0, 1), c(24, 2, 6), c(31, 6,10), c(31,22,20)],
        door:    [c( 3, 1, 1), c(13, 6, 3), c(23,12, 5), c(31,22,10)],
        boss:    [c(0,0,0), c(20, 4, 6), c( 6, 1, 2), c(31,20,16)],
        boss_hp_bonus: 194, boss_dmg_bonus: 4, mb_variant: 0, room_archetype: 7,
        enemy_pool: &[(3, 25), (7, 25), (11, 25), (8, 25)],
    },
    // 8 — Void Sanctum (deep purple/toxic green, final)
    StageTheme {
        id: 8, name: "VOID SANCTUM",
        floor:   [c( 4, 2, 7), c(10, 6,14), c(15,11,20), c(20,16,26)],
        wall:    [c( 2, 0, 4), c( 7, 2,10), c(11, 5,15), c(18,10,24)],
        crystal: [c( 0, 4, 2), c( 6,22, 8), c(14,31,12), c(28,31,24)],
        door:    [c( 2, 0, 3), c( 8, 4,10), c(16,10,20), c(26,18,30)],
        boss:    [c(0,0,0), c(13, 6,20), c( 3, 1, 7), c(20,31,18)],
        boss_hp_bonus: 216, boss_dmg_bonus: 5, mb_variant: 4, room_archetype: 8,
        enemy_pool: &[(7, 20), (11, 25), (15, 30), (8, 25)],
    },
];

/// Cracked secret wall — warm amber, deliberately constant across stages
/// so the "shoot me" signal always reads the same.
pub const CRACK_PAL: [Rgb5; 4] = [
    c(6, 2, 1), c(22, 11, 3), c(30, 18, 4), c(31, 28, 12),
];

pub fn register(reg: &mut Registry) {
    for s in STAGES {
        reg.add_stage(s);
    }
}
