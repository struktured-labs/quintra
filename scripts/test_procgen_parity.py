#!/usr/bin/env python3
"""Cross-seam procgen parity test: the Rust reference generator vs the
real ROM.

For each test case, boots the ROM in PyBoy, pokes a known run_seed into
run_state, door-walks into the target room so the cart's C generator runs
with that seed, dumps the WRAM room_tilemap (17x20 bytes), and compares
it against `procgen-dump` (quintra-procgen's reference impl).

Any divergence in RNG call order, tile constants, or room-role branching
between src/game/procgen.c and the Rust reference fails here.

Run: uv run --with pyboy python scripts/test_procgen_parity.py
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROOT / "rom/working/quintra.noi"
DUMP = ROOT / "target/release/procgen-dump"

ROOM_W, ROOM_H = 20, 17

# (run_seed, target_counter) — covers plain, mini-boss, shop, rest, boss
CASES = [
    (123456789, 1),
    (123456789, 2),
    (987654321, 3),
    (555555555, 4),
    (42424242, 5),
    (1337, 6),
]


def noi_addr(sym):
    text = NOI.read_text()
    m = re.search(rf"DEF {sym} 0x([0-9A-Fa-f]+)", text)
    if not m:
        sys.exit(f"FAIL: symbol {sym} not in {NOI}")
    return int(m.group(1), 16)


def reference(seed, counter):
    out = subprocess.run(
        [str(DUMP), str(seed), "0", str(counter), "0", "0"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    return [int(v) for v in out]


def main():
    from pyboy import PyBoy

    rs = noi_addr("_run_state")
    pl = noi_addr("_player")
    en = noi_addr("_entities")
    tm = noi_addr("_room_tilemap")

    failures = 0
    for seed, counter in CASES:
        pb = PyBoy(str(ROM), window="null", cgb=True)
        tick = lambda n: [pb.tick() for _ in range(n)]
        tick(240)
        pb.button("start"); tick(30)
        pb.button("a"); tick(60)          # Wolfkin -> room 0

        # Poke the run state: known seed, one room before the target
        for i, b in enumerate(seed.to_bytes(4, "little")):
            pb.memory[rs + 2 + i] = b     # run_seed at offset 2..5
        pb.memory[rs + 1] = counter - 1   # room_counter
        pb.memory[rs + 11] = 0            # bosses_beaten
        pb.memory[rs + 13] = 0            # secret_pending
        # Boss-room parity is about generated geometry, so satisfy the new
        # player-facing progression prerequisite before crossing room 5.
        pb.memory[rs + 23] = 1 if counter == 6 else 0  # Rift Sigil stage bit
        pb.memory[rs + 24] = 0

        # Walk through the S door -> counter increments -> C procgen runs.
        # Check the counter EVERY frame and release input the moment we
        # cross: walking on into the fresh room can kick its rubble, and
        # sampling mid-regeneration reads a half-built map (both showed up
        # as phantom parity failures).
        pb.button_press("down")
        for _ in range(80 * 22):
            pb.memory[pl + 2] = 12        # hp
            pb.memory[pl + 15] = 60       # iframes (no knockback stalls)
            # Parity validates generation, not combat. Remove hostiles so the
            # clear-gated forward door can be crossed deterministically.
            for i in range(32):
                ep = en + i * 28
                if pb.memory[ep] == 2:
                    pb.memory[ep] = 0
                    pb.memory[ep + 1] = 0
            pb.tick()
            if pb.memory[rs + 1] == counter:
                break
        pb.button_release("down")
        # Let generation finish: wait until the tilemap is stable 10 frames
        prev = None
        stable = 0
        for _ in range(240):
            pb.tick()
            cur = bytes(pb.memory[tm + i] for i in range(ROOM_W * ROOM_H))
            stable = stable + 1 if cur == prev else 0
            prev = cur
            if stable >= 10:
                break

        got = list(prev)
        want = reference(seed, counter)
        pb.stop(save=False)

        if got == want:
            print(f"  PASS seed={seed} counter={counter}")
        else:
            bad = next(i for i in range(len(want)) if got[i] != want[i])
            print(f"  FAIL seed={seed} counter={counter}: first diff at "
                  f"({bad // ROOM_W},{bad % ROOM_W}) rom={got[bad]} ref={want[bad]}")
            failures += 1

    print(f"[procgen-parity] {len(CASES) - failures}/{len(CASES)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
