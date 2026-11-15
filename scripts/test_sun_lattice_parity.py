#!/usr/bin/env python3
"""Sun Lattice generator parity: the cart's C vs the Rust reference.

Compiles src/game/sun_lattice_gen.c for the host (-DSL_HOST) and compares
every generated room (fixtures, scrambled and solved angles, crystal,
attempt count, arrival trace) with `sun-lattice-dump` from quintra-procgen,
for Stages 3-9 and both the Trial and Waystone roles. Any divergence in RNG
call order or u8 arithmetic fails here.

It also checks solver parity: the Rust fewest-turn solver (which never reads
the solved angles) and the Python BFS that drives the PyBoy strikes in
scripts/test_puzzles.py must return the same vane list for every C room.

Run: python3 scripts/test_sun_lattice_parity.py [rooms-per-case]
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sun_lattice_harness as slh  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SOLVER_ROOMS = 300   # Python BFS is slower; check a prefix of every case


def c_fixtures(line):
    out = []
    for tok in line.split()[3:]:
        if tok.startswith("C"):
            break
        x, y, kind, ang, solved = map(int, tok.split(","))
        out.append(dict(x=x, y=y, kind=kind, ang=ang, solved=solved))
    return out
DUMP = ROOT / "target/release/sun-lattice-dump"

HOST_MAIN = r"""
#include <stdio.h>
#include <stdlib.h>
#include "game/sun_lattice.h"
u8 room_tilemap[SL_MAP_H][SL_MAP_W];
int main(int argc, char **argv) {
    unsigned long n, i;
    int bb, role;
    u8 k;
    if (argc != 4) return 2;
    n = strtoul(argv[1], 0, 0);
    bb = atoi(argv[2]);
    role = atoi(argv[3]);
    for (i = 0; i < n; ++i) {
        u32 seed = (u32)(i * 2654435761u + 12345u);
        sl_generate(seed, (u8)bb, (u8)role);
        printf("%08lx %u %u", (unsigned long)seed, sl_attempts, sl_trace(0));
        for (k = 0; k < sl_n; ++k)
            printf(" %u,%u,%u,%u,%u", sl_x[k], sl_y[k], sl_kind[k], sl_ang[k],
                   sl_solved_ang[k]);
        printf(" C%u,%u\n", sl_crystal_x, sl_crystal_y);
    }
    return 0;
}
"""


def main():
    rooms = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
    cc = os.environ.get("CC", "cc")
    if not DUMP.exists():
        subprocess.run(["cargo", "build", "--release", "-p", "quintra-procgen",
                        "--bin", "sun-lattice-dump"], cwd=ROOT, check=True)
    with tempfile.TemporaryDirectory() as tmp:
        main_c = Path(tmp) / "host_main.c"
        exe = Path(tmp) / "slhost"
        main_c.write_text(HOST_MAIN)
        subprocess.run([cc, "-O1", "-Wall", "-Werror", "-Wno-unknown-pragmas",
                        "-DSL_HOST", f"-I{ROOT / 'src'}", "-o", str(exe),
                        str(main_c), str(ROOT / "src/game/sun_lattice_gen.c")],
                       check=True)
        failures = 0
        for bb in range(2, 9):
            for role in (0, 1):
                args = [str(rooms), str(bb), str(role)]
                c = subprocess.run([str(exe), *args], check=True,
                                   capture_output=True, text=True).stdout.splitlines()
                r = subprocess.run([str(DUMP), *args, "--plan"], check=True,
                                   capture_output=True, text=True).stdout.splitlines()
                assert len(c) == len(r) == rooms, (len(c), len(r))
                plans = [b.rsplit(" P", 1)[1] for b in r]
                r = [b.rsplit(" P", 1)[0] for b in r]
                bad = [(a, b) for a, b in zip(c, r) if a != b]
                turns = []
                for a, plan in list(zip(c, plans))[:SOLVER_ROOMS]:
                    fx = c_fixtures(a)
                    py = slh.solve(fx, None)
                    want = "-" if py is None else ",".join(map(str, py))
                    if plan != want or py is None:
                        bad.append((a, f"solver rust={plan} python={want}"))
                    else:
                        turns.append(len(py))
                lit = [a for a in c if a.split()[2] != "0"]
                fallback = sum(1 for a in c if a.split()[1] == "255")
                print(f"Stage {bb + 1} {'Waystone' if role else 'Trial'}: "
                      f"{rooms - len(bad)}/{rooms} match, {fallback} fallback, "
                      f"solver {len(turns)}/{min(rooms, SOLVER_ROOMS)} agree, "
                      f"turns {min(turns, default=0)}-{max(turns, default=0)} "
                      f"(mean {sum(turns) / max(1, len(turns)):.2f})")
                for a, b in bad[:3]:
                    print(f"  C:    {a}\n  Rust: {b}")
                if bad or lit:
                    failures += 1
                if lit:
                    print(f"  {len(lit)} rooms lit on arrival, e.g. {lit[0]}")
        if failures:
            sys.exit(f"FAIL: {failures} case(s) diverged")
    print("PASS: Sun Lattice C and Rust generators agree")


if __name__ == "__main__":
    main()
