//! The nine parametric 32x32 stage bosses.
//!
//! Ported 1:1 from scripts/sprite_authoring.py. All math is f64 with
//! truncating casts, matching Python's float + int() semantics exactly —
//! the golden test pins byte-identical output, so keep every constant
//! and comparison as-authored (including the quirks).

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

fn eyes(g: &mut Grid, pts: &[(i32, i32)]) {
    for &(ey, ex) in pts {
        for yy in (ey - 1)..=(ey + 1) {
            for xx in (ex - 1)..=(ex + 1) {
                if (0..32).contains(&yy) && (0..32).contains(&xx) {
                    g[yy as usize][xx as usize] = 3;
                }
            }
        }
    }
}

/// Stage 0 + the Void Lord base — the Colossus: ovoid body, horns,
/// glowing eyes and a jagged maw.
pub fn make_boss_big() -> Grid {
    let mut g = blank();
    let cx = 15.5f64;
    for y in 0..32usize {
        for x in 0..32usize {
            let dx = (x as f64 - cx).abs();
            let body = (x as f64 - cx).powi(2) / (13.0f64 * 13.0)
                + (y as f64 - 17.0).powi(2) / (13.0f64 * 13.0);
            if body <= 1.0 {
                g[y][x] = 2;
                if body >= 0.82 {
                    g[y][x] = 1;
                }
            }
            if y < 8 && (dx - (7 - y) as f64).abs() < 1.2 {
                g[y][x] = 1;
            }
            if y < 6 && (dx - (7 - y) as f64).abs() < 0.6 {
                g[y][x] = 3;
            }
        }
    }
    // Two glowing eyes (only over existing body pixels)
    for (ey, ex) in [(14i32, 10i32), (14, 21)] {
        for yy in (ey - 1)..=(ey + 1) {
            for xx in (ex - 1)..=(ex + 1) {
                if (0..32).contains(&yy)
                    && (0..32).contains(&xx)
                    && g[yy as usize][xx as usize] != 0
                {
                    g[yy as usize][xx as usize] = 3;
                }
            }
        }
    }
    // Glowing jagged maw
    for xx in 10..22usize {
        let yy = 21 + (xx % 2);
        if g[yy][xx] != 0 {
            g[yy][xx] = 3;
        }
        if g[yy + 1][xx] != 0 {
            g[yy + 1][xx] = 3;
        }
    }
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
    g
}

/// Stage 3 — Frost Spider: round body + 8 radial legs.
fn boss_spider() -> Grid {
    let mut g = blank();
    ellipse(&mut g, 16.0, 17.0, 9.0, 8.0, 2, 1);
    for k in 0..8 {
        let a = (k as f64 / 8.0) * 2.0 * std::f64::consts::PI;
        for step in 4..15 {
            let x = (16.0 + step as f64 * a.cos()) as i32;
            let y = (17.0 + step as f64 * a.sin()) as i32;
            if (0..32).contains(&y) && (0..32).contains(&x) {
                g[y as usize][x as usize] = 1;
            }
        }
    }
    eyes(&mut g, &[(14, 13), (14, 19), (16, 16)]);
    g
}

/// Stage 4 — Great Eye: giant eyeball, iris, pupil, lashes.
fn boss_eye() -> Grid {
    let mut g = blank();
    ellipse(&mut g, 16.0, 16.0, 15.0, 11.0, 1, 1);
    ellipse(&mut g, 16.0, 16.0, 10.0, 8.0, 2, 2);
    ellipse(&mut g, 16.0, 16.0, 4.0, 4.0, 3, 3);
    for k in 0..16 {
        let a = (k as f64 / 16.0) * 2.0 * std::f64::consts::PI;
        let x2 = (16.0 + 18.0 * a.cos()) as i32;
        let y2 = (16.0 + 14.0 * a.sin()) as i32;
        if (0..32).contains(&y2) && (0..32).contains(&x2) {
            g[y2 as usize][x2 as usize] = 1;
        }
    }
    g
}

/// Stage 5 — Reaper: hooded skull with a dark face cavity.
fn boss_reaper() -> Grid {
    let mut g = blank();
    ellipse(&mut g, 16.0, 14.0, 13.0, 12.0, 2, 1);
    for y in 20..32usize {
        let w = 13 - (y as i32 - 20);
        for x in (16 - w)..(16 + w) {
            if (0..32).contains(&x) {
                g[y][x as usize] = if x == 16 - w || x == 16 + w - 1 { 2 } else { 1 };
            }
        }
    }
    ellipse(&mut g, 16.0, 15.0, 6.0, 6.0, 0, 2);
    eyes(&mut g, &[(14, 13), (14, 19)]);
    g
}

/// Stage 6 — Golem: blocky armored torso with brick seams + core gem.
fn boss_golem() -> Grid {
    let mut g = blank();
    for y in 4..28usize {
        for x in 5..27usize {
            let edge = x < 7 || x > 24 || y < 6 || y > 25;
            let seam = (x - 5) % 6 == 0 || (y - 4) % 5 == 0;
            g[y][x] = if edge || seam { 1 } else { 2 };
        }
    }
    eyes(&mut g, &[(11, 12), (11, 20)]);
    for yy in 17..20usize {
        for xx in 15..18usize {
            g[yy][xx] = 3;
        }
    }
    g
}

/// Stage 7 — Bloodmoon Hydra: body + three necked heads.
fn boss_hydra() -> Grid {
    let mut g = blank();
    ellipse(&mut g, 16.0, 22.0, 11.0, 8.0, 2, 1);
    for (nx, ex) in [(-8i32, 6i32), (0, 16), (8, 26)] {
        for step in 0..16 {
            let x = (16.0 + nx as f64 * (step as f64 / 16.0)) as i32;
            let y = 22 - step;
            if (0..32).contains(&y) && (0..32).contains(&x) {
                g[y as usize][x as usize] = 1;
                if x + 1 < 32 {
                    g[y as usize][(x + 1) as usize] = 2;
                }
            }
        }
        let hx = 16 + nx;
        eyes(&mut g, &[(5, ex)]);
        for dy in -2i32..=2 {
            for dx in -2i32..=2 {
                let (yy, xx) = (6 + dy, hx + dx);
                if (0..32).contains(&yy)
                    && (0..32).contains(&xx)
                    && dx * dx + dy * dy <= 5
                    && g[yy as usize][xx as usize] == 0
                {
                    g[yy as usize][xx as usize] = 1;
                }
            }
        }
    }
    g
}

/// Stage 8 — Void Lord (final): the Colossus + spiked crown.
fn boss_voidlord() -> Grid {
    let mut g = make_boss_big();
    // Four widening crown spikes. The old modulo condition never matched
    // its step sequence, leaving the final boss byte-identical to stage 0.
    for (cx, height) in [(6usize, 4usize), (12, 6), (19, 6), (25, 4)] {
        for y in 0..height {
            let half = y / 2;
            for x in (cx - half)..=(cx + half) {
                g[y][x] = if y == 0 { 3 } else { 1 };
            }
        }
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
