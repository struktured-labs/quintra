//! The nine authored 32x32 stage-boss atlases.
//!
//! Curves retain the original f64/truncating raster grammar, while the most
//! silhouette-sensitive bosses use explicit spans and pixel accents. The
//! golden test pins the resulting 2bpp atlas byte-for-byte.

type Grid = Vec<Vec<u8>>;

fn blank() -> Grid {
    vec![vec![0u8; 32]; 32]
}

fn ellipse(g: &mut Grid, cx: f64, cy: f64, rx: f64, ry: f64, fill: u8, rim: u8) {
    for y in 0..32 {
        for x in 0..32 {
            let v = (x as f64 - cx).powi(2) / (rx * rx)
                + (y as f64 - cy).powi(2) / (ry * ry);
            if v <= 1.0 {
                g[y][x] = if v >= 0.80 { rim } else { fill };
            }
        }
    }
}

fn span(g: &mut Grid, y: usize, left: usize, right: usize, fill: u8, rim: u8) {
    for x in left..=right {
        g[y][x] = if x == left || x == right { rim } else { fill };
    }
}

fn paint(g: &mut Grid, value: u8, pts: &[(usize, usize)]) {
    for &(y, x) in pts {
        g[y][x] = value;
    }
}

fn line(g: &mut Grid, from: (usize, usize), to: (usize, usize), value: u8) {
    let (mut y, mut x) = (from.0 as i32, from.1 as i32);
    let (end_y, end_x) = (to.0 as i32, to.1 as i32);
    let dx = (end_x - x).abs();
    let sx = if x < end_x { 1 } else { -1 };
    let dy = -(end_y - y).abs();
    let sy = if y < end_y { 1 } else { -1 };
    let mut error = dx + dy;
    loop {
        g[y as usize][x as usize] = value;
        if x == end_x && y == end_y { break; }
        let twice = error * 2;
        if twice >= dy { error += dy; x += sx; }
        if twice <= dx { error += dx; y += sy; }
    }
}

/// Stage 0 — crowned crystal bruiser with a readable face and heavy fists.
pub fn make_boss_big() -> Grid {
    crate::large_bosses::crystal()
}

/// Stage 1 — Serpent atlas: a mobile 32x24 fanged head plus two animated
/// 8x8 body segments hidden in the unused bottom row. Runtime renders the
/// head as a 4x3 metasprite; the route-following tail is the BG plate set in
/// `src/render/serpent_body.c`.
///
/// GPT Image 2.6 pass: hand-reduced from a `gpt-image-2.6-sunburst` storm
/// cobra. Verdant boss OBJ indices: 1 violet rim, 2 magenta hood, 3 yellow
/// lightning. Lightning bolts run down both flares, an arrow crest tops the
/// hood, and the slanted eyes sit under a heavy brow.
fn stamp(g: &mut Grid, ox: usize, oy: usize, art: &[&str]) {
    for (y, row) in art.iter().enumerate() {
        for (x, pixel) in row.bytes().enumerate() {
            g[oy + y][ox + x] = if pixel == b'.' { 0 } else { pixel - b'0' };
        }
    }
}

const SERPENT_HEAD: [&str; 24] = [
    "..............1111..............",
    ".........11121333312111.........",
    ".......122222333333222221.......",
    "...11112223222333322232221111...",
    ".113321222233223322332222123311.",
    "12233321222223233232222212333221",
    "12223332111122333322111123332221",
    "12222333122211233211222133322221",
    "12333333312222222222221333333321",
    "11233311111112222221111111333211",
    ".122333133311222222113331333221.",
    "..1223331133122222213311333221..",
    "...12233311122222222111333221...",
    "....122231222222222222132221....",
    ".....1222312212222122132221.....",
    ".......122112222222211221.......",
    "........1211111111111121........",
    "..........122222222221..........",
    "...........1222222221...........",
    "............12211221............",
    ".............113311.............",
    "...............33...............",
    "..............3..3..............",
    ".............3....3.............",
];

