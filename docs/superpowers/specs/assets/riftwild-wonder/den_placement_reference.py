#!/usr/bin/env python3
"""Reference (proposal) for seeded hidden-dungeon placement. Not game code.

Mirrors the algorithm in 2026-11-15-riftwild-hidden-dungeons.md so reviewers
can see where dens would land on the captured atlases.
"""
import sys
from PIL import Image, ImageDraw

# Fields that already own a fixture on main (b304d449): discovery/riftwell,
# Warden groves, cave, gates, class groves, boss landmark, vault, Hollow relics.
SPECIAL = {0, 1, 3, 5, 8, 16, 17, 21, 23, 27, 29, 30, 32, 34, 22, 35}
GATES = ("CAIRN", "DROWNED", "SCAR")


def xs(x):
    x &= 0xFFFFFFFF
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFFFFFF
    return x & 0xFFFFFFFF


def place(seed, region):
    h = xs(seed ^ ((region * 0x9E3779B9) & 0xFFFFFFFF) ^ 0x52494654) or 1
    order = [0, 1, 2]
    for i in (2, 1):
        h = xs(h)
        j = (h >> 8) % (i + 1)
        order[i], order[j] = order[j], order[i]
    h = xs(h)
    hollow = (h >> 8) % 3
    dens = []
    for band in range(3):
        cand = [c for c in range(band * 12, band * 12 + 12)
                if c not in SPECIAL]
        h = xs(h)
        cell = cand[(h >> 8) % len(cand)]
        h = xs(h)
        dens.append({"band": band, "cell": cell, "gate": GATES[order[band]],
                     "quad": (h >> 8) & 3, "hollow": band == hollow})
    return dens


def overlay(atlas_png, seed, region, out_png):
    gap = 4
    im = Image.open(atlas_png).convert("RGB")
    d = ImageDraw.Draw(im)
    for i, dn in enumerate(place(seed, region)):
        r, c = divmod(dn["cell"], 6)
        ox, oy = c * (248 + gap), r * (248 + gap)
        qx = (56, 184, 56, 184)[dn["quad"]]
        qy = (56, 56, 184, 184)[dn["quad"]]
        col = (255, 0, 255) if dn["hollow"] else (0, 255, 255)
        d.ellipse((ox + qx - 14, oy + qy - 14, ox + qx + 14, oy + qy + 14),
                  outline=col, width=3)
        d.rectangle((ox + 2, oy + 226, ox + 246, oy + 246), fill=(0, 0, 0))
        d.text((ox + 6, oy + 230), f"DEN {i + 1}: {dn['gate']}"
               + (" (HOLLOW)" if dn["hollow"] else ""), fill=col)
    d.rectangle((0, im.height - 20, 960, im.height), fill=(0, 0, 0))
    d.text((6, im.height - 16),
           f"ILLUSTRATIVE den placement, seed {seed:08X} region {region + 1}"
           " (reference hash from the spec; not game output)",
           fill=(255, 255, 255))
    im.save(out_png)


if __name__ == "__main__":
    for s in sys.argv[1:]:
        seed = int(s, 16)
        print(s, place(seed, 0))
        overlay(f"riftwild-seed-{s}-b1.png", seed, 0,
                f"riftwild-den-placement-{s}.png")
