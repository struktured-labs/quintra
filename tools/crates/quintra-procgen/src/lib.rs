//! Procgen reference implementation.
//!
//! This is the host-side reference for the on-cartridge generator in
//! `src/game/procgen.c`: same seed, same RNG call order, same tilemap.
//! Property tests pin the door-connectivity invariant for every room
//! shape; `scripts/test_procgen_parity.py` cross-checks this crate's
//! output against the real ROM's WRAM in an emulator.

#![forbid(unsafe_code)]

pub mod rng;
pub mod room;
pub mod prism_toggle;
pub mod law_lock;
pub mod push_seal;
pub mod sun_lattice;
pub mod topology;

pub use rng::Xorshift32;
pub use room::{generate_tilemap, room_kind, room_seed, Tilemap};