const SERPENT_JAW: [&str; 24] = [
    "..............1111..............",
    ".........11121333312111.........",
    ".......122222333333222221.......",
    "...11112223222333322232221111...",
    ".113321222233223322332222123311.",
    "12233321222223233232222212333221",
    "12223332111122333322111123332221",
    "12222333122211233211222133322221",
    "12333333312222222222221333333321",
    "11233311111112222221111111333211",
    ".122333133311222222113331333221.",
    "..1223331133122222213311333221..",
    "...12233311122222222111333221...",
    "....122231122222222221132221....",
    ".....1221111111111111111221.....",
    "......12211311111111311221......",
    ".......121131111111131121.......",
    "........1213111111113121........",
    ".........12111111111121.........",
    "..........121111111121..........",
    "...........1221331221...........",
    "............12333321............",
    ".............123321.............",
    "..............1331..............",
];

fn serpent_tail_frames(g: &mut Grid) {
    // Tiles 12 and 13 are not part of the 4x3 head renderer. They are two
    // electric-scale animation frames kept for the atlas contract.
    let segment_a = [
        "...11...", "..1331..", ".132231.", "13233231",
        "13233231", ".132231.", "..1331..", "...11...",
    ];
    let segment_b = [
        "1..11..1", ".123321.", "..1331..", "12322321",
        "12322321", "..1331..", ".123321.", "1..11..1",
    ];
    stamp(g, 0, 24, &segment_a);
    stamp(g, 8, 24, &segment_b);
}

fn boss_serpent() -> Grid {
    let mut g = blank();
    stamp(&mut g, 0, 0, &SERPENT_HEAD);
    serpent_tail_frames(&mut g);
    g
}

/// The same hood with the jaws gaping: two long fangs over a dark throat.
/// Rows 24..31 stay the tail frames.
pub fn serpent_jaw() -> Grid {
    let mut g = blank();
    stamp(&mut g, 0, 0, &SERPENT_JAW);
    serpent_tail_frames(&mut g);
    g
}

/// Stage 2 — Kilnback pack / Cinder Rex atlas.
///
/// GPT Image 2.6 pass: hand-reduced from a `gpt-image-2.6-sunburst` sheet.
/// Kilnbacks are walking crucibles with a dark iron grate (heat shows only
/// when the vent blows its lid); Rex is an iron-jawed furnace hound with
/// dorsal heat spikes, a barred furnace grate on the flank and a slag-hammer
/// tail.
///
/// The first two tile rows contain four 16x8 crucible poses (closed walk A/B,
/// open vent, collapsed husk). The lower half is one native 32x16 furnace
/// hound. Runtime draws that grid 1:1: four columns, no duplicated tile.
/// Five Kilnbacks in a phalanx are still exactly ten sprites on one scanline.
///
/// Ember's live OBJ palette is not "1 = darkest". Index 1 is the rust brick
/// (`BGR555` 22,9,4), index 2 is the near-black iron (6,2,1), and index 3 is
/// the yellow heat (31,27,10). The strings below use those hardware indices:
/// brick volume is 1, iron rims and stompers are 2, magma is 3.
fn boss_maw() -> Grid {
    let mut g = blank();
    const WALK_A: [&str; 8] = [
        ".....2112.......",
        "...2211112......",
        "..211111111122..",
        ".22222222222222.",
        ".212121212122222",
        ".211111111112332",
        "..2112...2112.2.",
        "..222....222....",
    ];
    const WALK_B: [&str; 8] = [
        ".....2112.......",
        "...2211112......",
        "..211111111122..",
        ".22222222222222.",
        ".212121212122222",
        ".211111111112332",
        "...2112...2112..",
        "....222....222..",
    ];
    const VENT: [&str; 8] = [
        "..2112..3.33.3..",
        ".21112.3333333..",
        "..22.333333333..",
        ".22223333333222.",
        ".213333333122222",
        ".211111111112332",
        "..2112...2112.2.",
        "..222....222....",
    ];
    const HUSK: [&str; 8] = [
        "................",
        "................",
        "................",
        "......3.........",
        "...22.232.22....",
        "..21123312112...",
        ".2111132311112..",
        ".22222222222222.",
    ];
    // Authored facing west: column 0 is the jaw, column 3 is the slag hammer.
    // East travel sets S_FLIPX. Nothing here is stamped twice.
    const REX: [&str; 16] = [
        "...........3...3...3......22222.",
        "..2222222.232.232.232....2333332",
        ".211111112211111111112...2323232",
        "21122111112111111111112..2333332",
        "2113321111111132222111122.22222.",
        "2113311111113123333211112.212...",
        "23333332111131232323211121112...",
        "23232322111311123232111111122...",
        "2111111211311122222213111112....",
        ".2222222111112111111131112......",
        "........21111111111111112.......",
        ".......2111211211121112112......",
        "......21112.2112..2112.2112.....",
        "......2112..2112..2112..2112....",
        ".....23332..23332.23332..23332..",
        ".....22222..22222.22222..22222..",
    ];

    let mut stamp = |ox: usize, oy: usize, art: &[&str], width: usize| {
        for (y, row) in art.iter().enumerate() {
            assert_eq!(row.len(), width, "cinder row {y} at {ox},{oy}");
            for (x, pixel) in row.bytes().enumerate() {
                g[oy + y][ox + x] = if pixel == b'.' { 0 } else { pixel - b'0' };
            }
        }
    };
    stamp(0, 0, &WALK_A, 16);
    stamp(16, 0, &WALK_B, 16);
    stamp(0, 8, &VENT, 16);
    stamp(16, 8, &HUSK, 16);
    stamp(0, 16, &REX, 32);
    g
}

