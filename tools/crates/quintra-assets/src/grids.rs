//! Hand-authored ASCII sprite specs — the pixel source of truth.
//! Ported verbatim from scripts/sprite_authoring.py. Glyphs:
//! '.'/'0' = 0 transparent (or palette c0 for BG tiles), '1' light,
//! '2' mid, '3' dark.

pub const PLAYER_W: usize = 16;
pub const PLAYER_H: usize = 16;

// Player classes are monster-humans: bipedal, animal-headed. Shading
// convention (per class_obj_palettes): 1 = body, 2 = dark outline/shadow,
// 3 = highlight (eyes, light edges). Redrawn from flat single-tone blobs
// to outlined, readable silhouettes.

pub const WOLFKIN: [&str; 16] = [   // wolf-beast: pointed ears, snout
    "...2......2.....",
    "..212....212....",
    "..2122222212....",
    "..21311331312...",
    "..21111111112...",
    "..21121121112...",
    "...211111112....",
    "..2211111122....",
    ".21111111112....",
    ".21131111311.2..",
    "..2111111112....",
    "..21111111.2....",
    "..2112..2112....",
    "..2112..2112....",
    "..212....212....",
    "..22......22....",
];

pub const SAURAN: [&str; 16] = [    // lizard-man: dorsal crest, snout
    ".....2332.......",
    "....213312......",
    "....2111112.....",
    "...211313112....",
    "...21111111.2...",
    "...211313112....",
    "....21111112....",
    "..2211111122....",
    ".21111111112....",
    ".21131111311.2..",
    ".21111111112....",
    "..211111111.2...",
    "..2112..2112....",
    "..2112..2112....",
    "..212....212....",
    "..22......22....",
];

pub const CORVIN: [&str; 16] = [    // raven-man: side-profile beak, wings
    "...222..........",
    "..21112.........",
    "..2113233.......",
    "..211112........",
    "..21112.........",
    "...212..........",
    ".2211112........",
    "21111111.2......",
    "211311113112....",
    "21111111111.2...",
    ".211111111.2....",
    "..21111111.2....",
    "..2112..2112....",
    "..2112..2112....",
    "..212....212....",
    "..22......22....",
];

pub const PICSEAN: [&str; 16] = [   // fish-man: head fins, gills, webbed feet
    "....3......3....",
    "...23......32...",
    "...2322..2232...",
    "...2113223112...",
    "...21311131.2...",
    "...211111112....",
    "...211313112....",
    "..21111111112...",
    ".211131111311.2.",
    ".21111111111112.",
    "..211111111112..",
    "..2111111111.2..",
    "..2112..2112....",
    "..212....212....",
    ".2312....2132...",
    "..2........2....",
];

pub const VESPINE: [&str; 16] = [   // wasp-man: antennae, wings, striped, stinger
    "2..........2....",
    ".2........2.....",
    "..2113..3112....",
    "..21122221112...",
    "...211111112....",
    "...211313112....",
    "..32111111.23...",
    ".3311111111133..",
    ".31131313.133...",
    "..2113131312....",
    "..2113131312....",
    "...211111112....",
    "...2112.2112....",
    "...2112.2112....",
    "...212...212....",
    "....22...22.3...",
];

// Swarm tier (8x8): distinct silhouettes over samey blobs. Shading
// convention 1 body / 2 dark outline / 3 highlight+eyes, same as players.
pub const CRAWLER: [&str; 8] = [   // spider/tick: splayed legs, wide body
    "..2..2..",
    "2.2112.2",
    ".221122.",
    "21311312",
    "21111112",
    ".221122.",
    "2.2..2.2",
    "..2..2..",
];

pub const HORNET: [&str; 8] = [    // wasp: wings out, narrow body, stinger
    "3..22..3",
    "33.11.33",
    ".321123.",
    "..2132..",
    "..2112..",
    "..2312..",
    "...22...",
    "...2....",
];

pub const SKELETON: [&str; 8] = [  // skull: eye sockets + jaw
    "..2222..",
    ".211112.",
    ".231132.",
    ".211112.",
    ".221122.",
    "..2112..",
    ".212212.",
    ".2.22.2.",
];

