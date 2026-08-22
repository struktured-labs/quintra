//! Riftwild's 6x6 expedition graph. Every graph cell expands into one
//! scrolling 31x31-tile field on cartridge, so the complete region approaches
//! Zelda-I overworld scale while remaining deterministic and seed-light.

use quintra_content::{
    DoorMask, Registry, ScreenCell, ScreenCellKind, ZeldaOverworldBiome,
};

use crate::ids::*;

const OPEN: quintra_content::RoomTemplateId = ROOM_SMALL_EMPTY;

const OW: ScreenCellKind = ScreenCellKind::Overworld;
const CAVE: ScreenCellKind = ScreenCellKind::CaveEntrance;
const DUNGEON: ScreenCellKind = ScreenCellKind::DungeonEntrance;
const VAULT: ScreenCellKind = ScreenCellKind::Vault;
const BOSS: ScreenCellKind = ScreenCellKind::Boss;

const fn cell(
    edges: u8,
    kind: ScreenCellKind,
    secret_to: Option<u8>,
    staircase_to: Option<u8>,
) -> ScreenCell {
    ScreenCell {
        edges: DoorMask(edges),
        room_tpl_id: OPEN,
        secret_to,
        staircase_to,
        cell_kind: kind,
    }
}

// A mostly open looped grid is deliberately interrupted by reciprocal stone
// ridges. The broad graph still has many alternate paths, but it no longer
// reads as a featureless square when the player opens the Compass.
const fn horizontal_open(row: u8, col: u8) -> bool {
    !((row == 1 && col == 2)
        || (row == 2 && col == 0)
        || (row == 3 && col == 3)
        || (row == 4 && col == 1))
}

const fn vertical_open(row: u8, col: u8) -> bool {
    !((row == 0 && col == 4)
        || (row == 1 && col == 1)
        || (row == 2 && col == 3)
        || (row == 3 && col == 0)
        || (row == 4 && col == 4))
}

const fn field_edges(row: u8, col: u8) -> u8 {
    let mut edges = 0;
    if row > 0 && vertical_open(row - 1, col) { edges |= DoorMask::N; }
    if col < 5 && horizontal_open(row, col) { edges |= DoorMask::E; }
    if row < 5 && vertical_open(row, col) { edges |= DoorMask::S; }
    if col > 0 && horizontal_open(row, col - 1) { edges |= DoorMask::W; }
    edges
}

const fn field(
    row: u8,
    col: u8,
    kind: ScreenCellKind,
    staircase_to: Option<u8>,
) -> ScreenCell {
    cell(field_edges(row, col), kind, None, staircase_to)
}

pub const SAMPLE_ZELDA_OVERWORLD: ZeldaOverworldBiome = ZeldaOverworldBiome {
    id: BIOME_ZELDA_OVERWORLD,
    name: "Riftwild Expanse",
    screens: [
        [
            field(0, 0, OW, None),
            field(0, 1, OW, None),
            field(0, 2, OW, None),
            field(0, 3, OW, None),
            field(0, 4, OW, None),
            field(0, 5, CAVE, Some(30)),
        ],
        [
            field(1, 0, OW, None),
            field(1, 1, OW, None),
            field(1, 2, DUNGEON, None),
            field(1, 3, OW, None),
            field(1, 4, OW, None),
            field(1, 5, OW, None),
        ],
        [
            field(2, 0, OW, None),
            field(2, 1, OW, None),
            field(2, 2, OW, None),
            field(2, 3, OW, None),
            field(2, 4, OW, None),
            field(2, 5, OW, None),
        ],
        [
            field(3, 0, OW, None),
            field(3, 1, OW, None),
            field(3, 2, OW, None),
            field(3, 3, DUNGEON, None),
            field(3, 4, OW, None),
            field(3, 5, OW, None),
        ],
        [
            field(4, 0, OW, None),
            field(4, 1, OW, None),
            field(4, 2, OW, None),
            field(4, 3, BOSS, None),
            field(4, 4, OW, None),
            field(4, 5, OW, None),
        ],
        [
            field(5, 0, VAULT, None),
            field(5, 1, OW, None),
            field(5, 2, OW, None),
            field(5, 3, OW, None),
            field(5, 4, DUNGEON, None),
            field(5, 5, OW, None),
        ],
    ],
};

pub fn register(r: &mut Registry) {
    r.add_zelda_overworld(SAMPLE_ZELDA_OVERWORLD.clone());
}
