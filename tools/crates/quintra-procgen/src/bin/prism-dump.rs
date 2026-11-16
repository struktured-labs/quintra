//! Print the Rust reference Prism Toggle chamber for one room seed.
//! Usage: prism-dump <room-seed> <bosses-beaten>
//! Output: "tpl mirror swap flips" then 17 rows of the 20x17 court using the
//! template legend ('#', '.', 'a', 'b', 'o', 'G'); 'a' is colour 0 (amber).
use quintra_procgen::prism_toggle::{prism_variant, templates, Cell, Model, H, W};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let parse = |s: &str| -> u32 {
        s.strip_prefix("0x").map_or_else(|| s.parse().unwrap(), |h| u32::from_str_radix(h, 16).unwrap())
    };
    let seed = parse(&args[1]);
    let bb = parse(&args[2]) as u8;
    let (i, mirror, swap) = prism_variant(seed, bb);
    let t = &templates()[i];
    let m = Model::new(t, mirror, swap);
    println!("{} {} {} {}", i, mirror as u8, swap as u8, m.min_flips().unwrap());
    for y in 0..H {
        let row: String = (0..W)
            .map(|x| match m.grid[y * W + x] {
                Cell::Floor => '.',
                Cell::Wall => '#',
                Cell::Barrier(0) => 'a',
                Cell::Barrier(_) => 'b',
                Cell::Orb => 'o',
                Cell::Goal => 'G',
            })
            .collect();
        println!("{row}");
    }
}