pub const ORC: [&str; 8] = [
    ".111111.",
    "1331.331",
    "1111.111",
    "1111.111",
    ".111111.",
    ".111111.",
    ".1.11.1.",
    "1.1.1.1.",
];

pub const BOMBER: [&str; 8] = [
    "....3...",
    "...3....",
    "..1111..",
    ".111111.",
    "11311311",
    "11111111",
    ".111111.",
    "..1111..",
];

pub const SHADE: [&str; 8] = [     // hooded phantom with a wispy tail
    "..2222..",
    ".211112.",
    ".231132.",
    ".211112.",
    ".211112.",
    "..21112.",
    "..2.21..",
    ".2...2..",
];

pub const WARLOCK: [&str; 8] = [
    "...11...",
    "..1331..",
    ".111111.",
    "3.1111.3",
    ".311113.",
    ".111111.",
    ".1.11.1.",
    "11.11.11",
];

pub const ROPE: [&str; 8] = [   // snake: S-slither with a raised head
    ".22.....",
    "21132...",
    "211122..",
    ".221122.",
    "...21112",
    "..2112..",
    ".2112...",
    "22......",
];

pub const BULLET_A: [&str; 8] = [
    "...11...",
    "..1331..",
    ".133331.",
    "1333333.",
    "1333333.",
    ".133331.",
    "..1331..",
    "...11...",
];

pub const BULLET_B: [&str; 8] = [
    "........",
    "..1..1..",
    ".113311.",
    "..1331..",
    "..1331..",
    ".113311.",
    "..1..1..",
    "........",
];

pub const MUZZLE: [&str; 8] = [
    "........",
    "..1..1..",
    ".1.32.1.",
    "..3223..",
    "..2332..",
    ".1.23.1.",
    "..1..1..",
    "........",
];

pub const IMPACT: [&str; 8] = [
    "1.1..1.1",
    ".1.11.1.",
    "..1111..",
    ".111111.",
    ".111111.",
    "..1111..",
    ".1.11.1.",
    "1.1..1.1",
];

pub const WISP: [&str; 8] = [      // floating flame/teardrop, no legs
    "...2....",
    "..232...",
    ".23132..",
    ".231132.",
    ".211112.",
    ".231132.",
    "..2112..",
    "...22...",
];

pub const ITEM_ORB: [&str; 8] = [
    "...11...",
    "..1331..",
    ".133331.",
    ".133331.",
    ".133331.",
    "..1331..",
    "...11...",
    "........",
];

// ---- Dungeon BG tiles (glyph 0 = palette c0, opaque) ----

pub const BGT_FLOOR_PLAIN: [&str; 8] = [
    "22222222",
    "22222222",
    "22212222",
    "22222222",
    "22222222",
    "21222222",
    "22222222",
    "22222322",
];

pub const BGT_FLOOR_CRACK: [&str; 8] = [
    "22222222",
    "22122222",
    "22212222",
    "22221222",
    "22222122",
    "22221222",
    "22212222",
    "22222222",
];

pub const BGT_FLOOR_PEBBLE: [&str; 8] = [
    "22222222",
    "23222122",
    "22222222",
    "22221222",
    "21222322",
    "22222222",
    "22132122",
    "22222222",
];

pub const BGT_WALL_BRICK: [&str; 8] = [
    "33333333",
    "22212221",
    "22212221",
    "11111111",
    "12221222",
    "12221222",
    "11111111",
    "22212221",
];

pub const BGT_DOOR_FRAME: [&str; 8] = [
    "31111113",
    "30000003",
    "30000003",
    "30000003",
    "30000003",
    "30000003",
    "30000003",
    "30000003",
];

pub const BGT_PILLAR: [&str; 8] = [
    "33333332",
    "32222212",
    "32222212",
    "32222212",
    "32222212",
    "32222212",
    "31111112",
    "22222222",
];

pub const BGT_CRYSTAL: [&str; 8] = [
    "00033000",
    "00322300",
    "03222230",
    "32222223",
    "03222230",
    "00322300",
    "00033000",
    "00000000",
];