/// Head row is the roar, leg row is the stride. Drawn with S_BANK per row
/// from VRAM bank 1, so the idle atlas in bank 0 stays put.
pub fn cinder_rex_pose() -> Grid {
    const POSE: [&str; 16] = [
        ".2222......3...3...3......22222.",
        "211112....232.232.232....2333332",
        "2113311..2211111111112...2323232",
        "21111111212111111111112..2333332",
        "22222222.1111132222111122.22222.",
        "3333.....1113123333211112.212...",
        "33333....11131232323211121112...",
        "333.2321.11311123232111111122...",
        "2111111211311122222213111112....",
        ".2222222111112111111131112......",
        "........21111111111111112.......",
        "......211112.21111112.21112.....",
        "....211122...2112...2111112.....",
        "..21112.....2112.......21112....",
        ".23332.....23332........23332...",
        ".22222.....22222........22222...",
    ];
    let mut g = vec![vec![0u8; 32]; 16];
    for (y, row) in POSE.iter().enumerate() {
        assert_eq!(row.len(), 32);
        for (x, pixel) in row.bytes().enumerate() {
            g[y][x] = if pixel == b'.' { 0 } else { pixel - b'0' };
        }
    }
    g
}

/// Stage 3 — Frost Spider: plated abdomen and eight jointed ice legs.
fn boss_spider() -> Grid {
    let mut g = blank();
    // Bent two-pixel limbs remain legible against Frost Vault's web tiles.
    const LEGS: [[(usize, usize); 5]; 8] = [
        [(13, 10), (10, 7), (7, 5), (5, 2), (6, 0)],
        [(16, 9), (15, 6), (14, 3), (12, 1), (11, 0)],
        [(20, 9), (21, 6), (23, 3), (25, 1), (27, 0)],
        [(23, 11), (25, 8), (28, 6), (30, 3), (31, 1)],
        [(13, 22), (10, 25), (7, 27), (5, 30), (6, 31)],
        [(16, 23), (15, 26), (14, 29), (12, 30), (11, 31)],
        [(20, 23), (21, 26), (23, 29), (25, 30), (27, 31)],
        [(23, 21), (25, 24), (28, 26), (30, 29), (31, 30)],
    ];
    for leg in LEGS {
        for (index, segment) in leg.windows(2).enumerate() {
            line(&mut g, (segment[0].0.saturating_add(1).min(31),segment[0].1),
                (segment[1].0.saturating_add(1).min(31),segment[1].1),1);
            line(&mut g, segment[0], segment[1], if index == 1 || index == 2 { 3 } else { 2 });
        }
        for (index, &(y, x)) in leg.iter().enumerate() {
            g[y][x] = if index == 2 { 3 } else { 2 };
            if y + 1 < 32 && index > 0 && index < 4 { g[y + 1][x] = 2; }
        }
    }
    ellipse(&mut g, 16.0, 17.0, 8.0, 8.0, 2, 1);
    for y in 11..18 {
        for x in 11..15 { g[y][x] = 3; }
        for x in 19..22 { g[y][x] = 1; }
    }
    // Frost-star carapace, four pin eyes, and dark mandible split.
    paint(&mut g, 3, &[
        (10, 16), (11, 14), (11, 16), (11, 18),
        (12, 13), (12, 15), (12, 17), (12, 19),
        (13, 14), (13, 16), (13, 18), (14, 16),
        (15, 13), (15, 15), (15, 17), (15, 19),
    ]);
    paint(&mut g, 1, &[
        (19, 13), (19, 14), (19, 17), (19, 18),
        (20, 14), (20, 17), (21, 15), (21, 16),
    ]);
    paint(&mut g, 0, &[(22, 15), (22, 16), (23, 14), (23, 17)]);
    g
}

