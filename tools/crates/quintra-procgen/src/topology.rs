//! Dungeon topology reference: the seed-folded 6x5 snake maze, the seeded
//! entry cell and the mission graph.
//!
//! Mirrors `src/game/run_state_topology.c`, `run_state_entry.c` and
//! `mission_graph.c` (and the Python mirror `scripts/quintra_topology.py`,
//! which the PyBoy suite checks against the cartridge).

pub const GRID_W: u8 = 6;
pub const GRID_H: u8 = 5;
pub const NONE: u8 = 0xFF;
const STAGE_START: [u8; 9] = [0, 20, 41, 64, 87, 111, 137, 163, 191];
const STAGE_BOSS_ROOM: [u8; 9] = [19, 40, 62, 86, 110, 135, 162, 190, 220];
const FOLD_COLS: [[u8; 4]; 8] = [
    [2, 0, 5, 0],
    [0, 5, 5, 0],
    [0, 0, 5, 0],
    [5, 5, 5, 0],
    [2, 5, 5, 0],
    [0, 5, 4, 0],
    [0, 4, 5, 0],
    [0, 1, 5, 0],
];
const ENTRY_MIN_BOSS_DIST: u8 = 7;
pub const LANDMARKS: [u8; 8] = [0, 2, 5, 8, 11, 15, 17, 23];

/// Number of maze cells in stage `bb` (0-based bosses beaten).
pub fn dungeon_size(bb: u8) -> u8 {
    STAGE_BOSS_ROOM[bb as usize] - STAGE_START[bb as usize] + 1
}

/// Xor of the four run-seed bytes.
pub fn seed_mix(run_seed: u32) -> u8 {
    (run_seed ^ (run_seed >> 8) ^ (run_seed >> 16) ^ (run_seed >> 24)) as u8
}

fn cell_xy(cell: u8) -> (u8, u8) {
    let row = cell / GRID_W;
    let off = cell % GRID_W;
    (if row & 1 == 1 { GRID_W - 1 - off } else { off }, row)
}

fn cell_at(col: u8, row: u8) -> u8 {
    row * GRID_W + if row & 1 == 1 { GRID_W - 1 - col } else { col }
}

/// One seeded dungeon: its size and seed-folded maze adjacency.
#[derive(Clone, Debug)]
pub struct Maze {
    pub run_seed: u32,
    pub bb: u8,
    pub size: u8,
    /// `nb[cell][dir]` for DIR_N/E/S/W, `NONE` when there is no door.
    pub nb: Vec<[u8; 4]>,
}

impl Maze {
    pub fn new(run_seed: u32, bb: u8) -> Maze {
        let size = dungeon_size(bb);
        let fold = (seed_mix(run_seed) ^ bb.wrapping_mul(3)) & 7;
        let fold_col = |upper_row: u8| -> u8 {
            let lower_first = (upper_row + 1) * GRID_W;
            if lower_first >= size {
                return NONE;
            }
            let mut lower_count = (size - lower_first).min(GRID_W);
            let service_first = size - 3;
            if lower_first < service_first && lower_count > service_first - lower_first {
                lower_count = service_first - lower_first;
            }
            let mut col = FOLD_COLS[fold as usize][upper_row as usize];
            if (upper_row + 1) & 1 == 1 {
                col = col.max(GRID_W - lower_count);
            } else if col >= lower_count {
                col = lower_count - 1;
            }
            col
        };
        let neighbor = |cell: u8, dir: u8| -> u8 {
            let (mut col, mut row) = cell_xy(cell);
            let old_row = row;
            match dir {
                0 if row > 0 => row -= 1,
                1 if col < GRID_W - 1 => col += 1,
                2 if row < GRID_H - 1 => row += 1,
                3 if col > 0 => col -= 1,
                _ => return NONE,
            }
            let next = cell_at(col, row);
            if next >= size {
                return NONE;
            }
            if dir == 0 || dir == 2 {
                let upper = if dir == 0 { row } else { old_row };
                if col != fold_col(upper) && !(upper == 0 && col == 1) {
                    return NONE;
                }
            }
            next
        };
        let nb = (0..size)
            .map(|c| [neighbor(c, 0), neighbor(c, 1), neighbor(c, 2), neighbor(c, 3)])
            .collect();
        Maze { run_seed, bb, size, nb }
    }

    pub fn degree(&self, cell: u8) -> u8 {
        self.nb[cell as usize].iter().filter(|&&n| n != NONE).count() as u8
    }

    /// Plain BFS distances over cardinal doors from `start`.
    pub fn distances(&self, start: u8) -> Vec<u8> {
        let mut dist = vec![NONE; self.size as usize];
        let mut queue = std::collections::VecDeque::from([start]);
        dist[start as usize] = 0;
        while let Some(at) = queue.pop_front() {
            for &n in &self.nb[at as usize] {
                if n != NONE && dist[n as usize] == NONE {
                    dist[n as usize] = dist[at as usize] + 1;
                    queue.push_back(n);
                }
            }
        }
        dist
    }

