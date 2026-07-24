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

# (run_seed, target_counter) — covers puzzle, Sigil, both minibosses, a wide
# scrolling district cells, an exact compact plain room, shop, sanctuary, and boss roles in
# the twenty-room opening dungeon.
CASES = [
    (123456789, 1),
    (123456789, 2),
    (987654321, 3),
    (555555555, 4),
    (555555555, 6),
    (555555555, 8),
    (42424242, 7),
    (42424242, 9),
    (42424242, 15),
    (42424242, 17),
    (42424242, 18),
    (1337, 19),
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


def cell_xy(cell):
    row, offset = divmod(cell, 6)
    return ((5 - offset) if row & 1 else offset), row


def graph_step(source, target):
    sx, sy = cell_xy(source)
    tx, ty = cell_xy(target)
    return {
        (0, -1): ("up", 72, 0, ((9, 0), (10, 0))),
        (1, 0): ("right", 144, 60, ((19, 8), (19, 9))),
        (0, 1): ("down", 72, 120, ((9, 16), (10, 16))),
        (-1, 0): ("left", 0, 60, ((0, 8), (0, 9))),
    }[(tx - sx, ty - sy)]


def authored_overlay_cells(seed, counter, bosses_beaten=0):
    """Cells intentionally replaced after the base C/Rust generator agrees.

    The push-seal family clears an 8×6 apron and stamps its ordinary-looking
    cairn in the room-role layer. Puzzle mechanics have their own live-ROM
    contract; parity still compares every unaffected base-generator cell.

    Scrolling 224×200 dungeon districts deliberately replace the complete
    compact base plane after consuming its established RNG sequence. Their
    dedicated live-ROM contract validates the whole 28×25 field; parity
    separates all 340 legacy cells here and retains room 8 as an exact compact
    control.

    The opening boss similarly composes its giant Crystal projection after
    base generation. Its new column-19 seam is also authored world geometry:
    the real combat wall now lives in the offscreen extension at column 27.
    The colossal-arena test owns those cells and the 224px camera contract.
    """
    overlay = set()
    if bosses_beaten == 0 and counter in (4, 5, 6, 10, 11, 12, 13, 16):
        return set(range(ROOM_W * ROOM_H))
    if counter == 19 and bosses_beaten == 0:
        overlay.update(row * ROOM_W + (ROOM_W - 1)
                       for row in range(1, ROOM_H - 1))
        for y, width in enumerate((8, 12, 14, 14, 14, 14, 14, 12, 8)):
            left = 10 - width // 2
            overlay.update((y + 3) * ROOM_W + x
                           for x in range(left, left + width))
        return overlay

    local = counter
    if bosses_beaten % 3 != 0 or local not in (1, 7):
        return overlay
    room_seed = (seed ^ ((counter * 0x9E3779B9) & 0xFFFFFFFF)) & 0xFFFFFFFF
    if local == 7 and not (room_seed & 1):
        return {
            row * ROOM_W + col
            for x, y in ((5, 8), (10, 5), (14, 10))
            for row in range(y - 1, y + 2)
            for col in range(x - 1, x + 2)
        }
    x = 6 if room_seed & 1 else 12
    y = 5 if room_seed & 2 else 10
    return {
        row * ROOM_W + col
        for row in range(y - 2, y + 4)
        for col in range(x - 3, x + 5)
    }


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
        # Boss-room parity is about generated geometry, so satisfy the
        # player-facing progression prerequisite before crossing its threshold.
        pb.memory[rs + 23] = 1 if counter == 19 else 0  # Rift Sigil stage bit
        pb.memory[rs + 24] = 0
        pb.memory[rs + 27] = ((1 << 3) | (1 << 7)) if counter == 19 else 0
        pb.memory[rs + 28] = (1 << 7) if counter == 19 else 0

        # Cross the real reciprocal edge from the prior snake cell so the C
        # procgen runs for the requested target counter.
        # Check the counter EVERY frame and release input the moment we
        # cross: walking on into the fresh room can kick its rubble, and
        # sampling mid-regeneration reads a half-built map (both showed up
        # as phantom parity failures).
        direction, px, py, doors = graph_step(counter - 1, counter)
        for tx, ty in doors:
            pb.memory[tm + ty * ROOM_W + tx] = 3
        pb.memory[pl + 9] = px & 0xFF
        pb.memory[pl + 10] = px >> 8
        pb.memory[pl + 11] = py & 0xFF
        pb.memory[pl + 12] = py >> 8
        pb.button_press(direction)
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
        pb.button_release(direction)
        # A room counter increments at the beginning of its Zelda-style slide,
        # before the destination's procgen call and its temporary spawn flood
        # have completed.  Let that transition settle first; a merely stable
        # tilemap during the slide is not yet a completed generated room.
        tick(90)

        # Then require a stable map snapshot rather than sampling an in-flight
        # tile upload.
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
        overlay = authored_overlay_cells(seed, counter)
        pb.stop(save=False)

        # Spawn reachability borrows bit 7 while selecting legal enemy cells.
        # It is deliberately scratch state, never a rendered tile ID, so a
        # completed room generation must clear it before the map is exposed.
        # Check this separately from geometry parity: otherwise a leaked bit
        # produces a misleading "random tile mismatch" at every reachable
        # cell and conceals whether the real base layout also diverged.
        marked = sum(tile & 0x80 != 0 for tile in got)
        raw_got = [tile & 0x7F for tile in got]

        if marked:
            print(f"  FAIL seed={seed} counter={counter}: "
                  f"{marked} leaked spawn-reach marker tile(s)")
            failures += 1
        elif all(raw_got[i] == want[i]
                 for i in range(len(want)) if i not in overlay):
            suffix = f" ({len(overlay)} authored overlay cells separated)" if overlay else ""
            print(f"  PASS seed={seed} counter={counter}{suffix}")
        else:
            bad = next(i for i in range(len(want))
                       if i not in overlay and raw_got[i] != want[i])
            print(f"  FAIL seed={seed} counter={counter}: first diff at "
                  f"({bad // ROOM_W},{bad % ROOM_W}) rom={raw_got[bad]} ref={want[bad]}")
            failures += 1

    print(f"[procgen-parity] {len(CASES) - failures}/{len(CASES)} passed")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
