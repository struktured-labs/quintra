//! Zelda-style overworld biome definitions — fixed 4x4 screen grids.

use std::collections::VecDeque;

use serde::{Deserialize, Serialize};

use crate::refs::*;
use crate::room::DoorMask;

pub const SCREEN_QUAD_W: usize = 4;
pub const SCREEN_QUAD_H: usize = 4;
pub const SCREEN_QUAD_LEN: usize = SCREEN_QUAD_W * SCREEN_QUAD_H;
pub const ROOM_TPL_VOID: RoomTemplateId = RoomTemplateId::new(0xFFFF);

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum ScreenCellKind {
    Overworld,
    CaveEntrance,
    DungeonEntrance,
    Vault,
    Boss,
}

#[derive(Copy, Clone, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct ScreenCell {
    pub edges: DoorMask,
    pub room_tpl_id: RoomTemplateId,
    pub secret_to: Option<u8>,
    pub staircase_to: Option<u8>,
    pub cell_kind: ScreenCellKind,
}

pub type ScreenQuad = [[ScreenCell; SCREEN_QUAD_W]; SCREEN_QUAD_H];

#[derive(Clone, PartialEq, Eq, Debug)]
pub struct ZeldaOverworldBiome {
    pub id: BiomeId,
    pub name: &'static str,
    pub screens: ScreenQuad,
}

impl ZeldaOverworldBiome {
    pub fn validate(&self) -> Result<(), Vec<String>> {
        let mut errs = Vec::new();

        for idx in 0..SCREEN_QUAD_LEN {
            let cell = self.cell(idx);

            if cell.room_tpl_id.raw() == ROOM_TPL_VOID.raw() && cell.cell_kind != ScreenCellKind::Vault {
                errs.push(format!(
                    "zelda_overworld {} screen {} is void but kind is not Vault",
                    self.id.raw(),
                    idx,
                ));
            }
            if let Some(secret_to) = cell.secret_to {
                if secret_to as usize >= SCREEN_QUAD_LEN {
                    errs.push(format!(
                        "zelda_overworld {} screen {} secret_to {} out of range",
                        self.id.raw(),
                        idx,
                        secret_to,
                    ));
                } else if !is_adjacent(idx as u8, secret_to) {
                    errs.push(format!(
                        "zelda_overworld {} screen {} secret_to {} is not adjacent",
                        self.id.raw(),
                        idx,
                        secret_to,
                    ));
                }
            }

            if let Some(staircase_to) = cell.staircase_to {
                if staircase_to as usize >= SCREEN_QUAD_LEN {
                    errs.push(format!(
                        "zelda_overworld {} screen {} staircase_to {} out of range",
                        self.id.raw(),
                        idx,
                        staircase_to,
                    ));
                } else if self.cell(staircase_to as usize).cell_kind != ScreenCellKind::Vault {
                    errs.push(format!(
                        "zelda_overworld {} screen {} staircase_to {} does not target a Vault cell",
                        self.id.raw(),
                        idx,
                        staircase_to,
                    ));
                }
            }

            for (dir_bit, opposite_bit, maybe_neighbor) in neighbors(idx as u8) {
                let has_edge = cell.edges.has(dir_bit);
                match maybe_neighbor {
                    Some(neighbor_idx) => {
                        let neighbor = self.cell(neighbor_idx as usize);
                        if has_edge && !neighbor.edges.has(opposite_bit) {
                            errs.push(format!(
                                "zelda_overworld {} edge mismatch: screen {} has {:X} to screen {} but reverse edge is missing",
                                self.id.raw(),
                                idx,
                                dir_bit,
                                neighbor_idx,
                            ));
                        }
                    }
                    None if has_edge => errs.push(format!(
                        "zelda_overworld {} screen {} has out-of-bounds edge bit {:X}",
                        self.id.raw(),
                        idx,
                        dir_bit,
                    )),
                    None => {}
                }
            }
        }

        let start = 0_u8;
        if self.cell(start as usize).room_tpl_id.raw() == ROOM_TPL_VOID.raw() {
            errs.push(format!(
                "zelda_overworld {} screen 0 cannot be void",
                self.id.raw(),
            ));
        }

        if !errs.is_empty() {
            return Err(errs);
        }

        let visited = self.connected_from(start);
        for idx in 0..SCREEN_QUAD_LEN {
            let cell = self.cell(idx);
            if cell.room_tpl_id.raw() == ROOM_TPL_VOID.raw() {
                continue;
            }
            if !visited[idx] {
                errs.push(format!(
                    "zelda_overworld {} screen {} is unreachable from screen {}",
                    self.id.raw(),
                    idx,
                    start,
                ));
            }
        }

        if errs.is_empty() { Ok(()) } else { Err(errs) }
    }

