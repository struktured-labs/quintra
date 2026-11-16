#!/usr/bin/env python3
"""Generate src/render/riftwild_art.{c,h}: Riftwild tile variety in VRAM bank 1.

Every tile is hand-authored ASCII (colour index 0..3, 0 darkest, matching the
Riftwild BG palettes) except the great tree, which is drawn procedurally from
a fixed formula. The tiles load into VRAM bank 1 at 0x9000 (signed BG ids
0..127, BG-only on CGB). Riftwild uses ids RW_ART_TERRAIN_BASE.. and
RW_ART_PIECE_BASE..; the Hexa arena keeps 40..55 and 56..63 / 112..127 stay
free for other work (hidden dens).

  python3 scripts/gen_riftwild_art.py   # rewrites src/render/riftwild_art.c/.h
  python3 scripts/gen_riftwild_art.py --png OUT.png   # 8x preview sheet
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

T = {}  # name -> list of 8 strings

T["grass_tuft"] = """
........
........
..1.....
.1.1.1..
..111...
........
......1.
........"""
T["grass_pebble"] = """
........
........
........
...23...
...22...
........
.2......
........"""
T["grass_bloom"] = """
........
...3....
..323...
...3....
........
.....2..
....232.
.....2.."""
T["snow_drift"] = """
........
........
........
...111..
..13331.
........
........
........"""
T["snow_glint"] = """
........
...3....
..333...
...3....
........
......3.
........
........"""
T["sand_shell"] = """
........
........
........
...33...
..3223..
...33...
........
........"""
T["sand_crack"] = """
........
........
..1.....
...1....
...111..
......1.
........
........"""
T["mud_puddle"] = """
........
........
..1111..
.122221.
..1111..
........
........
........"""
T["mud_roots"] = """
........
........
..1...1.
...1.1..
....1...
........
........
........"""
T["path_stones"] = """
........
.111....
12221...
.111....
.....11.
....1221
.....11.
........"""
# 2x2 canopy: a forest border reads as round crowns instead of 8px dots.
T["tree_tl"] = """
.....333
...33111
..311121
.3112111
.3121111
31111211
31211111
31111111"""
T["tree_tr"] = """
333.....
11133...
121113..
1112113.
1111113.
12111113
11112113
11111113"""
T["tree_bl"] = """
31111211
31121111
.3111111
.3311121
..333111
....3333
......33
.......2"""
T["tree_br"] = """
11111113
11211113
1111113.
121113..
111333..
3333....
33......
2......."""
# 2x2 crag: one peak per 16x16 block, so a ridge reads as mountains.
T["crag_tl"] = """
.......3
......31
.....311
....3111
...31121
..311211
.3112111
31121111"""
T["crag_tr"] = """
3.......
33......
133.....
1113....
11113...
211113..
1211113.
11211113"""
T["crag_bl"] = """
31211111
11111211
12111111
11112111
11211111
21111121
11111111
33333333"""
T["crag_br"] = """
11111113
11211111
11111211
21111111
11112111
11211111
11111111
33333333"""
# Shorelines (water palette): land above / land left / both. The south,
# east and other corners are flips of these three.
T["shore_n"] = """
........
........
3.333.33
11221122
.22..22.
22112211
12211221
..22..22"""
T["shore_w"] = """
..3.1122
..3.2112
..3.1122
...3.22.
..3.2211
..3.1221
...3..22
..3.2112"""
T["shore_nw"] = """
........
........
.....333
....3122
...3.22.
..3.2211
..3.1221
...3..22"""

# Inner corner: all cardinal neighbours are water, land only on the NW
# diagonal. Flips cover NE/SW/SE. Rounds the stairsteps of diamond lakes.
T["shore_inner"] = """
..332211
.3.22112
3.221122
22112211
12211221
22112211
12211221
2211.22."""
# Sinkhole edges (crack palette). Same three-plus-inner set as water; flips
# cover the other sides. Color 0 is the surrounding earth, 3 the amber rim.
T["hole_n"] = """
........
........
3.323.33
11211121
.11..11.
11121112
21112111
..11..11"""
T["hole_w"] = """
..3.1112
..3.2111
..3.1112
...3.11.
..3.1121
..3.2111
...3..11
..3.1112"""
T["hole_nw"] = """
........
........
.....333
....3112
...3.11.
..3.1121
..3.2111
...3..11"""
T["hole_inner"] = """
..331112
.3.11121
3.111211
11121112
21112111
11121112
21112111
1112.11."""

# Set-piece props (walkable or solid tiles keep their logical BGT id).
T["column_top"] = """
.333333.
32222223
.333333.
..3223..
..3213..
..3223..
..3213..
..3223.."""
T["column_base"] = """
..3213..
..3223..
..3213..
..3223..
.333333.
32222223
31111113
.333333."""
T["column_broken"] = """
........
...3....
..323.3.
..3213..
..3223..
..3213..
..3223..
..3213.."""
T["flagstone"] = """
111.1111
111.1111
........
11111.11
11111.11
........
1.111111
1.111111"""
T["obelisk_top"] = """
...33...
..3223..
.321123.
.321323.
.321123.
.323123.
.321123.
.321323."""
T["obelisk_base"] = """
.321123.
.323123.
.321123.
.321323.
32111123
32222223
.333333.
........"""


def big(rows):
    rows = [r for r in rows.strip("\n").split("\n")]
    h, w = len(rows), len(rows[0])
    assert h % 8 == 0 and w % 8 == 0, (w, h)
    return rows


# A 16x24 Worldglass spire (CRYSTAL palette): the Riftwild glass, tall.
SPIRE = big("""
.......33.......
......3223......
......3223......
.....321123.....
.....321123.....
....32111123....
.3.3211111123.3.
.323211111123.3.
.32321111112323.
.32221111111223.
3212111111112123
3212111111112123
3211111131111123
3221111333111223
3211111131111123
3211111111111123
3211111111111123
3221111111111223
.32211111111223.
.33221111112233.
..332211112233..
...3332222333...
.....333333.....
................""")

# A 16x24 guardian statue on a plinth (DOOR palette, sandstone).
STATUE = big("""
......3333......
.....322223.....
....32211223....
....32122123....
.....322223.....
...3332112333...
..322232232223..
.32112322321123.
.321.322223.123.
.31..321123..13.
.....321123.....
.....321123.....
.....321123.....
....32211223....
....32111123....
....321..123....
....321..123....
...3221..1223...
..333333333333..
.32222222222223.
.32111111111123.
.32111111111123.
.33333333333333.
................""")


def great_tree():
    """24x24 lone giant tree (WALL palette), drawn from a fixed formula."""
    w = h = 24
    g = [["."] * w for _ in range(h)]
    cx, cy, r = 11.5, 9.5, 10.2
    for y in range(h):
        for x in range(w):
            d = math.hypot(x - cx, (y - cy) * 1.1)
            # Lobed crown so it reads as foliage, not a disc.
            lobe = r + 1.2 * math.sin(math.atan2(y - cy, x - cx) * 5)
            if d <= lobe - 1.0:
                c = "1"
                if (x * 7 + y * 13) % 11 == 0 or (x * 5 + y * 3) % 17 == 0:
                    c = "2"
                if y < cy - 3 and (x + y) % 5 == 0 and d < lobe - 2.5:
                    c = "3"
                g[y][x] = c
            elif d <= lobe:
                g[y][x] = "3"
    for y in range(17, 24):
        for x in range(9, 15):
            if g[y][x] in ".3" or y > 19:
                edge = x in (9, 14)
                g[y][x] = "3" if edge else ("2" if (x + y) % 3 else "1")
    for x in range(6, 18):
        if g[23][x] == ".":
            g[23][x] = "3" if x in (6, 17) else "2"
    return ["".join(r) for r in g]


TREE = great_tree()


def slice_big(name, rows):
    h, w = len(rows), len(rows[0])
    out = []
    for ty in range(h // 8):
        for tx in range(w // 8):
            out.append((f"{name}_{ty}_{tx}",
                        [rows[ty * 8 + y][tx * 8:tx * 8 + 8] for y in range(8)]))
    return out


TERRAIN = [
    "grass_tuft", "grass_pebble", "grass_bloom",
    "snow_drift", "snow_glint", "sand_shell", "sand_crack",
    "mud_puddle", "mud_roots", "path_stones",
    "tree_tl", "tree_tr", "tree_bl", "tree_br",
    "crag_tl", "crag_tr", "crag_bl", "crag_br",
    "shore_n", "shore_w", "shore_nw", "shore_inner",
    "hole_n", "hole_w", "hole_nw", "hole_inner",
]
PROPS = ["column_top", "column_base", "column_broken", "flagstone",
         "obelisk_top", "obelisk_base"]

TERRAIN_BASE = 0
PIECE_BASE = 64


def tiles():
    out = [(n, T[n].strip("\n").split("\n")) for n in TERRAIN]
    pieces = [(n, T[n].strip("\n").split("\n")) for n in PROPS]
    pieces += slice_big("spire", SPIRE)
    pieces += slice_big("statue", STATUE)
    pieces += slice_big("great_tree", TREE)
    return out, pieces


def encode(rows):
    assert len(rows) == 8 and all(len(r) == 8 for r in rows), rows
    data = []
    for r in rows:
        lo = hi = 0
        for x, ch in enumerate(r):
            v = 0 if ch == "." else int(ch)
            lo |= (v & 1) << (7 - x)
            hi |= ((v >> 1) & 1) << (7 - x)
        data += [lo, hi]
    return data


def write_c():
    terrain, pieces = tiles()
    assert TERRAIN_BASE + len(terrain) <= 40, "terrain must stay below Hexa 40"
    assert PIECE_BASE + len(pieces) <= 112, "pieces must leave 112..127 free"
    h = ["#ifndef QUINTRA_RENDER_RIFTWILD_ART_H",
         "#define QUINTRA_RENDER_RIFTWILD_ART_H",
         "// Generated by scripts/gen_riftwild_art.py. Do not edit by hand.",
         "// VRAM bank 1 BG ids (0x9000 signed region, attribute bit 3).",
         '#include "core/types.h"', "",
         f"#define RW_ART_TERRAIN_BASE {TERRAIN_BASE}",
         f"#define RW_ART_TERRAIN_COUNT {len(terrain)}",
         f"#define RW_ART_PIECE_BASE {PIECE_BASE}",
         f"#define RW_ART_PIECE_COUNT {len(pieces)}"]
    for i, (n, _) in enumerate(terrain):
        h.append(f"#define RWA_{n.upper()} {TERRAIN_BASE + i}")
    for i, (n, _) in enumerate(pieces):
        h.append(f"#define RWA_{n.upper()} {PIECE_BASE + i}")
    h += ["", "// Loads every Riftwild bank-1 tile; idempotent and cheap to repeat.",
          "void riftwild_art_load(void) BANKED;", "", "#endif", ""]
    c = ["#pragma bank 19", "// Bank 19: dens (PR) already claimed bank 18.",
         "// Generated by scripts/gen_riftwild_art.py. Do not edit by hand.",
         "#include <gb/gb.h>", '#include "render/riftwild_art.h"', "",
         "BANKREF(riftwild_art_load)", ""]
    for label, group in (("terrain", terrain), ("pieces", pieces)):
        c.append(f"static const u8 rw_{label}[{len(group) * 16}] = {{")
        for n, rows in group:
            c.append("    " + ", ".join(f"0x{b:02X}" for b in encode(rows))
                     + f",  // {n}")
        c.append("};")
        c.append("")
    c += ["void riftwild_art_load(void) BANKED {",
          "    VBK_REG = 1;",
          f"    set_bkg_data(RW_ART_TERRAIN_BASE, RW_ART_TERRAIN_COUNT, rw_terrain);",
          f"    set_bkg_data(RW_ART_PIECE_BASE, RW_ART_PIECE_COUNT, rw_pieces);",
          "    VBK_REG = 0;", "}", ""]
    (ROOT / "src/render/riftwild_art.h").write_text("\n".join(h))
    (ROOT / "src/render/riftwild_art.c").write_text("\n".join(c))
    print("wrote", len(terrain), "terrain +", len(pieces), "piece tiles")


PREVIEW_PAL = {
    "floor": [(16, 41, 16), (49, 123, 49), (98, 189, 74), (180, 238, 131)],
    "wall": [(8, 32, 16), (32, 82, 32), (65, 148, 57), (148, 205, 90)],
    "crystal": [(8, 41, 49), (32, 115, 148), (82, 197, 238), (222, 255, 255)],
    "door": [(32, 16, 8), (90, 49, 16), (172, 106, 41), (255, 197, 98)],
}


PREVIEW_PAL["crack"] = [(16, 8, 0), (74, 32, 8), (180, 90, 16), (255, 197, 74)]


def pal_for(name):
    if name.startswith(("tree", "crag", "great_tree")):
        return "wall"
    if name.startswith(("snow", "shore", "spire", "obelisk")):
        return "crystal"
    if name.startswith(("sand", "column", "flagstone", "statue")):
        return "door"
    if name.startswith("hole"):
        return "crack"
    return "floor"


def png(out):
    from PIL import Image
    terrain, pieces = tiles()
    allt = terrain + pieces
    cols = 10
    im = Image.new("RGB", (cols * 9 * 8, ((len(allt) + cols - 1) // cols) * 9 * 8), (60, 0, 60))
    for i, (n, rows) in enumerate(allt):
        pal = PREVIEW_PAL[pal_for(n)]
        ox, oy = (i % cols) * 72, (i // cols) * 72
        for y in range(8):
            for x in range(8):
                ch = rows[y][x]
                col = pal[0 if ch == "." else int(ch)]
                for dy in range(8):
                    for dx in range(8):
                        im.putpixel((ox + x * 8 + dx, oy + y * 8 + dy), col)
    im.save(out)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--png":
        png(sys.argv[2])
    else:
        write_c()
