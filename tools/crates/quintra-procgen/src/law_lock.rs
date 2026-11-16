//! Law Lock reference: the Dungeon Law's WAX/WANE state gates 1-3 doorways
//! on the required route. Mirrors `src/game/law_lock_gen.c` step for step
//! (the `law_lock_parity` test compiles the C on the host and compares), then
//! adds the checks the cartridge cannot afford: the full mission-tour
//! overhead (bitmask BFS over cell x Law state x objectives) and Argon's
//! per-stage caps (spec §9).

use crate::topology::{cache_cell, mission_graph, seed_mix, Maze, Missions, NONE};
use std::collections::VecDeque;

pub const MAX_GATES: usize = 3;
/// An altar stands at most this many rooms from the gate it serves.
pub const ALTAR_REACH: u8 = 3;

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Gate {
    pub a: u8,
    pub b: u8,
    pub dir: u8,
    pub open: u8,
}

/// Generator input, the exact `ll_*` globals the cartridge fills.
#[derive(Clone, Debug)]
pub struct Input {
    pub size: u8,
    pub nb: Vec<[u8; 4]>,
    pub entry: u8,
    pub roles: [u8; 7],
    pub cache: u8,
    pub order: u8,
    pub mix: u8,
    pub bb: u8,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct LawLock {
    pub gates: Vec<Gate>,
    pub altars: Vec<u8>,
    pub plain_boss: u8,
    pub law_boss: u8,
    pub plain_tour: u8,
    pub law_tour: u8,
}

#[derive(Clone, Copy, PartialEq)]
enum Mode {
    Plain,
    Frozen,
    Law,
}

impl Input {
    pub fn for_seed(run_seed: u32, bb: u8) -> (Input, Missions) {
        let maze = Maze::new(run_seed, bb);
        let entry = maze.entry_cell();
        let missions = mission_graph(&maze, entry);
        let cache = cache_cell(&maze, &missions);
        let input = Input {
            size: maze.size,
            nb: maze.nb.clone(),
            entry,
            roles: missions.roles,
            cache,
            order: missions.order & 1,
            mix: seed_mix(run_seed),
            bb,
        };
        (input, missions)
    }

    pub fn portal_peer(&self, cell: u8) -> u8 {
        if self.bb == 0 || self.size <= 8 {
            return NONE;
        }
        match cell {
            2 => 8,
            8 => 2,
            _ => NONE,
        }
    }

    fn gate_cell_ok(&self, c: u8) -> bool {
        !(c == self.entry || c >= self.size - 3 || c < 3 || c == self.roles[5] || c == self.roles[6])
    }
}

pub fn gate_at(gates: &[Gate], cell: u8, dir: u8) -> Option<usize> {
    gates.iter().position(|g| (g.a == cell && g.dir == dir) || (g.b == cell && (g.dir + 2) & 3 == dir))
}

pub fn edge_open(gates: &[Gate], cell: u8, dir: u8, state: u8) -> bool {
    gate_at(gates, cell, dir).map_or(true, |g| gates[g].open == state)
}

struct Gen<'a> {
    inp: &'a Input,
    gates: Vec<Gate>,
    altars: Vec<u8>,
    dist: Vec<u8>,
}

