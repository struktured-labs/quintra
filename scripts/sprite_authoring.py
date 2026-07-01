#!/usr/bin/env python3
"""
Sprite authoring helper for Quintra.

Source-of-truth: 16x16 (or 8x8) ASCII sprite specs in this file.
Outputs:
  - GBDK 2bpp tile-data C source (drop into render/tiles.c)
  - Aseprite pixel JSON (optional, for visualization round-trip)

Glyph map (ASCII -> palette index):
    .   = 0 = transparent (magenta in aseprite, color 0 in GBDK OBJ)
    1   = 1 = light (highlight)
    2   = 2 = mid  (body)
    3   = 3 = dark (outline)

8x8 sprite = 1 tile = 16 bytes.
16x16 sprite = 2x2 = 4 tiles, in row-major order:
    [top-left] [top-right]
    [bot-left] [bot-right]

In GBDK metasprite system, a 16x16 with sprite_tile T uses tiles T,T+1,T+2,T+3.
"""

import json
import sys


# ---------------- Sprite specs ------------------

# Each spec is a tuple of (name, ascii_grid_lines). Grids are W x H glyphs.

PLAYER_W = 16
PLAYER_H = 16

WOLFKIN = """\
..11........11..
.1331......1331.
.1331......1331.
..1111111111....
.111311111311...
.111111111111...
.1113111131111..
.111133311111...
.1111111111111..
11111111111111..
11111111111111..
1111.111111.11..
.111.11..11.111.
..1..1....1..1..
..1..1....1..1..
.................""".splitlines()

SAURAN = """\
.....111111.....
....11333311....
....13322331....
....11322311....
....11311311....
....11111111....
.....111111.....
....11111111....
..1111111111....
.111111111111...
1111111111111...
.111111111111...
..111111111111..
....1111111111..
....1.....1....1
....1......1...1""".splitlines()

CORVIN = """\
.....111111.....
....13311331....
....111111111...
....111111111111
....1111111111..
....111111111...
....1111111.....
..1111111111....
.111111111111...
1111111111111...
11..1111111..111
11..1111111..111
.1..1111111..1..
.....11111......
....1.....1.....
....1.....1.....""".splitlines()

PICSEAN = """\
......1111......
.....111111.....
....11111111....
...1111111111...
..111111111111..
..11331313111...
..1111111111....
....111111......
..11111111111...
1111111111111111
111111111111111.
.111111111111...
..1111.11111....
...1...1111.....
...11..1...11...
..111...11.111..""".splitlines()

VESPINE = """\
.1.....11.....1.
.11....11....11.
..11..1331..11..
...1111111111...
....11111111....
....13322331....
....11322311....
....11111111....
1111111111111111
.1111111111111..
..111111111111..
..1111111111....
...11111111.....
...111.1111.....
..11....111.....
.1.......1......""".splitlines()


# 8x8 enemies
ENEMY_W = 8
ENEMY_H = 8

CRAWLER = """\
..1111..
.131131.
.111111.
1.1111.1
1.1111.1
.111111.
1.1111.1
1.....1.""".splitlines()

HORNET = """\
1......1
.111111.
.131131.
.111111.
1.1111.1
1.1111.1
.1....1.
..1..1..""".splitlines()

SKELETON = """\
..1111..
.131131.
.111111.
.1.11.1.
.111111.
.111111.
1111.111
1...1...""".splitlines()

ORC = """\
.111111.
1331.331
1111.111
1111.111
.111111.
.111111.
.1.11.1.
1.1.1.1.""".splitlines()


# 8x8 bullet — animated 2-frame star. Bright core + spikes.
BULLET_A = """\
...11...
..1331..
.133331.
1333333.
1333333.
.133331.
..1331..
...11...""".splitlines()

BULLET_B = """\
........
..1..1..
.113311.
..1331..
..1331..
.113311.
..1..1..
........""".splitlines()

# 8x8 muzzle flash — spawns in front of player on fire, decays over ~3 frames
MUZZLE = """\
........
..1..1..
.1.32.1.
..3223..
..2332..
.1.23.1.
..1..1..
........""".splitlines()

# 8x8 hit impact FX — sparks radiating outward, ~6-frame lifetime
IMPACT = """\
1.1..1.1
.1.11.1.
..1111..
.111111.
.111111.
..1111..
.1.11.1.
1.1..1.1""".splitlines()


# 16x16 boss (Stone Sentinel)
BOSS = """\
....111111111...
...13322331111..
...13322331111..
...111111111111.
...111133311111.
...111322231111.
...111322231111.
...111133311111.
..111111111111..
.1111111111111..
1111111111111111
1111.111111.1111
.111.111111.111.
.111.111111.111.
..1...1111...1..
.11...1.1...11..""".splitlines()


# ---------------- Conversion --------------------

GLYPH_TO_IDX = {".": 0, "1": 1, "2": 2, "3": 3}
IDX_TO_HEX   = {0: "#FF00FF", 1: "#A0A0A0", 2: "#606060", 3: "#202020"}


