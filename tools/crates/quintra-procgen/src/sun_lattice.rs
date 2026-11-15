//! Sun Lattice reference generator and beam tracer.
//!
//! Host-side mirror of `src/game/sun_lattice_gen.c`: the same xorshift16
//! stream, the same RNG call order (including C's short-circuit skips), and
//! the same u8 wrap-around. `scripts/test_sun_lattice_parity.py` compiles the
//! C with `-DSL_HOST` and diffs it against `sun-lattice-dump` over thousands
//! of seeds per stage; the property tests below pin the gameplay contracts.

pub const MAX_FIX: usize = 20;
pub const MAP_W: u8 = 20;
pub const MAP_H: u8 = 17;
const BITS: usize = 43;
const X0: u8 = 3;
const X1: u8 = 16;
const Y0: u8 = 3;
const Y1: u8 = 13;
const PATH_CAP: u8 = 32;
const QUEUE: usize = 5;
const TRIES: u8 = 64;

pub const EMITTER: u8 = 1;
pub const VANE: u8 = 2;
pub const FIXED: u8 = 3;
pub const BIFROST: u8 = 4;
pub const OBELISK: u8 = 5;

/// Attempts value reported when the hand-checked fallback was used.
pub const FALLBACK: u8 = 0xFF;

const DX: [i8; 4] = [0, 1, 0, -1];
const DY: [i8; 4] = [-1, 0, 1, 0];

// Per-stage shape (index = min(bosses_beaten, 8) - 2; 0 = Stage 3).
const MAIN_V: [u8; 7] = [2, 2, 3, 3, 3, 3, 3];
const WEDGES: [u8; 7] = [0, 1, 1, 1, 1, 2, 2];
const SUB_V: [u8; 7] = [0, 1, 1, 1, 1, 0, 0];
const FIXED_N: [u8; 7] = [0, 0, 0, 1, 1, 2, 2];
const DECOY: [u8; 7] = [0, 0, 1, 1, 2, 2, 2];

