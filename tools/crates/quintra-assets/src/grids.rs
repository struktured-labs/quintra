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

// GPT Image 2.6 Sunburst pass (2026-11-13): each hero was edited from its old
// upscaled sprite, then hand-quantized back to these 16x16 three-colour grids.
pub const WOLFKIN: [&str; 16] = [   // wolf-beast: inner-ear light, brows over lit eyes, dark nose on a pale muzzle, claws
    "....2......2....", "...232....232...", "...2122222212...", "...2111111112...",
    "...2122112212...", "...2132112312...", "....21322312....", "...2211331122...",
    "..231211112132..", "..211213312112..", "..232111111232..", "...2111111112...",
    "...2112..2112...", "...2112..2112...", "..2112....2112..", "..2332....2332..",
];

pub const SAURAN: [&str; 16] = [   // lizard-man: lit dorsal crest, eye looking down the right-facing snout, pale belly scales
    "......2332......", ".....213312.....", ".....2133112....", "....211111112...",
    "....2132111112..", "....211111222...", ".....2111112....", "...2211331122...",
    "..231133331132..", "..211213312112..", "..23211331232...", "...211111112....",
    "...2112..2112...", "...2112..2112...", "..2112....2112..", "..2332....2332..",
];

pub const CORVIN: [&str; 16] = [   // raven-man: heavy brow, lit eye, two-tone beak, feathered shoulder glints
    ".....222........", "....21222.......", "....211323333...", "....21111222....",
    "....21112.......", ".....212........", "...221111122....", "..21311111312...",
    ".2113111113112..", "..21121111212...", "...211111112....", "...211111112....",
    "...2112..2112...", "...2112..2112...", "...212....212...", "..2332...2332...",
];

pub const PICSEAN: [&str; 16] = [   // fish-man: head fins, round lit eyes, wide mouth, striped gill fins, webbed feet
    "....3......3....", "...23......32...", "...2322..2232...", "...2111221112...",
    "...2132112312...", "...2121111212...", "...2112222112...", "..231111111132..",
    ".2321131131232..", "..211111111112..", "...2111111112...", "...2111111112...",
    "...2112..2112...", "...212....212...", "..23332..23332..", "...222....222...",
];

pub const VESPINE: [&str; 16] = [   // wasp-man: antennae, dark compound eyes, amber mandibles, wings, striped stinger
    "...2........2...", "....2......2....", "....21133112....", "....21211212....",
    "....21111112....", "....21333312....", "..332111111233..", ".33311111111333.",
    "..31131313113...", "...21131313123..", "...211313131223.", "....2111111223..",
    "....21122112....", "....21122112....", "....212..212....", "....232..232....",
];

// A real two-beat walk cycle. The feet trade the lead instead of alternating
// one generic leg edit with the neutral pose, while each species moves the
// appendage that defines its silhouette: Sauran's tail, Corvin's wings,
// Picsean's fins, and Vespine's full wing span.
pub const WOLFKIN_WALK_A: [&str; 16] = [
    "....2......2....", "...232....232...", "...2122222212...", "...2111111112...",
    "...2122112212...", "...2132112312...", "....21322312....", "...2211331122...",
    "..231211112132..", "..211213312112..", ".2321111111122..", "...2111111112...",
    "...2112..2112...", "...2332..2112...", "..........2112..", "..........2332..",
];
pub const SAURAN_WALK_A: [&str; 16] = [
    "......2332......", ".....213312.....", ".....2133112....", "....211111112...",
    "....2132111112..", "....211111222...", ".....2111112....", "...2211331122...",
    "..231133331132..", "..211213312112..", "..232113312222..", "...211111112....",
    "...2112..2112...", "...2332..2112...", "..........2112..", "..........2332..",
];
pub const CORVIN_WALK_A: [&str; 16] = [
    ".....222........", "....21222.......", "....211323333...", "....21111222....",
    "....21112.......", ".....212........", ".22111111122....", "..21311111312...",
    ".2113111113112..", "..21121111212...", "...211111112....", "...211111112....",
    "...2112..2112...", "...2332..2112...", "..........212...", ".........2332...",
];
pub const PICSEAN_WALK_A: [&str; 16] = [
    "....3......3....", "...23......32...", "...2322..2232...", "...2111221112...",
    "...2132112312...", "...2121111212...", "...2112222112...", ".3231111111132..",
    "..2321131131232.", "..211111111112..", "...2111111112...", "...2111111112...",
    "...2112..2112...", "...2332..212....", "..2222...23332..", "..........222...",
];
pub const VESPINE_WALK_A: [&str; 16] = [
    "...2........2...", "....2......2....", "....21133112....", "....21211212....",
    "....21111112....", "....21333312....", ".33321111112333.", ".33311111111333.",
    "..31131313113...", "...21131313123..", "...211313131223.", "....2111111223..",
    "....212..2112...", "....232..2112...", ".........212....", ".........232....",
];
pub const WOLFKIN_WALK_B: [&str; 16] = [
    "....2......2....", "...232....232...", "...2122222212...", "...2111111112...",
    "...2122112212...", "...2132112312...", "....21322312....", "...2211331122...",
    "..231211112132..", "..211213312112..", "..2211111111232.", "...2111111112...",
    "...2112..2112...", "...2112..2332...", "..2112..........", "..2332..........",
];
pub const SAURAN_WALK_B: [&str; 16] = [
    "......2332......", ".....213312.....", ".....2133112....", "....211111112...",
    "....2132111112..", "....211111222...", ".....2111112....", "...2211331122...",
    "..231133331132..", "..211213312112..", ".2223211331232..", "...211111112....",
    "...2112..2112...", "...2112..2332...", "..2112..........", "..2332..........",
];
pub const CORVIN_WALK_B: [&str; 16] = [
    ".....222........", "....21222.......", "....211323333...", "....21111222....",
    "....21112.......", ".....212........", "...2211111112...", "..213111113122..",
    ".2113111113112..", "..21121111212...", "...211111112....", "...211111112....",
    "...2112..2112...", "...2112..2332...", "...212..........", "..2332..........",
];
pub const PICSEAN_WALK_B: [&str; 16] = [
    "....3......3....", "...23......32...", "...2322..2232...", "...2111221112...",
    "...2132112312...", "...2121111212...", "...2112222112...", "..2311111111323.",
    ".2321131131232..", "..211111111112..", "...2111111112...", "...2111111112...",
    "...2112..2112...", "....212..2332...", "..23332...2222..", "...222..........",
];
pub const VESPINE_WALK_B: [&str; 16] = [
    "...2........2...", "....2......2....", "....21133112....", "....21211212....",
    "....21111112....", "....21333312....", "333.21111112.333", ".33311111111333.",
    "..31131313113...", "...21131313123..", "...211313131223.", "....2111111223..",
    "...2112..212....", "...2112..232....", "....212.........", "....232.........",
];
pub const WOLFKIN_CLAIM: [&str; 16] = claim_pose(WOLFKIN);
pub const SAURAN_CLAIM: [&str; 16] = claim_pose(SAURAN);
pub const CORVIN_CLAIM: [&str; 16] = claim_pose(CORVIN);
pub const PICSEAN_CLAIM: [&str; 16] = claim_pose(PICSEAN);
pub const VESPINE_CLAIM: [&str; 16] = claim_pose(VESPINE);

