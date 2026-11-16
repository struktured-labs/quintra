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

/// Stage 2 — Kilnback pack atlas (Cinder Rex lives in bank 1, see below).
///
/// GPT Image 2.6 pass 2 (`gpt-image-2.6-sunburst`), hand-reduced. Carmelo
/// asked for a bigger Ember boss, so each Kilnback is now a 16x16 walking
/// crucible (four sprites) instead of a 16x8 sliver. The 32x32 atlas holds
/// four poses as quadrants: walk A (top-left), walk B (top-right), open vent
/// (bottom-left) and collapsed husk (bottom-right). Pose `k` starts at atlas
/// tile {0,2,8,10}[k]; its four tiles are base, base+1, base+4, base+5.
///
/// Ember's live OBJ palette is not "1 = darkest". Index 1 is the rust brick
/// (`BGR555` 22,9,4), index 2 is the near-black iron (6,2,1), and index 3 is
/// the yellow heat (31,27,10).
fn boss_maw() -> Grid {
    let mut g = blank();
    const WALK_A: [&str; 16] = [
        "................",
        ".....2222.......",
        "....211112......",
        "...22122222.....",
        "..2111111112....",
        ".211111111112...",
        ".222222222222...",
        "21111111111112..",
        ".22222222222222.",
        "2112323333112112",
        "2112323333112232",
        ".221111111122133",
        "2111111111211212",
        "211122222221122.",
        "1112..211121112.",
        "112...2112.2112.",
    ];
    const WALK_B: [&str; 16] = [
        "................",
        "................",
        "................",
        "....2222........",
        "...211112.......",
        "...2222222......",
        "..211111112.....",
        ".21111111122....",
        "2111111111112...",
        "21111111111222..",
        ".21232323212112.",
        ".21232323112332.",
        ".21111111112232.",
        "21121111121122..",
        "11122222221112..",
        "1122112...2112..",
    ];
    const VENT: [&str; 16] = [
        "....22..........",
        ".222112...2.....",
        "2111121222322...",
        "11112222322232..",
        "111123322.232...",
        "1112333332.2....",
        "112.233333232...",
        "1122223333332...",
        "22111133333312..",
        "..2222132313222.",
        ".211232323222112",
        ".211232323212332",
        "..21111111112123",
        ".211211111121122",
        "211122222222112.",
        "21122112....2112",
    ];
    const HUSK: [&str; 16] = [
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "................",
        "........22......",
        ".....2.2332.....",
        "....212231222...",
        "...21112322312..",
        "..2122123321222.",
        ".211123332221112",
        "2222133211121122",
        "1111123211112211",
        "1121123211111111",
    ];

    let mut stamp = |ox: usize, oy: usize, art: &[&str]| {
        for (y, row) in art.iter().enumerate() {
            assert_eq!(row.len(), 16, "kilnback row {y} at {ox},{oy}");
            for (x, pixel) in row.bytes().enumerate() {
                g[oy + y][ox + x] = if pixel == b'.' { 0 } else { pixel - b'0' };
            }
        }
    };
    stamp(0, 0, &WALK_A);
    stamp(16, 0, &WALK_B);
    stamp(0, 16, &VENT);
    stamp(16, 16, &HUSK);
    g
}

fn grid48(art: &[&str]) -> Grid {
    assert_eq!(art.len(), 32);
    art.iter().map(|row| {
        assert_eq!(row.len(), 48);
        row.bytes().map(|p| if p == b'.' { 0 } else { p - b'0' }).collect()
    }).collect()
}

/// Cinder Rex, 48x32 (6x4 sprites), authored facing west: the iron jaw is
/// on the left, the slag-hammer tail curls up on the right. Drawn from
/// VRAM bank 1 OBJ 64..87. Reduced from the same GPT sheet as the pose.
pub fn cinder_rex_big() -> Grid {
    const REX: [&str; 32] = [
        ".........................................222....",
        ".............2222....222................21112...",
        "............233332..23332...........2.2211122...",
        "...........2333332.233332.22.......21212111212..",
        "..........2333333223333322332.....2111112123212.",
        ".........233333332333333333332...2111211123332..",
        "........222112222131122223332222.21122111223332.",
        ".......211111121113111111123233322111221233322..",
        ".....2211111121211331111113123332.211222.2332...",
        ".2222111111221123333311133221222.221111221232...",
        "211111112232221231113133221122.22322212122.2....",
        "21121223333211112111333211112123232..21112......",
        "1111111233211212211131211222212212...211112.....",
        "111111111111121121133311232232111122.21212......",
        "111111111111121121222322333233222111211112......",
        "222222222222112222111211333233212111121112......",
        "232332323321112111111111333233212111112112......",
        "23233232332111221111112133323321222221122.......",
        "2323323233211122122221222222222221311212........",
        ".22222222211112.21311211111111112113112.........",
        "2111111111111122111311211111111121131112........",
        "21111111111222.21113111222222222113331112.......",
        ".22222222122..211333333112....211311333112......",
        ".......2111122111311331112....2131113111112.....",
        "......211111112131113111112.221222223111112.....",
        ".....222221111222222222211221112....22222112....",
        "....21111122112...21111122.211112..21111112.....",
        "...21111111122...211111111211112..2111111112....",
        "...2111111112....211111111211112..2111111112....",
        "..232332321112..2322322221111112.233233232112..2",
        ".2332332332112.2332332332112222..233333333112.23",
        ".232332333222..233332332212.....233233233222..23",
    ];
    grid48(&REX)
}

