//! Law Lock C/Rust parity: compile the cartridge's `src/game/law_lock_gen.c`
//! for the host and compare every output with the Rust reference for all
//! nine stages over 3000 seeds. Skips (with a note) when no C compiler is
//! available; GitHub's ubuntu runners always have `cc`.

use quintra_procgen::law_lock::{generate, Input};
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};

const HOST_MAIN: &str = r#"
#include <stdio.h>
#include "game/law_lock.h"
int main(void) {
    unsigned v[8], i, d;
    while (scanf("%u %u %u %u %u %u", &v[0], &v[1], &v[2], &v[3], &v[4], &v[5]) == 6) {
        ll_size = (u8)v[0]; ll_entry = (u8)v[1]; ll_cache = (u8)v[2];
        ll_order = (u8)v[3]; ll_mix = (u8)v[4]; ll_bb = (u8)v[5];
        for (i = 0; i < LL_ROLES; ++i) { if (scanf("%u", &v[0]) != 1) return 1; ll_role[i] = (u8)v[0]; }
        for (i = 0; i < ll_size; ++i)
            for (d = 0; d < 4; ++d) { if (scanf("%u", &v[0]) != 1) return 1; ll_nb[i][d] = (u8)v[0]; }
        ll_generate();
        printf("%u", ll_gate_n);
        for (i = 0; i < ll_gate_n; ++i)
            printf(" %u,%u,%u,%u", ll_gate_a[i], ll_gate_b[i], ll_gate_dir[i], ll_gate_open[i]);
        printf(" A%u", ll_altar_n);
        for (i = 0; i < ll_altar_n; ++i) printf(" %u", ll_altar[i]);
        printf(" B%u,%u T%u,%u\n", ll_plain_boss, ll_law_boss, ll_plain_tour, ll_law_tour);
    }
    return 0;
}
"#;

#[test]
fn c_generator_matches_rust_reference() {
    let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("../../..");
    let dir = std::env::temp_dir().join(format!("quintra-law-lock-{}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let main_c = dir.join("main.c");
    let exe = dir.join("ll-host");
    std::fs::write(&main_c, HOST_MAIN).unwrap();
    let cc = std::env::var("CC").unwrap_or_else(|_| "cc".into());
    let built = Command::new(&cc)
        .args(["-O1", "-Wall", "-Werror", "-Wno-unknown-pragmas", "-DLL_HOST"])
        .arg(format!("-I{}", root.join("src").display()))
        .arg("-o")
        .arg(&exe)
        .arg(root.join("src/game/law_lock_gen.c"))
        .arg(&main_c)
        .status();
    match built {
        Ok(s) if s.success() => {}
        Ok(s) => panic!("host compile of law_lock_gen.c failed: {s}"),
        Err(e) => {
            eprintln!("skipping Law Lock C parity: no C compiler ({e})");
            return;
        }
    }
    let mut input = String::new();
    let mut expect = Vec::new();
    for bb in 0..9u8 {
        for i in 0..3000u32 {
            let seed = i.wrapping_mul(2654435761).wrapping_add(12345);
            let (inp, _) = Input::for_seed(seed, bb);
            input += &format!("{} {} {} {} {} {}", inp.size, inp.entry, inp.cache, inp.order, inp.mix, inp.bb);
            for r in inp.roles {
                input += &format!(" {r}");
            }
            for nb in &inp.nb {
                for n in nb {
                    input += &format!(" {n}");
                }
            }
            input.push('\n');
            let law = generate(&inp);
            let mut line = format!("{}", law.gates.len());
            for g in &law.gates {
                line += &format!(" {},{},{},{}", g.a, g.b, g.dir, g.open);
            }
            line += &format!(" A{}", law.altars.len());
            for a in &law.altars {
                line += &format!(" {a}");
            }
            line += &format!(" B{},{} T{},{}", law.plain_boss, law.law_boss, law.plain_tour, law.law_tour);
            expect.push((seed, bb, line));
        }
    }
    let mut child = Command::new(&exe).stdin(Stdio::piped()).stdout(Stdio::piped()).spawn().unwrap();
    // Feed stdin from a thread: the child streams its answers meanwhile.
    let mut stdin = child.stdin.take().unwrap();
    let feeder = std::thread::spawn(move || stdin.write_all(input.as_bytes()).unwrap());
    let out = child.wait_with_output().unwrap();
    feeder.join().unwrap();
    let got = String::from_utf8(out.stdout).unwrap();
    let got: Vec<&str> = got.lines().collect();
    assert_eq!(got.len(), expect.len(), "C produced {} rows", got.len());
    for ((seed, bb, want), have) in expect.iter().zip(got) {
        assert_eq!(have, want, "seed {seed:#010x} stage {}: C vs Rust", bb + 1);
    }
    let _ = std::fs::remove_dir_all(&dir);
}
