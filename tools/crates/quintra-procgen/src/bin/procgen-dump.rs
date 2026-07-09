//! procgen-dump — print the reference tilemap for a given run state.
//!
//! Usage: procgen-dump <run_seed> <biome_id> <room_counter> <bosses_beaten> <secret:0|1>
//! Output: 17 lines of 20 space-separated tile-id bytes (decimal) — the
//! exact expected contents of the cart's WRAM `room_tilemap`.
//! Consumed by scripts/test_procgen_parity.py.

use quintra_procgen::generate_tilemap;

fn main() {
    let a: Vec<String> = std::env::args().collect();
    if a.len() != 6 {
        eprintln!("usage: procgen-dump <run_seed> <biome> <counter> <bosses> <secret>");
        std::process::exit(2);
    }
    let seed: u32 = a[1].parse().expect("run_seed");
    let biome: u8 = a[2].parse().expect("biome");
    let counter: u8 = a[3].parse().expect("counter");
    let bosses: u8 = a[4].parse().expect("bosses");
    let secret = a[5] == "1";

    let m = generate_tilemap(seed, biome, counter, bosses, secret);
    for row in m {
        let line: Vec<String> = row.iter().map(|t| t.to_string()).collect();
        println!("{}", line.join(" "));
    }
}