impl Gen<'_> {
    fn altar_ok(&self, c: u8) -> bool {
        (self.inp.gate_cell_ok(c) || c == self.inp.size - 2)
            && !self.inp.roles.contains(&c)
            && c != 8
            && c != 15
            && c != self.inp.cache
            && (0..4).all(|d| gate_at(&self.gates, c, d).is_none())
    }

    /// `ll_bfs`: steps (a flip costs 1) to `goal`; fills `dist` (steps + 1).
    fn bfs(&mut self, start: u8, state: u8, mode: Mode, goal: u8) -> u8 {
        let n = self.inp.size as usize;
        self.dist = vec![0; 60.max(2 * n)];
        let mut found = NONE;
        let s = (start * 2 + state) as usize;
        self.dist[s] = 1;
        let mut q = VecDeque::from([s]);
        while let Some(node) = q.pop_front() {
            let cell = (node >> 1) as u8;
            let st = (node & 1) as u8;
            let step = self.dist[node] + 1;
            if cell == goal && found == NONE {
                found = self.dist[node] - 1;
            }
            for d in 0..6u8 {
                let (next, nst) = if d < 4 {
                    let nx = self.inp.nb[cell as usize][d as usize];
                    if nx == NONE || (mode != Mode::Plain && !edge_open(&self.gates, cell, d, st)) {
                        continue;
                    }
                    (nx, st)
                } else if d == 4 {
                    let nx = self.inp.portal_peer(cell);
                    if nx == NONE {
                        continue;
                    }
                    (nx, st)
                } else {
                    if mode != Mode::Law || !self.altars.contains(&cell) {
                        continue;
                    }
                    (cell, st ^ 1)
                };
                let idx = (next * 2 + nst) as usize;
                if self.dist[idx] != 0 {
                    continue;
                }
                self.dist[idx] = step;
                q.push_back(idx);
            }
        }
        found
    }

    /// `ll_find_candidates`: (parent, child) tour edges, outward by depth.
    fn candidates(&self) -> Vec<(u8, u8)> {
        let inp = self.inp;
        let n = inp.size as usize;
        let mut par = vec![NONE; n];
        let mut depth = vec![0u8; n];
        par[inp.entry as usize] = inp.entry;
        let mut q = VecDeque::from([inp.entry]);
        while let Some(at) = q.pop_front() {
            for d in 0..4 {
                let nx = inp.nb[at as usize][d];
                if nx != NONE && par[nx as usize] == NONE {
                    par[nx as usize] = at;
                    depth[nx as usize] = depth[at as usize] + 1;
                    q.push_back(nx);
                }
            }
        }
        let mut tour = vec![false; n];
        for &t in inp.roles.iter().chain(std::iter::once(&(inp.size - 2))) {
            if t >= inp.size || par[t as usize] == NONE {
                continue;
            }
            let mut at = t;
            while at != inp.entry {
                tour[at as usize] = true;
                at = par[at as usize];
            }
        }
        let mut out = vec![];
        for dep in 1..30u8 {
            for c in 0..inp.size {
                let p = par[c as usize];
                if tour[c as usize] && depth[c as usize] == dep && depth[p as usize] >= 2
                    && inp.gate_cell_ok(c) && inp.gate_cell_ok(p)
                {
                    out.push((p, c));
                }
            }
        }
        out
    }

    /// `ll_label`: flood the region holding `seed`; nearest legal altar.
    fn label(&self, comp: &mut [u8], seed: u8, label: u8) -> Option<u8> {
        let mut altar = None;
        let mut depth = vec![0u8; self.inp.size as usize];
        comp[seed as usize] = label;
        let mut q = VecDeque::from([seed]);
        while let Some(at) = q.pop_front() {
            if altar.is_none() && depth[at as usize] <= ALTAR_REACH && self.altar_ok(at) {
                altar = Some(at);
            }
            for d in 0..5u8 {
                let next = if d < 4 {
                    let n = self.inp.nb[at as usize][d as usize];
                    if n == NONE || gate_at(&self.gates, at, d).is_some() {
                        continue;
                    }
                    n
                } else {
                    let n = self.inp.portal_peer(at);
                    if n == NONE {
                        continue;
                    }
                    n
                };
                if comp[next as usize] != NONE {
                    continue;
                }
                comp[next as usize] = label;
                depth[next as usize] = depth[at as usize] + 1;
                q.push_back(next);
            }
        }
        altar
    }

    /// `ll_tour`: director-order tour, best cost per Law state per leg.
    fn tour(&mut self, mode: Mode) -> u8 {
        let inp = self.inp;
        let order = [
            inp.roles[0],
            if inp.order == 1 { inp.roles[2] } else { inp.roles[1] },
            if inp.order == 1 { inp.roles[1] } else { inp.roles[2] },
            inp.roles[3],
            inp.roles[4],
            inp.roles[5],
            inp.roles[6],
            inp.size - 2,
        ];
        let mut cost = [0u16, 0xFFFF];
        let mut at = inp.entry;
        for &next in &order {
            let mut nc = [0xFFFFu16; 2];
            for s in 0..2u8 {
                if cost[s as usize] == 0xFFFF {
                    continue;
                }
                self.bfs(at, s, mode, next);
                for s2 in 0..2 {
                    let d = self.dist[next as usize * 2 + s2] as u16;
                    if d != 0 && cost[s as usize] + d - 1 < nc[s2] {
                        nc[s2] = cost[s as usize] + d - 1;
                    }
                }
            }
            cost = nc;
            at = next;
        }
        let best = cost[0].min(cost[1]);
        if best > 250 { NONE } else { best as u8 }
    }

    /// `ll_place_altars`.
    fn place_altars(&mut self) -> bool {
        let inp = self.inp;
        self.altars.clear();
        let mut comp = vec![NONE; inp.size as usize];
        let mut label = 0;
        let anchors: Vec<u8> = self.gates.iter().flat_map(|g| [g.a, g.b]).chain(0..inp.size).collect();
        for anchor in anchors {
            if comp[anchor as usize] != NONE {
                continue;
            }
            if self.altars.len() > MAX_GATES {
                return false;
            }
            match self.label(&mut comp, anchor, label) {
                Some(a) => self.altars.push(a),
                None => return false,
            }
            label += 1;
        }
        true
    }

    fn try_place(&mut self, want: u8, cand: &[(u8, u8)], plain: u8, plain_tour: u8) -> Option<(u8, u8)> {
        let inp = self.inp;
        self.gates.clear();
        self.altars.clear();
        let n = cand.len() as u8;
        if n < want {
            return None;
        }
        for g in 0..want {
            let lo = (g * n) / want;
            let hi = ((g + 1) * n) / want;
            if hi <= lo {
                return None;
            }
            let span = hi - lo;
            let off = inp.mix.wrapping_add(g * 5) % span;
            let mut placed = false;
            for t in 0..span {
                let (a, b) = cand[(lo + (off + t) % span) as usize];
                if self.gates[..g as usize].iter().any(|x| x.a == a || x.a == b || x.b == a || x.b == b) {
                    continue;
                }
                let dir = (0..4).find(|&d| inp.nb[a as usize][d as usize] == b).unwrap_or(4);
                self.gates.truncate(g as usize);
                self.gates.push(Gate { a, b, dir, open: (g & 1) ^ 1 });
                if self.place_altars() {
                    placed = true;
                    break;
                }
            }
            if !placed {
                return None;
            }
        }
        let sanctuary = inp.size - 2;
        self.bfs(inp.entry, 0, Mode::Frozen, sanctuary);
        let reached = |dist: &[u8], c: u8| dist[2 * c as usize] != 0 || dist[2 * c as usize + 1] != 0;
        if inp.roles.iter().all(|&r| reached(&self.dist, r)) && reached(&self.dist, sanctuary) {
            return None;
        }
        let law = self.bfs(inp.entry, 0, Mode::Law, sanctuary);
        if law == NONE {
            return None;
        }
        if (0..inp.size as usize).any(|c| self.dist[2 * c] == 0 && self.dist[2 * c + 1] == 0) {
            return None;
        }
        if law.wrapping_sub(plain) > boss_slack(inp.bb) {
            return None;
        }
        if law as u16 * 2 > plain as u16 * 3 {
            return None;
        }
        let tour = self.tour(Mode::Law);
        if tour == NONE || tour.wrapping_sub(plain_tour) as u32 > tour_slack(inp.bb) {
            return None;
        }
        Some((law, tour))
    }
}