    /// `run_state_dungeon_entry_cell`.
    pub fn entry_cell(&self) -> u8 {
        let size = self.size;
        let dist = self.distances(size - 1);
        let grid_kind = |cell: u8| -> u8 {
            let (col, row) = cell_xy(cell);
            let mut degree = 0;
            for (c, r) in [
                (col as i8, row as i8 - 1),
                (col as i8 + 1, row as i8),
                (col as i8, row as i8 + 1),
                (col as i8 - 1, row as i8),
            ] {
                if c >= 0 && r >= 0 && (c as u8) < GRID_W && (r as u8) < GRID_H
                    && cell_at(c as u8, r as u8) < size
                {
                    degree += 1;
                }
            }
            match degree {
                0..=2 => 0,
                3 => 1,
                _ => 2,
            }
        };
        let ok = |cell: u8| -> bool {
            let d = dist[cell as usize];
            d != NONE && d >= ENTRY_MIN_BOSS_DIST && self.degree(cell) <= 2
                && ![5, 11, 17, 23].contains(&cell)
        };
        let s = self.run_seed;
        let mut mix: u16 = (s as u8) as u16 | (((s >> 8) as u8 as u16) << 8);
        mix ^= ((s >> 16) as u8) as u16 | (((s >> 24) as u8 as u16) << 8);
        mix ^= (self.bb as u16).wrapping_mul(251);
        let rot = (mix % 3) as u8;
        for i in 0..3 {
            let kind = (rot + i) % 3;
            let cands: Vec<u8> = (0..size - 3).filter(|&c| ok(c) && grid_kind(c) == kind).collect();
            if !cands.is_empty() {
                return cands[((mix >> 3) as usize) % cands.len()];
            }
        }
        0
    }
}

/// The seven mission roles: trial, sigil, warden, waystone, deep warden,
/// deep switch, deep gate (the `ll_role` order of `law_lock.h`).
#[derive(Clone, Debug)]
pub struct Missions {
    pub order: u8,
    pub roles: [u8; 7],
}

impl Missions {
    pub fn trial(&self) -> u8 {
        self.roles[0]
    }
    /// Sigil/Warden in the order the director asks for them.
    pub fn branch(&self) -> (u8, u8) {
        if self.order & 1 == 1 {
            (self.roles[2], self.roles[1])
        } else {
            (self.roles[1], self.roles[2])
        }
    }
}

/// `mission_graph_ensure` (without its malformed-topology fallback, which
/// today's mazes never reach).
pub fn mission_graph(m: &Maze, entry: u8) -> Missions {
    let size = m.size;
    let limit = size - 3;
    let mix = seed_mix(m.run_seed).wrapping_add(m.bb.wrapping_mul(41));
    let cache_reserve = (1..=size - 4)
        .rev()
        .find(|&c| !LANDMARKS.contains(&c) && m.degree(c) == 1);
    let reserved = |c: u8| c == entry || c >= limit || LANDMARKS.contains(&c) || Some(c) == cache_reserve;
    let mut seen = vec![false; size as usize];
    let mut queue = vec![entry];
    seen[entry as usize] = true;
    let mut eligible = Vec::new();
    let mut head = 0;
    while head < queue.len() {
        let cell = queue[head];
        head += 1;
        if !reserved(cell) {
            eligible.push(cell);
        }
        let turn = mix.wrapping_add(cell.wrapping_mul(3)) & 3;
        for step in 0..4 {
            let n = m.nb[cell as usize][((turn + step) & 3) as usize];
            if n == NONE || n >= limit || seen[n as usize] {
                continue;
            }
            seen[n as usize] = true;
            queue.push(n);
        }
    }
    let sel: [u8; 7] = if eligible.len() < 7 {
        [1, 3, 4, 6, 7, 9, 10]
    } else {
        std::array::from_fn(|i| eligible[(i * (eligible.len() - 1) + 3) / 6])
    };
    let order = mix & 1;
    let (sigil, warden) = if order == 1 { (sel[2], sel[1]) } else { (sel[1], sel[2]) };
    Missions { order, roles: [sel[0], sigil, warden, sel[3], sel[4], sel[5], sel[6]] }
}

/// `run_state_dungeon_cache_cell`.
pub fn cache_cell(m: &Maze, missions: &Missions) -> u8 {
    let fixed = |c: u8| LANDMARKS.contains(&c) || missions.roles.contains(&c);
    (1..=m.size - 4)
        .rev()
        .find(|&c| !fixed(c) && m.degree(c) == 1)
        .or_else(|| (1..m.size - 3).find(|&c| !fixed(c)))
        .unwrap_or(1)
}