def parse_grid(lines):
    """Return 2D list [y][x] of palette indices (0..3)."""
    return [[GLYPH_TO_IDX[c] for c in line] for line in lines]


def tile_2bpp_bytes(grid8x8):
    """Convert an 8x8 indexed grid (list of 8 lists of 8) to 16 GBDK 2bpp bytes.

    GBDK format per row: byte_low + byte_high where each pixel's color =
    (bit_in_high << 1) | bit_in_low (NOT the other way around — GB layouts pack
    bit 0 as low plane, bit 1 as high plane).
    """
    out = []
    for row in grid8x8:
        lo = 0
        hi = 0
        for x, idx in enumerate(row):
            bit = 7 - x   # MSB = leftmost
            lo |= ((idx & 0x1) << bit)
            hi |= (((idx >> 1) & 0x1) << bit)
        out.append(lo)
        out.append(hi)
    return out


def sprite_to_tiles(grid, w, h):
    """Slice a grid into 8x8 tiles in row-major order (TL,TR,BL,BR for 16x16)."""
    tiles = []
    for ty in range(0, h, 8):
        for tx in range(0, w, 8):
            tile = [row[tx:tx+8] for row in grid[ty:ty+8]]
            tiles.append(tile)
    return tiles


def grid_to_aseprite_pixels(grid, offset_x=0, offset_y=0):
    pixels = []
    for y, row in enumerate(grid):
        for x, idx in enumerate(row):
            if idx == 0:
                continue   # leave transparent
            pixels.append({
                "x": offset_x + x,
                "y": offset_y + y,
                "color": IDX_TO_HEX[idx],
            })
    return pixels


def emit_tile_c_array(name, tile_bytes):
    body = ", ".join(f"0x{b:02X}" for b in tile_bytes)
    return f"const u8 {name}[16] = {{ {body} }};"


def emit_metasprite_c_array(name, tile_lists):
    """Emit a flat array of N tiles * 16 bytes for a metasprite."""
    flat = []
    for tile in tile_lists:
        flat.extend(tile_2bpp_bytes(tile))
    body = ", ".join(f"0x{b:02X}" for b in flat)
    return f"const u8 {name}[{len(flat)}] = {{ {body} }};"


# ---------------- Main --------------------

PLAYERS = [
    ("wolfkin", WOLFKIN),
    ("sauran",  SAURAN),
    ("corvin",  CORVIN),
    ("picsean", PICSEAN),
    ("vespine", VESPINE),
]
ENEMIES_8 = [
    ("crawler",  CRAWLER),
    ("hornet",   HORNET),
    ("skeleton", SKELETON),
    ("orc",      ORC),
]

FX_8 = [
    ("bullet_a", BULLET_A),
    ("bullet_b", BULLET_B),
    ("muzzle",   MUZZLE),
    ("impact",   IMPACT),
]


def emit_all_c():
    print("// Auto-generated by scripts/sprite_authoring.py — do not edit by hand.")
    print("// Glyph map: .=0 transparent, 1=light, 2=mid, 3=dark")
    print()
    print('#include "core/types.h"')
    print()

    # Players (each is 16x16 = 4 tiles)
    for name, lines in PLAYERS:
        grid = parse_grid(lines)
        tiles = sprite_to_tiles(grid, PLAYER_W, PLAYER_H)
        print(emit_metasprite_c_array(f"sprite_class_{name}", tiles))

    # Enemies (each 8x8 = 1 tile)
    for name, lines in ENEMIES_8:
        grid = parse_grid(lines)
        bytes_ = tile_2bpp_bytes(grid)
        print(emit_tile_c_array(f"sprite_enemy_{name}", bytes_))

    # FX sprites (8x8 each)
    for name, lines in FX_8:
        grid = parse_grid(lines)
        bytes_ = tile_2bpp_bytes(grid)
        print(emit_tile_c_array(f"sprite_fx_{name}", bytes_))

    # Boss (16x16 = 4 tiles)
    grid = parse_grid(BOSS)
    tiles = sprite_to_tiles(grid, 16, 16)
    print(emit_metasprite_c_array("sprite_boss_sentinel", tiles))


def emit_aseprite_pixels():
    """Print one JSON array of all pixels positioned on the master sheet."""
    layout = []
    # Players row at y=0: spaced 16px apart
    for i, (name, lines) in enumerate(PLAYERS):
        grid = parse_grid(lines)
        layout.extend(grid_to_aseprite_pixels(grid, offset_x=i*16, offset_y=0))
    # Enemies at y=16
    for i, (name, lines) in enumerate(ENEMIES_8):
        grid = parse_grid(lines)
        layout.extend(grid_to_aseprite_pixels(grid, offset_x=i*8, offset_y=16))
    # Boss at (32, 24) (16x16)
    grid = parse_grid(BOSS)
    layout.extend(grid_to_aseprite_pixels(grid, offset_x=32, offset_y=24))
    print(json.dumps(layout))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "c"
    if mode == "c":
        emit_all_c()
    elif mode == "json":
        emit_aseprite_pixels()
    else:
        print(f"Unknown mode: {mode}", file=sys.stderr)
        sys.exit(1)