/// Stage 4 — Mire Heart: an asymmetric iris with rootlike vessels.
fn boss_eye() -> Grid {
    let mut g = blank();
    const ROOTS: [[(usize,usize);4];4] = [
        [(14,6),(10,3),(4,3),(2,6)],
        [(13,24),(8,28),(3,27),(1,24)],
        [(20,7),(24,3),(29,4),(30,9)],
        [(21,24),(24,29),(29,28),(30,23)],
    ];
    for root in ROOTS {
        for segment in root.windows(2) {
            line(&mut g,segment[0],segment[1],1);
            line(&mut g,(segment[0].0,segment[0].1+1),
                (segment[1].0,segment[1].1+1),2);
        }
        let (y,x) = root[3];
        g[y][x] = 3;
        g[y][x+1] = 3;
    }
    ellipse(&mut g,15.5,15.5,11.5,9.5,2,1);
    ellipse(&mut g,15.5,15.5,9.5,7.5,3,1);
    ellipse(&mut g,16.5,15.5,3.5,5.5,1,2);
    paint(&mut g,3,&[(12,15),(12,16),(13,15),(13,16)]);
    paint(&mut g,2,&[(8,11),(9,12),(9,13),(10,14),(10,15),
                    (8,21),(9,20),(9,19),(10,18)]);
    for y in 25..29 {
        g[y][12] = 2;
        g[y][19] = 1;
    }
    g
}

/// Stage 5 — Reaper: pointed hood, a crescent scythe, and a tattered mantle.
fn boss_reaper() -> Grid {
    reaper_pose(0)
}

fn reaper_haft(g: &mut Grid, y0: usize, x0: usize, y1: usize, x1: usize) {
    line(g, (y0, x0), (y1, x1), 3);
    line(g, (y0, x0 + 1), (y1, x1 + 1), 1);
}

fn reaper_crescent(g: &mut Grid, rows: &[(usize, usize, usize)]) {
    for &(y, left, right) in rows {
        for x in left..=right { g[y][x] = 3; }
    }
}