pub const BGT_RUBBLE: [&str; 8] = [
    "22222222",
    "22112222",
    "22112222",
    "22222222",
    "22222112",
    "22222112",
    "21122222",
    "22222222",
];

pub const BGT_WALL_CRACK: [&str; 8] = [
    "11311211",
    "11322111",
    "21133211",
    "12213321",
    "11331221",
    "21132211",
    "11223311",
    "11331111",
];

pub const BGT_BLOCK: [&str; 8] = [
    "33333333",
    "31111113",
    "31322313",
    "31233213",
    "31233213",
    "31322313",
    "31111113",
    "33333333",
];

// Spike-floor hazard: rows of upward metal points on the amber danger
// palette (glyph 3 = pale tip, 1 = amber body, 0 = dark gap).
pub const BGT_SPIKES: [&str; 8] = [
    "30300303",
    "12122121",
    "11111111",
    "00000000",
    "03030303",
    "21211212",
    "11111111",
    "00000000",
];


// Breakable clay pot: shoot it for loot. Solid until destroyed.
pub const BGT_POT: [&str; 8] = [
    "..2222..",
    ".231132.",
    "21111112",
    "21111112",
    "21311312",
    "21111112",
    ".211112.",
    "..2222..",
];

// 16x16 mini-boss (Stone Sentinel), hand-drawn
pub const BOSS_SENTINEL: [&str; 16] = [
    "....111111111...",
    "...13322331111..",
    "...13322331111..",
    "...111111111111.",
    "...111133311111.",
    "...111322231111.",
    "...111322231111.",
    "...111133311111.",
    "..111111111111..",
    ".1111111111111..",
    "1111111111111111",
    "1111.111111.1111",
    ".111.111111.111.",
    ".111.111111.111.",
    "..1...1111...1..",
    ".11...1.1...11..",
];

// ---- Emission lists (order matters — matches the Python pipeline) ----

pub const PLAYERS: [(&str, &[&str]); 5] = [
    ("wolfkin", &WOLFKIN),
    ("sauran", &SAURAN),
    ("corvin", &CORVIN),
    ("picsean", &PICSEAN),
    ("vespine", &VESPINE),
];

pub const ENEMIES_8: [(&str, &[&str]); 8] = [
    ("crawler", &CRAWLER),
    ("hornet", &HORNET),
    ("skeleton", &SKELETON),
    ("orc", &ORC),
    ("bomber", &BOMBER),
    ("shade", &SHADE),
    ("warlock", &WARLOCK),
    ("rope", &ROPE),
];

pub const FX_8: [(&str, &[&str]); 6] = [
    ("bullet_a", &BULLET_A),
    ("bullet_b", &BULLET_B),
    ("muzzle", &MUZZLE),
    ("impact", &IMPACT),
    ("wisp", &WISP),
    ("item_orb", &ITEM_ORB),
];

pub const DUNGEON_TILES: [(&str, &[&str]); 12] = [
    ("floor_plain", &BGT_FLOOR_PLAIN),
    ("floor_crack", &BGT_FLOOR_CRACK),
    ("floor_pebble", &BGT_FLOOR_PEBBLE),
    ("wall_brick", &BGT_WALL_BRICK),
    ("door_frame", &BGT_DOOR_FRAME),
    ("pillar", &BGT_PILLAR),
    ("crystal", &BGT_CRYSTAL),
    ("rubble", &BGT_RUBBLE),
    ("wall_crack", &BGT_WALL_CRACK),
    ("block", &BGT_BLOCK),
    ("spikes", &BGT_SPIKES),
    ("pot", &BGT_POT),
];

// Mini-boss silhouettes: 2x-scaled enemy art (order matters — indexed by
// the C-side miniboss table).
pub const MINIBOSS_SRC: [(&str, &[&str]); 2] = [
    ("orc", &ORC),
    ("skeleton", &SKELETON),
];

// Bruiser tier: heavy enemies rendered at player size (16x16). The C side
// loads these into 4-tile blocks and flags eids 4/6/8 as big16.
pub const BRUISER_SRC: [(&str, &[&str]); 3] = [
    ("orc", &ORC),
    ("bomber", &BOMBER),
    ("warlock", &WARLOCK),
];
