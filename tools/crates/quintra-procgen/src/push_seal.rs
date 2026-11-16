//! Push Seal (crate onto socket) reference model, mirroring
//! `prepare_push` in `src/game/puzzle.c`.
//!
//! The cart clears a floor apron around an L-shaped crate route and paints
//! a 2x2 gold socket. The crate must be pushed onto the socket; any other
//! shove no longer opens the room. The solver treats everything outside the
//! apron as wall (the real court can only add room) and must succeed from
//! every free starting tile in the apron, using the cart's push rules
//! (one tile per shove, never into the doorway approach bands).

use std::collections::{HashSet, VecDeque};

#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub struct PushRoom {
    pub crate_x: i32,
    pub crate_y: i32,
    pub socket_x: i32,
    pub socket_y: i32,
    pub x0: i32,
    pub y0: i32,
    pub x1: i32,
    pub y1: i32,
}

pub fn push_room(seed: u32) -> PushRoom {
    let sel = (seed >> 4) & 3;
    let sx = if sel & 1 != 0 { 10 } else { 8 };
    let sy = if sel & 2 != 0 { 8 } else { 6 };
    let dirx = if seed & 1 != 0 { 1 } else { -1 };
    let diry = if seed & 2 != 0 { 1 } else { -1 };
    let hx = 2 + ((seed >> 2) & 1) as i32;
    let mut vy = 2 + ((seed >> 3) & 1) as i32;
    if diry == 1 && sy == 6 {
        vy = 2;
    }
    let cx = sx - dirx * hx;
    let cy = sy - diry * vy;
    PushRoom {
        crate_x: cx,
        crate_y: cy,
        socket_x: sx,
        socket_y: sy,
        x0: (cx.min(sx) - 3).max(1),
        x1: (cx.max(sx) + 4).min(18),
        y0: (cy.min(sy) - 3).max(1),
        y1: (cy.max(sy) + 4).min(15),
    }
}

/// The cart refuses shoves that would park a crate in a doorway approach.
pub fn crate_pos_forbidden(nx: i32, ny: i32) -> bool {
    ((nx <= 3 || nx >= 15) && ny <= 10 && ny + 1 >= 7)
        || ((ny <= 3 || ny >= 12) && nx <= 12 && nx + 1 >= 7)
}

impl PushRoom {
    fn inside(&self, x: i32, y: i32) -> bool {
        x >= self.x0 && x <= self.x1 && y >= self.y0 && y <= self.y1
    }
    fn body_free(&self, x: i32, y: i32, cx: i32, cy: i32) -> bool {
        (0..2).all(|dy| {
            (0..2).all(|dx| {
                let (tx, ty) = (x + dx, y + dy);
                self.inside(tx, ty) && !(tx >= cx && tx < cx + 2 && ty >= cy && ty < cy + 2)
            })
        })
    }
    /// Fewest shoves to seat the crate from hero body start (hx, hy).
    pub fn solve_from(&self, hx: i32, hy: i32) -> Option<u32> {
        let start = (hx, hy, self.crate_x, self.crate_y);
        let mut seen = HashSet::from([start]);
        let mut q = VecDeque::from([(start, 0u32)]);
        while let Some(((x, y, cx, cy), d)) = q.pop_front() {
            if cx == self.socket_x && cy == self.socket_y {
                return Some(d);
            }
            for (dx, dy) in [(1, 0), (-1, 0), (0, 1), (0, -1)] {
                let (nx, ny) = (x + dx, y + dy);
                if self.body_free(nx, ny, cx, cy) {
                    let s = (nx, ny, cx, cy);
                    if seen.insert(s) {
                        q.push_front((s, d));
                    }
                    continue;
                }
                // Flush against the crate face and leaning into it?
                let touching = match (dx, dy) {
                    (1, 0) => x + 2 == cx && (y - cy).abs() <= 1,
                    (-1, 0) => x == cx + 2 && (y - cy).abs() <= 1,
                    (0, 1) => y + 2 == cy && (x - cx).abs() <= 1,
                    _ => y == cy + 2 && (x - cx).abs() <= 1,
                };
                if !touching {
                    continue;
                }
                let (ncx, ncy) = (cx + dx, cy + dy);
                let fits = (0..2).all(|a| (0..2).all(|b| self.inside(ncx + a, ncy + b)));
                if !fits || crate_pos_forbidden(ncx, ncy) {
                    continue;
                }
                let s = (x, y, ncx, ncy);
                if seen.insert(s) {
                    q.push_back((s, d + 1));
                }
            }
        }
        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_push_seal_is_solvable_from_anywhere_in_its_apron() {
        let mut variants = HashSet::new();
        for seed in 0..64u32 {
            let r = push_room(seed);
            variants.insert(r);
        }
        assert!(variants.len() >= 16, "too little variety: {}", variants.len());
        for r in variants {
            assert!(!crate_pos_forbidden(r.crate_x, r.crate_y));
            assert!(!crate_pos_forbidden(r.socket_x, r.socket_y));
            assert!(r.crate_x != r.socket_x && r.crate_y != r.socket_y,
                "{r:?} must need an L-shaped route");
            for y in r.y0..r.y1 {
                for x in r.x0..r.x1 {
                    if !r.body_free(x, y, r.crate_x, r.crate_y) {
                        continue;
                    }
                    let d = r.solve_from(x, y);
                    assert!(matches!(d, Some(n) if n >= 4), "{r:?} from {x},{y}: {d:?}");
                }
            }
        }
    }
}
