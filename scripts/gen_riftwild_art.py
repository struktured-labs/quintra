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
........
..1..1..
..1.1...
........
........
........"""
T["grass_pebble"] = """
........
........
........
........
...22...
...11...
........
........"""
T["grass_bloom"] = """
........
........
...3....
..323...
...1....
........
........
........"""
T["snow_drift"] = """
........
........
........
...222..
..2...2.
........
........
........"""
T["snow_glint"] = """
........
........
....3...
........
........
........
........
........"""
T["sand_shell"] = """
........
........
........
...22...
...11...
........
........
........"""
T["sand_crack"] = """
........
........
........
..11....
....111.
........
........
........"""
T["mud_puddle"] = """
........
........
........
..1111..
.112211.
..1111..
........
........"""
T["mud_roots"] = """
........
........
...1....
....1.1.
.....1..
........
........
........"""
T["path_stones"] = """
11111111
11122111
11233211
11122111
11111111
11111221
11112332
11111221"""
# 2x2 canopy: a forest border reads as round crowns instead of 8px dots.
T["tree_tl"] = """
.....111
...11333
..133333
.1333332
.1333222
13332212
13322122
13221222"""
T["tree_tr"] = """
111.....
32211...
222221..
2222221.
2222221.
22122221
21222121
12221221"""
T["tree_bl"] = """
12222221
12212222
.1221222
.1222122
..112222
...11112
......12
.....111"""
T["tree_br"] = """
22212221
21222121
2122121.
2212221.
222211..
21111...
21......
111....."""
# 2x2 crag: one peak per 16x16 block, so a ridge reads as mountains.
T["crag_tl"] = """
.......1
......13
.....133
....1333
....1333
...13332
..133322
..133221"""
T["crag_tr"] = """
1.......
31......
321.....
3221....
2221....
21121...
212221..
122221.."""
T["crag_bl"] = """
.1332221
.1322221
13322212
13222122
12221222
12212222
12122221
.1111111"""
T["crag_br"] = """
1222221.
2222121.
22212221
22122221
21222211
12222121
22221221
1111111."""
# Shorelines (water palette): land above / land left / both. The south,
# east and other corners are flips of these three.
T["shore_n"] = """
........
........
33333333
22222222
11111111
11112211
11111111
11111111"""
T["shore_w"] = """
..321111
..321111
..321111
..321121
..321111
..321111
..321111
..321111"""
T["shore_nw"] = """
........
........
....3333
...32222
..321111
..321111
..321122
..321111"""

# Inner corner: all cardinal neighbours are water, land only on the NW
# diagonal. Flips cover NE/SW/SE. Rounds the stairsteps of diamond lakes.
T["shore_inner"] = """
..321111
.3321111
33211111
22111111
11111111
11112211
11111111
11111111"""
# Sinkhole edges (crack palette). Same three-plus-inner set as water; flips
# cover the other sides. Color 0 is the surrounding earth, 3 the amber rim;
# a colour-0 band just inside the rim is the pit's shadowed lip, so the
# sinkhole reads sunken rather than as a raised slab.
T["hole_n"] = """
........
........
33233323
00000000
11111111
11111111
11111111
11111111"""
T["hole_w"] = """
..301111
..301111
..301111
..301111
..301111
..301111
..301111
..301111"""
T["hole_nw"] = """
........
........
....3332
...30000
..300111
..301111
..301111
..301111"""
T["hole_inner"] = """
..301111
.3301111
33011111
00111111
11111111
11111111
11111111
11111111"""

# Self-contained fallbacks (2026-11-17 tiles pass). A tree or crag cell
# whose aligned 2x2 metatile is incomplete draws *_lone instead of an
# orphan quarter; water/sinkhole cells with three or four land sides, or
# a one-tile channel, draw lone/cap/strait pieces (flips cover the rest).
# Ground tiles keep colour 0 = the shared Riftwild ground colour.
T["tree_lone"] = """
..1111..
.133221.
13322221
13222121
12212221
12222211
.112211.
...11..."""
T["crag_lone"] = """
...11...
..1331..
.133221.
.132221.
13322121
13221221
12222211
.111111."""
T["grass_plain"] = """
........
........
........
........
........
........
........
........"""
T["path_plain"] = """
11111111
11111111
11111111
11111111
11111111
11111111
11111111
11111111"""
T["shore_lone"] = """
........
........
..3333..
..3113..
..3113..
..3333..
........
........"""
T["shore_cap_n"] = """
........
........
..3333..
..3113..
..3113..
..3113..
..3113..
..3113.."""
T["shore_cap_w"] = """
........
........
..333333
..311111
..311111
..333333
........
........"""
T["shore_strait_h"] = """
........
........
33333333
11111111
11111111
33333333
........
........"""
T["shore_strait_v"] = """
..3113..
..3113..
..3113..
..3113..
..3113..
..3113..
..3113..
..3113.."""
T["hole_lone"] = """
........
........
..3323..
..3003..
..3013..
..3323..
........
........"""
T["hole_cap_n"] = """
........
........
..3323..
..3003..
..3013..
..3013..
..3013..
..3013.."""
T["hole_cap_w"] = """
........
........
..332333
..300000
..301111
..332333
........
........"""
T["hole_strait_h"] = """
........
........
33233323
00000000
11111111
33233323
........
........"""
T["hole_strait_v"] = """
..3013..
..3013..
..3013..
..3013..
..3013..
..3013..
..3013..
..3013.."""

# Worldglass shard cluster (crystal palette): BGT_CRYSTAL out in the
# Riftwild drew the square dungeon crystal block; this sits on the ground.
T["shard"] = """
....1...
...131..
.1.1321.
1311321.
13213221
12212221
.122221.
..1111.."""

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
    "tree_lone",
    "crag_lone",
    "grass_plain",
    "path_plain",
    "shore_lone",
    "shore_cap_n",
    "shore_cap_w",
    "shore_strait_h",
    "shore_strait_v",
    "hole_lone",
    "hole_cap_n",
    "hole_cap_w",
    "hole_strait_h",
    "hole_strait_v",
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
    pieces += [("shard", T["shard"].strip("\n").split("\n"))]
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
    c = ["#pragma bank 21",
         "// Bank 21: bank 19 keeps the hot Riftwild dress pass (tiles pass).",
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
    if name.startswith(("snow", "shore", "spire", "obelisk", "shard")):
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