/// Argon's direct-route cap on extra room steps (spec §9).
pub fn boss_slack(bb: u8) -> u8 {
    match bb {
        0..=2 => 4,
        3..=5 => 6,
        _ => 7,
    }
}

/// `ll_generate`.
pub fn generate(inp: &Input) -> LawLock {
    let mut gen = Gen { inp, gates: vec![], altars: vec![], dist: vec![] };
    let sanctuary = inp.size - 2;
    let plain = gen.bfs(inp.entry, 0, Mode::Plain, sanctuary);
    let plain_tour = gen.tour(Mode::Plain);
    let none = LawLock { gates: vec![], altars: vec![], plain_boss: plain, law_boss: plain, plain_tour, law_tour: plain_tour };
    let mut want: u8 = match inp.bb {
        0 => 0,
        1..=2 => 1,
        3..=5 => 2,
        _ => 3,
    };
    if want == 0 || inp.size < 8 || plain == NONE {
        return none;
    }
    let cand = gen.candidates();
    while want > 0 {
        if let Some((law, law_tour)) = gen.try_place(want, &cand, plain, plain_tour) {
            return LawLock { gates: gen.gates, altars: gen.altars, plain_boss: plain, law_boss: law, plain_tour, law_tour };
        }
        want -= 1;
    }
    none
}

