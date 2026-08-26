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

/// Stage 0 — Crystal Colossus: an angular guardian wrapped around a diamond
/// reactor. The former mathematical oval read as a friendly floating face;
/// this authored silhouette has a crown, slab shoulders, split feet, faceted
/// planes, and one unmistakable weak core instead of eyes and a smile.
pub fn make_boss_big() -> Grid {
    let mut g = blank();

    // Three uneven crown crystals. Their bright inner ridges establish a
    // single upper-left light source and keep the top from reading as horns.
    for &(y, l, r) in &[
        (0, 15, 16), (1, 14, 17), (2, 14, 17), (3, 13, 18),
        (3, 5, 7), (4, 4, 8), (5, 3, 9),
        (2, 24, 25), (3, 23, 26), (4, 22, 27), (5, 21, 28),
    ] {
        span(&mut g, y, l, r, 2, 1);
    }

    // Stepped shoulders and a narrowing torso. Long horizontal plate breaks
    // make the 32x32 object feel built from crystal slabs, not inflated.
    let body = [
        (6, 8, 23), (7, 6, 25), (8, 4, 27), (9, 2, 29),
        (10, 0, 31), (11, 1, 30), (12, 2, 29), (13, 3, 28),
        (14, 3, 28), (15, 4, 27), (16, 4, 27), (17, 5, 26),
        (18, 5, 26), (19, 6, 25), (20, 6, 25), (21, 7, 24),
        (22, 7, 24), (23, 8, 23), (24, 8, 23), (25, 9, 22),
        (26, 8, 23), (27, 7, 24), (28, 6, 25), (29, 5, 26),
        (30, 4, 27), (31, 4, 27),
    ];
    for &(y, left, right) in &body {
        span(&mut g, y, left, right, 2, 1);
    }

    // Shoulder shards, plate seams, and transparent fractures break the mass.
    paint(&mut g, 3, &[
        (4, 5), (5, 4), (5, 8), (3, 24), (4, 23),
        (6, 14), (6, 15), (7, 13), (8, 12), (9, 11),
        (9, 4), (10, 3), (11, 2), (9, 27), (10, 28),
        (12, 7), (13, 8), (14, 9), (12, 24), (13, 23), (14, 22),
        (20, 8), (21, 9), (22, 10), (20, 23), (21, 22), (22, 21),
        (27, 8), (28, 7), (29, 6), (27, 23), (28, 24), (29, 25),
    ]);
    paint(&mut g, 1, &[
        (10, 8), (10, 9), (10, 22), (10, 23),
        (18, 6), (18, 7), (18, 24), (18, 25),
        (23, 11), (23, 12), (23, 19), (23, 20),
    ]);
    paint(&mut g, 0, &[
        (11, 5), (12, 5), (12, 6), (15, 25), (16, 24), (16, 25),
        (24, 9), (25, 9), (24, 22), (25, 22),
        (29, 15), (29, 16), (30, 14), (30, 15), (30, 16), (30, 17),
        (31, 13), (31, 14), (31, 15), (31, 16), (31, 17), (31, 18),
    ]);

    // Seven-row diamond reactor: dark armored rim, white-hot centre, and a
    // vertical fault line. It reads as the target even during palette flash.
    for &(y, left, right) in &[
        (12, 15, 16), (13, 14, 17), (14, 13, 18), (15, 12, 19),
        (16, 13, 18), (17, 14, 17), (18, 15, 16),
    ] {
        span(&mut g, y, left, right, 3, 1);
    }
    g[14][15] = 3; g[14][16] = 3;
    g[15][14] = 3; g[15][15] = 0; g[15][16] = 0; g[15][17] = 3;
    g[16][15] = 3; g[16][16] = 3;
    g
}