/// Pose 0 rests the scythe on the shoulder. Pose 1 lifts the crescent.
/// Pose 2 reaches it out on the link. The cloak underneath is shared.
pub fn reaper_pose(pose: u8) -> Grid {
    let mut g = blank();
    for y in 1..14 {
        let width = (y + 1).min(8);
        span(&mut g, y, 15-width, 16+width, 1, 2);
    }
    for y in 13..30 {
        let width = 7 + (y-13)/4;
        span(&mut g, y, 15-width, 16+width, 1, 2);
        for x in 11..15 { g[y][x] = 2; }
    }
    for &(x, end) in &[(6, 29), (10, 31), (17, 30), (23, 31)] {
        for y in 27..=end { span(&mut g, y, x, x+2, 2, 1); }
    }
    ellipse(&mut g, 15.5, 8.0, 5.5, 4.5, 3, 2);
    for y in 7..9 {
        span(&mut g, y, 12, 13, 1, 1);
        span(&mut g, y, 18, 19, 1, 1);
    }
    paint(&mut g, 1, &[(10,15),(10,16),(12,14),(12,17)]);
    match pose {
        1 => {
            reaper_haft(&mut g, 4, 22, 20, 22);
            reaper_crescent(&mut g, &[
                (1, 10, 22), (2, 9, 12), (2, 20, 23), (3, 10, 11), (3, 21, 22), (4, 11, 18),
            ]);
        }
        2 => {
            reaper_haft(&mut g, 16, 4, 16, 12);
            reaper_haft(&mut g, 15, 18, 15, 26);
            reaper_crescent(&mut g, &[
                (11, 26, 31), (12, 25, 27), (12, 30, 31), (13, 26, 26), (13, 31, 31), (14, 28, 31),
            ]);
            for x in 6..11 { g[17][x] = 3; }
        }
        _ => {
            // Haft stays on the cloak's right edge so the blade does not
            // cross the eyes.
            reaper_haft(&mut g, 6, 26, 24, 26);
            reaper_crescent(&mut g, &[
                (2, 20, 30), (3, 19, 22), (3, 28, 31), (4, 20, 21), (4, 29, 30),
            ]);
        }
    }
    g
}

/// Stage 6 — Golem: separated limbs, temple crown, and a sun-heart.
fn boss_golem() -> Grid { golem_pose(false) }

/// Raised arms, a halo over the crown, and a lifted foot.
pub fn golem_halo() -> Grid { golem_pose(true) }

fn golem_pose(halo: bool) -> Grid {
    let mut g = blank();
    for y in 3..11 { span(&mut g, y, 9, 22, 2, 1); }
    for y in 10..14 { span(&mut g, y, 0, 31, 2, 1); }
    for y in 14..25 {
        span(&mut g, y, 0, 8, 2, 1);
        span(&mut g, y, 10, 21, 2, 1);
        span(&mut g, y, 23, 31, 2, 1);
    }
    for y in 24..32 {
        span(&mut g, y, 6, 14, 2, 1);
        span(&mut g, y, 17, 25, 2, 1);
    }
    for y in 11..14 {
        for x in 1..8 { g[y][x] = 3; }
        for x in 24..30 { g[y][x] = 3; }
    }
    for y in 14..23 {
        for x in 1..4 { g[y][x] = 3; }
        for x in 28..31 { g[y][x] = 1; }
    }
    for y in 25..30 {
        for x in 7..10 { g[y][x] = 3; }
        for x in 23..25 { g[y][x] = 1; }
    }
    for x in 11..21 { g[4][x] = 3; }
    for x in 12..20 { g[8][x] = 1; }
    for y in 15..22 { g[y][11] = 1; g[y][20] = 1; }
    for x in 1..8 { g[21][x] = 1; }
    for x in 24..31 { g[21][x] = 1; }
    // Crown blocks, masonry seams, inset eyes, and a diamond sun-heart.
    paint(&mut g, 3, &[
        (1, 11), (1, 20), (2, 10), (2, 11), (2, 20), (2, 21),
        (6, 12), (6, 19), (7, 12), (7, 19),
        (16, 15), (16, 16), (17, 14), (17, 15), (17, 16), (17, 17),
        (18, 13), (18, 14), (18, 15), (18, 16), (18, 17), (18, 18),
        (19, 14), (19, 15), (19, 16), (19, 17), (20, 15), (20, 16),
    ]);
    paint(&mut g, 1, &[
        (5, 15), (5, 16), (9, 11), (9, 20),
        (12, 8), (12, 15), (12, 16), (12, 23),
        (17, 5), (17, 25), (22, 4), (22, 7), (22, 12), (22, 19), (22, 24), (22, 27),
        (27, 10), (27, 21),
    ]);
    if halo {
        for y in 10..25 {
            for x in 0..9 { g[y][x] = 0; }
            for x in 23..32 { g[y][x] = 0; }
        }
        for y in 30..32 { for x in 6..15 { g[y][x] = 0; } }
        for x in 7..25 { g[0][x] = if x == 7 || x == 24 { 1 } else { 3 }; }
        for x in 10..22 { g[1][x] = 3; }
        for y in 4..16 {
            span(&mut g, y, 0, 7, 2, 1);
            span(&mut g, y, 24, 31, 2, 1);
        }
        for y in 4..8 {
            for x in 1..4 { g[y][x] = 3; }
            for x in 28..31 { g[y][x] = 1; }
        }
        paint(&mut g, 3, &[
            (15, 14), (15, 17), (21, 14), (21, 17),
            (17, 12), (17, 19), (19, 12), (19, 19),
        ]);
    }
    g
}

