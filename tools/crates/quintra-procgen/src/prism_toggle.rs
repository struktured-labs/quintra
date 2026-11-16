//! Prism Toggle (crystal-switch barrier room) reference model and solver.
//!
//! The chamber templates live in exactly one place, the cart source
//! `src/game/prism_toggle.c`, between the `PRISM-TEMPLATES-BEGIN/END`
//! markers. This module parses them, applies the same seed transform as the
//! cart (`prism_variant`), lays the chamber into the 20x17 compact court and
//! proves every variant with a breadth-first search over
//! (2x2 body position, raised colour):
//!
//! * solvable from the outer ring with base movement + melee strikes only;
//! * needs at least `MIN_FLIPS` orb strikes (it is a puzzle, not a corridor);
//! * no softlock: from every state the hero can reach, even when shots,
//!   bombs or a boomerang flip the orbs from range, the goal stays reachable
//!   with melee alone (the seal then lowers every barrier, so the ring is
//!   reachable too);
//! * a flip while the body stands in a barrier gap is modelled the way the
//!   cart defers it: the tile under the champion rises only after they step
//!   off, on whichever side they choose.

use std::collections::VecDeque;

pub const SRC: &str = include_str!("../../../../src/game/prism_toggle.c");
pub const W: usize = 20;
pub const H: usize = 17;
pub const TW: usize = 12;
pub const TH: usize = 11;
pub const OX: usize = 4;
pub const OY: usize = 3;
pub const MIN_FLIPS: u32 = 2;
/// Bomb / Morningstar / splash reach used for the conservative range model.
pub const RANGE: i32 = 3;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Cell {
    Floor,
    Wall,
    /// Barrier of colour 0 (amber) or 1 (azure).
    Barrier(u8),
    Orb,
    Goal,
}

#[derive(Clone, Debug)]
pub struct Template {
    pub tier: u8,
    pub rows: Vec<String>,
}

/// Parse the chamber templates and their tiers out of the cart source.
pub fn templates() -> Vec<Template> {
    let begin = SRC.find("PRISM-TEMPLATES-BEGIN").expect("begin marker");
    let end = SRC.find("PRISM-TEMPLATES-END").expect("end marker");
    let body = &SRC[begin..end];
    let mut out: Vec<Template> = Vec::new();
    let mut cur: Vec<String> = Vec::new();
    for line in body.lines() {
        let line = line.trim();
        if let Some(rest) = line.strip_prefix("/* tier ") {
            let tier: u8 = rest.split_whitespace().next().unwrap().parse().unwrap();
            out.push(Template { tier, rows: Vec::new() });
            continue;
        }
        if let Some(start) = line.find('"') {
            let stop = line[start + 1..].find('"').unwrap() + start + 1;
            cur.push(line[start + 1..stop].to_string());
            if cur.len() == TH {
                out.last_mut().expect("tier comment precedes rows").rows =
                    std::mem::take(&mut cur);
            }
        }
    }
    for t in &out {
        assert_eq!(t.rows.len(), TH);
        for r in &t.rows {
            assert_eq!(r.len(), TW, "template row {r:?}");
        }
    }
    out
}

/// Seed transform shared with `prism_prepare` on the cart.
/// Returns (template index, mirror, colour swap).
pub fn prism_variant(seed: u32, bosses_beaten: u8) -> (usize, bool, bool) {
    let tier = tier_for_stage(bosses_beaten);
    let all = templates();
    let ids: Vec<usize> = (0..all.len()).filter(|&i| all[i].tier == tier).collect();
    let pick = ((seed >> 8) as u8 as usize) % ids.len();
    (ids[pick], seed & 0x10 != 0, seed & 0x20 != 0)
}

pub fn tier_for_stage(bosses_beaten: u8) -> u8 {
    match bosses_beaten {
        0 => 0,
        1 | 2 => 1,
        _ => 2,
    }
}

/// Lay one variant into a 20x17 compact court. Border = wall, ring = floor.
pub fn layout(t: &Template, mirror: bool, swap: bool) -> Vec<Cell> {
    let mut g = vec![Cell::Floor; W * H];
    for y in 0..H {
        for x in 0..W {
            if x == 0 || y == 0 || x == W - 1 || y == H - 1 {
                g[y * W + x] = Cell::Wall;
            }
        }
    }
    for (ty, row) in t.rows.iter().enumerate() {
        for (tx, ch) in row.bytes().enumerate() {
            let sx = if mirror { TW - 1 - tx } else { tx };
            let c = match ch {
                b'#' => Cell::Wall,
                b'.' => Cell::Floor,
                b'a' => Cell::Barrier(if swap { 1 } else { 0 }),
                b'b' => Cell::Barrier(if swap { 0 } else { 1 }),
                b'o' => Cell::Orb,
                b'G' => Cell::Goal,
                other => panic!("bad template byte {}", other as char),
            };
            g[(OY + ty) * W + OX + sx] = c;
        }
    }
    g
}