/// Stage 1 — Serpent atlas: a mobile 32x24 fanged head plus two animated
/// 8x8 body segments hidden in the unused bottom row. Runtime renders the
/// head as a 4x3 metasprite and repeats those segment tiles along the actual
/// route history, so this is one connected creature rather than a coiled
/// picture swapped onto the generic 32x32 Colossus.
fn boss_serpent() -> Grid {
    let mut g = blank();
    // A deliberate front-facing cobra silhouette: the hood swells abruptly,
    // then narrows through the jaw into a forked tongue. This reads much more
    // clearly at native scale than the old mathematical oval.
    let hood_width = [
        12usize, 18, 24, 28, 32, 32, 30, 30, 28, 28, 26, 24,
        22, 20, 18, 16, 14, 12, 10, 8, 6, 4, 4, 2,
    ];
    for (y, width) in hood_width.iter().copied().enumerate() {
        let left = (32 - width) / 2;
        for x in left..left + width {
            g[y][x] = if x == left || x + 1 == left + width { 1 } else { 2 };
        }
    }

    // Nested lightning chevrons turn the hood itself into a storm warning.
    for &(y, x) in &[
        (2, 4), (2, 27), (3, 5), (3, 26), (4, 6), (4, 25),
        (5, 7), (5, 24), (9, 6), (9, 25), (10, 7), (10, 24),
        (11, 8), (11, 23),
    ] { g[y][x] = 3; }
    // Slanted eye sockets, bright pupils, nostrils, jaw, and paired fangs.
    for x in 9..13usize { g[6][x] = 1; }
    for x in 19..23usize { g[6][x] = 1; }
    for &(y, x) in &[
        (7, 9), (7, 10), (7, 21), (7, 22),
        (8, 10), (8, 11), (8, 20), (8, 21),
    ] { g[y][x] = 1; }
    g[8][11] = 3; g[8][20] = 3;
    g[12][13] = 1; g[12][18] = 1;
    for x in 11..21usize { g[14][x] = 1; }
    g[15][12] = 3; g[16][13] = 3;
    g[15][19] = 3; g[16][18] = 3;
    for x in 13..19usize { g[17][x] = 1; }
    // A second inner chevron gives the face depth without spending another
    // animation frame; the eye sockets now sit under a readable brow plate.
    paint(&mut g, 1, &[
        (10, 10), (10, 11), (10, 20), (10, 21),
        (11, 11), (11, 12), (11, 19), (11, 20),
        (13, 14), (13, 17),
    ]);
    paint(&mut g, 3, &[(4, 15), (4, 16), (12, 9), (12, 22)]);
    // Forked tongue pierces the narrowing neck silhouette.
    g[19][15] = 3; g[19][16] = 3;
    g[20][15] = 3; g[20][16] = 3;
    g[21][14] = 3; g[21][17] = 3;
    g[22][13] = 3; g[22][18] = 3;

    // Tiles 12 and 13 are not part of the 4x3 head renderer. They are two
    // electric-scale animation frames for the route-following tail.
    let segment_a = [
        "...11...", "..1331..", ".132231.", "13233231",
        "13233231", ".132231.", "..1331..", "...11...",
    ];
    let segment_b = [
        "1..11..1", ".123321.", "..1331..", "12322321",
        "12322321", "..1331..", ".123321.", "1..11..1",
    ];
    for (y, row) in segment_a.iter().enumerate() {
        for (x, pixel) in row.bytes().enumerate() {
            g[24 + y][x] = if pixel == b'.' { 0 } else { pixel - b'0' };
        }
    }
    for (y, row) in segment_b.iter().enumerate() {
        for (x, pixel) in row.bytes().enumerate() {
            g[24 + y][8 + x] = if pixel == b'.' { 0 } else { pixel - b'0' };
        }
    }
    g
}