    pub fn referenced_room_templates(&self) -> impl Iterator<Item = RoomTemplateId> + '_ {
        self.screens
            .iter()
            .flat_map(|row| row.iter())
            .filter_map(|cell| (cell.room_tpl_id.raw() != ROOM_TPL_VOID.raw()).then_some(cell.room_tpl_id))
    }

    fn connected_from(&self, start: u8) -> [bool; SCREEN_QUAD_LEN] {
        let mut visited = [false; SCREEN_QUAD_LEN];
        let mut q = VecDeque::new();
        visited[start as usize] = true;
        q.push_back(start);

        while let Some(idx) = q.pop_front() {
            let cell = self.cell(idx as usize);

            for (dir_bit, _, maybe_neighbor) in neighbors(idx) {
                let Some(neighbor_idx) = maybe_neighbor else { continue };
                if !cell.edges.has(dir_bit) {
                    continue;
                }
                if self.cell(neighbor_idx as usize).room_tpl_id.raw() == ROOM_TPL_VOID.raw() {
                    continue;
                }
                if !visited[neighbor_idx as usize] {
                    visited[neighbor_idx as usize] = true;
                    q.push_back(neighbor_idx);
                }
            }

            if let Some(secret_to) = cell.secret_to {
                if self.cell(secret_to as usize).room_tpl_id.raw() != ROOM_TPL_VOID.raw()
                    && !visited[secret_to as usize]
                {
                    visited[secret_to as usize] = true;
                    q.push_back(secret_to);
                }
            }

            if let Some(staircase_to) = cell.staircase_to {
                if self.cell(staircase_to as usize).room_tpl_id.raw() != ROOM_TPL_VOID.raw()
                    && !visited[staircase_to as usize]
                {
                    visited[staircase_to as usize] = true;
                    q.push_back(staircase_to);
                }
            }
        }

        visited
    }

    pub fn cell(&self, idx: usize) -> &ScreenCell {
        let y = idx / SCREEN_QUAD_W;
        let x = idx % SCREEN_QUAD_W;
        &self.screens[y][x]
    }
}

fn is_adjacent(a: u8, b: u8) -> bool {
    neighbors(a).into_iter().any(|(_, _, n)| n == Some(b))
}

fn neighbors(idx: u8) -> [(u8, u8, Option<u8>); 4] {
    let x = idx as usize % SCREEN_QUAD_W;
    let y = idx as usize / SCREEN_QUAD_W;
    [
        (
            DoorMask::N,
            DoorMask::S,
            if y > 0 {
                Some(idx - SCREEN_QUAD_W as u8)
            } else {
                None
            },
        ),
        (DoorMask::E, DoorMask::W, (x + 1 < SCREEN_QUAD_W).then_some(idx + 1)),
        (
            DoorMask::S,
            DoorMask::N,
            (y + 1 < SCREEN_QUAD_H).then_some(idx + SCREEN_QUAD_W as u8),
        ),
        (
            DoorMask::W,
            DoorMask::E,
            if x > 0 { Some(idx - 1) } else { None },
        ),
    ]
}
