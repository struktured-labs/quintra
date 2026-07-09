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

/// Stage 1 — Serpent: coiled spiral body with a fanged head.
fn boss_serpent() -> Grid {
    let mut g = blank();
    for t in (0..260).step_by(2) {
        let a = t as f64 / 40.0;
        let r = 4.0 + t as f64 / 22.0;
        let x = (16.0 + r * a.cos()) as i32;
        let y = (16.0 + r * a.sin() * 0.7) as i32;
        for dy in -2i32..=2 {
            for dx in -2i32..=2 {
                if dx * dx + dy * dy <= 5
                    && (0..32).contains(&(y + dy))
                    && (0..32).contains(&(x + dx))
                {
                    g[(y + dy) as usize][(x + dx) as usize] =
                        if dx * dx + dy * dy >= 4 { 1 } else { 2 };
                }
            }
        }
    }
    eyes(&mut g, &[(6, 22), (8, 26)]);
    g
}

/// Stage 2 — Infernal Maw: broad demon head, huge glowing mouth.
fn boss_maw() -> Grid {
    let mut g = blank();
    ellipse(&mut g, 16.0, 15.0, 14.0, 13.0, 2, 1);
    for y in 0..8usize {
        for hx in [16 - (8 - y as i32), 16 + (8 - y as i32)] {
            if (0..32).contains(&hx) {
                g[y][hx as usize] = 1;
            }
        }
    }
    eyes(&mut g, &[(11, 10), (11, 22)]);
    for x in 7..25usize {
        let yy = 20 + (x % 3);
        if g[yy][x] != 0 {
            g[yy][x] = 3;
        }
        if g[yy + 1][x] != 0 {
            g[yy + 1][x] = 3;
        }
    }
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
/// NOTE: the crown loop is dead code as originally authored (x steps
/// 4,7,10,... none satisfy x % 6 == 3) — kept verbatim for fidelity.
fn boss_voidlord() -> Grid {
    let mut g = make_boss_big();
    for x in (4..28usize).step_by(3) {
        for y in 0..4usize {
            if (x as i32 % 6 - 3).abs() < 1 {
                g[y][x] = 1;
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
