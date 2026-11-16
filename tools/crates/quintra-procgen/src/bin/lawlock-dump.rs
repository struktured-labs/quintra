//! Print the Rust reference Law Lock for one run seed and stage.
//! Usage: lawlock-dump <run-seed> <bosses-beaten>
//! Output, one line: "G n a,b,dir,open ... A n altar ... B plain,law T plain,law"
use quintra_procgen::law_lock::{generate, Input};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let parse = |s: &str| -> u32 {
        s.strip_prefix("0x").map_or_else(|| s.parse().unwrap(), |h| u32::from_str_radix(h, 16).unwrap())
    };
    let seed = parse(&args[1]);
    let bb = parse(&args[2]) as u8;
    let (inp, _) = Input::for_seed(seed, bb);
    let law = generate(&inp);
    let mut line = format!("G {}", law.gates.len());
    for g in &law.gates {
        line += &format!(" {},{},{},{}", g.a, g.b, g.dir, g.open);
    }
    line += &format!(" A {}", law.altars.len());
    for a in &law.altars {
        line += &format!(" {a}");
    }
    line += &format!(" B {},{} T {},{} E {}", law.plain_boss, law.law_boss, law.plain_tour, law.law_tour, inp.entry);
    println!("{line}");
}