// Zelda-style major-item silhouette: each species keeps its authored head,
// while both arms form a high V toward the separately rendered Sigil above.
// The stable planted feet distinguish this from walking and hurt frames.
const fn claim_pose(mut pose: [&'static str; 16]) -> [&'static str; 16] {
    pose[6] = ".12.21....12.21.";
    pose[7] = ".112.21..12.211.";
    pose[8] = "..112.2112.211..";
    pose[9] = "...2111111112...";
    pose[10] = "....21111112....";
    pose[11] = "....21111112....";
    pose[12] = "....211..2112...";
    pose[13] = "....211..2112...";
    pose[14] = "....212..212....";
    pose[15] = "....22....22....";
    pose
}

// Damage has its own readable recoil instead of borrowing the walk frame.
// The upper half remains class-authored, while the torso folds and the feet
// brace into a wide stagger. Species-specific appendages stay visible.
pub const WOLFKIN_HURT: [&str; 16] = wolfkin_hurt();
pub const SAURAN_HURT: [&str; 16] = sauran_hurt();
pub const CORVIN_HURT: [&str; 16] = corvin_hurt();
pub const PICSEAN_HURT: [&str; 16] = picsean_hurt();
pub const VESPINE_HURT: [&str; 16] = vespine_hurt();

const fn hurt_pose(mut pose: [&'static str; 16]) -> [&'static str; 16] {
    pose[9] = "...211111112....";
    pose[10] = "....21111112....";
    pose[11] = ".....211112.....";
    pose[12] = "....2112.2112...";
    pose[13] = ".....212.212....";
    pose[14] = ".....22..22.....";
    pose[15] = "....22....22....";
    pose
}

const fn wolfkin_hurt() -> [&'static str; 16] {
    let mut pose = hurt_pose(WOLFKIN);
    pose[8] = ".2211111111122..";
    pose
}

const fn sauran_hurt() -> [&'static str; 16] {
    let mut pose = hurt_pose(SAURAN);
    pose[10] = "..22211111112...";
    pose
}

const fn corvin_hurt() -> [&'static str; 16] {
    let mut pose = hurt_pose(CORVIN);
    pose[7] = ".2211111111122..";
    pose
}

const fn picsean_hurt() -> [&'static str; 16] {
    let mut pose = hurt_pose(PICSEAN);
    pose[7] = ".3211111111123..";
    pose
}

const fn vespine_hurt() -> [&'static str; 16] {
    let mut pose = hurt_pose(VESPINE);
    pose[6] = "333.21111112.333";
    pose
}

// Spirit Convergence forms: recognizably the same champions, but with a
// larger supernatural silhouette and a class-specific crown/wing/fin shape.
pub const WOLFKIN_ASCENDED: [&str; 16] = [
    "..3.2......2.3..", "...2123..3212...", "..321222222123..", "...2131331312...",
    "...2113331112...", "..321121121123..", ".33221111112233.", "..322111111223..",
    ".32111111111123.", ".32113111131123.", "..32111111123...", "...211111112....",
    "..32112..21123..", "...2112..2112...", "..3212....2123..", "..322......223..",
];
pub const SAURAN_ASCENDED: [&str; 16] = [
    "...3..2332..3...", "....32133123....", "....3211111233..", "...321131311233.",
    "...321111111123.", "..332113131123..", ".33222111112233.", "3322111111112233",
    ".32111111111123.", "..321311113123..", "...321111123....", "...321111123....",
    "..32112..21123..", "...2112..2112...", "..3212....2123..", "..322......223..",
];
pub const CORVIN_ASCENDED: [&str; 16] = [
    "...3.222.....3..", "..3321112...33..", ".3322111323333..", "33222111112.333.",
    ".33221112...33..", "..332212..233...", "3322211111222333", "3211111111111123",
    ".32113111131123.", "..321111111123..", ".33221111112233.", "..332111112233..",
    "..32112..21123..", "...2112..2112...", "..3212....2123..", "..322......223..",
];
pub const PICSEAN_ASCENDED: [&str; 16] = [
    "3...3......3...3", ".3.233....332.3.", "..32322..22323..", ".33211322311233.",
    "3322131113122333", ".33211111112233.", "3322113131122233", ".32111111111123.",
    "3211131111311123", ".32111111111123.", "..321111111123..", "...321111123....",
    "..32112..21123..", "...212....212...", ".32312....21323.", "..32........23..",
];
pub const VESPINE_ASCENDED: [&str; 16] = [
    "3..2........2..3", ".3..2......2..3.", "33..21133112..33", "3333211221123333",
    ".33321111112333.", "..332113311233..", "3333211111123333", "3311111111111133",
    "3331131313111333", ".3321131311233..", "..321131311233..", "...3211111223...",
    "...3211221123...", "...3211221123...", "...3212..2123...", "...322....223...",
];

// Spirit Convergence used to lock each champion to the single neutral pose,
// so a maxed-out A+B form visibly slid across the floor. One authored lower
// half per champion is enough for a true two-beat stride: runtime mirrors and
// swaps only these two bottom tiles for the opposite foot, leaving asymmetric
// heads, wings, fins, and crowns stable instead of flipping the whole hero.
pub const WOLFKIN_ASCENDED_STEP: [&str; 16] = ascended_step(WOLFKIN_ASCENDED);
pub const SAURAN_ASCENDED_STEP: [&str; 16] = ascended_step(SAURAN_ASCENDED);
pub const CORVIN_ASCENDED_STEP: [&str; 16] = ascended_step(CORVIN_ASCENDED);
pub const PICSEAN_ASCENDED_STEP: [&str; 16] = picsean_ascended_step();
pub const VESPINE_ASCENDED_STEP: [&str; 16] = ascended_step(VESPINE_ASCENDED);

const fn ascended_step(mut pose: [&'static str; 16]) -> [&'static str; 16] {
    pose[12] = "...3211..21123..";
    pose[13] = "....212..2112...";
    pose[14] = "...322....2123..";
    pose[15] = "..........223...";
    pose
}

const fn picsean_ascended_step() -> [&'static str; 16] {
    let mut pose = ascended_step(PICSEAN_ASCENDED);
    // Keep Picsean's webbed lead foot broad enough to read at 1x on a GBC.
    pose[14] = "..3232....2123..";
    pose[15] = "...32.....223...";
    pose
}

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
    "33.22.33",
    "33233233",
    ".321123.",
    "..2112..",
    "..2222..",
    "..2112..",
    "...22...",
    "...2....",
];

pub const SKELETON: [&str; 8] = [  // skull: eye sockets + jaw
    ".222222.",
    "21111112",
    "21311312",
    "21122112",
    ".212212.",
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
    "21311312",
    "21111112",
    "21111112",
    ".211112.",
    ".21.212.",
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
    ".222....",
    "21312...",
    "2111122.",
    ".223112.",
    "...2312.",
    ".2223122",
    "21111112",
    ".222222.",
];

pub const SENTRY: [&str; 8] = [   // turret orb: 4 cardinal cannon ports
    "...33...",
    "..2222..",
    ".211112.",
    "32311323",
    "32211223",
    ".211112.",
    "..2222..",
    "...33...",
];

pub const FOLD_STAR: [&str; 8] = [ // contracted diamond with four false rays
    "1..22..1",
    ".1.22.1.",
    "..2332..",
    "22311322",
    "22311322",
    "..2332..",
    ".1.22.1.",
    "1..22..1",
];

pub const FLUTTERBAT: [&str; 8] = [ // Keese-like swept wings and tiny eyes
    "11....11",
    "111..111",
    "13122131",
    ".112211.",
    "..2332..",
    ".11..11.",
    "11....11",
    ".1....1.",
];

pub const GLOAM_LEECH: [&str; 8] = [ // grasping crescent around a red maw
    "..2222..",
    ".231132.",
    "231..132",
    "21.33.12",
    "21.33.12",
    "231..132",
    ".231132.",
    "..2..2..",
];

pub const CINDER_MAW: [&str; 8] = [ // furnace shell with bright open jaws
    "...33...",
    "..3223..",
    ".321123.",
    "32133123",
    "32133123",
    ".321123.",
    "..3113..",
    ".3.11.3.",
];

// A deliberate middle scale: ten visible pixels wide by fifteen tall inside
// a 16x16 metasprite. It reads twice-ish as large as a swarm enemy without
// becoming another square four-times-area bruiser.
pub const CINDER_MAW_MEDIUM: [&str; 16] = [
    "......3333......",
    ".....322223.....",
    "....32111123....",
    "....32133123....",
    "...3213333123...",
    "...3213..3123...",
    "...3213..3123...",
    "...3213333123...",
    "....32111123....",
    "....33211233....",
    ".....321123.....",
    ".....321123.....",
    ".....32..23.....",
    "....33....33....",
    "....3......3....",
    "................",
];

// Facet Ram: a stocky crystal ram, redrawn from a GPT Image 2.6 Sunburst
// reference. Horizontal art faces east: curled ivory horn and snout on the
// right, the bright rune on its rump (left) is the vulnerable rear. Vertical
// art faces south: horned face at the bottom, the same weak rune at the top.
// The _B frames carry the opposite leg stride and a rune flicker; they are
// streamed over both views at once by enemy_anim_tick (8 tiles, 242..249).
pub const FACET_RAM_H: [&str; 16] = [
    "................",
    "................",
    "................",
    "..........333...",
    ".33222222231322.",
    "3132111112331132",
    "3332111121313112",
    "3132111211133222",
    ".332112111112...",
    "...222222222....",
    "...22.....22....",
    "...2.2....2.2...",
    "..2...2..2...2..",
    ".22...22.22..22.",
    "................",
    "................",
];

pub const FACET_RAM_H_B: [&str; 16] = [
    "................",
    "................",
    "................",
    "..........333...",
    ".33222222231322.",
    "3332111112331132",
    "3132111121313112",
    "3332111211133222",
    ".332112111112...",
    "...222222222....",
    "...22.....22....",
    "...22.....22....",
    "...22.....22....",
    "..222....222....",
    "................",
    "................",
];

pub const FACET_RAM_V: [&str; 16] = [
    "................",
    ".......33.......",
    "......3113......",
    ".....221122.....",
    "....22111122....",
    "...2111111112...",
    "...2112222112...",
    "...2111111112...",
    ".33.21111112.33.",
    "3113.211112.3113",
    "3133213113123313",
    ".33.21111112.33.",
    ".....222222.....",
    "....22....22....",
    "...22......22...",
    "................",
];

pub const FACET_RAM_V_B: [&str; 16] = [
    "................",
    ".......33.......",
    "......3333......",
    ".....221122.....",
    "....22111122....",
    "...2111111112...",
    "...2112222112...",
    "...2111111112...",
    ".33.21111112.33.",
    "3113.211112.3113",
    "3133213113123313",
    ".33.21111112.33.",
    ".....222222.....",
    "....22....22....",
    ".....22..22.....",
    "................",
];

// The stage Reaper is narrow rather than another round/square bruiser. Its
// raised crescent is visible during the long mortal-strike tell, while the
// hollow robe keeps the body distinct from villagers and Warlocks.
pub const STAGE_REAPER: [&str; 16] = [
    "..........3.....",
    ".........333....",
    "....222.33.33...",
    "...21112...33...",
    "..2111112...33..",
    "..2113312....3..",
    ".221111112..33..",
    ".211111111233...",
    ".21113311123....",
    "..2111111123....",
    "..2211111223....",
    "...21111123.....",
    "...21111123.....",
    "..22.2112.22....",
    ".22..2112..22...",
    "22...2222...22..",
];

pub const RETURN_REAPER: [&str; 24] = [
    ".................33333..",
    "...............33322233.",
    "...2.......2..3322....33",
    "...22.....22.332.......3",
    "....2222222..32........3",
    "...221111122.3........3.",
    "..221111111223.......3..",
    "..211333331123......3...",
    ".22133113311223....3....",
    ".211311113111233333.....",
    "221133333311122..3......",
    "211113333111112..3......",
    "211211331121112..3......",
    ".21221111221212223......",
    ".22221111222223333......",
    "..2221111122222..3......",
    "..221111111122...3......",
    ".22112111211122..3......",
    ".211221112211122.3......",
    "221122111221112223......",
    "211222111222111223......",
    "2122.21112.2211123......",
    "222..21112..221223......",
    "22...22122...222.3......",
];

pub const RETURN_WEAVER: [&str; 24] = [
    concat!("........", "..3333..", "........"),
    concat!("........", ".322223.", "........"),
    concat!("...33...", "32211223", "...33..."),
    concat!("..3223..", "22111122", "..3223.."),
    concat!("..32223.", "21111112", ".32223.."),
    concat!("...32223", "11111111", "32223..."),
    concat!("....3222", "11333311", "2223...."),
    concat!(".....322", "13322331", "223....."),
    concat!("......32", "33211233", "23......"),
    concat!(".....322", "32133123", "223....."),
    concat!("...33222", "32133123", "22233..."),
    concat!("..322222", "33211233", "222223.."),
    concat!(".3222332", "13322331", "2332223."),
    concat!("32223.32", "11333311", "23.32223"),
    concat!("3223..32", "21111112", "23..3223"),
    concat!(".33..322", "22111122", "223..33."),
    concat!("....3223", "32211223", "3223...."),
    concat!("...3223.", ".322223.", ".3223..."),
    concat!("..3223..", "..3223..", "..3223.."),
    concat!("..323...", "...33...", "...323.."),
    concat!("..33....", "..3..3..", "....33.."),
    concat!("........", ".3....3.", "........"),
    concat!("........", "3......3", "........"),
    concat!("........", "........", "........"),
];

pub const RETURN_MAW: [&str; 24] = [
    concat!("...33...", "........", "...33..."),
    concat!("..3223..", "........", "..3223.."),
    concat!("..32223.", "........", ".32223.."),
    concat!("...32223", "33333333", "32223..."),
    concat!("....3222", "22222222", "2223...."),
    concat!("...32222", "11111111", "22223..."),
    concat!("..322221", "11311311", "122223.."),
    concat!(".3222221", "13311331", "1222223."),
    concat!("32222221", "13311331", "12222223"),
    concat!("32222221", "11111111", "12222223"),
    concat!("32223321", "33333333", "12332223"),
    concat!("32233321", "31311313", "12333223"),
    concat!(".3223321", "11111111", "1233223."),
    concat!("..322221", "33133133", "122223.."),
    concat!("..322222", "33333333", "222223.."),
    concat!("..322222", "22222222", "222223.."),
    concat!("...32222", "22111122", "22223..."),
    concat!("....3222", "22111122", "2223...."),
    concat!("...32222", "23....32", "22223..."),
    concat!("..322222", "23....32", "222223.."),
    concat!("..322223", "33....33", "322223.."),
    concat!(".3222223", "........", "3222223."),
    concat!(".3333333", "........", "3333333."),
    concat!("........", "........", "........"),
];

pub const MORTAL_SCYTHE: [&str; 8] = [
    ".....333",
    "...3332.",
    "..3322..",
    ".332....",
    ".32.....",
    "..3.....",
    "..3.....",
    ".33.....",
];

pub const RIFT_OOZE: [&str; 8] = [ // unstable blob with two budding fragments
    "..1..1..",
    ".122221.",
    "12322321",
    "12233221",
    ".123321.",
    "..2222..",
    ".22..22.",
    "2......2",
];

pub const MIRROR_MOTH: [&str; 8] = [ // bilateral wings around an icy mirror core
    "1..22..1",
    "11.22.11",
    ".112211.",
    "..2332..",
    "..1331..",
    ".11..11.",
    "11....11",
    "1......1",
];

pub const MIRE_SPORE: [&str; 8] = [ // folded cap, bright volatile core, rootlets
    "..2222..",
    ".211112.",
    "21211212",
    ".233332.",
    ".232232.",
    "..2332..",
    "..2112..",
    ".21..12.",
];

pub const ECHO_GUARD: [&str; 8] = [ // tall shield, eye slit, countering spear
    ".2222.3.",
    "21111233",
    "2211223.",
    "2133123.",
    "2111123.",
    ".211223.",
    "..22223.",
    ".2.2..3.",
];

pub const FROST_LANCER: [&str; 8] = [ // icy visor, raised lance, split skates
    "..3.3..3",
    "..3223.3",
    ".3211233",
    "32111123",
    ".1233213",
    "..1331.3",
    ".31..133",
    "3..3...3",
];

pub const VINE_COIL: [&str; 8] = [ // coiled vine bulb, thorned leaf crown
    "...2.2..",
    "..23232.",
    ".2311132",
    "23122132",
    "23133132",
    ".2311132",
    "..23232.",
    "...2.2..",
];

pub const SHARD_CRAB: [&str; 8] = [ // low crystal shell, bright cracked core
    "...33...",
    ".332233.",
    "32111123",
    "31122113",
    "31233213",
    "32111123",
    ".33..33.",
    "3.3..3.3",
];

pub const VOID_HALO: [&str; 8] = [ // fractured ring with a dark central void
    "..3223..",
    ".321123.",
    "32111123",
    "21311312",
    "21111112",
    "32111123",
    ".321123.",
    "..3223..",
];

pub const RIFT_CANTOR: [&str; 8] = [ // antlered mask around an open chanting mouth
    "3.3..3.3",
    ".3.22.3.",
    "3.2222.3",
    ".211112.",
    "21311312",
    ".213312.",
    "..2332..",
    ".3.22.3.",
];

pub const RUNE_LANTERN: [&str; 8] = [ // hooded lantern with a four-rune halo
    "...33...",
    "..2222..",
    "32211223",
    ".223322.",
    ".233332.",
    ".213312.",
    "..2112..",
    ".3.11.3.",
];

pub const DREAD_BELL: [&str; 8] = [ // hanging iron bell; pale clapper reads at a glance
    "...33...",
    "..2112..",
    ".211112.",
    ".221122.",
    "21211212",
    "21111112",
    "33333333",
    ".3.33.3.",
];

pub const RIFT_WARDEN: [&str; 8] = [ // split-mask sentinel, open outer lanes
    "...33...",
    "..3223..",
    ".322223.",
    "32122123",
    "32111123",
    ".321123.",
    ".31..13.",
    ".32..23.",
];

pub const PRISM_SKITTER: [&str; 8] = [ // faceted core with asymmetric orbit fins
    "..3.3.3.",
    ".323232.",
    "32111123",
    "21311312",
    "32111123",
    ".322223.",
    ".3.22.3.",
    "3..3.3..",
];

pub const DUSK_MIDGE: [&str; 8] = [ // forked wings, bright eyes, tail spark
    "..3..3..",
    "..2..2..",
    ".211112.",
    "32311323",
    "32111123",
    ".211112.",
    ".3.33.3.",
    "3.3..3.3",
];

pub const SUNWHEEL: [&str; 8] = [ // radiant ring, offset spokes, dark core
    "...33...",
    ".311113.",
    ".122221.",
    "31322313",
    "31222213",
    ".122221.",
    ".311113.",
    "...33...",
];

pub const CINDER_KITE: [&str; 8] = [ // wide ember wings, suspended furnace core
    "3......3",
    ".3....3.",
    "..3223..",
    ".321123.",
    "32133123",
    ".321123.",
    "..3..3..",
    "...33...",
];

pub const BOG_TOAD: [&str; 8] = [ // squat mire toad, wide eyes and pounce legs
    ".33..33.",
    "32311323",
    "21111112",
    "21333312",
    "21111112",
    ".211112.",
    "21122112",
    "22....22",
];

pub const BRAMBLE_SPRITE: [&str; 8] = [ // thorned leaf halo, bright seed core
    ".2.22.2.",
    ".211112.",
    "21333312",
    "13233231",
    "13333331",
    "21333312",
    ".211112.",
    ".2.22.2.",
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

// Rift Lens projectile: the renderer chains these two tiles along velocity.
// A bright solid core and dark rim make the result read as a thick beam rather
// than two ordinary bullets touching one another.
pub const BEAM_HEAD: [&str; 8] = [
    "..3333..",
    ".321123.",
    "32111123",
    "31133113",
    "31133113",
    "32111123",
    ".321123.",
    "..3333..",
];

pub const BEAM_TAIL: [&str; 8] = [
    "........",
    ".333333.",
    "32111123",
    "31133113",
    "31133113",
    "32111123",
    ".333333.",
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
    ".23332..",
    ".231132.",
    "21311312",
    "21111112",
    ".211112.",
    "..2222..",
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

// Hanging market tag: the cut corner and bright center read as merchandise,
// not loose currency, when alternated with a ware's ordinary pickup icon.
pub const SHOP_TAG: [&str; 8] = [
    "..222...",
    ".21112..",
    "2111112.",
    "2113312.",
    "2113312.",
    ".21112..",
    "..222...",
    "........",
];

// Merchant callout: a compact speech bubble with a gold coin. It appears only
// while the champion is close enough to trade, so market NPCs communicate
// without turning every room into a modal dialogue screen.
pub const MERCHANT_CALLOUT: [&str; 8] = [
    ".11111..",
    "1222221.",
    "12.33.21",
    "12333321",
    "12333321",
    "1222221.",
    ".111.1..",
    "....1...",
];

// Cyan lightning in a faceted orb: a rare short-lived combat boon, distinct
// from gold currency and the permanent relic orb.
pub const SURGE_ORB: [&str; 8] = [
    "...3....",
    "..323...",
    ".32123..",
    "1231231.",
    ".123321.",
    "..3123..",
    ".321.3..",
    "...3....",
];

// A small hollow ward shard. Four of these orbit Sauran while Stoneskin is
// active, so the body/projectile immunity reads at a glance rather than as a
// generic impact flash.
pub const SHIELD_AURA: [&str; 8] = [
    "...11...",
    "..1331..",
    ".13..31.",
    "13....31",
    "13....31",
    ".13..31.",
    "..1331..",
    "...11...",
];

// Picsean's guard is a broad curling wave rather than Sauran's compact stone
// shard. Runtime orbit radius reinforces the same mechanical distinction.
pub const WATER_AURA: [&str; 8] = [
    "....33..",
    "..3333..",
    ".33..33.",
    "33...33.",
    ".3..33..",
    "..333...",
    ".33333..",
    "..111...",
];

// Wolfkin's steel: an asymmetric pointed blade with a crossguard and hilt.
// The runtime X/Y flips it around the aim vector, so the starting melee kit
// reads as a sword thrust/slash rather than a tiny fist or slow bullet.
pub const SWORD: [&str; 8] = [
    ".......3",
    "......33",
    ".....32.",
    "....32..",
    "...32...",
    "..322...",
    ".3111...",
    "33.3....",
];

// Rift Flail: a heavy faceted head linked to a short diagonal chain. The
// uneven mass reads differently from the straight sword even during a fast
// room fight.
pub const FLAIL: [&str; 8] = [
    ".....333",
    "....3223",
    "....3233",
    "...1.33.",
    "..1.....",
    ".1......",
    "1.......",
    "22......",
];

// Tail Spike / Stinger: a hooked organic barb, not borrowed sword steel.
pub const SPIKE: [&str; 8] = [
    ".......3",
    ".....333",
    "...3332.",
    "..332...",
    ".332....",
    "332.....",
    ".21.....",
    "..11....",
];

// Astral Spear: an asymmetric pointed shaft, intentionally unlike the broad
// sword arc. It occupies a town-only NPC tile while dungeon combat is active.
pub const SPEAR: [&str; 8] = [
    ".......3",
    "......33",
    ".....32.",
    "....32..",
    "...32...",
    "..32....",
    ".32.....",
    "33......",
];

// Town elder: hooded face and crooked staff, readable at true GB scale.
pub const VILLAGER: [&str; 8] = [
    "..222...",
    ".21112..",
    ".21312..",
    ".21112..",
    "..212.3.",
    ".211123.",
    ".212.3..",
    ".2.2.3..",
];

// Travelling merchant: broad hat, bright face, striped apron. Deliberately
// distinct from the elder's narrow hood/staff silhouette at 1x scale.
pub const MERCHANT: [&str; 8] = [
    ".333333.",
    "33333333",
    "..2112..",
    ".213312.",
    ".211112.",
    "..2332..",
    ".231132.",
    ".2.11.2.",
];

// Village smith: horned welding mask, bright hammer, heavy apron. The broad
// hammer-side silhouette distinguishes the forge from both hood and hat NPCs.
pub const SMITH: [&str; 8] = [
    ".2....2.",
    "..2222.3",
    ".23113.3",
    ".21112.3",
    "..233.33",
    ".231133.",
    ".231132.",
    ".2.11.2.",
];

// Village rune keeper: tall vial-cap, bright lenses, and hanging satchel.
pub const APOTHECARY: [&str; 8] = [
    "...11...",
    "..1331..",
    ".132231.",
    ".131131.",
    "..1221..",
    ".113311.",
    ".13..31.",
    "..1..1..",
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

// Closed portcullis. Runtime rendering substitutes this for the ordinary
// threshold only while that particular graph exit is sealed; collision keeps
// the underlying BGT_DOOR so the same edge opens without rebuilding terrain.
pub const BGT_DOOR_LOCKED: [&str; 8] = [
    "31111113",
    "30222203",
    "30222203",
    "30222203",
    "30222203",
    "30222203",
    "30222203",
    "31111113",
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

// Floor-rooted cluster: uneven spires on a wide base. The old symmetric
// diamond read as a pendant sitting on a pedestal.
pub const BGT_CRYSTAL: [&str; 8] = [
    "03000300",
    "03300330",
    "03222330",
    "33222223",
    "32322232",
    "33322333",
    "33333333",
    "32222223",
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

// Recessed floor pressure plate. GPT Image 2.6 Sunburst concept, hand-
// quantized to the 4-colour BGPAL_DOOR indices: raised gold bezel, inner
// well, and a jewel highlight. Pressed is the same silhouette, sunken.
pub const BGT_SWITCH: [&str; 8] = [
    "23333332",
    "32111123",
    "31233313",
    "31332313",
    "31333313",
    "31233313",
    "32111123",
    "21111110",
];

// Not in DUNGEON_TILES: the 16-byte array lives in src/render/tiles_switch.c
// (bank 22) so bank 2 stays at the 256-byte floor.
#[allow(dead_code)] // referenced by the banked-source gold test
pub const BGT_SWITCH_PRESSED: [&str; 8] = [
    "23222232",
    "21000012",
    "20111102",
    "20122102",
    "20111102",
    "20111102",
    "21000013",
    "22222221",
];

// An asymmetric spiral makes orientation intentionally difficult after a hop.
pub const BGT_PORTAL: [&str; 8] = [
    "..1221..",
    ".133331.",
    "132..231",
    "13.22.31",
    "13.21.31",
    "132..231",
    ".133331.",
    "..1221..",
];

// 16x16 mini-boss (Stone Sentinel). GPT Image 2.6 Sunburst pass: lit visor
// eyes and a palette-2 rim around the unchanged colour-1 body. Slot 6 is the
// stage boss palette, so colour 2 is cyan in Crystal Caverns but near-black
// in Bloodmoon; the body therefore stays colour 1 in both stages.
pub const BOSS_SENTINEL: [&str; 16] = [
    "....222222222...",
    "...23311111122..",
    "...21331133112..",
    "...211111111122.",
    "...211133311122.",
    "...211322231122.",
    "...211322231122.",
    "...211133311122.",
    "..211111111122..",
    ".2211111111112..",
    "2332111111112332",
    "2112.211112.2112",
    ".212.211112.212.",
    ".222.211112.222.",
    "..2...2112...2..",
    ".22...2.2...22..",
];

// Mini-boss animation (GPT Image 2.6 Sunburst pass, 2026-11-15). Every
// variant gets three hand-quantized 16x16 poses streamed into the shared
// four-tile SPR_BOSS slot: 0 = idle/left-foot beat, 1 = bobbed right-foot
// beat, 2 = attack telegraph (held for the last 12 ticks before a volley).
// Same palettes, glyph roles, 16x16 box and hitbox as the old single frame.
// The Sentinel keeps its shipped pass-1 pose as frame 0; its body stays
// colour 1 because slot 6 colour 2 is near-black in Bloodmoon.
// Sentinel: stone guardian; telegraph lifts both fists while the core flares.
pub const MB_SENTINEL_STEP: [&str; 16] = [
    "................",
    "....222222222...",
    "...23311111122..",
    "...21331133112..",
    "...211111111122.",
    "...211133311122.",
    "...211322231122.",
    "...211322231122.",
    "...211133311122.",
    "..211111111122..",
    ".2211111111112..",
    "2332111111112332",
    "2112.211112.2112",
    ".212.211112.212.",
    "......2112......",
    ".....22..22.....",
];
pub const MB_SENTINEL_TELL: [&str; 16] = [
    "222..........222",
    "232..222222..232",
    "212.23111132.212",
    "212.21333312.212",
    ".21221111112212.",
    "..212113311212..",
    "...2213333122...",
    "...2113333112...",
    "...2111331112...",
    "..221111111122..",
    ".21111111111112.",
    ".21221111112212.",
    "..2.21111112.2..",
    "....21122112....",
    "...2112..2112...",
    "...222....222...",
];
// Orc: moss-green tusked brute; telegraph roars with both fists overhead.
pub const MB_ORC_IDLE: [&str; 16] = [
    "................",
    ".....222222.....",
    "....21111112....",
    "...2111111112...",
    "...2222112222...",
    "..221331133122..",
    ".22111111111122.",
    "2111232112321112",
    "2111122222211112",
    "2112111111112112",
    "2112111221112112",
    "2112211111122112",
    ".22.21111112.22.",
    "....21122112....",
    "...21112.2112...",
    "...2222..222....",
];
pub const MB_ORC_STEP: [&str; 16] = [
    "................",
    "................",
    ".....222222.....",
    "....21111112....",
    "...2111111112...",
    "...2222112222...",
    "..221331133122..",
    ".22111111111122.",
    "2111232112321112",
    "2111122222211112",
    "2112111111112112",
    "2112211221122112",
    ".22.21111112.22.",
    "....21122112....",
    "...2112.21112...",
    "....222..2222...",
];
pub const MB_ORC_TELL: [&str; 16] = [
    ".22..........22.",
    "2112.222222.2112",
    "2112211111122112",
    "2111211111121112",
    ".21122222222112.",
    "..213313313312..",
    "..211123321112..",
    "...2132222312...",
    "...2133333312...",
    "...2112222112...",
    "..221111111122..",
    "..211112211112..",
    "...2111221112...",
    "...2112..2112...",
    "..21112..21112..",
    "..2222....2222..",
];
// Skeleton: skull champion with ribcage; telegraph drops the jaw and flings the arms out.
pub const MB_SKELETON_IDLE: [&str; 16] = [
    "....22222222....",
    "...2111111112...",
    "..211111111112..",
    "..213311113312..",
    "..213311113312..",
    "..211112211112..",
    "...2111111112...",
    "....21212122....",
    "...2.222222.2...",
    "..21211111212...",
    "..212.2222.212..",
    "..2.2111111.2...",
    ".....222222.....",
    "....21122112....",
    "...2112..2112...",
    "...222...222....",
];
pub const MB_SKELETON_STEP: [&str; 16] = [
    "................",
    "....22222222....",
    "...2111111112...",
    "..211111111112..",
    "..213311113312..",
    "..213311113312..",
    "..211112211112..",
    "...2111111112...",
    "....21212122....",
    "...2.222222.2...",
    "..21211111212...",
    "..212.2222.212..",
    "..2.21111112.2..",
    "....21222212....",
    "....2112.2112...",
    "....222...222...",
];
pub const MB_SKELETON_TELL: [&str; 16] = [
    "....22222222....",
    "...2111111112...",
    "..211111111112..",
    "..213311113312..",
    "..213311113312..",
    "..211112211112..",
    "...2122222212...",
    "...2122222212...",
    "22..21111112..22",
    "2122.222222.2212",
    ".21121111112112.",
    "..2.2.2222.2.2..",
    "....21111112....",
    "....21222212....",
    "...2112..2112...",
    "...222....222...",
];
// Bomber: living bomb on stubby feet; telegraph squashes wide as the fuse bursts.
pub const MB_BOMBER_IDLE: [&str; 16] = [
    "..........3.....",
    ".........333....",
    "........3.3.....",
    ".......3........",
    "......2222......",
    "....22111122....",
    "...2111111132...",
    "..211111111312..",
    "..212211112212..",
    "..211321123112..",
    "..211331133112..",
    "..211111111112..",
    "...2111221112...",
    "....22111122....",
    "...21112.2112...",
    "...2222...22....",
];
pub const MB_BOMBER_STEP: [&str; 16] = [
    "................",
    "..........3.....",
    "........33.33...",
    "........3.3.....",
    "........3.......",
    "......2222......",
    "....22111122....",
    "...2111111132...",
    "..211111111312..",
    "..212211112212..",
    "..211321123112..",
    "..211331133112..",
    "..211111111112..",
    "...2111221112...",
    "....22111122....",
    "...2112..21112..",
];
pub const MB_BOMBER_TELL: [&str; 16] = [
    ".....3..3..3....",
    "......3333......",
    "....33333333....",
    "......3333......",
    ".....3.33.3.....",
    "......2222......",
    "..222211112222..",
    ".21111111111132.",
    "2111111111111312",
    "2111222112221112",
    "2113332112333112",
    "2111111111111112",
    ".21111222211112.",
    "..222111111222..",
    "..21112..21112..",
    "..2222....2222..",
];
// Warlock: hooded caster with orb hands; telegraph raises both blazing orbs.
pub const MB_WARLOCK_IDLE: [&str; 16] = [
    ".......22.......",
    "......2112......",
    ".....211112.....",
    "....21122112....",
    "...2122222212...",
    "...2123223212...",
    "...2122222212...",
    "..221122221122..",
    ".23211111111232.",
    "2332211111122332",
    ".23121111112132.",
    "..2121111112122.",
    "..211211112112..",
    "..211211112112..",
    ".21112222211112.",
    ".2222.33..222...",
];
pub const MB_WARLOCK_STEP: [&str; 16] = [
    "................",
    ".......22.......",
    "......2112......",
    ".....211112.....",
    "....21122112....",
    "...2122222212...",
    "...2123223212...",
    "...2122222212...",
    "..221122221122..",
    ".23211111111232.",
    "2332211111122332",
    ".23121111112132.",
    "..2121111112122.",
    "..211211112112..",
    ".21112222211112.",
    "..222..33.2222..",
];
pub const MB_WARLOCK_TELL: [&str; 16] = [
    ".33..........33.",
    "3333...22...3333",
    "3333..2112..3333",
    ".33..211112..33.",
    ".21.21122112.12.",
    ".21212222221212.",
    ".21212322321212.",
    "..221222222122..",
    "...2112222112...",
    "....21111112....",
    "...2111111112...",
    "...2112112112...",
    "..211211112112..",
    "..211211112112..",
    ".21112222211112.",
    ".2222.33.33.2222",
];

// Indexed by stage_mb_variant (0 sentinel, 1 orc, 2 skeleton, 3 bomber,
// 4 warlock); the C loader addresses variant * 3 + pose.
pub const MINIBOSS_ANIM: [(&str, [&[&str]; 3]); 5] = [
    ("sentinel", [&BOSS_SENTINEL, &MB_SENTINEL_STEP, &MB_SENTINEL_TELL]),
    ("orc", [&MB_ORC_IDLE, &MB_ORC_STEP, &MB_ORC_TELL]),
    ("skeleton", [&MB_SKELETON_IDLE, &MB_SKELETON_STEP, &MB_SKELETON_TELL]),
    ("bomber", [&MB_BOMBER_IDLE, &MB_BOMBER_STEP, &MB_BOMBER_TELL]),
    ("warlock", [&MB_WARLOCK_IDLE, &MB_WARLOCK_STEP, &MB_WARLOCK_TELL]),
];

// ---- Enemy animation (GPT Image 2.6 Sunburst monster pass, 2026-11-15) ----
// Second frames for the redrawn rank and file. Frame A stays the resident
// art above; enemy_anim_tick streams A/B into the canonical OBJ slot on the
// shared 16-frame beat. Enemies without an authored B use their mirrored A,
// which reproduces the old whole-sprite X flip exactly.
pub const CRAWLER_B: [&str; 8] = [
    ".2....2.",
    "..2112..",
    "22211222",
    ".231132.",
    ".211112.",
    "22211222",
    "..2..2..",
    ".2....2.",
];
pub const HORNET_B: [&str; 8] = [
    "...22...",
    "..2332..",
    "33211233",
    "33211233",
    ".322223.",
    "..2112..",
    "...22...",
    "...2....",
];
pub const ROPE_B: [&str; 8] = [
    "..222...",
    ".21312..",
    "32111122",
    "..223112",
    "...23112",
    ".222312.",
    "21111112",
    ".222222.",
];
pub const FOLD_STAR_B: [&str; 8] = [
    "...22...",
    "..2112..",
    ".213312.",
    "21333312",
    "21333312",
    ".213312.",
    "..2112..",
    "...22...",
];
pub const FLUTTERBAT_B: [&str; 8] = [
    "........",
    "...22...",
    "..2112..",
    "12133121",
    "11222211",
    "11.22.11",
    "1......1",
    "........",
];
pub const GLOAM_LEECH_B: [&str; 8] = [
    "........",
    "..2222..",
    ".231132.",
    "23133132",
    ".231132.",
    "..2222..",
    "..2..2..",
    ".2....2.",
];
pub const RIFT_OOZE_B: [&str; 8] = [
    "........",
    ".1....1.",
    "..2222..",
    ".123321.",
    "12322321",
    "12222221",
    ".222222.",
    "........",
];
pub const CINDER_KITE_B: [&str; 8] = [
    "3.3..3.3",
    "33.22.33",
    ".332233.",
    "..2112..",
    ".213312.",
    "..2112..",
    "...33...",
    "........",
];
pub const VINE_COIL_B: [&str; 8] = [
    "..2.2...",
    ".23232..",
    ".2311132",
    "23122132",
    "23133132",
    ".2311132",
    "..23232.",
    "..2.2...",
];
pub const SHARD_CRAB_B: [&str; 8] = [
    "3..33..3",
    ".332233.",
    "32111123",
    "31122113",
    "31233213",
    "32111123",
    "3.3..3.3",
    ".3....3.",
];
// Bruiser tier redrawn at native 16x16 (was 2x-scaled 8x8 art). A bruiser
// sits a size class below its mini-boss cousin so the two never read alike.
pub const BRUISER_ORC_A: [&str; 16] = [
    "................",
    "................",
    ".....222222.....",
    "....21111112....",
    "...2111111112...",
    "..222133133122..",
    ".2321111111112..",
    ".2332131131312..",
    ".23322111111222.",
    "..2332222222112.",
    "..2112111111212.",
    "...222111111222.",
    ".....2111112....",
    "....2112.2112...",
    "....2112.2112...",
    "....222..222....",
];
pub const BRUISER_ORC_B: [&str; 16] = [
    "................",
    "................",
    "................",
    ".....222222.....",
    "....21111112....",
    "...2111111112...",
    ".22.2133133122..",
    "2332111111112...",
    "23322131131312..",
    ".23322111111222.",
    "..2112222222112.",
    "...222111111212.",
    ".....2111112222.",
    "....2112.2112...",
    "...2112...2112..",
    "...222.....222..",
];
pub const BRUISER_BOMBER_A: [&str; 16] = [
    "................",
    "..........3.....",
    ".........3.3....",
    "........2.......",
    ".......2........",
    ".....22222......",
    "....2111112.....",
    "...211111132....",
    "...213113112....",
    "...213113112....",
    "...211111112....",
    "...212222212....",
    "....2111112.....",
    ".....22222......",
    "....212..212....",
    "....22....22....",
];
pub const BRUISER_BOMBER_B: [&str; 16] = [
    "................",
    "................",
    "..........3.....",
    "........2333....",
    ".......2..3.....",
    ".....22222......",
    "....2111112.....",
    "...211111132....",
    "...213113112....",
    "...213113112....",
    "...211111112....",
    "...212222212....",
    "....2111112.....",
    ".....22222......",
    "...212....212...",
    "...22......22...",
];
pub const CINDER_MAW_MEDIUM_B: [&str; 16] = [
    ".....3.33.3.....",
    "......3223......",
    "....32111123....",
    "....32111123....",
    "...3211331123...",
    "...3213333123...",
    "...3213333123...",
    "...3211331123...",
    "....32111123....",
    "....33211233....",
    ".....321123.....",
    ".....321123.....",
    "......3223......",
    ".....33..33.....",
    ".....3....3.....",
    "................",
];

pub const SKELETON_B: [&str; 8] = [
    "........",
    ".222222.",
    "21111112",
    "21311312",
    "21111112",
    ".221122.",
    ".212212.",
    ".2.22.2.",
];
pub const WISP_B: [&str; 8] = [
    "....2...",
    "...232..",
    "..23332.",
    ".231132.",
    "21311312",
    "21111112",
    ".211112.",
    "..2222..",
];
pub const SENTRY_B: [&str; 8] = [
    "3......3",
    ".322223.",
    ".211112.",
    ".231132.",
    ".221122.",
    ".211112.",
    ".322223.",
    "3......3",
];
pub const MIRROR_MOTH_B: [&str; 8] = [
    ".1.22.1.",
    "1..22..1",
    "11.22.11",
    ".123321.",
    "..2332..",
    "..1..1..",
    ".1....1.",
    "........",
];
pub const MIRE_SPORE_B: [&str; 8] = [
    ".222222.",
    "21111112",
    "21211212",
    ".233332.",
    ".232232.",
    "..2332..",
    ".2.11.2.",
    "2..11..2",
];
pub const SHADE_B: [&str; 8] = [
    "..2222..",
    ".211112.",
    "21311312",
    "21111112",
    ".211112.",
    ".21112..",
    "..212.2.",
    "...2...2",
];
pub const RUNE_LANTERN_B: [&str; 8] = [
    ".3.33.3.",
    "..2222..",
    ".221122.",
    "32233223",
    ".233332.",
    ".233332.",
    "..2112..",
    "3..11..3",
];
pub const PRISM_SKITTER_B: [&str; 8] = [
    ".3.3.3..",
    ".232323.",
    "32111123",
    "21311312",
    "32111123",
    ".322223.",
    "..3.2.3.",
    ".3.3..3.",
];
pub const BOG_TOAD_B: [&str; 8] = [
    "........",
    ".33..33.",
    "32311323",
    "21111112",
    "21333312",
    "21111112",
    "2.2222.2",
    "22....22",
];
pub const BRAMBLE_SPRITE_B: [&str; 8] = [
    "2..22..2",
    ".211112.",
    "21333312",
    "21233212",
    "21333312",
    "21322312",
    ".211112.",
    "2..22..2",
];
pub const FROST_LANCER_B: [&str; 8] = [
    "..3.3..3",
    "..3223.3",
    ".3211233",
    "32111123",
    ".1233213",
    "..1331.3",
    "..31.13.",
    ".3..3..3",
];
pub const RIFT_CANTOR_B: [&str; 8] = [
    "33....33",
    "3.3223.3",
    "..2222..",
    ".211112.",
    "21311312",
    ".233332.",
    "..2112..",
    ".3.22.3.",
];

pub const ECHO_GUARD_B: [&str; 8] = [
    ".2222...",
    "211112..",
    "221122..",
    "21331333",
    "211112..",
    ".21122..",
    "..2222..",
    ".2..2...",
];
pub const DREAD_BELL_B: [&str; 8] = [
    "........",
    "...33...",
    "..2112..",
    ".211112.",
    ".212212.",
    "21111112",
    "33333333",
    "3..33..3",
];
pub const RIFT_WARDEN_B: [&str; 8] = [
    "........",
    "...33...",
    "..3223..",
    ".322223.",
    "32122123",
    "32111123",
    ".321123.",
    "3.3..3.3",
];
pub const DUSK_MIDGE_B: [&str; 8] = [
    "..3..3..",
    "..2..2..",
    ".211112.",
    ".231132.",
    "32111123",
    "33211233",
    "3.3..3.3",
    ".3.33.3.",
];
pub const SUNWHEEL_B: [&str; 8] = [
    "3......3",
    ".311113.",
    ".122221.",
    "11322311",
    "11222211",
    ".122221.",
    ".311113.",
    "3......3",
];
pub const VOID_HALO_B: [&str; 8] = [
    "..2332..",
    ".231132.",
    "23111132",
    "31311313",
    "31111113",
    "23111132",
    ".231132.",
    "..2332..",
];
// Warlock bruiser redrawn at native 16x16 (was 2x-scaled 8x8): hooded caster,
// hands raised with sparks on B.
pub const BRUISER_WARLOCK_A: [&str; 16] = [
    "................",
    ".......22.......",
    "......2112......",
    ".....211112.....",
    "....21333312....",
    "...2112222112...",
    "...2123223212...",
    ".33211222211233.",
    "3332111221112333",
    ".33211111111233.",
    "..211111111112..",
    "..211111111112..",
    "..211112211112..",
    "..21112..21112..",
    "..2222....2222..",
    "................",
];
pub const BRUISER_WARLOCK_B: [&str; 16] = [
    "..3..........3..",
    ".333...22...333.",
    "..3...2112...3..",
    "..2..211112..2..",
    "..2.21333312.2..",
    "..221122221122..",
    "...2123223212...",
    "...2112222112...",
    "...2111221112...",
    "..211111111112..",
    "..211111111112..",
    ".21111111111112.",
    ".21111122111112.",
    ".21112....21112.",
    ".2222......2222.",
    "................",
];


// Placeholder silhouettes for the 2026-11-17 specialist pass. GPT Image
// 2.6 candidates will replace these once quantized; the AI and tests do
// not depend on the exact pixels.
pub const VEIL_MAGUS: [&str; 8] = [
    "..1.....",
    ".233....",
    ".12332..",
    ".131111.",
    "..22111.",
    ".13332..",
    ".12222..",
    "..1.1...",
];
pub const VEIL_MAGUS_B: [&str; 8] = [
    "..1.....",
    ".233..1.",
    ".123212.",
    ".131111.",
    ".22322..",
    "22133...",
    ".22211..",
    "........",
];
pub const HEX_WALKER: [&str; 8] = [
    "........",
    "..1331..",
    "..2311..",
    "..122...",
    "..2332..",
    "..132...",
    "........",
    "........",
];
pub const HEX_WALKER_B: [&str; 8] = [
    "........",
    ".2332...",
    ".23211..",
    "..31111.",
    ".232111.",
    ".13322..",
    ".12211..",
    "........",
];
pub const ZAG_DART: [&str; 8] = [
    "........",
    "...1....",
    "..122...",
    "..3332..",
    "..11....",
    "........",
    "........",
    "........",
];
pub const ZAG_DART_B: [&str; 8] = [
    "........",
    "..21....",
    "..1332..",
    ".13222..",
    "..2112..",
    "........",
    "........",
    "........",
];
// Basilisk core: blank. The 32x32 body is GPT art in bank-1 OBJ
// (src/render/basilisk_art.c), drawn by new_monsters_draw().
pub const LEYBEAM: [&str; 8] = [
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
];
pub const LEYBEAM_B: [&str; 8] = [
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
    "........",
];
pub const FUSE_HURLER: [&str; 8] = [
    "...1....",
    "..232...",
    ".11321..",
    ".133321.",
    ".332112.",
    ".13.11..",
    "..3122..",
    "..2..2..",
];
pub const FUSE_HURLER_B: [&str; 8] = [
    "........",
    "..32....",
    "..32111.",
    "..231...",
    "..22....",
    "........",
    "........",
    "........",
];

pub const VAULT_HAND: [&str; 16] = [
    "......33333.....",
    ".....133332.....",
    "......12.32.....",
    "......11.21.....",
    ".....111111.....",
    ".....1.21121....",
    "....122...11....",
    "..1133223.2111..",
    ".12.21.33.23.21.",
    ".1311.3112122.1.",
    "122.111.11.1.321",
    "132.1.2..2.1.2.1",
    ".2..131..2...131",
    "....11...11...1.",
    "....11...11.....",
    ".....1..........",
];
pub const VAULT_HAND_B: [&str; 16] = [
    "...1111111111...",
    "...13333322321..",
    "....233333332...",
    ".....122231.....",
    "......1111......",
    "......1.12......",
    ".....111111.....",
    "....1..1..11....",
    "....111.32.211..",
    "..11.3132233.1..",
    ".1123113...232..",
    ".1.311.2...12.1.",
    ".122.1.1...1331.",
    ".131..11..1..2..",
    "..231..1..111...",
    "....1.....1.....",
];
pub const BANE_BRUTE: [&str; 16] = [
    "................",
    ".......1........",
    "......11111.....",
    ".....11.2321....",
    "....11323121....",
    "...232132221....",
    "..13332312211...",
    ".1332232122221..",
    ".2331333332331..",
    ".13212323211331.",
    ".13211111111332.",
    ".1221111111112..",
    "....23211231....",
    "...2331..232....",
    "...1111..111....",
    "................",
];
pub const BANE_BRUTE_B: [&str; 16] = [
    "................",
    "................",
    ".......221......",
    ".....2133321....",
    "....12221211....",
    "..123133212231..",
    "..233231122132..",
    ".22123223321331.",
    ".13123322123331.",
    "...11122311211..",
    "...1..1111......",
    "...3211.1221....",
    "..231.11231.....",
    "..121...111.....",
    "................",
    "................",
];

pub struct EnemyAnim {
    pub eid: u8,
    pub slot: u8,
    pub a: &'static [&'static str],
    pub b: Option<&'static [&'static str]>,
}

const fn anim(eid: u8, slot: u8, a: &'static [&'static str],
              b: Option<&'static [&'static str]>) -> EnemyAnim {
    EnemyAnim { eid, slot, a, b }
}

// Content enemy id -> canonical OBJ slot (content/src/ids.rs). Bosses, the
// mini-boss Sentinel, Facet Ram and the Reaper own their own pose drivers.
pub const ENEMY_ANIM: [EnemyAnim; 39] = [
    anim( 0,  20, &CRAWLER, Some(&CRAWLER_B)),
    anim( 2,  21, &HORNET, Some(&HORNET_B)),
    anim( 3,  22, &SKELETON, Some(&SKELETON_B)),
    anim( 4,  56, &BRUISER_ORC_A, Some(&BRUISER_ORC_B)),
    anim( 5,  34, &WISP, Some(&WISP_B)),
    anim( 6,  60, &BRUISER_BOMBER_A, Some(&BRUISER_BOMBER_B)),
    anim( 7,  37, &SHADE, Some(&SHADE_B)),
    anim( 8,  64, &BRUISER_WARLOCK_A, Some(&BRUISER_WARLOCK_B)),
    anim( 9,  39, &ROPE, Some(&ROPE_B)),
    anim(10,  68, &SENTRY, Some(&SENTRY_B)),
    anim(11,  72, &FOLD_STAR, Some(&FOLD_STAR_B)),
    anim(12,  73, &FLUTTERBAT, Some(&FLUTTERBAT_B)),
    anim(13,  74, &GLOAM_LEECH, Some(&GLOAM_LEECH_B)),
    anim(14,  64, &CINDER_MAW_MEDIUM, Some(&CINDER_MAW_MEDIUM_B)),
    anim(15,  76, &RIFT_OOZE, Some(&RIFT_OOZE_B)),
    anim(16,  77, &MIRROR_MOTH, Some(&MIRROR_MOTH_B)),
    anim(17,  78, &MIRE_SPORE, Some(&MIRE_SPORE_B)),
    anim(18,  80, &ECHO_GUARD, Some(&ECHO_GUARD_B)),
    anim(19, 124, &RUNE_LANTERN, Some(&RUNE_LANTERN_B)),
    anim(20, 125, &DREAD_BELL, Some(&DREAD_BELL_B)),
    anim(21,  81, &RIFT_WARDEN, Some(&RIFT_WARDEN_B)),
    anim(22,  69, &PRISM_SKITTER, Some(&PRISM_SKITTER_B)),
    anim(23,  79, &DUSK_MIDGE, Some(&DUSK_MIDGE_B)),
    anim(24,  79, &SUNWHEEL, Some(&SUNWHEEL_B)),
    anim(25,  79, &CINDER_KITE, Some(&CINDER_KITE_B)),
    anim(26,  79, &BOG_TOAD, Some(&BOG_TOAD_B)),
    anim(27,  79, &BRAMBLE_SPRITE, Some(&BRAMBLE_SPRITE_B)),
    anim(28,  79, &FROST_LANCER, Some(&FROST_LANCER_B)),
    anim(29,  79, &VINE_COIL, Some(&VINE_COIL_B)),
    anim(30,  79, &SHARD_CRAB, Some(&SHARD_CRAB_B)),
    anim(31,  79, &VOID_HALO, Some(&VOID_HALO_B)),
    anim(32,  70, &RIFT_CANTOR, Some(&RIFT_CANTOR_B)),
    anim(35, 216, &VEIL_MAGUS, Some(&VEIL_MAGUS_B)),
    anim(36, 217, &HEX_WALKER, Some(&HEX_WALKER_B)),
    anim(37, 212, &VAULT_HAND, Some(&VAULT_HAND_B)),
    anim(38, 208, &BANE_BRUTE, Some(&BANE_BRUTE_B)),
    anim(39, 218, &ZAG_DART, Some(&ZAG_DART_B)),
    anim(40, 219, &LEYBEAM, Some(&LEYBEAM_B)),
    anim(41, 220, &FUSE_HURLER, Some(&FUSE_HURLER_B)),
];

// ---- Emission lists (order matters — matches the Python pipeline) ----

pub const PLAYERS: [(&str, &[&str]); 5] = [
    ("wolfkin", &WOLFKIN),
    ("sauran", &SAURAN),
    ("corvin", &CORVIN),
    ("picsean", &PICSEAN),
    ("vespine", &VESPINE),
];

pub const PLAYERS_WALK_A: [(&str, &[&str]); 5] = [
    ("wolfkin", &WOLFKIN_WALK_A),
    ("sauran", &SAURAN_WALK_A),
    ("corvin", &CORVIN_WALK_A),
    ("picsean", &PICSEAN_WALK_A),
    ("vespine", &VESPINE_WALK_A),
];

pub const PLAYERS_WALK_B: [(&str, &[&str]); 5] = [
    ("wolfkin", &WOLFKIN_WALK_B),
    ("sauran", &SAURAN_WALK_B),
    ("corvin", &CORVIN_WALK_B),
    ("picsean", &PICSEAN_WALK_B),
    ("vespine", &VESPINE_WALK_B),
];

pub const PLAYERS_HURT: [(&str, &[&str]); 5] = [
    ("wolfkin", &WOLFKIN_HURT),
    ("sauran", &SAURAN_HURT),
    ("corvin", &CORVIN_HURT),
    ("picsean", &PICSEAN_HURT),
    ("vespine", &VESPINE_HURT),
];

pub const PLAYERS_CLAIM: [(&str, &[&str]); 5] = [
    ("wolfkin", &WOLFKIN_CLAIM),
    ("sauran", &SAURAN_CLAIM),
    ("corvin", &CORVIN_CLAIM),
    ("picsean", &PICSEAN_CLAIM),
    ("vespine", &VESPINE_CLAIM),
];

pub const PLAYERS_ASCENDED: [(&str, &[&str]); 5] = [
    ("wolfkin", &WOLFKIN_ASCENDED),
    ("sauran", &SAURAN_ASCENDED),
    ("corvin", &CORVIN_ASCENDED),
    ("picsean", &PICSEAN_ASCENDED),
    ("vespine", &VESPINE_ASCENDED),
];

pub const PLAYERS_ASCENDED_STEP: [(&str, &[&str]); 5] = [
    ("wolfkin", &WOLFKIN_ASCENDED_STEP),
    ("sauran", &SAURAN_ASCENDED_STEP),
    ("corvin", &CORVIN_ASCENDED_STEP),
    ("picsean", &PICSEAN_ASCENDED_STEP),
    ("vespine", &VESPINE_ASCENDED_STEP),
];

pub const ENEMIES_8: [(&str, &[&str]); 31] = [
    ("crawler", &CRAWLER),
    ("hornet", &HORNET),
    ("skeleton", &SKELETON),
    ("orc", &ORC),
    ("bomber", &BOMBER),
    ("shade", &SHADE),
    ("warlock", &WARLOCK),
    ("rope", &ROPE),
    ("sentry", &SENTRY),
    ("fold_star", &FOLD_STAR),
    ("flutterbat", &FLUTTERBAT),
    ("gloam_leech", &GLOAM_LEECH),
    ("cinder_maw", &CINDER_MAW),
    ("rift_ooze", &RIFT_OOZE),
    ("mirror_moth", &MIRROR_MOTH),
    ("mire_spore", &MIRE_SPORE),
    ("echo_guard", &ECHO_GUARD),
    ("rune_lantern", &RUNE_LANTERN),
    ("dread_bell", &DREAD_BELL),
    ("rift_warden", &RIFT_WARDEN),
    ("prism_skitter", &PRISM_SKITTER),
    ("dusk_midge", &DUSK_MIDGE),
    ("sunwheel", &SUNWHEEL),
    ("cinder_kite", &CINDER_KITE),
    ("bog_toad", &BOG_TOAD),
    ("bramble_sprite", &BRAMBLE_SPRITE),
    ("frost_lancer", &FROST_LANCER),
    ("vine_coil", &VINE_COIL),
    ("shard_crab", &SHARD_CRAB),
    ("void_halo", &VOID_HALO),
    ("rift_cantor", &RIFT_CANTOR),
];

pub const FX_8: [(&str, &[&str]); 21] = [
    ("bullet_a", &BULLET_A),
    ("bullet_b", &BULLET_B),
    ("beam_head", &BEAM_HEAD),
    ("beam_tail", &BEAM_TAIL),
    ("muzzle", &MUZZLE),
    ("impact", &IMPACT),
    ("wisp", &WISP),
    ("item_orb", &ITEM_ORB),
    ("shop_tag", &SHOP_TAG),
    ("merchant_callout", &MERCHANT_CALLOUT),
    ("surge_orb", &SURGE_ORB),
    ("shield_aura", &SHIELD_AURA),
    ("sword", &SWORD),
    ("flail", &FLAIL),
    ("spike", &SPIKE),
    ("spear", &SPEAR),
    ("water_aura", &WATER_AURA),
    ("villager", &VILLAGER),
    ("merchant", &MERCHANT),
    ("smith", &SMITH),
    ("apothecary", &APOTHECARY),
];

pub const DUNGEON_TILES: [(&str, &[&str]); 15] = [
    ("floor_plain", &BGT_FLOOR_PLAIN),
    ("floor_crack", &BGT_FLOOR_CRACK),
    ("floor_pebble", &BGT_FLOOR_PEBBLE),
    ("wall_brick", &BGT_WALL_BRICK),
    ("door_frame", &BGT_DOOR_FRAME),
    ("door_locked", &BGT_DOOR_LOCKED),
    ("pillar", &BGT_PILLAR),
    ("crystal", &BGT_CRYSTAL),
    ("rubble", &BGT_RUBBLE),
    ("wall_crack", &BGT_WALL_CRACK),
    ("block", &BGT_BLOCK),
    ("spikes", &BGT_SPIKES),
    ("pot", &BGT_POT),
    ("switch", &BGT_SWITCH),
    ("portal", &BGT_PORTAL),
];


// Bruiser tier: heavy enemies rendered at player size (16x16). The C side
// loads these into 4-tile blocks and flags eids 4/6/8 as big16.
pub const BRUISER_SRC: [(&str, &[&str]); 3] = [
    ("orc", &BRUISER_ORC_A),
    ("bomber", &BRUISER_BOMBER_A),
    ("warlock", &BRUISER_WARLOCK_A),
];

// Water ride (Tide Raft and Picsean swim). Reference: GPT Image 2.6
// Sunburst raft/swim candidates (docs/previews/water-ride/), hand-quantized.
// The raft uses OBJ palette 5 (coin): 1 = gold log, 2 = brown seam/hull,
// 3 = cream rope and foam. Frame B lifts the waterline foam and shifts the
// wake so the two-beat bob reads as the raft riding the swell.
pub const WATER_RAFT_A: [&str; 8] = [
    ".2222222222222222222222.",
    ".2112112112112112112112.",
    ".2332332332332332332332.",
    ".2112112112112112112112.",
    ".2112112112112112112112.",
    "322222222222222222222223",
    ".3222222222222222222223.",
    "3..33...3..33...3..33..3",
];

pub const WATER_RAFT_B: [&str; 8] = [
    ".2222222222222222222222.",
    ".2112112112112112112112.",
    ".2332332332332332332332.",
    ".2112112112112112112112.",
    "321121121121121121121123",
    ".2222222222222222222222.",
    "332222222222222222222233",
    ".33..3...33..3...33..33.",
];

// Picsean's swim ring replaces the champion's lower 16x8 strip in the class
// palette (1 = river blue, 2 = deep water, 3 = pale foam). Foam and deep
// water carry the outline because river blue alone vanishes on the water
// tile. The open centre
// lets the water tile show where the legs would be; frame B widens the ring
// and throws foam at its corners like a kick.
pub const WATER_SWIM_A: [&str; 8] = [
    "...3333333333...",
    ".33222111122233.",
    "3322........2233",
    "32............23",
    "32............23",
    "3322........2233",
    ".33222111122233.",
    "...3333333333...",
];

pub const WATER_SWIM_B: [&str; 8] = [
    "3.333333333333.3",
    ".32221111112223.",
    "322..........223",
    "32............23",
    "32............23",
    "322..........223",
    ".32221111112223.",
    "3.333333333333.3",
];
