#!/usr/bin/env python3
"""Generate the stage-transition vignettes (spec 2026-11-16 §2).

Each vignette is DATA: one quantized 112x96 picture under assets/vignettes/,
a name and motto, and a few timing numbers. This script composes the full
160x144 screen (ROV double frame, picture at tile col 3 row 1, name and motto
on rows 15-16), recovers the CGB palettes, deduplicates tiles with H/V flips,
and emits one banked C file per picture plus a shared header.

  python3 scripts/gen_vignettes.py           # rewrite src/render/vignette_*.{c,h}
  python3 scripts/gen_vignettes.py --check   # fail if the checked-in files are stale
  python3 scripts/gen_vignettes.py --png DIR # write one PNG per state/variant

Adding a dungeon later = one PNG + one PICTURES entry (+ its stage in STAGES).
Tile budget: <= 175 tiles per picture. BG slots 0x80..0xFF then 0x40..0x6E
(8800 signed addressing): the ranges the room resume path reloads.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets" / "vignettes"
OUT_DIR = ROOT / "src" / "render"

VX, VY = 24, 8                  # picture origin (tile col 3, row 1)
PW, PH = 112, 96
BLACK = (1, 0, 3)               # RGB555 of the ROV-style violet black
FRAME_MID = (12, 11, 16)
FRAME_LIGHT = (28, 28, 30)
MAX_TILES = 175
TILE_CHUNK = 32   # tiles per VIG_OP_TILES step (emitted as arg << 5)
# A chunk must never straddle the 0xFF -> 0x40 slot seam: set_bkg_data wraps
# to 0x00 (0x9000), not 0x40.
assert 128 % TILE_CHUNK == 0 and TILE_CHUNK == 1 << 5
assert MAX_TILES <= 128 + (0x6F - 0x40)
META_SIZE = 152

FONT = {
    '.': (0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x18, 0x00),
    '1': (0x00, 0x18, 0x28, 0x08, 0x08, 0x08, 0x3E, 0x00),
    '2': (0x00, 0x3C, 0x42, 0x02, 0x3C, 0x40, 0x7E, 0x00),
    '4': (0x00, 0x08, 0x18, 0x28, 0x48, 0x7E, 0x08, 0x00),
    '5': (0x00, 0x7E, 0x40, 0x7C, 0x02, 0x42, 0x3C, 0x00),
    '8': (0x00, 0x3C, 0x42, 0x3C, 0x42, 0x42, 0x3C, 0x00),
    'A': (0x00, 0x3C, 0x42, 0x42, 0x7E, 0x42, 0x42, 0x00),
    'B': (0x00, 0x7C, 0x42, 0x7C, 0x42, 0x42, 0x7C, 0x00),
    'C': (0x00, 0x3C, 0x42, 0x40, 0x40, 0x42, 0x3C, 0x00),
    'D': (0x00, 0x78, 0x44, 0x42, 0x42, 0x44, 0x78, 0x00),
    'E': (0x00, 0x7E, 0x40, 0x7C, 0x40, 0x40, 0x7E, 0x00),
    'F': (0x00, 0x7E, 0x40, 0x7C, 0x40, 0x40, 0x40, 0x00),
    'G': (0x00, 0x3C, 0x42, 0x40, 0x4E, 0x42, 0x3C, 0x00),
    'H': (0x00, 0x42, 0x42, 0x7E, 0x42, 0x42, 0x42, 0x00),
    'I': (0x00, 0x3E, 0x08, 0x08, 0x08, 0x08, 0x3E, 0x00),
    'J': (0x00, 0x04, 0x04, 0x04, 0x04, 0x44, 0x38, 0x00),
    'K': (0x00, 0x44, 0x48, 0x70, 0x48, 0x44, 0x42, 0x00),
    'L': (0x00, 0x40, 0x40, 0x40, 0x40, 0x40, 0x7E, 0x00),
    'M': (0x00, 0x42, 0x66, 0x5A, 0x42, 0x42, 0x42, 0x00),
    'N': (0x00, 0x42, 0x62, 0x52, 0x4A, 0x46, 0x42, 0x00),
    'O': (0x00, 0x3C, 0x42, 0x42, 0x42, 0x42, 0x3C, 0x00),
    'P': (0x00, 0x7C, 0x42, 0x42, 0x7C, 0x40, 0x40, 0x00),
    'Q': (0x00, 0x3C, 0x42, 0x42, 0x52, 0x4A, 0x3C, 0x00),
    'R': (0x00, 0x7C, 0x42, 0x42, 0x7C, 0x44, 0x42, 0x00),
    'S': (0x00, 0x3C, 0x40, 0x3C, 0x02, 0x42, 0x3C, 0x00),
    'T': (0x00, 0xFE, 0x10, 0x10, 0x10, 0x10, 0x10, 0x00),
    'U': (0x00, 0x42, 0x42, 0x42, 0x42, 0x42, 0x3C, 0x00),
    'V': (0x00, 0x42, 0x42, 0x42, 0x42, 0x24, 0x18, 0x00),
    'W': (0x00, 0x42, 0x42, 0x42, 0x42, 0x5A, 0x24, 0x00),
    'X': (0x00, 0x42, 0x24, 0x18, 0x18, 0x24, 0x42, 0x00),
    'Y': (0x00, 0x82, 0x44, 0x28, 0x10, 0x10, 0x10, 0x00),
    'Z': (0x00, 0x7E, 0x04, 0x08, 0x10, 0x20, 0x7E, 0x00),
}


def to555(rgb):
    return tuple(int(round(c / 255 * 31)) for c in rgb)


def from555(c):
    return tuple(int(round(v * 255 / 31)) for v in c)


def ease_frames():
    return None


# ---------------------------------------------------------------- pictures

def load(name):
    return np.asarray(Image.open(ASSETS / name).convert("RGB")).astype(int)


JAG = [0, 2, 1, 3, 0, -1, 2, 1, 0, 3, 1, -1, 0, 2]


def rift_states(pic, pals):
    """Arch interior opens from a magenta tear line in 5 steps (0 = shut).

    Cell-based so the whole effect costs 5 new tiles: one void tile and four
    jagged tear-edge shapes (X-flipped for the right-hand edge)."""
    mag = (pic[..., 0] > 170) & (pic[..., 2] > 140) & (pic[..., 1] < 130)
    bounds = {}
    for y in range(0, 80):
        xs = np.where(mag[y, 20:92])[0] + 20
        if len(xs) >= 2 and xs.max() - xs.min() > 8:
            bounds[y] = (xs.min() + 2, xs.max() - 1)
    # palette holding the tear magenta; void = its darkest colour
    def magness(c):
        r, g, b = from555(c)
        return r + b - 2 * g
    pi = max(range(len(pals)), key=lambda i: max(magness(c) for c in pals[i]))
    edge_ix = max(range(4), key=lambda e: magness(pals[pi][e]))
    void = np.zeros((8, 8), int)
    edges = []
    for k in range(4):
        e = void.copy()
        for y in range(8):
            x = 4 + (y // 2 + k) % 3
            e[y, x:x + 2] = edge_ix
        edges.append(e)
    rows = {}
    for cy in range(1, 13):
        y = (cy - 1) * 8 + 4
        if y not in bounds:
            continue
        l, r = bounds[y]
        cells = [cx for cx in range(3, 17) if l <= (cx - 3) * 8 + 4 <= r]
        if cells:
            rows[cy] = cells
    out = []
    for step in range(5):
        st = {}
        for cy, cells in rows.items():
            mid = (cells[0] + cells[-1] + 1) / 2
            half = [0, 1, 2, 3, 4][step]
            jag = JAG[cy % len(JAG)] % 4
            lo, hi = mid - half, mid + half
            for cx in cells:
                if lo <= cx < hi:
                    continue
                if half and cx == int(lo) - 1 + (lo != int(lo)):
                    st[(cx, cy)] = (edges[jag], pi)
                elif half and cx == int(hi):
                    st[(cx, cy)] = (edges[jag][:, ::-1], pi)
                else:
                    st[(cx, cy)] = (void, pi)
        out.append(st)
    return out


def ember_states(pic, pals):
    """Cinder Rex: eyes shut (blink) and eyes flaring."""
    blink = pic.copy()
    blink[46:51, 40:73] = (24, 8, 8)
    flare = pic.copy()
    for ex in (47, 63):
        flare[47:50, ex:ex + 3] = (255, 240, 120)
    return [blink, flare]


def hollow(c):
    rgb = np.array(from555(c), float)
    g = rgb.mean()
    v = np.clip(g * np.array([0.75, 0.95, 1.15]) + rgb * 0.15, 0, 255)
    return to555(v)


def lava(c):
    r, g, b = from555(c)
    return r > 180 and b < 120 and g > 40


def crystal(c):
    """Bright cyan facets; leave the white sparkle and purple rock alone."""
    r, g, b = from555(c)
    return b > 200 and g > 140 and r < 160


def flower(c):
    """Magenta blooms for the Verdant palette pulse."""
    r, g, b = from555(c)
    return r > 100 and b > 70 and g < 90 and r > g


def ice(c):
    """Bright frost highlights."""
    r, g, b = from555(c)
    return b > 220 and g > 180 and r > 150


def bubble(c):
    """Lime slime drips for the mire bubble cycle."""
    r, g, b = from555(c)
    return g > 150 and b < 80 and 80 < r < 200


def heart(c):
    """Darker mire moss, pulsed as the dark heart."""
    r, g, b = from555(c)
    return 40 < g < 100 and r < 90 and b < 90 and g >= r and (r + g + b) > 80


def torch(c):
    """Pale brazier cores and the keep window, not the mid-purple sky."""
    r, g, b = from555(c)
    return r > 220 and b > 220 and g > 170


def sun(c):
    """Warm mid-pale gold (sun disk and a few gleams), not sky white or brick gold."""
    r, g, b = from555(c)
    return r > 230 and 220 < g < 240 and 120 < b < 160


def moon(c):
    """Blood-red moon body."""
    r, g, b = from555(c)
    return r > 180 and g < 80 and b < 80


def shimmer(c):
    """Void rift wisps."""
    r, g, b = from555(c)
    return r > 140 and b > 160 and g < 120


def _is_iron(rgb):
    r, g, b = (int(v) for v in rgb)
    return b > r >= g and (r - g) >= 12 and 150 < r + g + b < 500


def portcullis_states(pic, pals):
    """Raise the iron bars inside the Shadow Keep arch in 3 steps."""
    pals = pals
    h, w, _ = pic.shape
    void = (16, 16, 16)
    x0, x1, y0, y1 = 44, 72, 46, 81
    bars = np.zeros((h, w), bool)
    for y in range(y0, y1):
        for x in range(x0, x1):
            if _is_iron(pic[y, x]):
                bars[y, x] = True
    lum = pic.sum(2)
    opening = np.zeros((h, w), bool)
    opening[40:81, 44:72] = (lum[40:81, 44:72] < 360) | bars[40:81, 44:72]
    out = []
    for dy in (8, 16, 28):
        st = pic.copy()
        ys, xs = np.where(bars)
        st[ys, xs] = void
        for y, x in zip(ys, xs):
            ny = y - dy
            if 0 <= ny < h and 44 <= x < 72 and ny >= 36:
                if lum[ny, x] >= 400 and not bars[ny, x]:
                    continue
                if opening[ny, x] or ny < y0:
                    st[ny, x] = pic[y, x]
        out.append(st)
    return out




# One picture = one ROM file. Variants share its tiles and differ in text and
# palettes. Times are frames from the end of the black load (60 fps).
PICTURES = [
    dict(name="riftgate", png="riftgate.png", states=rift_states,
         # state 0 = base (open); states 1..5 = tear steps 0..4
         events=[(0, 1), (10, 2), (22, 3), (34, 4), (46, 5), (58, 0)],
         hero=dict(x=VX + 48, y0=VY + 100, y1=VY + 54, t0=30, t1=130,
                   fade=126, step=3),
         flash=134, exit_t=160, exit_white=1, cycle=None, sfx=1,
         variants=[
             dict(id="VIG_RIFT_WAKING", title="WAKING RIFTWILD",
                  motto="THE WILD REMEMBERS", pal=None),
             dict(id="VIG_RIFT_HOLLOW", title="HOLLOW RIFTWILD",
                  motto="THE WILD FORGETS", pal=hollow),
         ]),
    dict(name="ember_depths", png="ember_depths.png", states=ember_states,
         events=[(0, 0), (56, 1), (64, 0), (132, 2), (136, 0), (140, 2),
                 (144, 0), (148, 2), (152, 0), (156, 2), (160, 0)],
         hero=dict(x=VX + 48, y0=VY + 100, y1=VY + 54, t0=16, t1=116,
                   fade=92, step=9),
         flash=0, exit_t=164, exit_white=0, cycle=dict(period=10, match=lava),
         sfx=1,
         variants=[dict(id="VIG_STAGE_EMBER", title="EMBER DEPTHS",
                        motto="THE KILN WAKES", pal=None, stage=2)]),
    dict(name="crystal_caverns", png="crystal_caverns.png", states=lambda pic, pals: [],
         bank=21,
         events=[],
         hero=dict(x=VX + 48, y0=VY + 100, y1=VY + 54, t0=16, t1=116,
                   fade=92, step=9),
         flash=0, exit_t=164, exit_white=0, cycle=dict(period=8, match=crystal),
         sfx=1,
         variants=[dict(id="VIG_STAGE_CRYSTAL", title="CRYSTAL CAVERNS",
                        motto="CRYSTALS LISTEN", pal=None, stage=0)]),
    dict(name="verdant_hollow", png="verdant_hollow.png", states=lambda pic, pals: [],
         bank=21, fx="leaves",
         events=[],
         hero=dict(x=VX + 48, y0=VY + 100, y1=VY + 54, t0=16, t1=116,
                   fade=92, step=9),
         flash=0, exit_t=164, exit_white=0, cycle=dict(period=12, match=flower),
         sfx=1,
         variants=[dict(id="VIG_STAGE_VERDANT", title="VERDANT HOLLOW",
                        motto="THE ROOTS HUNGER", pal=None, stage=1)]),
    dict(name="frost_vault", png="frost_vault.png", states=lambda pic, pals: [],
         bank=22, fx="snow",
         events=[],
         hero=dict(x=VX + 48, y0=VY + 100, y1=VY + 54, t0=16, t1=116,
                   fade=92, step=9),
         flash=0, exit_t=164, exit_white=0, cycle=None,
         sfx=1,
         variants=[dict(id="VIG_STAGE_FROST", title="FROST VAULT",
                        motto="NOTHING THAWS HERE", pal=None, stage=3)]),
    dict(name="toxic_mire", png="toxic_mire.png", states=lambda pic, pals: [],
         bank=22, fx=None,
         events=[],
         hero=dict(x=VX + 48, y0=VY + 100, y1=VY + 54, t0=16, t1=116,
                   fade=92, step=9),
         flash=0, exit_t=164, exit_white=0, cycle=dict(period=10, match=bubble),
         pulse=dict(period=24, match=heart),
         sfx=1,
         variants=[dict(id="VIG_STAGE_MIRE", title="TOXIC MIRE",
                        motto="A DARK HEART BEATS", pal=None, stage=4)]),
    dict(name="shadow_keep", png="shadow_keep.png", states=portcullis_states,
         bank=22, fx=None,
         events=[(0, 0), (40, 1), (80, 2), (120, 3)],
         hero=dict(x=VX + 48, y0=VY + 100, y1=VY + 54, t0=16, t1=116,
                   fade=92, step=9),
         flash=0, exit_t=164, exit_white=0, cycle=dict(period=6, match=torch),
         sfx=1,
         variants=[dict(id="VIG_STAGE_SHADOW", title="SHADOW KEEP",
                        motto="THE GATE WATCHES", pal=None, stage=5)]),
    dict(name="golden_temple", png="golden_temple.png", states=lambda pic, pals: [],
         bank=23, fx=None,
         events=[],
         hero=dict(x=VX + 48, y0=VY + 100, y1=VY + 54, t0=16, t1=116,
                   fade=92, step=9),
         flash=0, exit_t=164, exit_white=0, cycle=None,
         pulse=dict(period=16, match=sun),
         sfx=1,
         variants=[dict(id="VIG_STAGE_GOLDEN", title="GOLDEN TEMPLE",
                        motto="THE SUN NEVER SETS", pal=None, stage=6)]),
    dict(name="bloodmoon", png="bloodmoon.png", states=lambda pic, pals: [],
         bank=23, fx="bats",
         events=[],
         hero=dict(x=VX + 48, y0=VY + 100, y1=VY + 54, t0=16, t1=116,
                   fade=92, step=9),
         flash=0, exit_t=164, exit_white=0, cycle=None,
         pulse=dict(period=20, match=moon),
         sfx=1,
         variants=[dict(id="VIG_STAGE_BLOODMOON", title="BLOODMOON",
                        motto="THE MOON BLEEDS", pal=None, stage=7)]),
    dict(name="void_sanctum", png="void_sanctum.png", states=lambda pic, pals: [],
         bank=23, fx="shards",
         events=[],
         hero=dict(x=VX + 48, y0=VY + 100, y1=VY + 54, t0=16, t1=116,
                   fade=92, step=9),
         flash=0, exit_t=164, exit_white=0, cycle=dict(period=8, match=shimmer),
         sfx=1,
         variants=[dict(id="VIG_STAGE_VOID", title="VOID SANCTUM",
                        motto="WHERE NAMES END", pal=None, stage=8)]),
]


# ---------------------------------------------------------------- compose

def recover_palettes(pic):
    sets = []
    for ty in range(PH // 8):
        for tx in range(PW // 8):
            t = pic[ty * 8:ty * 8 + 8, tx * 8:tx * 8 + 8].reshape(-1, 3)
            sets.append(frozenset(to555(c) for c in map(tuple, t)))
    pals = []
    for s in sorted(set(sets), key=lambda s: (-len(s), sorted(s))):
        best = None
        for i, p in enumerate(pals):
            u = p | s
            if len(u) <= 4 and (best is None or len(u) < len(pals[best] | s)):
                best = i
        if best is None:
            pals.append(set(s))
        else:
            pals[best] |= s
    if len(pals) > 6:
        raise SystemExit(f"picture needs {len(pals)} palettes (max 6)")
    out = []
    for p in pals:
        cols = sorted(p, key=lambda c: (c[0] * 3 + c[1] * 6 + c[2], c))
        while len(cols) < 4:
            cols.append(cols[-1])
        out.append(cols)
    return out


def text_cells(row, s):
    """Return {(col,row): 8x8 index array} for one centred line."""
    cells = {}
    col0 = (20 - len(s)) // 2
    for i, ch in enumerate(s):
        idx = np.ones((8, 8), int)
        if ch != " ":
            for y, bits in enumerate(FONT[ch]):
                for x in range(8):
                    if bits & (0x80 >> x):
                        idx[y, x] = 3
        cells[(col0 + i, row)] = idx
    return cells


def frame_screen():
    """160x144 index plane for palette 7 cells: 1 = opaque black."""
    a = np.ones((144, 160), int)
    def rect(x0, y0, x1, y1, v):
        a[y0, x0:x1 + 1] = v
        a[y1, x0:x1 + 1] = v
        a[y0:y1 + 1, x0] = v
        a[y0:y1 + 1, x1] = v
    rect(VX - 6, VY - 6, VX + PW + 5, VY + PH + 5, 3)
    rect(VX - 3, VY - 3, VX + PW + 2, VY + PH + 2, 2)
    return a


def in_picture(cx, cy):
    return 3 <= cx < 17 and 1 <= cy < 13


def cell_index(rgb_tile, pal):
    d = ((rgb_tile[:, :, None, :] - np.array(pal)[None, None]) ** 2).sum(3)
    return d.argmin(2), int(d.min(2).sum())


class Tiles:
    def __init__(self):
        self.patterns = []
        self.lookup = {}

    def add(self, idx):
        for flip, arr in ((0, idx), (0x20, idx[:, ::-1]), (0x40, idx[::-1]),
                          (0x60, idx[::-1, ::-1])):
            key = arr.tobytes()
            if key in self.lookup:
                return self.lookup[key], flip
        n = len(self.patterns)
        self.patterns.append(idx.copy())
        self.lookup[idx.astype(int).tobytes()] = n
        return n, 0


def slot(i):
    return 0x80 + i if i < 128 else 0x40 + (i - 128)


def validate(pic_def):
    """Reject data the u8 player cannot run (see src/game/vignette.c)."""
    name, h = pic_def["name"], pic_def["hero"]
    def need(ok, why):
        if not ok:
            raise SystemExit(f"{name}: {why}")
    need(len(pic_def["events"]) <= 16, "more than 16 events (VM_EV holds 16)")
    need(all(0 <= f < pic_def["exit_t"] for f, _s in pic_def["events"]),
         "event frame outside 0..exit_t")
    # vig_t is u8 and the exit fade runs 16 frames past exit_t.
    need(16 <= pic_def["exit_t"] <= 235, "exit_t must be 16..235")
    need(h["step"] > 0, "hero fade step must be > 0")
    need(h["t1"] > h["t0"], "hero walk needs t1 > t0")
    need(0 <= h["x"] <= 144 and 0 <= h["y1"] <= h["y0"] <= 128,
         "hero path off screen")
    if pic_def.get("flash"):
        need(pic_def["flash"] + 8 <= 255, "flash too late for u8 time")
    if pic_def.get("cycle"):
        need(1 <= pic_def["cycle"]["period"] <= 255, "cycle period 1..255")
    for v in pic_def["variants"]:
        for line in (v["title"], v["motto"]):
            need(len(line) <= 20, f"text over 20 cells: {line!r}")
            missing = sorted({ch for ch in line if ch != " " and ch not in FONT})
            need(not missing, f"no FONT glyph for {missing} in {line!r}")


def build(pic_def):
    validate(pic_def)
    pic = load(pic_def["png"])
    pic555 = np.array([[to555(c) for c in row] for row in pic])
    pals = recover_palettes(pic)
    pal_np = [[list(c) for c in p] for p in pals]
    tiles = Tiles()
    frame = frame_screen()

    def picture_cell(img555, cx, cy, exact):
        t = img555[(cy - 1) * 8:(cy - 1) * 8 + 8, (cx - 3) * 8:(cx - 3) * 8 + 8]
        best = None
        for pi, p in enumerate(pal_np):
            idx, err = cell_index(t, p)
            if best is None or err < best[1]:
                best = (idx, err, pi)
            if err == 0:
                break
        if exact and best[1]:
            raise SystemExit(f"{pic_def['name']}: cell {cx},{cy} not exact")
        n, flip = tiles.add(best[0])
        return n, flip | best[2]

    def frame_cell(cx, cy, overlay=None):
        idx = frame[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8].copy()
        if overlay is not None:
            idx = overlay
        n, flip = tiles.add(idx)
        return n, flip | 7 | 0x80          # palette 7, BG over OBJ

    base_t = [[0] * 20 for _ in range(18)]
    base_a = [[0] * 20 for _ in range(18)]
    v0 = pic_def["variants"][0]
    texts = []
    for v in pic_def["variants"]:
        cells = {}
        cells.update(text_cells(15, v["title"]))
        cells.update(text_cells(16, v["motto"]))
        texts.append(cells)
    for cy in range(18):
        for cx in range(20):
            if in_picture(cx, cy):
                n, a = picture_cell(pic555, cx, cy, True)
            else:
                n, a = frame_cell(cx, cy, texts[0].get((cx, cy)))
            base_t[cy][cx], base_a[cy][cx] = n, a
    base_count = len(tiles.patterns)
    text_rows = []
    for cells in texts:
        rows_t, rows_a = [], []
        for cy in (15, 16):
            for cx in range(20):
                ov = cells.get((cx, cy))
                if ov is None:
                    ov = np.ones((8, 8), int)
                n, a = frame_cell(cx, cy, ov)
                rows_t.append(n)
                rows_a.append(a)
        text_rows.append((rows_t, rows_a))

    # states: 0 = base picture; 1.. from the picture's state function
    extra = pic_def["states"](pic, pals)
    state_cells = []
    union = set()
    for img in extra:
        if isinstance(img, dict):
            cells = {}
            for (cx, cy), (idx, pi) in img.items():
                n, flip = tiles.add(idx)
                cells[(cx, cy)] = (n, flip | pi)
            state_cells.append(cells)
            union |= set(cells)
            continue
        img555 = np.array([[to555(c) for c in row] for row in img])
        cells = {}
        for cy in range(1, 13):
            for cx in range(3, 17):
                a = img555[(cy - 1) * 8:(cy - 1) * 8 + 8, (cx - 3) * 8:(cx - 3) * 8 + 8]
                b = pic555[(cy - 1) * 8:(cy - 1) * 8 + 8, (cx - 3) * 8:(cx - 3) * 8 + 8]
                if (a != b).any():
                    cells[(cx, cy)] = picture_cell(img555, cx, cy, False)
        state_cells.append(cells)
        union |= set(cells)
    union = sorted(union, key=lambda c: (c[1], c[0]))
    spans = []
    for cx, cy in union:
        if spans and spans[-1][0] == cy and spans[-1][1] + spans[-1][2] == cx:
            spans[-1][2] += 1
        else:
            spans.append([cy, cx, 1])
    st_t, st_a = [], []
    for s in [{}] + state_cells:
        for cx, cy in union:
            n, a = s.get((cx, cy), (base_t[cy][cx], base_a[cy][cx]))
            st_t.append(n)
            st_a.append(a)

    print(f"[vignettes] {pic_def['name']}: base {base_count} tiles", file=sys.stderr)
    if len(tiles.patterns) > MAX_TILES:
        raise SystemExit(f"{pic_def['name']}: {len(tiles.patterns)} tiles > {MAX_TILES}")

    # palettes per variant (6 picture palettes, 6 = black, 7 = frame/text)
    variant_pals = []
    for v in pic_def["variants"]:
        ps = [list(p) for p in pals]
        if v["pal"]:
            ps = [[v["pal"](c) for c in p] for p in ps]
        while len(ps) < 6:
            ps.append([BLACK] * 4)
        ps.append([BLACK] * 4)
        ps.append([BLACK, BLACK, FRAME_MID, FRAME_LIGHT])
        variant_pals.append(ps)

    cyc_slots, cyc_cols = [], []
    if pic_def["cycle"]:
        cols = sorted({c for p in pals for c in p if pic_def["cycle"]["match"](c)},
                      key=lambda c: (from555(c)[1], c))
        cyc_cols = cols[:8]
        for pi, p in enumerate(pals):
            for e, c in enumerate(p):
                if c in cyc_cols and len(cyc_slots) < 8:
                    cyc_slots.append(((pi << 2) | e, cyc_cols.index(c)))

    pulse_mask = 0
    if pic_def.get("pulse"):
        for pi, p in enumerate(pals):
            for e, c in enumerate(p):
                if pic_def["pulse"]["match"](c):
                    pulse_mask |= 1 << (pi * 4 + e)

    metas = []
    for vi, v in enumerate(pic_def["variants"]):
        h = pic_def["hero"]
        m = [0] * META_SIZE
        m[0] = len(tiles.patterns)
        m[1] = 1 + len(extra)
        m[2] = len(pic_def["events"])
        m[3], m[4], m[5] = h["x"], h["y0"], h["y1"]
        m[6], m[7], m[8], m[9] = h["t0"], h["t1"], h["fade"], h["step"]
        m[10], m[11] = pic_def["exit_t"], pic_def["exit_white"]
        if cyc_slots and not v["pal"]:
            m[12] = pic_def["cycle"]["period"]
            m[13], m[14] = len(cyc_slots), len(cyc_cols)
        m[15] = pic_def["flash"]
        m[16] = 180
        m[17] = pic_def["sfx"]
        m[18] = vi
        fx_ids = {"leaves": 1, "snow": 2, "bats": 3, "shards": 4}
        if pic_def.get("fx") in fx_ids:
            m[19] = fx_ids[pic_def["fx"]]
        pulse = pic_def.get("pulse")
        if pulse and pulse_mask:
            m[16] = pulse["period"]
            m[20] = pulse_mask & 0xFF
            m[21] = (pulse_mask >> 8) & 0xFF
            m[22] = (pulse_mask >> 16) & 0xFF
            m[23] = (pulse_mask >> 24) & 0xFF
        for i, (f, s) in enumerate(pic_def["events"]):
            m[24 + i * 2], m[25 + i * 2] = f, s
        for i, (sl, b) in enumerate(cyc_slots):
            m[56 + i * 2], m[57 + i * 2] = sl, b
        for i, c in enumerate(cyc_cols):
            w = c[0] | (c[1] << 5) | (c[2] << 10)
            m[72 + i * 2], m[73 + i * 2] = w & 0xFF, w >> 8
        for pi, p in enumerate(variant_pals[vi]):
            for e, c in enumerate(p):
                w = c[0] | (c[1] << 5) | (c[2] << 10)
                o = 88 + (pi * 4 + e) * 2
                m[o], m[o + 1] = w & 0xFF, w >> 8
        metas.append(m)

    return dict(name=pic_def["name"], tiles=tiles.patterns, base_t=base_t,
                base_a=base_a, text_rows=text_rows, spans=spans, st_t=st_t,
                st_a=st_a, n_union=len(union), metas=metas,
                variant_pals=variant_pals, pic=pic_def,
                state_cells=[{}] + state_cells)


# ---------------------------------------------------------------- emit

def tile_bytes(idx):
    out = []
    for y in range(8):
        lo = hi = 0
        for x in range(8):
            v = int(idx[y, x])
            if v & 1:
                lo |= 0x80 >> x
            if v & 2:
                hi |= 0x80 >> x
        out += [lo, hi]
    return out


def carr(name, data, per=16, ctype="u8"):
    lines = [f"static const {ctype} {name}[{len(data)}] = {{"]
    for i in range(0, len(data), per):
        lines.append("    " + ", ".join(f"0x{v:02X}" for v in data[i:i + per]) + ",")
    lines.append("};")
    return "\n".join(lines)


def emit_c(b):
    n = b["name"]
    mapped = lambda seq: [slot(t) for t in seq]
    tiles = []
    for t in b["tiles"]:
        tiles += tile_bytes(t)
    base_t = mapped([t for row in b["base_t"] for t in row])
    base_a = [a for row in b["base_a"] for a in row]
    text_t, text_a = [], []
    for rt, ra in b["text_rows"]:
        text_t += mapped(rt)
        text_a += ra
    metas = [v for m in b["metas"] for v in m]
    out = [
        f"#pragma bank {b['pic'].get('bank', 20)}",
        f"// Generated by scripts/gen_vignettes.py from assets/vignettes/{b['pic']['png']}.",
        "// Do not edit by hand.",
        "#include <gb/gb.h>",
        "#include <string.h>",
        '#include "render/vignette_data.h"',
        "",
        f"BANKREF(vig_io_{n})",
        "",
        carr(f"{n}_tiles", tiles),
        carr(f"{n}_map", base_t, 20),
        carr(f"{n}_attr", base_a, 20),
        carr(f"{n}_text_t", text_t, 20),
        carr(f"{n}_text_a", text_a, 20),
        carr(f"{n}_meta", metas, 16),
    ]
    if b["n_union"]:
        sp = [v for s in b["spans"] for v in s]
        out += [carr(f"{n}_spans", sp, 3),
                carr(f"{n}_st_t", mapped(b["st_t"]), 16),
                carr(f"{n}_st_a", b["st_a"], 16)]
    out += [
        "",
        f"void vig_io_{n}(u8 op, u8 arg, u8 *dst) BANKED {{",
        "    u8 i, n;",
        "    switch (op) {",
        "    case VIG_OP_META:",
        f"        memcpy(dst, {n}_meta + (u16)arg * VIG_META_SIZE, VIG_META_SIZE);",
        "        break;",
        "    case VIG_OP_TILES:",
        "        i = (u8)(arg << 5);",
        f"        n = (u8)({len(b['tiles'])}u - i);",
        "        if (n > 32) n = 32;",
        f"        set_bkg_data(VIG_SLOT(i), n, {n}_tiles + ((u16)i << 4));",
        "        break;",
        "    case VIG_OP_ROWS:",
        "        for (i = (u8)(arg * 6); i < (u8)(arg * 6 + 6); ++i) {",
        f"            set_bkg_tiles(0, i, 20, 1, {n}_map + (u16)i * 20);",
        "            VBK_REG = 1;",
        f"            set_bkg_tiles(0, i, 20, 1, {n}_attr + (u16)i * 20);",
        "            VBK_REG = 0;",
        "        }",
        "        break;",
        "    case VIG_OP_TEXT:",
        f"        set_bkg_tiles(0, 15, 20, 2, {n}_text_t + (u16)arg * 40);",
        "        VBK_REG = 1;",
        f"        set_bkg_tiles(0, 15, 20, 2, {n}_text_a + (u16)arg * 40);",
        "        VBK_REG = 0;",
        "        break;",
    ]
    if b["n_union"]:
        out += [
            "    case VIG_OP_STATE: {",
            f"        const u8 *t = {n}_st_t + (u16)arg * {b['n_union']}u;",
            f"        const u8 *a = {n}_st_a + (u16)arg * {b['n_union']}u;",
            f"        const u8 *s = {n}_spans;",
            f"        for (i = 0; i < {len(b['spans'])}u; ++i, s += 3) {{",
            "            set_bkg_tiles(s[1], s[0], s[2], 1, t);",
            "            VBK_REG = 1;",
            "            set_bkg_tiles(s[1], s[0], s[2], 1, a);",
            "            VBK_REG = 0;",
            "            t += s[2];",
            "            a += s[2];",
            "        }",
            "        break;",
            "    }",
        ]
    out += ["    }", "    dst;", "}", ""]
    return "\n".join(out)


def emit_h(builds):
    lines = [
        "// Generated by scripts/gen_vignettes.py. Do not edit by hand.",
        "#ifndef QUINTRA_RENDER_VIGNETTE_DATA_H",
        "#define QUINTRA_RENDER_VIGNETTE_DATA_H",
        "",
        "#include <gb/gb.h>",
        '#include "core/types.h"',
        "",
        "#define VIG_OP_META  0",
        "#define VIG_OP_TILES 1",
        "#define VIG_OP_ROWS  2",
        "#define VIG_OP_TEXT  3",
        "#define VIG_OP_STATE 4",
        f"#define VIG_META_SIZE {META_SIZE}",
        "// Logical tile i -> signed BG index (8800 mode): 0x80.. then 0x40..",
        "#define VIG_SLOT(i) ((u8)((i) < 128 ? 0x80 + (i) : 0x40 + (i) - 128))",
        "",
        "// meta byte offsets",
        "#define VM_TILES 0",
        "#define VM_STATES 1",
        "#define VM_EVENTS 2",
        "#define VM_HERO_X 3",
        "#define VM_HERO_Y0 4",
        "#define VM_HERO_Y1 5",
        "#define VM_WALK_T0 6",
        "#define VM_WALK_T1 7",
        "#define VM_FADE_T0 8",
        "#define VM_FADE_STEP 9",
        "#define VM_EXIT_T 10",
        "#define VM_EXIT_WHITE 11",
        "#define VM_CYC_PERIOD 12",
        "#define VM_CYC_SLOTS 13",
        "#define VM_CYC_LEN 14",
        "#define VM_FLASH_T 15",
        "#define VM_FRAMES 16",
        "#define VM_SFX 17",
        "#define VM_VARIANT 18",
        "#define VM_FX 19",
        "#define VIG_FX_NONE 0",
        "#define VIG_FX_LEAVES 1",
        "#define VIG_FX_SNOW 2",
        "#define VIG_FX_BATS 3",
        "#define VIG_FX_SHARDS 4",
        "#define VM_PULSE_PERIOD 16",
        "#define VM_PULSE_MASK 20",
        "#define VM_EV 24",
        "#define VM_CYC 56",
        "#define VM_CYC_COL 72",
        "#define VM_PAL 88",
        "",
    ]
    vid = 0
    table = []
    stages = ["0xFF"] * 9
    for fi, b in enumerate(builds):
        lines.append(f"void vig_io_{b['name']}(u8 op, u8 arg, u8 *dst) BANKED;")
        lines.append(f"#define VIG_FILE_{b['name'].upper()} {fi}")
        for vi, v in enumerate(b["pic"]["variants"]):
            lines.append(f"#define {v['id']} {vid}")
            table.append((fi, vi))
            if "stage" in v:
                stages[v["stage"]] = str(vid)
            vid += 1
    lines += [
        f"#define VIG_COUNT {vid}",
        "// id -> (file << 4) | variant",
        "#define VIG_TABLE { " + ", ".join(f"0x{(f << 4) | v:02X}" for f, v in table) + " }",
        "// dungeon stage (0..8) -> vignette id, 0xFF = none yet",
        "#define VIG_STAGE_TABLE { " + ", ".join(stages) + " }",
        "#define VIG_DISPATCH(file, op, arg, dst) do { switch (file) { \\",
    ]
    for fi, b in enumerate(builds):
        lines.append(f"    case {fi}: vig_io_{b['name']}((op), (arg), (dst)); break; \\")
    lines += ["    } } while (0)", "", "#endif", ""]
    return "\n".join(lines)


def preview_png(b, directory):
    """Render each state/variant from the emitted data (exact ROM pixels)."""
    directory.mkdir(parents=True, exist_ok=True)
    for vi in range(len(b["metas"])):
        pals = b["variant_pals"][vi]
        for si, cells in enumerate(b["state_cells"]):
            img = np.zeros((144, 160, 3), np.uint8)
            for cy in range(18):
                for cx in range(20):
                    n, a = b["base_t"][cy][cx], b["base_a"][cy][cx]
                    if cy in (15, 16):
                        rt, ra = b["text_rows"][vi]
                        n, a = rt[(cy - 15) * 20 + cx], ra[(cy - 15) * 20 + cx]
                    n, a = cells.get((cx, cy), (n, a))
                    idx = b["tiles"][n]
                    if a & 0x20:
                        idx = idx[:, ::-1]
                    if a & 0x40:
                        idx = idx[::-1]
                    pal = pals[a & 7]
                    img[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8] = np.array(
                        [from555(pal[v]) for v in idx.flat]).reshape(8, 8, 3)
            Image.fromarray(img).save(directory / f"{b['name']}-v{vi}-s{si}.png")


def main(argv):
    builds = [build(p) for p in PICTURES]
    files = {OUT_DIR / "vignette_data.h": emit_h(builds)}
    for b in builds:
        files[OUT_DIR / f"vignette_{b['name']}.c"] = emit_c(b)
        print(f"[vignettes] {b['name']}: {len(b['tiles'])} tiles, "
              f"{len(b['state_cells']) - 1} states over {b['n_union']} cells",
              file=sys.stderr)
    if "--png" in argv:
        d = Path(argv[argv.index("--png") + 1])
        for b in builds:
            preview_png(b, d)
        return 0
    if "--check" in argv:
        stale = [str(p) for p, s in files.items()
                 if not p.exists() or p.read_text() != s]
        if stale:
            print("[vignettes] STALE: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("[vignettes] OK generated files are current", file=sys.stderr)
        return 0
    for p, s in files.items():
        p.write_text(s)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
