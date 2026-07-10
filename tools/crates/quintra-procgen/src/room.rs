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
pub const BGT_BLOCK_TR: u8 = 28;
pub const BGT_BLOCK_BL: u8 = 29;
pub const BGT_BLOCK_BR: u8 = 30;

pub const ROOMS_PER_STAGE: u8 = 6;

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
    let boss = room_counter > 0
        && room_counter % ROOMS_PER_STAGE == 0
        && room_counter / ROOMS_PER_STAGE > bosses_beaten;
    let miniboss = !boss && room_counter % ROOMS_PER_STAGE == 3;
    let shop = !boss && !miniboss && room_counter % ROOMS_PER_STAGE == 4;
    let rest = !boss && room_counter % ROOMS_PER_STAGE == 5;
    RoomKind { boss, miniboss, shop, rest }
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
    let mut rng = Xorshift32::new(room_seed(run_seed, biome_id, room_counter));
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

        // ---- Interior shape (8 layouts; lanes cols 9-11 / rows 7-9 clear)
        let shape = rng.next_u8() & 0x07;
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
        m[10][6] = HUD_COIN;
        m[10][7] = HUD_DIGIT_0 + 1;
        m[10][8] = HUD_DIGIT_0;
        m[10][9] = HUD_COIN;
        m[10][10] = HUD_DIGIT_0 + 2;
        m[10][11] = HUD_DIGIT_0 + 5;
        m[10][12] = HUD_COIN;
        m[10][13] = HUD_DIGIT_0 + 4;
        m[10][14] = HUD_DIGIT_0;
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

    #[test]
    fn deterministic() {
        for seed in [1u32, 0xDEADBEEF, 12345] {
            assert_eq!(
                generate_tilemap(seed, 0, 1, 0, false),
                generate_tilemap(seed, 0, 1, 0, false),
            );
        }
    }

    /// The load-bearing invariant behind every room shape: all four doors
    /// stay mutually reachable in every non-boss room, for any seed —
    /// counting crystals as passable (the player can always shoot through).
    #[test]
    fn all_doors_reachable_across_seeds_and_roles() {
        for seed in 0..400u32 {
            for counter in 1..=6u8 {
                let kind = room_kind(counter, 0);
                if kind.boss { continue; }
                let m = generate_tilemap(seed.wrapping_mul(2654435761) + 7, 0, counter, 0, false);
                let reach = flood(&m, DOORS[0], passable_with_shots);
                for d in DOORS {
                    assert!(reach.contains(&d),
                        "seed {seed} counter {counter}: door {d:?} unreachable\n{}",
                        dump(&m));
                }
            }
        }
    }

    /// Vault overlays may block lanes with crystals, but never seal doors.
    #[test]
    fn vault_rooms_stay_passable() {
        for seed in 0..200u32 {
            let m = generate_tilemap(seed * 31 + 5, 0, 2, 0, true);
            let reach = flood(&m, DOORS[0], passable_with_shots);
            for d in DOORS {
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
        let m = generate_tilemap(0xABCD, 0, 6, 0, false);
        for d in DOORS {
            assert_eq!(m[d.0][d.1], BGT_WALL, "boss room has an open door at {d:?}");
        }
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