/// Stage 2 — Kilnback pack / Cinder Rex atlas.
///
/// The first two tile rows contain four 16x8 pack poses (walk A/B, exposed
/// furnace vent, and burning husk). The lower half is one long 32x16 Cinder
/// Rex. Runtime composes five independent animals from the upper tiles, then
/// unfolds the surviving pack into the lower silhouette. Keeping every
/// Kilnback only two OBJ tiles wide is intentional: five in a phalanx consume
/// exactly the real GBC's ten-sprites-per-scanline limit.
fn boss_maw() -> Grid {
    let mut g = blank();
    const WALK_A: [&str; 8] = [
        "....3..3..33....", // dorsal vents, not a round body
        "...1221221111...",
        "..122222233211..", // one pale eye behind the wedge jaw
        "112223322222211.",
        ".122222222333221",
        "..112211221111..",
        "...11....11.....", // separated piston legs
        "..11......11....",
    ];
    const WALK_B: [&str; 8] = [
        "....3..3..33....",
        "...1221221111...",
        "..122222233211..",
        "112223322222211.",
        ".122222222333221",
        "..112211221111..",
        "..11......11....",
        "....11..11......",
    ];
    const VENT: [&str; 8] = [
        "....3..33333....",
        "...1221333311...",
        "..122223313211..", // open white-hot rear furnace
        "112223333122211.",
        ".122222222333221",
        "..112211221111..",
        "...11....11.....",
        "..11......11....",
    ];
    const HUSK: [&str; 8] = [
        "..3.3..333.3....",
        ".3.1221331313...",
        "..13232331321...",
        "131223331322.13.",
        ".123313233313.31",
        "..11.31.21.11...",
        "...3.....3......",
        "..3.......3.....",
    ];
    const REX: [&str; 16] = [
        "................................",
        "..............3.....3...........",
        "............131...131...........",
        "..........11221112211......33...",
        "........112222222222111..1131...",
        "..1111112222332222222221123211..", // low wedge snout enters before the torso
        "..11132222222222222223322222221.", // single white-hot eye, never a round face
        "11222222222222222222222223322111",
        ".11333122222222222222222222.111.", // tooth-lit lower jaw separates from the ground
        "..1311122112211221122111111.....",
        "......11....11....11....11......",
        ".....131...131...131...131......",
        "....11.1..11.1..11.1..11.1......",
        "...11..1.11..1.11..1.11..1......",
        "..11.....11.....11.....11.......",
        "................................",
    ];

    let mut stamp = |ox: usize, oy: usize, art: &[&str]| {
        for (y, row) in art.iter().enumerate() {
            for (x, pixel) in row.bytes().enumerate() {
                g[oy + y][ox + x] = if pixel == b'.' { 0 } else { pixel - b'0' };
            }
        }
    };
    stamp(0, 0, &WALK_A);
    stamp(16, 0, &WALK_B);
    stamp(0, 8, &VENT);
    stamp(16, 8, &HUSK);
    stamp(0, 16, &REX);
    // Small silhouette polish: a higher broken dorsal ridge and a readable
    // tail hook give the long Rex a beginning and end at native scale. These
    // occupy formerly transparent pixels and do not change its 32x16 budget.
    paint(&mut g, 3, &[
        (16, 13), (16, 18), (17, 10), (17, 21),
        (18, 8), (18, 23), (19, 6), (19, 25),
    ]);
    paint(&mut g, 1, &[
        (20, 4), (19, 3), (18, 2), (17, 1),
        (21, 2), (22, 1), (23, 0),
    ]);
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
        for segment in leg.windows(2) {
            line(&mut g, segment[0], segment[1], 1);
        }
        for (index, &(y, x)) in leg.iter().enumerate() {
            g[y][x] = if index == 2 { 3 } else { 1 };
            if y + 1 < 32 && index > 0 && index < 4 { g[y + 1][x] = 1; }
        }
    }
    ellipse(&mut g, 16.0, 17.0, 7.0, 6.5, 2, 1);
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
    ellipse(&mut g, 16.0, 16.0, 15.0, 11.0, 1, 1);
    ellipse(&mut g, 16.0, 16.0, 10.0, 8.0, 2, 2);
    ellipse(&mut g, 16.0, 16.0, 4.5, 6.0, 3, 1);
    // A dark vertical seed keeps the weak point organic instead of reading as
    // a perfect target icon; the offset glint maintains gaze direction.
    for y in 12..21 { g[y][16] = 1; }
    paint(&mut g, 3, &[(12, 13), (13, 12), (13, 13), (14, 12)]);
    // Uneven capillaries and lashes root the eye into the projected organism.
    paint(&mut g, 3, &[
        (8, 7), (9, 8), (10, 9), (6, 21), (8, 20), (9, 19),
        (19, 7), (20, 8), (21, 9), (22, 22), (21, 21), (20, 20),
    ]);
    paint(&mut g, 1, &[
        (3, 5), (5, 7), (7, 9), (2, 16), (4, 16),
        (4, 27), (6, 25), (8, 23), (24, 8), (27, 6),
        (24, 23), (27, 26), (16, 0), (16, 31),
    ]);
    g
}