/// Roar + stride, same box: jaw thrown open with fire in the mouth and the
/// legs in a long reaching step. Bank 1 OBJ 88..111. Runtime picks idle or
/// pose per 16px row band, so the head can roar while the legs plant.
pub fn cinder_rex_big_pose() -> Grid {
    const POSE: [&str; 32] = [
        "................................................",
        "................................................",
        "................................................",
        "...........................................22...",
        "....................222...................2112..",
        "...................23332.222............2.21122.",
        "..................23333223332.........2212111212",
        "......2222...2222233333233332222.....21111112321",
        ".....2111122211111332222223323332...211121122332",
        "....2111121111111121113311122333222.211221233232",
        "...211111123333222211113111113232332211122.2332.",
        "....22222112332121121133311111123332.211122.232.",
        "....233322111111211233113111221222322.222112.2..",
        ".....222.23111112112311133321212122232..2112....",
        ".....222..2221121111311113212222113232..21112...",
        ".22.233322222122112311113311332321232.222122....",
        "233222333333212.22322112132233233221121111112...",
        ".2233333333321121321111122123323311111111112....",
        "..23333333332112321111111212332331122212112.....",
        "..2223333332111212231211112222222221112.22......",
        ".232.22222221112211311211111111111113112........",
        "..2..2323211122.2111311212111111112133112.......",
        ".....23233112.22111333122.22222222133311122.....",
        ".....2111112221311331332.21112..213311331112....",
        "......22222211113331112.2111112..231111121112...",
        "........21111111313222221111112...222312111112..",
        "...2222211121112122..211112112.......2221122222.",
        "..2111112111212.2...211111122..........211111112",
        ".2111111121122.....2212111112...........21111112",
        "232323311222......23323232112............2323232",
        "3333233212........23233332112............2323333",
        "3232232.2.........2323223222.............2323323",
    ];
    grid48(&POSE)
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
    fn kilnbacks_are_square_crucibles_with_a_blown_vent() {
        let g = boss_maw();
        let ink = |x0: usize, y0: usize, color: u8| {
            g[y0..y0 + 16].iter().flat_map(|row| &row[x0..x0 + 16])
                .filter(|&&p| p == color).count()
        };
        // Walk frames are mostly brick and iron; the vent pours heat.
        assert!(ink(0, 16, 3) > ink(0, 0, 3) + 10, "vent shows molten heat");
        assert!(ink(0, 0, 1) > 40 && ink(16, 0, 1) > 40, "walk bodies");
        assert_ne!(g[15][0..16], g[15][16..32], "walk frames move the feet");
        // Every pose is a full 16px-tall body, not the old 16x8 sliver.
        for (x0, y0) in [(0, 0), (16, 0), (0, 16)] {
            assert!(g[y0 + 3..y0 + 6].iter().any(|r| r[x0..x0 + 16].iter().any(|&p| p != 0)),
                "pose at {x0},{y0} has an upper half");
        }
    }

    #[test]
    fn cinder_rex_is_a_48x32_furnace_hound_with_a_roar() {
        let idle = super::cinder_rex_big();
        let pose = super::cinder_rex_big_pose();
        assert_eq!((idle.len(), idle[0].len()), (32, 48));
        let tiles = |g: &Vec<Vec<u8>>| (0..24).filter(|t| {
            let (r, c) = (t / 6, t % 6);
            g[r * 8..r * 8 + 8].iter().any(|row| row[c * 8..c * 8 + 8].iter().any(|&p| p != 0))
        }).count();
        assert!(tiles(&idle) >= 20, "rex fills its 6x4 box");
        let changed = |rows: std::ops::Range<usize>| idle[rows.clone()].iter().flatten()
            .zip(pose[rows].iter().flatten()).filter(|(a, b)| a != b).count();
        assert!(changed(0..16) > 60, "roar changes the head band");
        assert!(changed(16..32) > 60, "stride changes the leg band");
        // Four planted feet in the idle frame.
        let feet = (0..48).filter(|&x| idle[31][x] != 0).count();
        assert!(feet >= 16, "feet reach the floor");
    }
}