pub struct Model {
    pub grid: Vec<Cell>,
    /// Colour raised on arrival (template colour `a`, after the swap).
    pub start_raised: u8,
}

impl Model {
    pub fn new(t: &Template, mirror: bool, swap: bool) -> Self {
        Model { grid: layout(t, mirror, swap), start_raised: if swap { 1 } else { 0 } }
    }
    fn at(&self, x: i32, y: i32) -> Cell {
        if x < 0 || y < 0 || x >= W as i32 || y >= H as i32 {
            return Cell::Wall;
        }
        self.grid[y as usize * W + x as usize]
    }
    fn walkable(&self, x: i32, y: i32, raised: u8) -> bool {
        match self.at(x, y) {
            Cell::Floor | Cell::Goal => true,
            Cell::Barrier(c) => c != raised,
            _ => false,
        }
    }
    fn body_ok(&self, x: i32, y: i32, raised: u8) -> bool {
        (0..2).all(|dy| (0..2).all(|dx| self.walkable(x + dx, y + dy, raised)))
    }
    fn body_tiles(x: i32, y: i32) -> [(i32, i32); 4] {
        [(x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)]
    }
    fn on_goal(&self, x: i32, y: i32) -> bool {
        Self::body_tiles(x, y).iter().any(|&(a, b)| self.at(a, b) == Cell::Goal)
    }
    /// The champion's swing reaches a solid tile orthogonally beside the body.
    pub fn melee_flip(&self, x: i32, y: i32) -> bool {
        let n = [
            (x - 1, y), (x - 1, y + 1), (x + 2, y), (x + 2, y + 1),
            (x, y - 1), (x + 1, y - 1), (x, y + 2), (x + 1, y + 2),
        ];
        n.iter().any(|&(a, b)| self.at(a, b) == Cell::Orb)
    }
    /// Conservative: any straight line through non-wall tiles, or anything
    /// within `RANGE` tiles of the body (bombs, Morningstar, splash).
    pub fn range_flip(&self, x: i32, y: i32) -> bool {
        if self.melee_flip(x, y) {
            return true;
        }
        for (bx, by) in Self::body_tiles(x, y) {
            for oy in 0..H as i32 {
                for ox in 0..W as i32 {
                    if self.at(ox, oy) == Cell::Orb
                        && (ox - bx).abs().max((oy - by).abs()) <= RANGE
                    {
                        return true;
                    }
                }
            }
            for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
                let (mut cx, mut cy) = (bx + dx, by + dy);
                loop {
                    match self.at(cx, cy) {
                        Cell::Orb => return true,
                        Cell::Wall => break,
                        _ => {}
                    }
                    cx += dx;
                    cy += dy;
                }
            }
        }
        false
    }
    /// Melee or a straight unobstructed line (shots, boomerang, Hookshot).
    pub fn sight_flip(&self, x: i32, y: i32) -> bool {
        if self.melee_flip(x, y) {
            return true;
        }
        for (bx, by) in Self::body_tiles(x, y) {
            for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
                let (mut cx, mut cy) = (bx + dx, by + dy);
                loop {
                    match self.at(cx, cy) {
                        Cell::Orb => return true,
                        Cell::Wall => break,
                        _ => {}
                    }
                    cx += dx;
                    cy += dy;
                }
            }
        }
        false
    }
    /// Where the body can stand once a strike at (x, y) has flipped the
    /// colours. The cart defers raising any barrier tile under the body
    /// until the champion steps off it, so a flip inside a doorway gap lets
    /// the hero walk out (on either side) before that tile closes.
    pub fn land_after_flip(&self, x: i32, y: i32, c: u8) -> Vec<(i32, i32)> {
        let n = c ^ 1;
        if self.body_ok(x, y, n) {
            return vec![(x, y)];
        }
        let mut out = Vec::new();
        let mut seen = vec![(x, y)];
        let mut q = VecDeque::from([(x, y, 0)]);
        while let Some((px, py, k)) = q.pop_front() {
            if self.body_ok(px, py, n) {
                out.push((px, py));
                continue;
            }
            if k == 3 {
                continue;
            }
            for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
                let (qx, qy) = (px + dx, py + dy);
                if !seen.contains(&(qx, qy)) && self.body_ok(qx, qy, c) {
                    seen.push((qx, qy));
                    q.push_back((qx, qy, k + 1));
                }
            }
        }
        out
    }
    fn idx(x: i32, y: i32, c: u8) -> usize {
        ((y as usize * W + x as usize) << 1) | c as usize
    }
    /// 0-1 BFS: (flips needed to reach state) from `starts`.
    fn search(&self, starts: &[(i32, i32, u8)], ranged: bool) -> Vec<u32> {
        let mut dist = vec![u32::MAX; W * H * 2];
        let mut q = VecDeque::new();
        for &(x, y, c) in starts {
            dist[Self::idx(x, y, c)] = 0;
            q.push_back((x, y, c));
        }
        while let Some((x, y, c)) = q.pop_front() {
            let d = dist[Self::idx(x, y, c)];
            for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
                let (nx, ny) = (x + dx, y + dy);
                if self.body_ok(nx, ny, c) && dist[Self::idx(nx, ny, c)] > d {
                    dist[Self::idx(nx, ny, c)] = d;
                    q.push_front((nx, ny, c));
                }
            }
            let can = if ranged { self.range_flip(x, y) } else { self.melee_flip(x, y) };
            if can {
                for (nx, ny) in self.land_after_flip(x, y, c) {
                    if dist[Self::idx(nx, ny, c ^ 1)] > d + 1 {
                        dist[Self::idx(nx, ny, c ^ 1)] = d + 1;
                        q.push_back((nx, ny, c ^ 1));
                    }
                }
            }
        }
        dist
    }
    fn ring_start(&self) -> (i32, i32) {
        (1, 1)
    }
    fn is_ring(x: i32, y: i32) -> bool {
        let inside = x + 1 >= OX as i32 && x < (OX + TW) as i32
            && y + 1 >= OY as i32 && y < (OY + TH) as i32;
        !inside
    }
    /// Fewest melee strikes from the ring to the goal, if solvable.
    pub fn min_flips(&self) -> Option<u32> {
        let (sx, sy) = self.ring_start();
        let d = self.search(&[(sx, sy, self.start_raised)], false);
        let mut best = None;
        for y in 0..H as i32 {
            for x in 0..W as i32 {
                for c in 0..2u8 {
                    let v = d[Self::idx(x, y, c)];
                    if v != u32::MAX && self.on_goal(x, y) {
                        best = Some(best.map_or(v, |b: u32| b.min(v)));
                    }
                }
            }
        }
        best
    }
    /// Every problem found; empty means the variant is proven.
    pub fn validate(&self) -> Vec<String> {
        let mut errs = Vec::new();
        match self.min_flips() {
            None => errs.push("unsolvable with melee".into()),
            Some(f) if f < MIN_FLIPS => errs.push(format!("only {f} flip(s)")),
            _ => {}
        }
        let (sx, sy) = self.ring_start();
        let reach = self.search(&[(sx, sy, self.start_raised)], true);
        for y in 0..H as i32 {
            for x in 0..W as i32 {
                for c in 0..2u8 {
                    if reach[Self::idx(x, y, c)] == u32::MAX {
                        continue;
                    }
                    let d = self.search(&[(x, y, c)], false);
                    let mut goal = false;
                    let mut ring = false;
                    for yy in 0..H as i32 {
                        for xx in 0..W as i32 {
                            for cc in 0..2u8 {
                                if d[Self::idx(xx, yy, cc)] == u32::MAX {
                                    continue;
                                }
                                goal |= self.on_goal(xx, yy);
                                ring |= Self::is_ring(xx, yy);
                            }
                        }
                    }
                    // Reaching the seal lowers every barrier on the cart, so
                    // a reachable goal also guarantees the way back out.
                    if !goal {
                        errs.push(format!(
                            "softlock at body {x},{y} raised {c} (goal {goal}, ring {ring})"
                        ));
                    }
                }
            }
        }
        errs.sort();
        errs.dedup();
        errs
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_template_variant_is_proven() {
        let all = templates();
        for tier in 0..3u8 {
            assert!(all.iter().any(|t| t.tier == tier), "tier {tier} has no template");
        }
        let mut failures = Vec::new();
        for (i, t) in all.iter().enumerate() {
            for mirror in [false, true] {
                for swap in [false, true] {
                    let m = Model::new(t, mirror, swap);
                    let errs = m.validate();
                    if !errs.is_empty() {
                        failures.push(format!("template {i} mirror {mirror} swap {swap}: {errs:?}"));
                    }
                }
            }
        }
        assert!(failures.is_empty(), "{}", failures.join("\n"));
    }

    #[test]
    fn harder_tiers_need_more_strikes() {
        let all = templates();
        for t in &all {
            let f = Model::new(t, false, false).min_flips().unwrap();
            assert!(f >= MIN_FLIPS + u32::from(t.tier.min(1)), "tier {} template needs {f}", t.tier);
        }
    }

    #[test]
    fn variant_is_stable_and_covers_every_template() {
        let all = templates();
        let mut seen = vec![false; all.len()];
        for s in 0..4096u32 {
            for bb in 0..9u8 {
                let (i, _, _) = prism_variant(s.wrapping_mul(2654435761), bb);
                assert_eq!(all[i].tier, tier_for_stage(bb));
                seen[i] = true;
            }
        }
        assert!(seen.iter().all(|&s| s));
    }
}
#[cfg(test)]
mod dbg {
    #[test]
    #[ignore]
    fn print_flips() {
        for (i, t) in super::templates().iter().enumerate() {
            println!("{i} tier {} flips {:?}", t.tier, super::Model::new(t, false, false).min_flips());
        }
    }
}