/// Shortest required walk in room steps (flips are free): from the entry,
/// visit every mission objective (Sigil/Warden in director order, Deep
/// Switch before Deep Gate) and end at the sanctuary. `law = None` measures
/// the plain maze. Bitmask BFS over (cell, Law state, objective mask).
pub fn tour_steps(inp: &Input, missions: &Missions, law: Option<&LawLock>) -> u32 {
    let (first, second) = missions.branch();
    // Objective bits: 0 first branch, 1 second branch (after 0), 2 trial,
    // 3 waystone, 4 deep warden, 5 deep switch, 6 deep gate (after 5).
    let obj = [first, second, missions.trial(), inp.roles[3], inp.roles[4], inp.roles[5], inp.roles[6]];
    let full: u8 = 0x7F;
    let sanctuary = inp.size - 2;
    let take = |cell: u8, mask: u8| -> u8 {
        let mut m = mask;
        for (bit, &c) in obj.iter().enumerate() {
            if c != cell {
                continue;
            }
            let ok = match bit {
                1 => m & 1 != 0,
                6 => m & 0x20 != 0,
                _ => true,
            };
            if ok {
                m |= 1 << bit;
            }
        }
        m
    };
    let n = inp.size as usize;
    let idx = |c: u8, s: u8, m: u8| ((c as usize * 2 + s as usize) << 7) | m as usize;
    let mut dist = vec![u32::MAX; n * 2 * 128];
    let start = (inp.entry, 0u8, take(inp.entry, 0));
    dist[idx(start.0, start.1, start.2)] = 0;
    let mut dq = VecDeque::from([start]);
    let gates: &[Gate] = law.map_or(&[], |l| &l.gates);
    let altars: &[u8] = law.map_or(&[], |l| &l.altars);
    while let Some((c, s, m)) = dq.pop_front() {
        let d0 = dist[idx(c, s, m)];
        if c == sanctuary && m == full {
            return d0;
        }
        if altars.contains(&c) {
            let i = idx(c, s ^ 1, m);
            if dist[i] > d0 {
                dist[i] = d0;
                dq.push_front((c, s ^ 1, m));
            }
        }
        let mut step = |nx: u8| {
            let nm = take(nx, m);
            let i = idx(nx, s, nm);
            if dist[i] > d0 + 1 {
                dist[i] = d0 + 1;
                dq.push_back((nx, s, nm));
            }
        };
        for d in 0..4u8 {
            let nx = inp.nb[c as usize][d as usize];
            if nx != NONE && edge_open(gates, c, d, s) {
                step(nx);
            }
        }
        let p = inp.portal_peer(c);
        if p != NONE {
            step(p);
        }
    }
    u32::MAX
}

/// Argon's mission-tour caps (spec §9): extra room steps over the plain
/// tour, by stage band.
pub fn tour_slack(bb: u8) -> u32 {
    match bb {
        0..=2 => 6,
        3..=5 => 10,
        _ => 12,
    }
}

