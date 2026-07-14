//! Zelda-style 4x4 overworld sample.

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

pub const SAMPLE_ZELDA_OVERWORLD: ZeldaOverworldBiome = ZeldaOverworldBiome {
    id: BIOME_ZELDA_OVERWORLD,
    name: "Riftwild Expanse",
    screens: [
        [
            cell(DoorMask::E | DoorMask::S, OW, None, None),
            cell(DoorMask::E | DoorMask::S | DoorMask::W, OW, None, None),
            cell(DoorMask::E | DoorMask::S | DoorMask::W, CAVE, None, Some(15)),
            cell(DoorMask::S | DoorMask::W, OW, None, None),
        ],
        [
            cell(DoorMask::N | DoorMask::E | DoorMask::S, OW, Some(5), None),
            cell(DoorMask::N | DoorMask::E | DoorMask::S | DoorMask::W, OW, Some(4), None),
            cell(DoorMask::N | DoorMask::E | DoorMask::S | DoorMask::W, DUNGEON, None, None),
            cell(DoorMask::N | DoorMask::S | DoorMask::W, OW, None, None),
        ],
        [
            cell(DoorMask::N | DoorMask::E | DoorMask::S, OW, None, None),
            cell(DoorMask::N | DoorMask::E | DoorMask::S | DoorMask::W, OW, None, None),
            cell(DoorMask::N | DoorMask::E | DoorMask::S | DoorMask::W, OW, None, None),
            cell(DoorMask::N | DoorMask::S | DoorMask::W, CAVE, None, None),
        ],
        [
            cell(DoorMask::N | DoorMask::E, OW, None, None),
            cell(DoorMask::N | DoorMask::E | DoorMask::W, OW, None, None),
            cell(DoorMask::N | DoorMask::E | DoorMask::W, BOSS, None, None),
            cell(DoorMask::N | DoorMask::W, VAULT, None, None),
        ],
    ],
};

pub fn register(r: &mut Registry) {
    r.add_zelda_overworld(SAMPLE_ZELDA_OVERWORLD.clone());
}
