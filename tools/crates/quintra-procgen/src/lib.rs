//! Procgen reference implementation — graph-on-grid biome/room layout.
//!
//! This is the host-side reference. The on-cartridge port lives in
//! `src/game/procgen.c` and must produce the same output for the same
//! seed (Rust tests pin this).
//!
//! Phase 1 stub.

#![forbid(unsafe_code)]

pub mod rng;

pub use rng::Xorshift32;
