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
        // The first Colossus is a pattern lesson, not a five-second burst
        // check. With the Sentinel's 50 base this lands at 200 HP: enough
        // time for a shop/relic-assisted starter kit to see the opening,
        // ring, body-spacing, and phase break before the kill, without
        // changing boss damage or turning an early contact sequence into an
        // unwinnable expedition.
        boss_hp_bonus: 150, boss_hp_cap: 200, endless_boss_hp_cap: 255,
        boss_dmg_bonus: 1, mb_variant: 0, room_archetype: 0,
        // Shard Crabs replace a small crawler slice: their one-hit shell
        // introduces a readable bait-and-punish beat without increasing the
        // opening room body count or changing pool weight.
        enemy_pool: &[(0, 29), (30, 6), (12, 30), (9, 20), (13, 15)],
    },
    // 1 — Verdant Hollow (mossy green)
    StageTheme {
        id: 1, name: "VERDANT HOLLOW",
        floor:   [c( 3, 6, 3), c( 8,14, 7), c(13,20,11), c(20,26,16)],
        wall:    [c( 1, 3, 1), c( 4, 9, 3), c( 7,14, 6), c(13,22,11)],
        crystal: [c( 1, 4, 0), c( 8,24, 4), c(18,31,10), c(30,31,22)],
        door:    [c( 2, 2, 1), c(11, 8, 2), c(20,14, 3), c(30,24, 8)],
        boss:    [c(0,0,0), c( 9,19, 7), c( 2, 6, 2), c(26,31,14)],
        // The Serpent remains tougher than Crystal in movement/pattern terms,
        // but 220 HP plus continuous rebound movement turned the second boss
        // into an attrition wall for a legitimate starter build. 205 leaves
        // the first stage's 200-HP lesson below it while preserving a clear
        // re-engagement-and-dodge fight instead of an extra damage lap.
        boss_hp_bonus: 155, boss_hp_cap: 205, endless_boss_hp_cap: 255,
        boss_dmg_bonus: 1, mb_variant: 1, room_archetype: 1,
        // Vine Coils replace part of the Flutterbat band with a slow,
        // readable opposite-pair lane prompt. The table remains exactly 100:
        // this makes Verdant Hollow more distinct without adding bodies,
        // inflating enemy HP, or perturbing the procgen RNG draw count.
        enemy_pool: &[(12, 17), (2, 15), (4, 25), (9, 15), (13, 20), (29, 8)],
    },
    // 2 — Ember Depths (molten red/orange)
    StageTheme {
        id: 2, name: "EMBER DEPTHS",
        floor:   [c( 7, 2, 2), c(16, 7, 5), c(23,12, 7), c(30,20,12)],
        wall:    [c( 3, 0, 0), c(11, 3, 2), c(17, 6, 3), c(26,12, 6)],
        crystal: [c( 5, 1, 0), c(28,10, 2), c(31,22, 4), c(31,31,20)],
        door:    [c( 2, 1, 0), c(12, 8, 2), c(22,15, 3), c(31,26, 8)],
        boss:    [c(0,0,0), c(22, 9, 4), c( 6, 2, 1), c(31,27,10)],
        // The Maw's fast aimed breath and lunge carry its difficulty; 150 HP
        // prevents an early melee pattern lesson becoming an attrition wall.
        boss_hp_bonus: 190, boss_hp_cap: 150, endless_boss_hp_cap: 150,
        boss_dmg_bonus: 2, mb_variant: 2, room_archetype: 2,
        // Cinder Kites add a mobile, low-damage fan to the heavy Maw's
        // stationary three-way pressure.  Fold Stars and Rift Oozes give the
        // third dungeon visible timing and movement lessons: the former
        // blooms into invulnerable echoes then contracts, the latter splits,
        // scatters, and reforms.  They replace the old Skeleton slice rather
        // than adding bodies, HP, or a new procgen draw.
        enemy_pool: &[(11, 8), (6, 30), (4, 22), (14, 16), (25, 12), (15, 12)],
    },
    // 3 — Frost Vault (icy cyan/white)
    StageTheme {
        id: 3, name: "FROST VAULT",
        floor:   [c( 6, 9,12), c(14,19,23), c(20,26,29), c(27,31,31)],
        wall:    [c( 3, 5, 8), c( 8,13,18), c(13,20,25), c(20,27,31)],
        crystal: [c( 4, 8,12), c(12,26,31), c(22,31,31), c(31,31,31)],
        door:    [c( 2, 3, 4), c(10, 9, 4), c(20,16, 6), c(30,26,12)],
        boss:    [c(0,0,0), c(12,18,24), c( 3, 5, 9), c(31,31,31)],
        // Frost is a first-campaign movement lesson, but its former 130-HP
        // cap let the strongest base kit erase the new screen-scale Spider
        // in a 7.3-second uninterrupted lane. 150 preserves the blink/web
        // danger while guaranteeing enough time to read more than one cycle.
        // Its returning endless silhouette resumes the one-byte ceiling.
        boss_hp_bonus: 205, boss_hp_cap: 150, endless_boss_hp_cap: 255,
        boss_dmg_bonus: 2, mb_variant: 3, room_archetype: 3,
        // Frost is led by moving pressure; its 10% rotating Sentry is a
        // readable lane hazard, while Frost Lancers take the upper 8% of the
        // old Wisp band. The total stays 100: a new lane decision, not more
        // bodies or a changed procgen draw count.
        enemy_pool: &[(5, 15), (28, 8), (3, 23), (6, 22), (10, 10), (16, 22)],
    },
    // 4 — Toxic Mire (sickly yellow-green)
    StageTheme {
        id: 4, name: "TOXIC MIRE",
        floor:   [c( 5, 6, 1), c(12,14, 3), c(18,20, 6), c(24,26,10)],
        wall:    [c( 2, 3, 0), c( 7, 8, 1), c(11,13, 3), c(17,19, 6)],
        crystal: [c( 3, 5, 0), c(16,26, 2), c(26,31, 6), c(31,31,18)],
        door:    [c( 2, 2, 0), c(11, 9, 2), c(20,16, 4), c(29,25, 9)],
        boss:    [c(0,0,0), c(16,20, 4), c( 4, 6, 1), c(31,31,14)],
        boss_hp_bonus: 220, boss_hp_cap: 255, endless_boss_hp_cap: 255,
        boss_dmg_bonus: 3, mb_variant: 4, room_archetype: 4,
        // Bog Toad replaces a slice of the old passive pool: a telegraphed
        // pounce changes positional decisions without increasing density.
        // Preserve the original table's first 92 roll values exactly; only
        // the upper eight points of the former Spore band become Bog Toad.
        // That gives procgen a new encounter without perturbing established
        // deterministic controller routes or increasing room population.
        enemy_pool: &[(12, 15), (5, 15), (6, 20), (15, 25), (17, 17), (26, 8)],
    },
    // 5 — Shadow Keep (cold grey/violet)
    StageTheme {
        id: 5, name: "SHADOW KEEP",
        floor:   [c( 4, 4, 6), c(10,10,13), c(15,15,19), c(21,21,26)],
        wall:    [c( 2, 2, 3), c( 6, 6, 9), c(10,10,14), c(16,16,22)],
        crystal: [c( 3, 1, 5), c(14, 8,22), c(22,16,30), c(30,28,31)],
        door:    [c( 2, 2, 3), c(10, 8, 6), c(19,15, 8), c(28,24,14)],
        boss:    [c(0,0,0), c(13,11,20), c( 3, 3, 6), c(28,22,31)],
        boss_hp_bonus: 230, boss_hp_cap: 255, endless_boss_hp_cap: 255,
        boss_dmg_bonus: 3, mb_variant: 2, room_archetype: 5,
        // Gloam Bramble replaces a small Prism Skitter slice with a slower
        // opposite-lane orbit. Shadow Keep stays a deliberate positioning
        // test without increasing generated body count.
        enemy_pool: &[(7, 20), (3, 20), (5, 15), (11, 15), (19, 15), (22, 10), (27, 5)],
    },
    // 6 — Golden Temple (warm gold/sand)
    StageTheme {
        id: 6, name: "GOLDEN TEMPLE",
        floor:   [c( 8, 6, 2), c(18,14, 6), c(25,20, 9), c(31,27,15)],
        wall:    [c( 4, 3, 1), c(12, 9, 3), c(18,14, 5), c(26,21, 9)],
        crystal: [c( 6, 4, 0), c(28,22, 4), c(31,29, 8), c(31,31,22)],
        door:    [c( 3, 2, 0), c(14,11, 2), c(24,19, 4), c(31,28,10)],
        boss:    [c(0,0,0), c(22,17, 5), c( 6, 4, 1), c(31,30,18)],
        boss_hp_bonus: 240, boss_hp_cap: 230, endless_boss_hp_cap: 230,
        boss_dmg_bonus: 4, mb_variant: 3, room_archetype: 6,
        // The Sunwheel makes the Temple a positioning test: it maintains a
        // compact orbit and marks a changing opposite lane, while the rest
        // of the pool preserves room for melee and counter-play lessons.
        enemy_pool: &[(4, 15), (6, 15), (7, 15), (18, 15), (20, 15), (21, 15), (24, 10)],
    },
    // 7 — Bloodmoon (crimson/black)
    StageTheme {
        id: 7, name: "BLOODMOON",
        floor:   [c( 6, 1, 2), c(13, 3, 5), c(19, 5, 8), c(26,10,12)],
        wall:    [c( 3, 0, 1), c( 8, 1, 2), c(13, 2, 4), c(20, 6, 8)],
        crystal: [c( 5, 0, 1), c(24, 2, 6), c(31, 6,10), c(31,22,20)],
        door:    [c( 3, 1, 1), c(13, 6, 3), c(23,12, 5), c(31,22,10)],
        boss:    [c(0,0,0), c(20, 4, 6), c( 6, 1, 2), c(31,20,16)],
        // Hydra's five mixed-speed streams should create the late-game
        // spectacle, not compensate for a five-second health window. A
        // 150-HP cap gives the strongest base kit an 8.3-second ideal lane;
        // real weaving and the three-head animation extend it naturally.
        boss_hp_bonus: 248, boss_hp_cap: 150, endless_boss_hp_cap: 150,
        boss_dmg_bonus: 4, mb_variant: 0, room_archetype: 7,
        enemy_pool: &[(3, 18), (7, 18), (11, 20), (8, 15), (20, 11), (21, 11), (23, 7)],
    },
    // 8 — Void Sanctum (deep purple/toxic green, final)
    StageTheme {
        id: 8, name: "VOID SANCTUM",
        floor:   [c( 4, 2, 7), c(10, 6,14), c(15,11,20), c(20,16,26)],
        wall:    [c( 2, 0, 4), c( 7, 2,10), c(11, 5,15), c(18,10,24)],
        crystal: [c( 0, 4, 2), c( 6,22, 8), c(14,31,12), c(28,31,24)],
        door:    [c( 2, 0, 3), c( 8, 4,10), c(16,10,20), c(26,18,30)],
        boss:    [c(0,0,0), c(13, 6,20), c( 3, 1, 7), c(20,31,18)],
        boss_hp_bonus: 255, boss_hp_cap: 220, endless_boss_hp_cap: 220,
        boss_dmg_bonus: 5, mb_variant: 4, room_archetype: 8,
        // Void Halo replaces Void Sanctum's fast Dusk Midge band with a
        // wider, slower opposite-pair lane puzzle. Midge still owns its
        // Bloodmoon encounter; the final pool remains seven entries and 100
        // weight, so this changes neither body density nor procgen draw count.
        enemy_pool: &[(7, 17), (11, 17), (15, 20), (19, 15), (20, 13), (21, 10), (31, 8)],
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