/// Tiles a beam passes over when tracing against a room tilemap.
pub fn passable(t: u8) -> bool {
    matches!(t, 1 | 19 | 20 | 31 | 33 | 97 | 101..=104 | 108)
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Fixture {
    pub x: u8,
    pub y: u8,
    pub kind: u8,
    pub ang: u8,
    pub solved_ang: u8,
}

#[derive(Clone, Debug)]
pub struct Lattice {
    pub fixtures: Vec<Fixture>,
    /// (x, y) of the shatterable blocker, or None.
    pub crystal: Option<(u8, u8)>,
    /// Failed build attempts, or [`FALLBACK`].
    pub attempts: u8,
}

/// Result of one trace: beam cells by axis and which fixtures are lit.
#[derive(Clone, Debug, Default)]
pub struct Trace {
    pub beam_h: Vec<(u8, u8)>,
    pub beam_v: Vec<(u8, u8)>,
    pub lit: Vec<bool>,
    pub solved: bool,
}

fn cell(x: u8, y: u8) -> usize {
    // Callers bounds-check first, exactly like the C, so y*20+x < 340.
    y as usize * MAP_W as usize + x as usize
}

fn bit_get(b: &[u8; BITS], x: u8, y: u8) -> bool {
    let i = cell(x, y);
    b[i >> 3] & (1 << (i & 7)) != 0
}

fn bit_set(b: &mut [u8; BITS], x: u8, y: u8) {
    let i = cell(x, y);
    b[i >> 3] |= 1 << (i & 7);
}

fn step(v: u8, d: i8, n: u8) -> u8 {
    v.wrapping_add((d as i16 * n as i16) as u8)
}

fn in_box(x: u8, y: u8) -> bool {
    (X0..=X1).contains(&x) && (Y0..=Y1).contains(&y)
}

struct Gen {
    rs: u16,
    fx: Vec<Fixture>,
    occ: [u8; BITS],
    fixbits: [u8; BITS],
    end_d: u8,
    pq: Vec<(u8, u8, u8, u8, u8)>,
    crystal: Option<(u8, u8)>,
    attempts: u8,
}

impl Gen {
    fn rnd(&mut self) -> u8 {
        self.rs ^= self.rs << 7;
        self.rs ^= self.rs >> 9;
        self.rs ^= self.rs << 8;
        self.rs as u8
    }

    fn far_from_fixtures(&self, x: u8, y: u8) -> bool {
        self.fx.iter().all(|f| x.abs_diff(f.x) >= 3 || y.abs_diff(f.y) >= 3)
    }

    fn add(&mut self, x: u8, y: u8, kind: u8, ang: u8) {
        self.fx.push(Fixture { x, y, kind, ang, solved_ang: ang });
        bit_set(&mut self.occ, x, y);
        bit_set(&mut self.fixbits, x, y);
    }

    fn seg_ok(&self, x: u8, y: u8, d: u8, len: u8) -> bool {
        let (mut cx, mut cy) = (x, y);
        for _ in 0..len {
            cx = step(cx, DX[d as usize], 1);
            cy = step(cy, DY[d as usize], 1);
            if cx >= MAP_W || cy >= MAP_H || bit_get(&self.occ, cx, cy) {
                return false;
            }
        }
        in_box(cx, cy) && self.far_from_fixtures(cx, cy)
    }

    fn seg_mark(&mut self, mut x: u8, mut y: u8, d: u8, len: u8) {
        for _ in 0..len {
            x = step(x, DX[d as usize], 1);
            y = step(y, DY[d as usize], 1);
            bit_set(&mut self.occ, x, y);
        }
    }

    fn run_branch(&mut self, mut x: u8, mut y: u8, mut d: u8, vanes: u8, term: u8) -> bool {
        let mut used: u8 = 0;
        for i in 0..=vanes {
            let base = self.rnd() % 5;
            let mut len = 0;
            for t in 0..5u8 {
                let cand = 3 + (base + t) % 5;
                if used.wrapping_add(cand) <= PATH_CAP && self.seg_ok(x, y, d, cand) {
                    len = cand;
                    break;
                }
            }
            if len == 0 {
                return false;
            }
            self.seg_mark(x, y, d, len);
            used = used.wrapping_add(len);
            x = step(x, DX[d as usize], len);
            y = step(y, DY[d as usize], len);
            if i == vanes {
                if term == BIFROST
                    && !(room_ahead(x, y, (d + 1) & 3) && room_ahead(x, y, (d + 3) & 3))
                {
                    return false;
                }
                self.add(x, y, term, 0);
                self.end_d = d;
                return true;
            }
            let turn = if self.rnd() & 1 != 0 { 1 } else { 3 };
            let mut nd = (d + turn) & 3;
            if !room_ahead(x, y, nd) {
                nd = (nd + 2) & 3;
                if !room_ahead(x, y, nd) {
                    return false;
                }
            }
            self.add(x, y, VANE, if d ^ 1 == nd { 0 } else { 1 });
            d = nd;
        }
        false
    }

    fn reset(&mut self) {
        self.fx.clear();
        self.pq.clear();
        self.crystal = None;
        self.occ = [0; BITS];
        self.fixbits = [0; BITS];
    }

    fn build_tree(&mut self, s: usize) -> bool {
        let ex = X0 + self.rnd() % 14;
        let ey = Y0 + self.rnd() % 11;
        let mut ed = self.rnd() & 3;
        let mut k = 0;
        while k < 4 && !room_ahead(ex, ey, ed) {
            ed = (ed + 1) & 3;
            k += 1;
        }
        if k == 4 {
            return false;
        }
        self.add(ex, ey, EMITTER, ed);
        let mut wedges_left = WEDGES[s];
        let t = if wedges_left > 0 { BIFROST } else { OBELISK };
        self.pq.push((ex, ey, ed, MAIN_V[s], t));
        wedges_left = wedges_left.saturating_sub(1);
        let mut qi = 0;
        while qi < self.pq.len() {
            let (x, y, d, v, t) = self.pq[qi];
            if !self.run_branch(x, y, d, v, t) {
                return false;
            }
            if t == BIFROST {
                let w = *self.fx.last().unwrap();
                let d = self.end_d;
                let t1 = if wedges_left > 0 { BIFROST } else { OBELISK };
                self.pq.push((w.x, w.y, (d + 1) & 3, SUB_V[s], t1));
                wedges_left = wedges_left.saturating_sub(1);
                self.pq.push((w.x, w.y, (d + 3) & 3, SUB_V[s], OBELISK));
            }
            qi += 1;
        }
        true
    }

    fn fallback(&mut self) {
        self.reset();
        self.add(3, 4, EMITTER, 1);
        self.add(14, 4, VANE, 1);
        self.add(14, 12, VANE, 0);
        self.add(4, 12, OBELISK, 0);
        // Reserve the solved path so decoys never land on it.
        self.seg_mark(3, 4, 1, 11);
        self.seg_mark(14, 4, 2, 8);
        self.seg_mark(14, 12, 3, 10);
        self.attempts = FALLBACK;
    }
}

fn room_ahead(x: u8, y: u8, d: u8) -> bool {
    in_box(step(x, DX[d as usize], 3), step(y, DY[d as usize], 3))
}

/// Generate the scrambled lattice for a room. `bosses_beaten` is the run's
/// count (2 = Stage 3, the first lattice stage); `role` is 0 for the Trial
/// and 1 for the Waystone.
pub fn generate(seed: u32, bosses_beaten: u8, role: u8) -> Lattice {
    let s = (bosses_beaten.clamp(2, 8) - 2) as usize;
    let mut rs = (seed as u16) ^ ((seed >> 16) as u16);
    if role != 0 {
        rs ^= 0x5A5A;
    }
    if rs == 0 {
        rs = 0xACE1;
    }
    let mut g = Gen {
        rs,
        fx: Vec::with_capacity(MAX_FIX),
        occ: [0; BITS],
        fixbits: [0; BITS],
        end_d: 0,
        pq: Vec::with_capacity(QUEUE + 2),
        crystal: None,
        attempts: 0,
    };
    loop {
        g.reset();
        if g.build_tree(s) {
            break;
        }
        g.attempts += 1;
        if g.attempts >= TRIES {
            g.fallback();
            break;
        }
    }

    let mut rot = g.fx.iter().filter(|f| f.kind == VANE).count() as u8;
    let mut fixed_left = FIXED_N[s];
    let mut i = 0;
    while i < g.fx.len() && fixed_left > 0 && rot > 2 {
        if g.fx[i].kind == VANE && g.rnd() & 1 != 0 {
            g.fx[i].kind = FIXED;
            fixed_left -= 1;
            rot -= 1;
        }
        i += 1;
    }

    let path_n = g.fx.len();
    let want = DECOY[s] + u8::from(role != 0);
    for _ in 0..want {
        if g.fx.len() >= MAX_FIX {
            break;
        }
        for _ in 0..8 {
            let x = X0 + g.rnd() % 14;
            let y = Y0 + g.rnd() % 11;
            let a = g.rnd() & 1;
            if !bit_get(&g.occ, x, y) && g.far_from_fixtures(x, y) {
                g.add(x, y, VANE, a);
                break;
            }
        }
    }

    if (s == 0 && role == 0) || (s >= 3 && g.rnd() & 3 == 0) {
        let e = g.fx[0];
        g.crystal = Some((step(e.x, DX[e.ang as usize], 2), step(e.y, DY[e.ang as usize], 2)));
    }

    // Only path vanes count; Stage 3 flips half (rounded up), Stage 4+ all.
    let mut flipped: u8 = 0;
    let want = if s != 0 { rot } else { (rot + 1) >> 1 };
    for i in 0..path_n {
        if g.fx[i].kind == VANE && g.rnd() & 1 != 0 {
            g.fx[i].ang ^= 1;
            flipped += 1;
        }
    }
    let mut i = 0;
    while i < path_n && (flipped < want || trace(&g.fx, None).solved) {
        if g.fx[i].kind == VANE && g.fx[i].ang == g.fx[i].solved_ang {
            g.fx[i].ang ^= 1;
            flipped += 1;
        }
        i += 1;
    }
    if trace(&g.fx, None).solved {
        g.fallback();
        g.fx[1].ang = 0;
    }
    Lattice { fixtures: g.fx, crystal: g.crystal, attempts: g.attempts }
}

/// Trace every beam. With `map`, rays stop on tiles that are not
/// [`passable`] (the cart's `sl_trace(1)`); without, the open-room check
/// the generator uses.
pub fn trace(fx: &[Fixture], map: Option<&[[u8; MAP_W as usize]; MAP_H as usize]>) -> Trace {
    let mut out = Trace { lit: vec![false; fx.len()], ..Trace::default() };
    let mut q: Vec<(u8, u8, u8)> = Vec::with_capacity(QUEUE);
    for f in fx {
        if f.kind == EMITTER && q.len() < QUEUE {
            q.push((f.x, f.y, f.ang));
        }
    }
    let mut qi = 0;
    while qi < q.len() {
        let (mut x, mut y, mut d) = q[qi];
        for _ in 0..PATH_CAP {
            x = step(x, DX[d as usize], 1);
            y = step(y, DY[d as usize], 1);
            if x >= MAP_W || y >= MAP_H {
                break;
            }
            if let Some(i) = fx.iter().position(|f| f.x == x && f.y == y) {
                let k = fx[i].kind;
                if k == VANE || k == FIXED {
                    d = if fx[i].ang != 0 { 3 - d } else { d ^ 1 };
                    continue;
                }
                if k == BIFROST {
                    for nd in [(d + 1) & 3, (d + 3) & 3] {
                        if q.len() < QUEUE {
                            q.push((x, y, nd));
                        }
                    }
                } else if k == OBELISK {
                    out.lit[i] = true;
                }
                break;
            }
            if let Some(m) = map {
                if !passable(m[y as usize][x as usize]) {
                    break;
                }
            }
            if d & 1 != 0 {
                out.beam_h.push((x, y));
            } else {
                out.beam_v.push((x, y));
            }
        }
        qi += 1;
    }
    let obelisks: Vec<bool> = fx
        .iter()
        .zip(&out.lit)
        .filter(|(f, _)| f.kind == OBELISK)
        .map(|(_, &l)| l)
        .collect();
    out.solved = !obelisks.is_empty() && obelisks.iter().all(|&l| l);
    out
}

/// Fixtures turned to their solved angles.
pub fn solved(l: &Lattice) -> Vec<Fixture> {
    l.fixtures.iter().map(|f| Fixture { ang: f.solved_ang, ..*f }).collect()
}

/// One line per room, byte-identical to the C host harness.
pub fn dump_line(seed: u32, l: &Lattice) -> String {
    let mut s = format!("{seed:08x} {} {}", l.attempts, u8::from(trace(&l.fixtures, None).solved));
    for f in &l.fixtures {
        s += &format!(" {},{},{},{},{}", f.x, f.y, f.kind, f.ang, f.solved_ang);
    }
    let (cx, cy) = l.crystal.unwrap_or((0xFF, 0xFF));
    s += &format!(" C{cx},{cy}");
    s
}

/// The seed sequence the C host harness walks.
pub fn harness_seed(i: u32) -> u32 {
    i.wrapping_mul(2_654_435_761).wrapping_add(12_345)
}


/// Fewest vane turns that light every Obelisk, found without peeking at
/// `solved_ang`: an exhaustive search over the rotatable vanes, smallest
/// turn count first (ties break on the lowest fixture indices). Each turn
/// flips a vane between `/` and `\\`, so a vane is turned at most once.
/// `None` means no setting of the rotatable vanes lights every Obelisk.
pub fn solve(
    fx: &[Fixture],
    map: Option<&[[u8; MAP_W as usize]; MAP_H as usize]>,
) -> Option<Vec<usize>> {
    let vanes: Vec<usize> = (0..fx.len()).filter(|&i| fx[i].kind == VANE).collect();
    let k = vanes.len();
    assert!(k <= 16, "{k} rotatable vanes is beyond the search budget");
    let mut masks: Vec<u32> = (0..1u32 << k).collect();
    masks.sort_by_key(|m| (m.count_ones(), std::cmp::Reverse(m.reverse_bits())));
    let mut work = fx.to_vec();
    for m in masks {
        for (b, &i) in vanes.iter().enumerate() {
            work[i].ang = fx[i].ang ^ ((m >> b) & 1) as u8;
        }
        if trace(&work, map).solved {
            return Some((0..k).filter(|b| m >> b & 1 != 0).map(|b| vanes[b]).collect());
        }
    }
    None
}

/// Every setting of the rotatable vanes that lights every Obelisk.
pub fn solution_count(fx: &[Fixture]) -> usize {
    let vanes: Vec<usize> = (0..fx.len()).filter(|&i| fx[i].kind == VANE).collect();
    let mut work = fx.to_vec();
    (0..1u32 << vanes.len())
        .filter(|m| {
            for (b, &i) in vanes.iter().enumerate() {
                work[i].ang = fx[i].ang ^ ((m >> b) & 1) as u8;
            }
            trace(&work, None).solved
        })
        .count()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rooms_start_unlit_and_solve() {
        for stage in 3..=9u8 {
            for role in 0..2 {
                let mut fallbacks = 0;
                for i in 0..500 {
                    let l = generate(harness_seed(i), stage - 1, role);
                    assert!(!trace(&l.fixtures, None).solved, "stage {stage} seed {i} lit on arrival");
                    assert!(trace(&solved(&l), None).solved, "stage {stage} seed {i} unsolvable");
                    if l.attempts == FALLBACK {
                        fallbacks += 1;
                    }
                }
                assert!(fallbacks < 25, "stage {stage} role {role}: {fallbacks}/500 fallbacks");
            }
        }
    }

    #[test]
    fn fixtures_stay_spaced_inside_the_box() {
        for stage in 3..=9u8 {
            for i in 0..300 {
                let l = generate(harness_seed(i), stage - 1, 0);
                for (a, f) in l.fixtures.iter().enumerate() {
                    assert!(in_box(f.x, f.y), "{f:?} outside the box");
                    for g in &l.fixtures[a + 1..] {
                        assert!(f.x.abs_diff(g.x) >= 3 || f.y.abs_diff(g.y) >= 3, "{f:?} crowds {g:?}");
                    }
                }
            }
        }
    }

    #[test]
    fn stage_shape_grows() {
        let count = |stage: u8, kind| {
            (0..200)
                .map(|i| generate(harness_seed(i), stage - 1, 0))
                .filter(|l| l.attempts != FALLBACK)
                .map(|l| l.fixtures.iter().filter(|f| f.kind == kind).count())
                .max()
                .unwrap_or(0)
        };
        assert_eq!(count(3, BIFROST), 0);
        assert_eq!(count(4, BIFROST), 1);
        assert_eq!(count(8, BIFROST), 2);
        assert_eq!(count(5, FIXED), 0);
        assert!(count(6, FIXED) >= 1);
    }

    #[test]
    fn stage3_trial_teaches_the_crystal() {
        for i in 0..100 {
            let l = generate(harness_seed(i), 2, 0);
            if l.attempts != FALLBACK {
                assert!(l.crystal.is_some(), "seed {i}");
            }
            assert!(generate(harness_seed(i), 2, 1).crystal.is_none());
        }
    }

    #[test]
    fn walls_block_beams() {
        let l = generate(harness_seed(7), 3, 0);
        let open = [[1u8; MAP_W as usize]; MAP_H as usize];
        let walls = [[0u8; MAP_W as usize]; MAP_H as usize];
        let s = solved(&l);
        assert!(trace(&s, Some(&open)).solved);
        assert!(!trace(&s, Some(&walls)).solved);
    }

    #[test]
    fn scrambled_rooms_are_solvable_from_scratch() {
        // The solver never reads solved_ang, so this proves the scramble
        // left a reachable solution, and that it needs at least one turn.
        for stage in 3..=9u8 {
            for role in 0..2 {
                for i in 0..400 {
                    let l = generate(harness_seed(i), stage - 1, role);
                    let plan = solve(&l.fixtures, None)
                        .unwrap_or_else(|| panic!("stage {stage} role {role} seed {i} unsolvable"));
                    assert!(!plan.is_empty(), "stage {stage} seed {i} needs no turns");
                    let mut f = l.fixtures.clone();
                    for &v in &plan {
                        f[v].ang ^= 1;
                    }
                    assert!(trace(&f, None).solved);
                    // The intended tree is never shorter than the plan, and
                    // from Stage 4 the plan turns every rotatable path vane
                    // (no shortcut) in nearly every room; see below.
                    let intended = l
                        .fixtures
                        .iter()
                        .filter(|f| f.kind == VANE && f.ang != f.solved_ang)
                        .count();
                    assert!(plan.len() <= intended, "stage {stage} seed {i}");
                }
            }
        }
    }

    #[test]
    fn late_stages_need_more_turns() {
        let mean = |stage: u8| {
            let n = 300;
            (0..n)
                .map(|i| solve(&generate(harness_seed(i), stage - 1, 0).fixtures, None).unwrap().len())
                .sum::<usize>() as f64
                / n as f64
        };
        let means: Vec<f64> = (3..=9).map(mean).collect();
        // Stage 3 teaches; every later stage needs clearly more turns.
        for (k, m) in means.iter().enumerate().skip(1) {
            assert!(*m >= means[0] + 0.75, "Stage {} mean {m:.2} vs Stage 3 {:.2}", k + 3, means[0]);
        }
    }

    #[test]
    fn fixed_vanes_and_wedges_never_turn() {
        for i in 0..200 {
            let l = generate(harness_seed(i), 6, 1);
            for v in solve(&l.fixtures, None).unwrap() {
                assert_eq!(l.fixtures[v].kind, VANE);
            }
        }
    }
}