/// Stage 7 — Bloodmoon Hydra: scaled body and three substantial necked heads.
fn boss_hydra() -> Grid {
    let mut g = blank();
    ellipse(&mut g, 16.0, 23.0, 12.0, 8.0, 2, 1);
    for y in 19..28 {
        for x in 8..17 {
            if g[y][x] == 2 { g[y][x] = 3; }
        }
    }
    for &(root_x, head_x) in &[(10i32, 5i32), (16, 16), (22, 27)] {
        for step in 0..13i32 {
            let x = root_x + (head_x - root_x) * step / 12;
            let y = 22 - step;
            for dx in -2..=2 {
                if (0..32).contains(&(x + dx)) {
                    g[y as usize][(x + dx) as usize] = match dx {
                        -1 => 3, 0 | 1 => 2, _ => 1,
                    };
                }
            }
        }
        ellipse(&mut g, head_x as f64, 7.0, 4.0, 3.5, 2, 1);
        for y in 5..8 {
            for x in (head_x - 2)..=(head_x + 1) {
                g[y][x as usize] = 3;
            }
        }
        for x in (head_x - 2)..=(head_x + 2) {
            g[8][x as usize] = 1;
        }
        g[9][(head_x - 1) as usize] = 3;
        g[9][(head_x + 1) as usize] = 3;
        if head_x < 16 {
            paint(&mut g, 1, &[(3, 2), (2, 1), (4, 8), (3, 9)]);
            paint(&mut g, 3, &[(6, 4)]);
        } else if head_x == 16 {
            paint(&mut g, 1, &[(3, 13), (1, 12), (3, 19), (1, 20)]);
            paint(&mut g, 3, &[(6, 15), (6, 16)]);
        } else {
            paint(&mut g, 1, &[(4, 23), (3, 22), (3, 30), (2, 31)]);
            paint(&mut g, 3, &[(6, 28)]);
        }
    }
    // Belly keel and alternating moon scales stop the lower mass feeling flat.
    paint(&mut g, 3, &[
        (18, 11), (18, 16), (18, 21), (21, 8), (21, 13), (21, 18), (21, 23),
        (24, 10), (24, 15), (24, 20), (27, 13), (27, 18),
    ]);
    paint(&mut g, 0, &[(29, 15), (29, 16), (30, 14), (30, 17), (31, 13), (31, 18)]);
    g
}

/// Stage 8 — Void Lord: a crowned hollow mantle and event-horizon mask.
fn boss_voidlord() -> Grid { void_pose(false) }

/// Crown flared and mantle pulled in. Shown before the existing blink,
/// which stays four ticks.
pub fn void_blink() -> Grid { void_pose(true) }

