//! Reference room-tilemap generator — a 1:1 mirror of the deterministic
//! part of `src/game/procgen.c::procgen_generate_current_room` (everything
//! up to and including the tilemap; entity spawns come after and don't
//! touch tiles).
//!
//! RNG call ORDER is part of the contract: one draw per interior floor
//! cell, then shape roll, rubble, blocks, crack — exactly as the C
//! consumes them. `scripts/test_procgen_parity.py` compares this output
//! against the real ROM's WRAM tilemap; the property tests below pin the
//! door-connectivity invariant for every room shape.

use crate::rng::Xorshift32;

pub const ROOM_W: usize = 20;
pub const ROOM_H: usize = 17;

// Tile ids — mirror src/render/tiles.h
pub const BGT_FLOOR: u8 = 1;
pub const BGT_WALL: u8 = 2;
pub const BGT_DOOR: u8 = 3;
pub const HUD_COIN: u8 = 7;
pub const HUD_DIGIT_0: u8 = 9;
pub const BGT_FLOOR2: u8 = 19;
pub const BGT_FLOOR3: u8 = 20;
pub const BGT_PILLAR: u8 = 21;
pub const BGT_CRYSTAL: u8 = 22;
pub const BGT_RUBBLE: u8 = 23;
pub const BGT_WALL_CRACK: u8 = 24;
pub const BGT_BLOCK: u8 = 25;      // crate TL quadrant
pub const BGT_SPIKES: u8 = 31;
pub const BGT_POT: u8 = 32;
pub const BGT_BLOCK_TR: u8 = 28;
pub const BGT_BLOCK_BL: u8 = 29;
pub const BGT_BLOCK_BR: u8 = 30;
pub const BGT_PORTAL: u8 = 34;
pub const BGT_COLOSSUS_VOID: u8 = 55;
pub const BGT_COLOSSUS_SCALE: u8 = 56;
pub const BGT_COLOSSUS_EDGE_L: u8 = 57;
pub const BGT_COLOSSUS_EDGE_R: u8 = 58;
pub const BGT_COLOSSUS_EYE: u8 = 59;
pub const BGT_COLOSSUS_RUNE: u8 = 61;
pub const BGT_COLOSSUS_MAW: u8 = 62;
pub const BGT_COLOSSUS_HORN: u8 = 63;

pub const STAGE_START: [u8; 9] = [0, 10, 21, 34, 46, 59, 74, 88, 103];
pub const STAGE_BOSS_ROOM: [u8; 9] = [9, 20, 32, 45, 58, 72, 87, 102, 118];

pub type Tilemap = [[u8; ROOM_W]; ROOM_H];

/// Mirror of `procgen_room_seed` in procgen.c.
pub fn room_seed(run_seed: u32, biome_id: u8, room_counter: u8) -> u32 {
    run_seed
        ^ ((biome_id as u32) << 16)
        ^ (room_counter as u32).wrapping_mul(0x9E37_79B9)
}

/// Room-role flags derived the same way the C does.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RoomKind {
    pub boss: bool,
    pub miniboss: bool,
    pub shop: bool,
    pub rest: bool,
}

pub fn room_kind(room_counter: u8, bosses_beaten: u8) -> RoomKind {
    let stage = usize::from(bosses_beaten.min(8));
    let start = STAGE_START[stage];
    let boss_room = STAGE_BOSS_ROOM[stage];
    let local = room_counter.saturating_sub(start);
    let size = boss_room - start + 1;
    let boss = room_counter == boss_room;
    let miniboss = !boss && (local == 3 || (size >= 14 && local == 9));
    let shop = !boss && !miniboss && local == size - 3;
    let rest = !boss && room_counter == boss_room - 1;
    RoomKind { boss, miniboss, shop, rest }
}

fn dungeon_neighbor(local: u8, size: u8, dir: u8) -> Option<u8> {
    let mut row = local / 4;
    let offset = local % 4;
    let mut col = if row & 1 != 0 { 3 - offset } else { offset };
    match dir {
        0 if row > 0 => row -= 1,
        1 if col < 3 => col += 1,
        2 if row < 3 => row += 1,
        3 if col > 0 => col -= 1,
        _ => return None,
    }
    let next = row * 4 + if row & 1 != 0 { 3 - col } else { col };
    (next < size).then_some(next)
}

