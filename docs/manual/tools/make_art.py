#!/usr/bin/env python3
"""Original pixel plates for the Quintra manual.

Colors are the cartridge's 5-bit BGR555 ramps from class_palettes.c and
stages.rs, expanded to 8-bit. No third-party artwork is traced. Output is
native-resolution PNG (nearest-neighbor scaling happens only in the PDF
build, at an integer factor).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1] / "content" / "images"


def rgb5(r: int, g: int, b: int) -> tuple[int, int, int, int]:
    return tuple(int(round(c * 255 / 31)) for c in (r, g, b)) + (255,)


INK = rgb5(2, 1, 3)
NIGHT = rgb5(4, 2, 7)
VOID = rgb5(8, 4, 14)
CREAM = rgb5(30, 28, 22)
GOLD = rgb5(31, 24, 6)
AMBER = rgb5(30, 18, 4)
HEART = rgb5(31, 6, 8)
CYAN = rgb5(4, 25, 31)
WHITE = rgb5(31, 31, 31)
MOSS = rgb5(8, 20, 6)
EMBER = rgb5(28, 10, 2)

# class_obj_palettes: index 1 body, 2 shadow, 3 accent.
HEROES = {
    "wolfkin": (rgb5(28, 22, 14), rgb5(14, 8, 4), rgb5(30, 28, 20)),
    "sauran": (rgb5(10, 24, 8), rgb5(4, 12, 4), rgb5(24, 30, 12)),
    "corvin": (rgb5(14, 10, 22), rgb5(6, 4, 12), rgb5(26, 24, 30)),
    "picsean": (rgb5(10, 20, 28), rgb5(4, 8, 18), rgb5(20, 30, 30)),
    "vespine": (rgb5(30, 26, 6), rgb5(12, 10, 2), rgb5(30, 14, 4)),
}


class Pix:
    def __init__(self, w: int, h: int, fill=(0, 0, 0, 0)):
        self.im = Image.new("RGBA", (w, h), fill)
        self.w = w
        self.h = h

    def p(self, x: int, y: int, c) -> None:
        if 0 <= x < self.w and 0 <= y < self.h and c[3]:
            self.im.putpixel((int(x), int(y)), c)

    def rect(self, x, y, w, h, c) -> None:
        for yy in range(int(y), int(y + h)):
            for xx in range(int(x), int(x + w)):
                self.p(xx, yy, c)

    def fill(self, c) -> None:
        self.rect(0, 0, self.w, self.h, c)

    def ellipse(self, cx, cy, rx, ry, c) -> None:
        if rx <= 0 or ry <= 0:
            return
        for y in range(int(cy - ry), int(cy + ry) + 1):
            for x in range(int(cx - rx), int(cx + rx) + 1):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.05:
                    self.p(x, y, c)

    def blit(self, other: "Pix", ox: int, oy: int) -> None:
        self.im.alpha_composite(other.im, (ox, oy))

    def save(self, name: str) -> None:
        path = ROOT / name
        path.parent.mkdir(parents=True, exist_ok=True)
        self.im.save(path, "PNG")


def outlined_ellipse(pix, cx, cy, rx, ry, fill, edge) -> None:
    pix.ellipse(cx, cy, rx + 1, ry + 1, edge)
    pix.ellipse(cx, cy, rx, ry, fill)


def hero(kind: str) -> Pix:
    body, edge, accent = HEROES[kind]
    p = Pix(40, 56)
    # ground shadow
    p.ellipse(20, 52, 10, 2, (*edge[:3], 180))
    if kind == "wolfkin":
        p.rect(10, 4, 4, 6, edge)
        p.rect(26, 4, 4, 6, edge)
        p.rect(11, 5, 2, 4, accent)
        p.rect(27, 5, 2, 4, accent)
        outlined_ellipse(p, 20, 16, 9, 8, body, edge)
        p.ellipse(20, 19, 4, 3, accent)
        p.rect(16, 18, 2, 1, edge)
        p.rect(22, 18, 2, 1, edge)
        p.rect(14, 14, 3, 3, INK)
        p.rect(23, 14, 3, 3, INK)
        p.p(15, 15, accent)
        p.p(24, 15, accent)
        outlined_ellipse(p, 20, 34, 8, 9, body, edge)
        p.rect(8, 28, 4, 8, body)
        p.rect(28, 28, 4, 8, body)
        p.rect(14, 42, 4, 8, edge)
        p.rect(22, 42, 4, 8, edge)
    elif kind == "sauran":
        outlined_ellipse(p, 20, 18, 10, 8, body, edge)
        p.rect(8, 16, 4, 3, accent)
        p.rect(28, 16, 4, 3, accent)
        p.rect(13, 16, 3, 3, INK)
        p.rect(24, 16, 3, 3, INK)
        p.rect(17, 20, 6, 2, edge)
        outlined_ellipse(p, 20, 34, 11, 10, body, edge)
        p.rect(12, 30, 16, 3, accent)
        p.rect(6, 30, 5, 6, body)
        p.rect(29, 30, 5, 6, body)
        p.rect(30, 36, 8, 3, accent)  # tail
        p.rect(13, 43, 5, 8, edge)
        p.rect(22, 43, 5, 8, edge)
    elif kind == "corvin":
        p.rect(4, 18, 10, 4, edge)
        p.rect(26, 18, 10, 4, edge)
        p.rect(6, 16, 8, 3, body)
        p.rect(26, 16, 8, 3, body)
        outlined_ellipse(p, 20, 16, 8, 7, body, edge)
        p.rect(17, 18, 6, 3, accent)  # beak
        p.rect(13, 14, 3, 3, INK)
        p.rect(22, 14, 3, 3, INK)
        p.p(14, 15, accent)
        p.p(23, 15, accent)
        outlined_ellipse(p, 20, 32, 7, 9, body, edge)
        p.rect(15, 40, 3, 8, edge)
        p.rect(22, 40, 3, 8, edge)
    elif kind == "picsean":
        p.rect(16, 2, 8, 5, accent)  # crest
        outlined_ellipse(p, 20, 16, 9, 8, body, edge)
        p.ellipse(28, 18, 5, 3, accent)  # fin-snout
        p.rect(12, 14, 3, 3, INK)
        p.rect(18, 14, 3, 3, INK)
        p.p(13, 15, accent)
        p.p(19, 15, accent)
        outlined_ellipse(p, 18, 34, 8, 10, body, edge)
        p.rect(8, 28, 5, 8, body)
        p.rect(26, 46, 8, 3, accent)
        p.rect(12, 43, 4, 7, edge)
        p.rect(20, 43, 4, 7, edge)
    else:
        p.ellipse(12, 14, 7, 4, (*accent[:3], 230))
        p.ellipse(28, 14, 7, 4, (*accent[:3], 230))
        p.ellipse(12, 14, 4, 2, body)
        p.ellipse(28, 14, 4, 2, body)
        outlined_ellipse(p, 20, 18, 7, 7, body, edge)
        p.rect(13, 16, 3, 3, INK)
        p.rect(22, 16, 3, 3, INK)
        p.rect(18, 22, 4, 3, edge)  # sting-mouth
        outlined_ellipse(p, 20, 34, 7, 8, body, edge)
        p.rect(18, 40, 4, 6, edge)
        p.rect(19, 46, 2, 6, accent)  # stinger
        p.rect(12, 30, 3, 6, body)
        p.rect(25, 30, 3, 6, body)
    return p


def boss_plate(kind: str) -> Pix:
    p = Pix(72, 48, (0, 0, 0, 0))
    if kind == "crystal":
        p.fill((0, 0, 0, 0))
        for x, y, w, h, c in (
            (30, 8, 12, 28, CYAN),
            (18, 16, 14, 22, rgb5(10, 22, 29)),
            (42, 14, 14, 24, rgb5(16, 18, 26)),
            (34, 4, 6, 10, WHITE),
            (24, 20, 4, 4, WHITE),
        ):
            p.rect(x, y, w, h, c)
    elif kind == "serpent":
        p.ellipse(36, 28, 22, 10, rgb5(10, 3, 15))
        p.ellipse(36, 28, 14, 6, rgb5(27, 8, 24))
        p.ellipse(52, 18, 8, 6, rgb5(31, 31, 14))
        p.rect(48, 16, 3, 3, INK)
        p.rect(54, 16, 3, 3, INK)
    elif kind == "rex":
        p.rect(16, 20, 40, 16, rgb5(22, 9, 4))
        p.rect(40, 10, 22, 14, rgb5(31, 22, 4))
        p.rect(52, 14, 4, 4, INK)
        p.rect(18, 34, 6, 8, rgb5(6, 2, 1))
        p.rect(30, 34, 6, 8, rgb5(6, 2, 1))
        p.rect(44, 36, 8, 4, AMBER)
    elif kind == "spider":
        p.ellipse(36, 24, 10, 8, rgb5(12, 18, 24))
        p.ellipse(36, 24, 4, 4, WHITE)
        for a, b in ((8, 10), (8, 34), (18, 6), (18, 40), (54, 8), (54, 38), (62, 16), (62, 32)):
            p.rect(a, b, 12, 2, rgb5(3, 5, 9))
    elif kind == "mire":
        p.ellipse(36, 24, 14, 12, rgb5(16, 20, 4))
        p.ellipse(36, 24, 6, 5, rgb5(31, 31, 14))
        p.rect(20, 34, 3, 10, rgb5(4, 6, 1))
        p.rect(34, 36, 3, 10, rgb5(4, 6, 1))
        p.rect(48, 34, 3, 10, rgb5(4, 6, 1))
    elif kind == "reaper":
        p.rect(28, 6, 16, 10, rgb5(13, 11, 20))
        p.rect(22, 16, 28, 22, rgb5(3, 3, 6))
        p.rect(30, 20, 4, 4, rgb5(28, 22, 31))
        p.rect(40, 20, 4, 4, rgb5(28, 22, 31))
        p.rect(8, 28, 16, 3, rgb5(21, 21, 26))
    elif kind == "sun":
        p.ellipse(36, 24, 12, 12, GOLD)
        p.ellipse(36, 24, 5, 5, rgb5(6, 4, 1))
        for x, y in ((34, 2), (34, 40), (8, 22), (58, 22), (16, 8), (52, 8), (16, 36), (52, 36)):
            p.rect(x, y, 4, 4, rgb5(31, 30, 18))
    elif kind == "hydra":
        p.ellipse(24, 16, 8, 6, rgb5(20, 4, 6))
        p.ellipse(40, 12, 8, 6, rgb5(31, 6, 10))
        p.ellipse(52, 20, 8, 6, rgb5(6, 1, 2))
        p.rect(30, 22, 16, 16, rgb5(20, 4, 6))
        p.rect(22, 14, 3, 3, GOLD)
        p.rect(38, 10, 3, 3, GOLD)
        p.rect(50, 18, 3, 3, GOLD)
    else:  # void
        p.ellipse(36, 24, 16, 14, rgb5(3, 1, 7))
        p.ellipse(36, 24, 6, 6, rgb5(20, 31, 18))
        p.rect(34, 8, 4, 6, rgb5(13, 6, 20))
        p.rect(18, 22, 6, 4, rgb5(13, 6, 20))
        p.rect(50, 22, 6, 4, rgb5(13, 6, 20))
    return p


def cover() -> Pix:
    p = Pix(160, 208, rgb5(3, 1, 6))
    for y in range(168):
        shade = 3 + y // 34
        p.rect(0, y, 160, 1, rgb5(shade, 1 + shade // 3, min(16, 5 + shade)))
    # stars
    for x, y in ((12, 18), (28, 40), (46, 14), (70, 28), (110, 16), (138, 36), (150, 12), (90, 48), (20, 70)):
        p.p(x, y, CREAM)
        p.p(x + 1, y, GOLD)
    # rift
    crack = [78, 80, 77, 82, 79, 84, 76, 81, 80, 75, 83, 79, 81, 77, 80]
    for i, x in enumerate(crack):
        y = 24 + i * 8
        p.rect(x, y, 3, 8, CYAN)
        p.rect(x + 3, y + 2, 2, 4, WHITE)
        p.rect(x - 4, y + 3, 3, 2, GOLD)
    # ground
    p.rect(0, 168, 160, 40, rgb5(6, 4, 8))
    p.rect(0, 168, 160, 2, GOLD)
    figures = ["wolfkin", "sauran", "corvin", "picsean", "vespine"]
    for i, name in enumerate(figures):
        p.blit(hero(name), 4 + i * 32, 148)
    # corner ticks
    p.rect(4, 4, 18, 2, GOLD)
    p.rect(4, 4, 2, 12, GOLD)
    p.rect(138, 4, 18, 2, GOLD)
    p.rect(154, 4, 2, 12, GOLD)
    return p


def back_mark() -> Pix:
    p = Pix(96, 32, (0, 0, 0, 0))
    colors = [HEROES[k][0] for k in ("wolfkin", "sauran", "corvin", "picsean", "vespine")]
    for i, c in enumerate(colors):
        p.ellipse(10 + i * 18, 16, 6, 6, c)
        p.ellipse(10 + i * 18, 16, 2, 2, CREAM)
    return p


def road_map() -> Pix:
    p = Pix(120, 168, rgb5(8, 6, 4))
    names_y = [8, 22, 36, 58, 72, 86, 108, 122, 136]
    cols = [
        rgb5(9, 10, 17),
        rgb5(7, 14, 6),
        rgb5(17, 6, 3),
        rgb5(13, 20, 25),
        rgb5(11, 13, 3),
        rgb5(10, 10, 14),
        rgb5(18, 14, 5),
        rgb5(13, 2, 4),
        rgb5(11, 5, 15),
    ]
    for i, (y, c) in enumerate(zip(names_y, cols)):
        p.rect(36, y, 48, 12, c)
        p.rect(36, y, 48, 1, GOLD)
        if i in (2, 5):
            p.rect(88, y + 4, 20, 4, CREAM)  # village after a region
    # 6x6 riftwild inset
    p.rect(8, 150, 40, 2, GOLD)
    for r in range(6):
        for c in range(6):
            col = MOSS if (r + c) % 2 == 0 else rgb5(4, 8, 3)
            if r > 3:
                col = rgb5(7, 2, 10) if (r + c) % 2 == 0 else rgb5(4, 2, 7)
            p.rect(78 + c * 6, 132 + r * 6, 5, 5, col)
    return p


def hud_diagram() -> Pix:
    """Original diagram of the window HUD, not a cartridge capture."""
    p = Pix(160, 48, rgb5(1, 1, 2))
    # hearts: 7 slots, one half
    for i in range(7):
        c = HEART if i < 6 else rgb5(10, 2, 3)
        p.rect(2 + i * 9, 4, 7, 6, c)
        if i == 6:
            p.rect(2 + i * 9 + 4, 4, 3, 6, rgb5(1, 1, 2))
    # mp pips
    for i in range(4):
        p.rect(70 + i * 5, 5, 3, 4, CYAN if i < 3 else rgb5(3, 8, 12))
    # will bar
    p.rect(96, 5, 28, 4, rgb5(8, 4, 14))
    p.rect(96, 5, 16, 4, rgb5(24, 8, 31))
    p.rect(92, 4, 3, 6, GOLD)  # tier digit block
    # coin
    p.rect(132, 4, 6, 6, GOLD)
    p.rect(140, 5, 12, 4, CREAM)
    # boss bar
    p.rect(4, 28, 152, 6, rgb5(3, 1, 4))
    p.rect(4, 28, 90, 6, AMBER)
    p.rect(4, 18, 40, 4, CREAM)
    return p


def aim_rose() -> Pix:
    p = Pix(64, 64, (0, 0, 0, 0))
    p.ellipse(32, 32, 22, 22, rgb5(6, 4, 8))
    p.ellipse(32, 32, 4, 4, GOLD)
    dirs = [(32, 8), (48, 14), (54, 32), (48, 50), (32, 56), (16, 50), (10, 32), (16, 14)]
    for i, (x, y) in enumerate(dirs):
        c = CYAN if i % 2 == 0 else CREAM
        p.rect(x - 2, y - 2, 5, 5, c)
    # persistent aim marker, northeast
    p.rect(46, 12, 7, 7, GOLD)
    return p


# 5x7 glyphs, rows of bits. Only the words we paint into plates.
GLYPHS = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "V": ["10001", "10001", "10001", "10001", "01010", "01010", "00100"],
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def text_pix(s: str, color, scale: int = 1) -> Pix:
    w = len(s) * 6 * scale
    p = Pix(max(w, 1), 7 * scale, (0, 0, 0, 0))
    for i, ch in enumerate(s):
        glyph = GLYPHS.get(ch, GLYPHS[" "])
        for gy, row in enumerate(glyph):
            for gx, bit in enumerate(row):
                if bit == "1":
                    p.rect(i * 6 * scale + gx * scale, gy * scale, scale, scale, color)
    return p


def placeholder() -> Pix:
    p = Pix(160, 208, rgb5(12, 9, 6))
    p.rect(4, 4, 152, 200, rgb5(20, 16, 10))
    p.rect(8, 8, 144, 192, rgb5(8, 6, 4))
    p.rect(12, 12, 136, 184, (0, 0, 0, 0))
    # inner empty field
    p.rect(16, 16, 128, 176, rgb5(18, 14, 9))
    label = text_pix("RESERVED", INK, 2)
    p.blit(label, 28, 70)
    label2 = text_pix("PAINTED COVER", INK, 1)
    p.blit(label2, 34, 100)
    label3 = text_pix("NOT FINAL ART", rgb5(12, 4, 3), 1)
    p.blit(label3, 40, 120)
    return p


def ornament() -> Pix:
    p = Pix(16, 16, (0, 0, 0, 0))
    p.rect(7, 1, 2, 14, GOLD)
    p.rect(1, 7, 14, 2, GOLD)
    p.rect(6, 6, 4, 4, CYAN)
    p.p(7, 7, WHITE)
    return p


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    cover().save("cover-plate.png")
    back_mark().save("five-sparks.png")
    road_map().save("road-map.png")
    hud_diagram().save("hud-diagram.png")
    aim_rose().save("aim-rose.png")
    placeholder().save("placeholder-painted-cover.png")
    ornament().save("spark.png")
    for name in HEROES:
        hero(name).save(f"hero-{name}.png")
    for name in (
        "crystal",
        "serpent",
        "rex",
        "spider",
        "mire",
        "reaper",
        "sun",
        "hydra",
        "void",
    ):
        boss_plate(name).save(f"boss-{name}.png")
    print(f"wrote plates to {ROOT}")


if __name__ == "__main__":
    main()