fn void_pose(blink: bool) -> Grid {
    let mut g = blank();
    for y in 7..13 {
        span(&mut g, y, 10, 21, 2, 1);
    }
    for y in 11..24 {
        let inset = (y - 11) / 3;
        span(&mut g, y, inset, 10, 2, 1);
        span(&mut g, y, 21, 31-inset, 2, 1);
    }
    for y in 12..18 {
        for x in 2..8 { g[y][x] = 3; }
        for x in 24..30 { g[y][x] = 3; }
    }
    for y in 23..32 {
        let taper = (y - 23) / 3;
        span(&mut g, y, 5+taper, 11, 2, 1);
        span(&mut g, y, 20, 26-taper, 2, 1);
        g[y][9] = 3;
        g[y][22] = 3;
    }
    for (cx, height) in [(3usize, 4usize), (8, 7), (15, 9), (22, 7), (28, 4)] {
        for y in 0..height {
            let half = y / 2;
            let left = cx.saturating_sub(half);
            let right = (cx + half).min(31);
            for x in left..=right {
                g[y][x] = if x == cx { 3 } else if x < cx { 2 } else { 1 };
            }
        }
    }
    for y in 12..20 {
        for x in 10..22 { g[y][x] = if y == 15 || y == 16 { 0 } else { 1 }; }
    }
    for x in 8..24 { g[15][x] = 3; }
    for x in 11..21 { g[16][x] = 3; }
    paint(&mut g, 0, &[
        (10, 5), (11, 6), (12, 7), (10, 26), (11, 25), (12, 24),
        (21, 10), (22, 11), (23, 12), (21, 21), (22, 20), (23, 19),
    ]);
    if blink {
        for y in 11..24 {
            for x in 0..5 { g[y][x] = 0; }
            for x in 27..32 { g[y][x] = 0; }
        }
        for x in 11..21 { g[0][x] = 3; g[1][x] = if x > 13 && x < 18 { 3 } else { 2 }; }
        for x in 6..26 { g[15][x] = 3; }
        for x in 9..23 { g[14][x] = 3; }
    }
    g
}

/// All nine, in stage order.
pub fn boss_stages() -> Vec<Grid> {
    vec![
        make_boss_big(), // 0 Colossus
        boss_serpent(),  // 1
        boss_maw(),      // 2
        boss_spider(),   // 3
        boss_eye(),      // 4
        boss_reaper(),   // 5
        boss_golem(),    // 6
        boss_hydra(),    // 7
        boss_voidlord(), // 8 final
    ]
}

#[cfg(test)]
mod tests {
    use super::boss_maw;

    #[test]
    fn cinder_rex_is_a_native_four_column_furnace_hound() {
        let g = boss_maw();
        let ink = |rows: std::ops::Range<usize>, x0: usize, x1: usize, color: u8| {
            g[rows].iter().flat_map(|row| &row[x0..x1]).filter(|&&p| p == color).count()
        };
        // Closed armor has no magma speckles. The vent is a solid cauldron.
        assert_eq!(ink(0..6, 0, 16, 3), 2, "walk eye slit only");
        assert!(ink(8..12, 0, 16, 3) > 20, "vent cauldron");
        assert!(g[8][16..32].iter().all(|&p| p == 0) && g[9][16..32].iter().all(|&p| p == 0),
            "husk roof collapsed");
        assert!(g[14][16..32].iter().any(|&p| p != 0), "husk rests on the floor");
        // One eye, two pillar legs, four distinct columns. No stretched twin.
        assert_eq!(&g[20][3..5], &[3, 3]);
        assert_eq!(&g[21][3..5], &[3, 3]);
        let cols: Vec<Vec<u8>> = (0..4).map(|c| {
            (16..32).flat_map(|y| g[y][c * 8..c * 8 + 8].to_vec()).collect()
        }).collect();
        for i in 0..4 {
            for j in i + 1..4 {
                assert_ne!(cols[i], cols[j], "rex columns {i} and {j} match");
            }
        }
        let planted = (27..32).filter(|y| {
            g[*y][11..16].iter().any(|&p| p != 0) && g[*y][21..26].iter().any(|&p| p != 0)
        }).count();
        assert!(planted >= 4, "both pillar legs reach the floor");
    }

    #[test]
    fn cinder_rex_roar_opens_the_jaw_and_the_stride_reaches() {
        let idle = boss_maw();
        let pose = super::cinder_rex_pose();
        let changed = |rows: std::ops::Range<usize>| {
            idle[rows.start + 16..rows.end + 16].iter().flatten()
                .zip(pose[rows].iter().flatten())
                .filter(|(a, b)| a != b).count()
        };
        assert!(changed(0..8) > 20, "roar matches the closed jaw");
        assert!(changed(8..16) > 20, "stride matches the planted legs");
        assert!(pose[6][..6].contains(&3), "jaw did not open");
        assert_ne!(pose[15][4], 0, "stride has no trailing foot");
        assert_eq!(pose[15][8], 0, "planted foot is still under the body");
    }
}
