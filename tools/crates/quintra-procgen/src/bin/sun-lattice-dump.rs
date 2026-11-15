//! Dump Sun Lattice rooms in the C host harness format.
//!
//! usage: sun-lattice-dump N BOSSES_BEATEN ROLE [--plan]
//!        sun-lattice-dump --room SEED BOSSES_BEATEN ROLE
//!
//! `--plan` appends ` P<i>,<j>...` with the solver's fewest-turn vane list.
//! `--room` dumps one room for an explicit seed (hex with 0x, or decimal),
//! with its plan, for the ROM parity check in scripts/test_puzzles.py.

use quintra_procgen::sun_lattice::{dump_line, generate, harness_seed, solve, Lattice};

fn plan(l: &Lattice) -> String {
    match solve(&l.fixtures, None) {
        Some(p) => format!(" P{}", p.iter().map(|i| i.to_string()).collect::<Vec<_>>().join(",")),
        None => " P-".to_string(),
    }
}

fn parse_u32(s: &str) -> u32 {
    match s.strip_prefix("0x") {
        Some(h) => u32::from_str_radix(h, 16).expect("hex seed"),
        None => s.parse().expect("seed"),
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args.len() == 4 && args[0] == "--room" {
        let seed = parse_u32(&args[1]);
        let l = generate(seed, args[2].parse().expect("BOSSES_BEATEN"), args[3].parse().expect("ROLE"));
        println!("{}{}", dump_line(seed, &l), plan(&l));
        return;
    }
    let with_plan = args.len() == 4 && args[3] == "--plan";
    if args.len() != 3 && !with_plan {
        eprintln!("usage: sun-lattice-dump N BOSSES_BEATEN ROLE [--plan] | --room SEED BOSSES_BEATEN ROLE");
        std::process::exit(2);
    }
    let n: u32 = args[0].parse().expect("N");
    let bosses_beaten: u8 = args[1].parse().expect("BOSSES_BEATEN");
    let role: u8 = args[2].parse().expect("ROLE");
    for i in 0..n {
        let seed = harness_seed(i);
        let l = generate(seed, bosses_beaten, role);
        if with_plan {
            println!("{}{}", dump_line(seed, &l), plan(&l));
        } else {
            println!("{}", dump_line(seed, &l));
        }
    }
}