/// Generate the room tilemap for the given run state — the reference for
/// what the cart's WRAM `room_tilemap` holds right after generation.
pub fn generate_tilemap(
    run_seed: u32,
    biome_id: u8,
    room_counter: u8,
    bosses_beaten: u8,
    secret_pending: bool,
) -> Tilemap {
    let kind = room_kind(room_counter, bosses_beaten);
    let seed = room_seed(run_seed, biome_id, room_counter);
    let mut rng = Xorshift32::new(seed);
    let mut m: Tilemap = [[0; ROOM_W]; ROOM_H];

    // ---- Base: border walls + textured floor (one draw per floor cell)
    for y in 0..ROOM_H {
        for x in 0..ROOM_W {
            if y == 0 || y == ROOM_H - 1 || x == 0 || x == ROOM_W - 1 {
                m[y][x] = BGT_WALL;
            } else {
                let r = rng.next_u8();
                m[y][x] = if r < 38 {
                    BGT_FLOOR2
                } else if r < 64 {
                    BGT_FLOOR3
                } else {
                    BGT_FLOOR
                };
            }
        }
    }

    if !kind.boss {
        // Doors are 2 tiles (16px) wide — hero-sized, and wide enough
        // for the feet-anchored 12px collision box.
        m[0][9] = BGT_DOOR;
        m[0][10] = BGT_DOOR;
        m[ROOM_H - 1][9] = BGT_DOOR;
        m[ROOM_H - 1][10] = BGT_DOOR;
        m[8][0] = BGT_DOOR;
        m[9][0] = BGT_DOOR;
        m[8][ROOM_W - 1] = BGT_DOOR;
        m[9][ROOM_W - 1] = BGT_DOOR;

        // The dungeon uses the reciprocal 4x4 geography shown on the
        // cartridge Compass. Prefix cells outside the active stage are walls,
        // not four cosmetic doors that all advance one counter.
        let stage = usize::from(bosses_beaten.min(8));
        let local = room_counter.saturating_sub(STAGE_START[stage]);
        let size = STAGE_BOSS_ROOM[stage] - STAGE_START[stage] + 1;
        if dungeon_neighbor(local, size, 0).is_none() {
            m[0][9] = BGT_WALL;
            m[0][10] = BGT_WALL;
        }
        if dungeon_neighbor(local, size, 1).is_none() {
            m[8][ROOM_W - 1] = BGT_WALL;
            m[9][ROOM_W - 1] = BGT_WALL;
        }
        if dungeon_neighbor(local, size, 2).is_none() {
            m[ROOM_H - 1][9] = BGT_WALL;
            m[ROOM_H - 1][10] = BGT_WALL;
        }
        if dungeon_neighbor(local, size, 3).is_none() {
            m[8][0] = BGT_WALL;
            m[9][0] = BGT_WALL;
        }

        // ---- Interior shape (8 layouts; lanes cols 9-11 / rows 7-9 clear)
        let shape = rng.range_u8(11);   // 11 interior layouts
        match shape {
            1 => {
                for (y, x) in [(4, 4), (4, 15), (13, 4), (13, 15)] {
                    m[y][x] = BGT_PILLAR;
                }
            }
            2 => {
                let mut placed = 0;
                let mut tries = 12;
                while placed < 4 && tries > 0 {
                    tries -= 1;
                    let cx = (2 + rng.range_u8(ROOM_W as u8 - 4)) as usize;
                    let cy = (2 + rng.range_u8(ROOM_H as u8 - 4)) as usize;
                    if (9..=11).contains(&cx) || (7..=9).contains(&cy) {
                        continue;
                    }
                    m[cy][cx] = BGT_CRYSTAL;
                    placed += 1;
                }
            }
            3 => {
                for (y, x) in [(4, 4), (4, 5), (4, 14), (4, 15),
                               (13, 4), (13, 5), (13, 14), (13, 15)] {
                    m[y][x] = BGT_PILLAR;
                }
            }
            4 => {
                for i in 4..=15usize {
                    if (9..=11).contains(&i) { continue; }
                    m[4][i] = BGT_PILLAR;
                    m[12][i] = BGT_PILLAR;
                }
                for i in 4..=12usize {
                    if (7..=9).contains(&i) { continue; }
                    m[i][4] = BGT_PILLAR;
                    m[i][15] = BGT_PILLAR;
                }
            }
            5 => {
                for i in 2..=14usize {
                    if (7..=9).contains(&i) { continue; }
                    m[i][5] = BGT_PILLAR;
                    m[i][14] = BGT_PILLAR;
                }
            }
            6 => {
                for (y, x) in [(3, 3), (4, 4), (5, 5),
                               (3, 16), (4, 15), (5, 14),
                               (13, 3), (12, 4), (11, 5),
                               (13, 16), (12, 15), (11, 14)] {
                    m[y][x] = BGT_CRYSTAL;
                }
            }
            7 => {
                for x in [3usize, 5, 7, 13, 15, 17] {
                    m[5][x] = BGT_PILLAR;
                    m[11][x] = BGT_PILLAR;
                }
            }
            8 => {
                // Serpentine: two staggered half-walls, N/S lane (9-11) clear.
                for i in 2..=12usize {
                    if i < 9 || i > 11 { m[5][i] = BGT_PILLAR; }
                }
                for i in 7..=17usize {
                    if i < 9 || i > 11 { m[11][i] = BGT_PILLAR; }
                }
            }
            9 => {
                for x in [4usize, 8, 12, 16] {
                    m[4][x] = BGT_PILLAR;
                    m[12][x] = BGT_PILLAR;
                }
            }
            10 => {
                // Central chamber: pillar ring with door-lane openings
                // (cols 9-11, rows 7-9).
                for i in 6..=13usize {
                    if i < 9 || i > 11 {
                        m[6][i] = BGT_PILLAR;
                        m[10][i] = BGT_PILLAR;
                    }
                }
                for i in 6..=10usize {
                    if i < 7 || i > 9 {
                        m[i][6] = BGT_PILLAR;
                        m[i][13] = BGT_PILLAR;
                    }
                }
            }
            _ => {} // 0: open room
        }

        // ---- Rubble x3
        for _ in 0..3 {
            let rx = (2 + rng.range_u8(ROOM_W as u8 - 4)) as usize;
            let ry = (2 + rng.range_u8(ROOM_H as u8 - 4)) as usize;
            if m[ry][rx] == BGT_FLOOR {
                m[ry][rx] = BGT_RUBBLE;
            }
        }

        // ---- Pushable crates 0-2, hero-sized (2x2 tiles)
        let nb = rng.next_u8() % 3;
        for _ in 0..nb {
            let bx = (3 + rng.range_u8(ROOM_W as u8 - 6)) as usize;
            let by = (3 + rng.range_u8(ROOM_H as u8 - 6)) as usize;
            if (8..=11).contains(&bx) || (6..=9).contains(&by) {
                continue;
            }
            if bx + 1 >= ROOM_W - 1 || by + 1 >= ROOM_H - 1 {
                continue;
            }
            if m[by][bx] == BGT_FLOOR
                && m[by][bx + 1] == BGT_FLOOR
                && m[by + 1][bx] == BGT_FLOOR
                && m[by + 1][bx + 1] == BGT_FLOOR
            {
                m[by][bx] = BGT_BLOCK;
                m[by][bx + 1] = BGT_BLOCK_TR;
                m[by + 1][bx] = BGT_BLOCK_BL;
                m[by + 1][bx + 1] = BGT_BLOCK_BR;
            }
        }

        // ---- Secret cracked wall (~half of rooms)
        if rng.next_u8() & 0x01 == 0 {
            let side = rng.next_u8() & 0x03;
            match side {
                0 => {
                    let pos = (2 + rng.range_u8(ROOM_W as u8 - 4)) as usize;
                    if pos != 9 && pos != 10 { m[0][pos] = BGT_WALL_CRACK; }
                }
                1 => {
                    let pos = (2 + rng.range_u8(ROOM_W as u8 - 4)) as usize;
                    if pos != 9 && pos != 10 { m[ROOM_H - 1][pos] = BGT_WALL_CRACK; }
                }
                2 => {
                    let pos = (2 + rng.range_u8(ROOM_H as u8 - 4)) as usize;
                    if pos != 8 && pos != 9 { m[pos][0] = BGT_WALL_CRACK; }
                }
                _ => {
                    let pos = (2 + rng.range_u8(ROOM_H as u8 - 4)) as usize;
                    if pos != 8 && pos != 9 { m[pos][ROOM_W - 1] = BGT_WALL_CRACK; }
                }
            }
        }

        // ---- Spike patch (~1/4 of rooms): 2x2 hazard cluster, lanes clear.
        // One roll + two position draws — must match procgen.c exactly.
        if rng.next_u8() & 0x03 == 0 {
            let spx = (3 + rng.range_u8(ROOM_W as u8 - 7)) as usize;
            let spy = (3 + rng.range_u8(ROOM_H as u8 - 7)) as usize;
            if !(8..=11).contains(&spx) && !(6..=9).contains(&spy) {
                for sdy in 0..2 {
                    for sdx in 0..2 {
                        let ft = m[spy + sdy][spx + sdx];
                        if ft == BGT_FLOOR || ft == BGT_FLOOR2 || ft == BGT_FLOOR3 {
                            m[spy + sdy][spx + sdx] = BGT_SPIKES;
                        }
                    }
                }
            }
        }

        // ---- Breakable pots (0-2): interior floor, lanes clear. One count
        // draw + 2 per pot — must match procgen.c exactly.
        {
            let np = rng.next_u8() % 3;
            for _ in 0..np {
                let ptx = (2 + rng.range_u8(ROOM_W as u8 - 4)) as usize;
                let pty = (2 + rng.range_u8(ROOM_H as u8 - 4)) as usize;
                if (9..=11).contains(&ptx) || (7..=9).contains(&pty) {
                    continue;
                }
                let ft = m[pty][ptx];
                if ft == BGT_FLOOR || ft == BGT_FLOOR2 || ft == BGT_FLOOR3 {
                    m[pty][ptx] = BGT_POT;
                }
            }
        }
    }

    // ---- Post-base overlays (seed-independent tile stamps), same order
    // as the C: vault first (early-returns before the role branches).
    if secret_pending && !kind.boss {
        for i in 7..=12usize {
            m[5][i] = BGT_CRYSTAL;
            m[11][i] = BGT_CRYSTAL;
        }
        m[7][6] = BGT_CRYSTAL;
        m[9][6] = BGT_CRYSTAL;
        m[7][13] = BGT_CRYSTAL;
        m[9][13] = BGT_CRYSTAL;
        return m;
    }

    if kind.rest {
        m[6][7] = BGT_CRYSTAL;
        m[6][12] = BGT_CRYSTAL;
        m[10][7] = BGT_CRYSTAL;
        m[10][12] = BGT_CRYSTAL;
        return m;
    }

    if kind.shop {
        // Mirror procgen.c's non-RNG premium shelf: the run seed chooses
        // temporary Surge ($20) or permanent vitality ($40), while the other
        // two offers stay fixed. This is tile-level parity only; entities are
        // validated by the live shop contract.
        let premium_price = if (((run_seed as u8) ^ bosses_beaten) & 1) != 0 {
            20
        } else {
            40
        };
        m[10][6] = HUD_COIN;
        m[10][7] = HUD_DIGIT_0 + 1;
        m[10][8] = HUD_DIGIT_0;
        m[10][9] = HUD_COIN;
        m[10][10] = HUD_DIGIT_0 + 2;
        m[10][11] = HUD_DIGIT_0 + 5;
        m[10][12] = HUD_COIN;
        m[10][13] = HUD_DIGIT_0 + premium_price / 10;
        m[10][14] = HUD_DIGIT_0;
    }

    // Mirror procgen.c's rift apron and body-width route to the central lane.
    let stage = usize::from(bosses_beaten.min(8));
    let local = room_counter.saturating_sub(STAGE_START[stage]);
    if bosses_beaten > 0 && (local == 2 || local == 4)
    {
        let px = if seed & 4 != 0 { 5 } else { 14 };
        let py = if seed & 8 != 0 { 4 } else { 12 };
        let (left, right) = if px < 10 { (px - 2, 10) } else { (9, px) };
        let (top, bottom) = if py < 8 { (py - 2, 8) } else { (7, py) };
        for y in py - 2..=py {
            for x in left..=right {
                m[y as usize][x as usize] = BGT_FLOOR;
            }
        }
        for y in top..=bottom {
            for x in 9..=11 {
                m[y as usize][x as usize] = BGT_FLOOR;
            }
        }
        for y in py - 2..=py {
            for x in px - 2..=px {
                m[y as usize][x as usize] = BGT_FLOOR;
            }
        }
        m[py as usize][px as usize] = BGT_PORTAL;
    }

    // room.c applies the opening Crystal Colossus's projection after the
    // procgen base is complete. The parity dump represents the final exposed
    // WRAM tilemap, so mirror that deterministic 112x72 stamp here rather
    // than exempting boss tiles in the cross-language check. Mire is dynamic
    // and Void has its own live-ROM contracts; neither is part of this fixed
    // stage-zero reference case.
    if kind.boss && bosses_beaten % 9 == 0 {
        let widths = [8usize, 12, 14, 14, 14, 14, 14, 12, 8];
        for (y, &width) in widths.iter().enumerate() {
            let left = 10 - width / 2;
            for x in 0..width {
                let tile = if x == 0 {
                    BGT_COLOSSUS_EDGE_L
                } else if x == width - 1 {
                    BGT_COLOSSUS_EDGE_R
                } else if y == 0 && (x == 1 || x == width - 2) {
                    BGT_COLOSSUS_HORN
                } else if y == 2 && (x == 3 || x == width - 4) {
                    BGT_COLOSSUS_EYE
                } else if y == 4 && x >= width / 2 - 2 && x <= width / 2 + 1 {
                    BGT_COLOSSUS_MAW
                } else if y >= 6 && (x + y) & 2 != 0 {
                    BGT_COLOSSUS_VOID
                } else if (x + y) & 3 == 0 {
                    BGT_COLOSSUS_RUNE
                } else {
                    BGT_COLOSSUS_SCALE
                };
                m[y + 3][left + x] = tile;
            }
        }
    }

    m
}