/// Stage 5 — Reaper: pointed hood, blade shoulders, and a tattered mantle.
fn boss_reaper() -> Grid {
    let mut g = blank();
    for &(y, left, right) in &[
        (1, 15, 16), (2, 14, 17), (3, 13, 18), (4, 12, 19),
        (5, 10, 21), (6, 8, 23), (7, 6, 25), (8, 4, 27),
        (9, 2, 29), (10, 1, 30), (11, 2, 29), (12, 3, 28),
        (13, 4, 27), (14, 5, 26), (15, 5, 26), (16, 4, 27),
        (17, 3, 28), (18, 2, 29), (19, 2, 29), (20, 3, 28),
        (21, 3, 28), (22, 4, 27), (23, 4, 27), (24, 5, 26),
        (25, 5, 26), (26, 6, 25), (27, 6, 25), (28, 7, 24),
        (29, 7, 24), (30, 8, 23), (31, 8, 23),
    ] { span(&mut g, y, left, right, 1, 2); }
    // Hollow face sits high beneath the overhanging hood.
    ellipse(&mut g, 16.0, 13.5, 6.5, 5.5, 0, 2);
    paint(&mut g, 3, &[(13, 12), (13, 13), (13, 19), (13, 20)]);
    paint(&mut g, 2, &[
        (6, 13), (7, 12), (8, 11), (6, 18), (7, 19), (8, 20),
        (18, 7), (19, 6), (18, 24), (19, 25),
    ]);
    // Cut transparent teeth from the hem and sharpen both shoulder blades.
    paint(&mut g, 0, &[
        (28, 10), (29, 10), (30, 9), (29, 15), (30, 15), (31, 14),
        (28, 21), (29, 21), (30, 22),
    ]);
    paint(&mut g, 3, &[(9, 1), (10, 0), (9, 30), (10, 31)]);
    g
}

/// Stage 6 — Golem: separated limbs, temple crown, and a sun-heart.
fn boss_golem() -> Grid {
    let mut g = blank();
    for y in 3..11 { span(&mut g, y, 9, 22, 2, 1); }
    for y in 10..14 { span(&mut g, y, 4, 27, 2, 1); }
    for y in 14..24 {
        span(&mut g, y, 2, 8, 2, 1);
        span(&mut g, y, 10, 21, 2, 1);
        span(&mut g, y, 23, 29, 2, 1);
    }
    for y in 24..32 {
        span(&mut g, y, 7, 14, 2, 1);
        span(&mut g, y, 17, 24, 2, 1);
    }
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
    g
}

/// Stage 7 — Bloodmoon Hydra: scaled body and three substantial necked heads.
fn boss_hydra() -> Grid {
    let mut g = blank();
    ellipse(&mut g, 16.0, 23.0, 12.0, 8.0, 2, 1);
    for &(root_x, head_x) in &[(10i32, 5i32), (16, 16), (22, 27)] {
        for step in 0..13i32 {
            let x = root_x + (head_x - root_x) * step / 12;
            let y = 22 - step;
            for dx in -1..=1 {
                if (0..32).contains(&(x + dx)) {
                    g[y as usize][(x + dx) as usize] = if dx == 0 { 2 } else { 1 };
                }
            }
        }
        ellipse(&mut g, head_x as f64, 7.0, 4.0, 3.5, 2, 1);
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

/// Stage 8 — Void Lord: the Colossus body overtaken by a many-point crown and
/// a horizontal event-horizon mask. It remains an evolved visual rhyme with
/// stage one without becoming a palette swap of the new crystal reactor.
fn boss_voidlord() -> Grid {
    let mut g = make_boss_big();
    for (cx, height) in [(3usize, 4usize), (8, 7), (15, 9), (22, 7), (28, 4)] {
        for y in 0..height {
            let half = y / 2;
            let left = cx.saturating_sub(half);
            let right = (cx + half).min(31);
            for x in left..=right {
                g[y][x] = if y == 0 || (x == cx && y < 3) { 3 } else { 1 };
            }
        }
    }
    // Erase the diamond target and replace it with a cold horizon slit.
    for y in 12..20 {
        for x in 10..22 { g[y][x] = if y == 15 || y == 16 { 0 } else { 1 }; }
    }
    for x in 8..24 { g[15][x] = 3; }
    for x in 11..21 { g[16][x] = 3; }
    paint(&mut g, 0, &[
        (10, 5), (11, 6), (12, 7), (10, 26), (11, 25), (12, 24),
        (21, 10), (22, 11), (23, 12), (21, 21), (22, 20), (23, 19),
    ]);
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
