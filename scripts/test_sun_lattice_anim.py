#!/usr/bin/env python3
"""Sun Lattice beams and mirrors animate without touching the puzzle (#250).

The laser shimmer and the mirror highlight are tile-data animation only:
the same VRAM bank 1 tiles (57 mirror, 60..62 beams) are re-uploaded with
new pixels. This locks that

  * the beam tiles and the mirror tile really cycle through four frames,
  * the Brazier, Wedge and Obelisk tiles stay still,
  * no map cell, fixture angle or traced beam changes while it runs,
  * a spark sprite appears on a mirror the light is bouncing off, and
    never on a mirror the light does not reach.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sun_lattice_harness as slh  # noqa: E402
import test_puzzles as tp  # noqa: E402

EN, SL = tp.EN, tp.SL
ENT_FX = 4
TILE_BASE = 0x9000
STILL = (56, 58, 59)           # Brazier, Wedge, Obelisk
BEAMS = (60, 61, 62)
MIRROR = 57
REFLECTORS = (slh.SLK_VANE, slh.SLK_FIXED, slh.SLK_BIFROST)


def tile(pb, index):
    return bytes(pb.memory[1, TILE_BASE + index * 16 + i] for i in range(16))


def bg_cells(pb):
    ox, oy = tp.addr("_room_bg_origin_x"), tp.addr("_room_bg_origin_y")
    out = []
    for y in range(17):
        for x in range(20):
            a = (0x9800 + ((pb.memory[oy] + y) & 31) * 32
                 + ((pb.memory[ox] + x) & 31))
            out.append((pb.memory[0, a], pb.memory[1, a]))
    return out


def sparks(pb):
    found = set()
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == ENT_FX and pb.memory[ep + 1] & 1:
            found.add(((pb.memory[ep + 3] | pb.memory[ep + 4] << 8) >> 3,
                       (pb.memory[ep + 7] | pb.memory[ep + 8] << 8) >> 3))
    return found


def in_beam(f, beams_h, beams_v):
    x, y = f["x"], f["y"]
    return ((x - 1, y) in beams_h or (x + 1, y) in beams_h
            or (x, y - 1) in beams_v or (x, y + 1) in beams_v)


def contract(stage, solve):
    pb = tp.enter_mission_cell(stage, "trial")
    assert pb.memory[tp.KIND] == slh.PUZZLE_SUN_LATTICE
    tp.clear_hostiles(pb)
    for _ in range(90):
        pb.tick()
    if solve:
        tp.solve_sun_lattice(pb)
        for _ in range(60):
            pb.tick()
    fixtures = slh.read_state(pb, SL)
    beams_h = slh.read_bits(pb, SL["_sl_beam_h"])
    beams_v = slh.read_bits(pb, SL["_sl_beam_v"])
    cells = bg_cells(pb)
    still = {t: tile(pb, t) for t in STILL}
    seen = {t: set() for t in BEAMS + (MIRROR,)}
    spark_cells = set()
    for _ in range(96):
        pb.tick()
        for t in seen:
            seen[t].add(tile(pb, t))
        spark_cells |= sparks(pb)
    for t in BEAMS:
        assert len(seen[t]) == 4, f"beam tile {t} showed {len(seen[t])} frames"
    assert len(seen[MIRROR]) == 4, (
        f"mirror tile showed {len(seen[MIRROR])} frames")
    for t in STILL:
        assert tile(pb, t) == still[t], f"tile {t} is not meant to animate"
    # Display only: the map, the fixtures and the trace are exactly as before.
    assert bg_cells(pb) == cells, "animation rewrote a background cell"
    assert slh.read_state(pb, SL) == fixtures, "animation changed a fixture"
    assert slh.read_bits(pb, SL["_sl_beam_h"]) == beams_h
    assert slh.read_bits(pb, SL["_sl_beam_v"]) == beams_v
    tp.lattice_beams_match(pb, fixtures)
    lit = {(f["x"], f["y"]) for f in fixtures
           if f["kind"] in REFLECTORS and in_beam(f, beams_h, beams_v)}
    dark = {(f["x"], f["y"]) for f in fixtures
            if f["kind"] in REFLECTORS} - lit
    if lit:
        assert spark_cells & lit, (
            f"no spark on a mirror in the beam: lit={sorted(lit)} "
            f"sparks={sorted(spark_cells)}")
    assert not (spark_cells & dark), (
        f"spark on a mirror outside the beam: {sorted(spark_cells & dark)}")
    pb.stop(save=False)
    return len(lit), len(dark)


def main():
    for stage, solve in ((3, False), (5, True)):
        lit, dark = contract(stage, solve)
        print(f"  stage {stage} {'solved' if solve else 'fresh'}: "
              f"{lit} mirror(s) in the beam, {dark} outside")
    print("[sun-lattice-anim] PASS beams and mirror cycle four frames, "
          "fixtures still, map and trace untouched, sparks only on lit mirrors")


if __name__ == "__main__":
    main()