/// Every softlock / pacing property for one generated dungeon.
pub fn validate(inp: &Input, missions: &Missions, law: &LawLock) -> Result<(), String> {
    let n = inp.size;
    // Product graph from (entry, WAX): every (cell, state) node reached can
    // still reach every cell (undirected graph + one altar per region).
    let mut seen = vec![false; n as usize * 2];
    let mut q = VecDeque::from([(inp.entry, 0u8)]);
    seen[inp.entry as usize * 2] = true;
    while let Some((c, s)) = q.pop_front() {
        let mut nexts = vec![];
        for d in 0..4u8 {
            let nx = inp.nb[c as usize][d as usize];
            if nx != NONE && edge_open(&law.gates, c, d, s) {
                nexts.push((nx, s));
            }
        }
        if inp.portal_peer(c) != NONE {
            nexts.push((inp.portal_peer(c), s));
        }
        if law.altars.contains(&c) {
            nexts.push((c, s ^ 1));
        }
        for (nx, ns) in nexts {
            if !seen[nx as usize * 2 + ns as usize] {
                seen[nx as usize * 2 + ns as usize] = true;
                q.push_back((nx, ns));
            }
        }
    }
    for c in 0..n as usize {
        for s in 0..2 {
            if seen[c * 2 + s] && law.gates.is_empty() && s == 1 {
                return Err("state 1 reachable without a Law Lock".into());
            }
        }
        if !seen[c * 2] && !seen[c * 2 + 1] {
            return Err(format!("cell {c} unreachable"));
        }
    }
    // Every region (gates as walls) holds exactly the altar flip it needs.
    for g in &law.gates {
        for cell in [g.a, g.b] {
            if cell == inp.roles[5] || cell == inp.roles[6] || cell == inp.entry || cell >= n - 3 || cell < 3 {
                return Err(format!("gate on forbidden cell {cell}"));
            }
        }
        if inp.nb[g.a as usize][g.dir as usize] != g.b {
            return Err("gate is not a maze edge".into());
        }
    }
    for &a in &law.altars {
        if inp.roles.contains(&a) || a < 3 || a == 8 || a == 15 || a == inp.cache || a == inp.entry || (a >= n - 3 && a != n - 2) {
            return Err(format!("altar on forbidden cell {a}"));
        }
    }
    if !law.gates.is_empty() {
        if law.law_boss as u16 * 2 > law.plain_boss as u16 * 3 {
            return Err(format!("route {} > 1.5x plain {}", law.law_boss, law.plain_boss));
        }
        if law.law_boss > law.plain_boss + boss_slack(inp.bb) {
            return Err(format!("route {} > plain {} + {}", law.law_boss, law.plain_boss, boss_slack(inp.bb)));
        }
        let plain = tour_steps(inp, missions, None);
        let with = tour_steps(inp, missions, Some(law));
        if with == u32::MAX || with > plain + tour_slack(inp.bb) {
            return Err(format!("tour {with} vs plain {plain} exceeds +{}", tour_slack(inp.bb)));
        }
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn seeds() -> impl Iterator<Item = u32> {
        (0..3000u32).map(|i| i.wrapping_mul(2654435761).wrapping_add(12345))
    }

    #[test]
    fn every_stage_and_seed_is_softlock_free_and_within_caps() {
        let mut gated = [0u32; 9];
        let mut gates = [0u32; 9];
        let mut worst = [0u32; 9];
        let mut longest = [0u32; 9];
        for bb in 0..9u8 {
            for seed in seeds() {
                let (inp, missions) = Input::for_seed(seed, bb);
                let law = generate(&inp);
                if let Err(e) = validate(&inp, &missions, &law) {
                    panic!("seed {seed:#010x} stage {}: {e} ({law:?})", bb + 1);
                }
                if !law.gates.is_empty() {
                    let b = bb as usize;
                    gated[b] += 1;
                    gates[b] += law.gates.len() as u32;
                    let plain = tour_steps(&inp, &missions, None);
                    let with = tour_steps(&inp, &missions, Some(&law));
                    worst[b] = worst[b].max(with - plain);
                    longest[b] = longest[b].max(with);
                }
            }
        }
        assert_eq!(gated[0], 0, "Stage 1 stays Law-free");
        for bb in 1..9 {
            // Law Lock must actually happen in most dungeons (Stage 2's
            // 21-cell maze has the fewest legal altar rooms).
            let floor = if bb == 1 { 35 } else { 60 };
            assert!(gated[bb] * 100 >= 3000 * floor, "stage {} gated only {}/3000", bb + 1, gated[bb]);
        }
        eprintln!("gated per stage {gated:?}\ngates {gates:?}\nworst tour overhead {worst:?}\nlongest tour {longest:?}");
    }

    #[test]
    fn plain_tour_matches_a_hand_count() {
        // The tour BFS without Law must be at least the direct route.
        for seed in seeds().take(200) {
            for bb in 0..9 {
                let (inp, missions) = Input::for_seed(seed, bb);
                let law = generate(&inp);
                assert!(tour_steps(&inp, &missions, None) >= law.plain_boss as u32);
            }
        }
    }
}