/// Mirror of room.c::room_tile_walkable.
pub fn walkable(t: u8) -> bool {
    t == BGT_FLOOR
        || t == BGT_FLOOR2
        || t == BGT_FLOOR3
        || t == BGT_RUBBLE
        || t == BGT_DOOR
        || t == BGT_SPIKES
        || t == BGT_PORTAL
        || (BGT_COLOSSUS_VOID..=BGT_COLOSSUS_HORN).contains(&t)
        || t == HUD_COIN
        || (HUD_DIGIT_0..=HUD_DIGIT_0 + 9).contains(&t)
}

/// Passable if walkable OR destructible-by-shots (crystals shatter).
pub fn passable_with_shots(t: u8) -> bool {
    walkable(t) || t == BGT_CRYSTAL
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::collections::BTreeSet;

    fn flood(m: &Tilemap, start: (usize, usize), pass: fn(u8) -> bool) -> Vec<(usize, usize)> {
        let mut seen = vec![start];
        let mut stack = vec![start];
        while let Some((y, x)) = stack.pop() {
            let mut push = |ny: usize, nx: usize| {
                if pass(m[ny][nx]) && !seen.contains(&(ny, nx)) {
                    seen.push((ny, nx));
                    stack.push((ny, nx));
                }
            };
            if y > 0 { push(y - 1, x); }
            if y + 1 < ROOM_H { push(y + 1, x); }
            if x > 0 { push(y, x - 1); }
            if x + 1 < ROOM_W { push(y, x + 1); }
        }
        seen
    }

    const DOORS: [(usize, usize); 8] = [
        (0, 9), (0, 10),
        (ROOM_H - 1, 9), (ROOM_H - 1, 10),
        (8, 0), (9, 0),
        (8, ROOM_W - 1), (9, ROOM_W - 1),
    ];

    fn open_doors(m: &Tilemap) -> Vec<(usize, usize)> {
        DOORS.into_iter().filter(|&(y, x)| m[y][x] == BGT_DOOR).collect()
    }

    #[test]
    fn deterministic() {
        for seed in [1u32, 0xDEADBEEF, 12345] {
            assert_eq!(
                generate_tilemap(seed, 0, 1, 0, false),
                generate_tilemap(seed, 0, 1, 0, false),
            );
        }
    }

    /// The load-bearing invariant behind every room shape: every authored
    /// reciprocal graph door stays mutually reachable in every non-boss room —
    /// counting crystals as passable (the player can always shoot through).
    #[test]
    fn all_doors_reachable_across_seeds_and_roles() {
        for seed in 0..400u32 {
            for counter in 1..=6u8 {
                let kind = room_kind(counter, 0);
                if kind.boss { continue; }
                let m = generate_tilemap(seed.wrapping_mul(2654435761) + 7, 0, counter, 0, false);
                let doors = open_doors(&m);
                assert!(!doors.is_empty());
                let reach = flood(&m, doors[0], passable_with_shots);
                for d in doors {
                    assert!(reach.contains(&d),
                        "seed {seed} counter {counter}: door {d:?} unreachable\n{}",
                        dump(&m));
                }
            }
        }
    }

    /// Vault overlays may block lanes with crystals, but never seal authored
    /// graph doors.
    #[test]
    fn vault_rooms_stay_passable() {
        for seed in 0..200u32 {
            let m = generate_tilemap(seed * 31 + 5, 0, 2, 0, true);
            let doors = open_doors(&m);
            assert!(!doors.is_empty());
            let reach = flood(&m, doors[0], passable_with_shots);
            for d in doors {
                assert!(reach.contains(&d), "vault seed {seed}: door {d:?} sealed\n{}", dump(&m));
            }
        }
    }

    /// Door lanes are strictly walkable (no pillars/blocks/crystals) in
    /// plain rooms — shapes must carve around them.
    #[test]
    fn lanes_clear_in_plain_rooms() {
        for seed in 0..400u32 {
            for counter in [1u8, 2] {
                let m = generate_tilemap(seed * 97 + 13, 0, counter, 0, false);
                for y in 1..ROOM_H - 1 {
                    for x in 9..=11usize {
                        assert!(walkable(m[y][x]),
                            "seed {seed}: N/S lane blocked at ({y},{x})\n{}", dump(&m));
                    }
                }
                for x in 1..ROOM_W - 1 {
                    for y in 7..=9usize {
                        assert!(walkable(m[y][x]),
                            "seed {seed}: E/W lane blocked at ({y},{x})\n{}", dump(&m));
                    }
                }
            }
        }
    }

    /// Boss rooms are sealed: base walls only, no doors, no decor.
    #[test]
    fn boss_rooms_are_sealed() {
        let m = generate_tilemap(0xABCD, 0, STAGE_BOSS_ROOM[0], 0, false);
        for d in DOORS {
            assert_eq!(m[d.0][d.1], BGT_WALL, "boss room has an open door at {d:?}");
        }
    }

    #[test]
    fn nonlinear_rifts_have_a_clear_hero_footprint() {
        for seed in 0..400u32 {
            for counter in [STAGE_START[1] + 2, STAGE_START[1] + 4] {
                let m = generate_tilemap(seed.wrapping_mul(97) + 13, 0, counter, 1, false);
                let portal = (0..ROOM_H).flat_map(|y| (0..ROOM_W).map(move |x| (y, x)))
                    .find(|&(y, x)| m[y][x] == BGT_PORTAL)
                    .expect("late dungeon rift missing");
                let (py, px) = portal;
                assert!(px >= 1 && py >= 1);
                for y in py - 1..=py {
                    for x in px - 1..=px {
                        assert!(walkable(m[y][x]),
                            "seed {seed} room {counter}: rift footprint blocked at ({y},{x})\\n{}",
                            dump(&m));
                    }
                }
            }
        }
    }

    /// Procgen must change decisions that affect play, not merely repaint the
    /// floor texture.  Keep this deliberately statistical and conservative:
    /// exact seeds remain deterministic, while a broad seed corpus must cover
    /// secrets on every wall, both merchant forks, all four nonlinear-rift
    /// anchors, and a healthy number of distinct obstacle/prop silhouettes.
    #[test]
    fn seed_corpus_has_meaningful_variety() {
        let mut room_signatures = BTreeSet::new();
        let mut secret_sides = BTreeSet::new();
        let mut premium_prices = BTreeSet::new();
        let mut rift_anchors = BTreeSet::new();
        let mut crate_rooms = 0;
        let mut spike_rooms = 0;
        let mut pot_rooms = 0;

        for ordinal in 0..512u32 {
            let seed = ordinal.wrapping_mul(0x9E37_79B9).wrapping_add(7);
            let room = generate_tilemap(seed, 0, 1, 0, false);
            let mut signature = [0u8; ROOM_W * ROOM_H];
            for (index, &tile) in room.iter().flatten().enumerate() {
                // Floor texture and walkable rubble are visual seasoning.
                // Everything else changes cover, collision, interaction, or
                // route knowledge and therefore belongs in the signature.
                signature[index] = match tile {
                    BGT_FLOOR | BGT_FLOOR2 | BGT_FLOOR3 | BGT_RUBBLE => BGT_FLOOR,
                    _ => tile,
                };
            }
            room_signatures.insert(signature);
            crate_rooms += usize::from(room.iter().flatten().any(|&t| t == BGT_BLOCK));
            spike_rooms += usize::from(room.iter().flatten().any(|&t| t == BGT_SPIKES));
            pot_rooms += usize::from(room.iter().flatten().any(|&t| t == BGT_POT));

            if room[0].contains(&BGT_WALL_CRACK) { secret_sides.insert(0u8); }
            if room[ROOM_H - 1].contains(&BGT_WALL_CRACK) { secret_sides.insert(1u8); }
            if room.iter().any(|row| row[0] == BGT_WALL_CRACK) { secret_sides.insert(2u8); }
            if room.iter().any(|row| row[ROOM_W - 1] == BGT_WALL_CRACK) {
                secret_sides.insert(3u8);
            }

            let shop = generate_tilemap(seed, 0, STAGE_BOSS_ROOM[0] - 2, 0, false);
            premium_prices.insert((shop[10][13] - HUD_DIGIT_0) * 10
                + (shop[10][14] - HUD_DIGIT_0));

            let rift = generate_tilemap(seed, 0, STAGE_START[1] + 2, 1, false);
            let anchor = (0..ROOM_H)
                .flat_map(|y| (0..ROOM_W).map(move |x| (x, y)))
                .find(|&(x, y)| rift[y][x] == BGT_PORTAL)
                .expect("late dungeon rift missing");
            rift_anchors.insert(anchor);
        }

        assert!(room_signatures.len() >= 128,
            "seed corpus collapsed to {} meaningful room silhouettes",
            room_signatures.len());
        assert_eq!(secret_sides, BTreeSet::from([0, 1, 2, 3]));
        assert_eq!(premium_prices, BTreeSet::from([20, 40]));
        assert_eq!(rift_anchors,
            BTreeSet::from([(5, 4), (5, 12), (14, 4), (14, 12)]));
        // Loose props/hazards should be optional rather than universal, but
        // common enough that a 512-seed run does not read as empty rooms.
        for (label, count) in [("crates", crate_rooms), ("spikes", spike_rooms),
                               ("pots", pot_rooms)] {
            assert!((32..480).contains(&count),
                "{label} appeared in {count}/512 rooms");
        }

        eprintln!(
            "procgen variety: {} meaningful silhouettes/512, crates={}, spikes={}, pots={}, secrets=4 sides, shops=2 forks, rifts=4 anchors",
            room_signatures.len(), crate_rooms, spike_rooms, pot_rooms,
        );
    }

    fn dump(m: &Tilemap) -> String {
        m.iter()
            .map(|row| {
                row.iter()
                    .map(|&t| match t {
                        BGT_WALL => '#',
                        BGT_DOOR => 'D',
                        BGT_PILLAR => 'P',
                        BGT_CRYSTAL => '*',
                        BGT_BLOCK => 'B',
                        BGT_WALL_CRACK => '%',
                        BGT_RUBBLE => ',',
                        _ => '.',
                    })
                    .collect::<String>()
            })
            .collect::<Vec<_>>()
            .join("\n")
    }
}
