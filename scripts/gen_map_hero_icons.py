#!/usr/bin/env python3
"""The 8x8 Compass hero icons, one per class.

The dungeon Compass shows the hero's real 16x16 sprite in its 2x2 node. The
Riftwild and town maps and the legend only have one tile, and a 2:1
reduction of the sprite is mush, so these five are drawn by hand to keep
each class's silhouette: Wolfkin's ears, Sauran's snout and tail, Corvin's
beak, Picsean's head fin, Vespine's antennae and wings. They use the same
colour indices as the class sprites (o outline 2, # body 1, + highlight 3),
so they take the hero's own palette.

Run with --preview out.png to look at them beside the full sprites; the
default prints the C table for src/game/map_marks.c.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLASSES = ("wolfkin", "sauran", "corvin", "picsean", "vespine")


def sprite(name):
    text = (ROOT / "src/render/sprites_gen.c").read_text()
    body = re.search(rf"const u8 sprite_class_{name}\[64\] = \{{([^}}]*)\}}",
                     text).group(1)
    data = [int(v, 16) for v in re.findall(r"0x[0-9A-Fa-f]{2}", body)]
    px = [[0] * 16 for _ in range(16)]
    for t, (ox, oy) in enumerate(((0, 0), (8, 0), (0, 8), (8, 8))):
        for row in range(8):
            lo, hi = data[t * 16 + row * 2], data[t * 16 + row * 2 + 1]
            for col in range(8):
                bit = 7 - col
                px[oy + row][ox + col] = ((lo >> bit) & 1) | (((hi >> bit) & 1) << 1)
    return px


MINI = {
    "wolfkin": """
o......o
oo....oo
o######o
o#+##+#o
o######o
.o####o.
.o#oo#o.
.oo..oo.""",
    "sauran": """
..oo....
.o##o...
.o#+#oo.
.o#####o
oo####o.
o#o###o.
.oo#o#o.
...oo.oo""",
    "corvin": """
..ooo...
.o###o..
.o#+#ooo
.o####+o
.o###oo.
o#####o.
.o#o#o..
.oo.oo..""",
    "picsean": """
...oo...
..o++o..
.oo##oo.
o##+#+#o
o######o
.o####o.
.o#oo#o.
.oo..oo.""",
    "vespine": """
.o....o.
..o..o..
..o##o..
+o#++#o+
++####++
.o#++#o.
..o##o..
...oo...""",
}
INDEX = {".": 0, "#": 1, "o": 2, "+": 3}


def mini(name):
    rows = MINI[name].strip().splitlines()
    assert len(rows) == 8 and all(len(r) == 8 for r in rows), name
    return [[INDEX[c] for c in row] for row in rows]


def encode(px):
    data = []
    for row in px:
        lo = sum(((c & 1) << (7 - i)) for i, c in enumerate(row))
        hi = sum((((c >> 1) & 1) << (7 - i)) for i, c in enumerate(row))
        data += [lo, hi]
    return data


def main():
    minis = [mini(name) for name in CLASSES]
    if "--preview" in sys.argv:
        from PIL import Image
        shade = {0: (20, 30, 24), 1: (60, 60, 90), 2: (200, 150, 60), 3: (250, 240, 200)}
        img = Image.new("RGB", (5 * 24 * 8, 16 * 8), shade[0])
        for i, name in enumerate(CLASSES):
            big = sprite(name)
            for y in range(16):
                for x in range(16):
                    img.paste(shade[big[y][x]], (i * 192 + x * 8, y * 8, i * 192 + x * 8 + 8, y * 8 + 8))
            for y in range(8):
                for x in range(8):
                    img.paste(shade[minis[i][y][x]], (i * 192 + 128 + x * 8, y * 8, i * 192 + 136 + x * 8, y * 8 + 8))
        img.save(sys.argv[sys.argv.index("--preview") + 1])
        return
    print("static const u8 map_hero_mini[5][16] = {")
    for name, px in zip(CLASSES, minis):
        print("    { " + ", ".join(f"0x{b:02X}" for b in encode(px)) + " }, // " + name)
    print("};")


if __name__ == "__main__":
    main()
