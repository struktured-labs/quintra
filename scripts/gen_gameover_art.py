#!/usr/bin/env python3
"""Quantize the Game Over visor and emit src/render/gameover_art.{c,h}.

  python3 scripts/gen_gameover_art.py                 # placeholder geometry
  python3 scripts/gen_gameover_art.py --png RAW.png   # GPT image -> C
  python3 scripts/gen_gameover_art.py --png RAW.png --preview OUT.png

Tile budget: VRAM bank 1, at most 96 unique 8x8 patterns (plus H/V flips).
Raw model PNGs are not committed. Colour 0 is a shared deep near-black.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT_C = ROOT / "src" / "render" / "gameover_art.c"
OUT_H = ROOT / "src" / "render" / "gameover_art.h"

# Dest well on the 20x18 screen (leaves row 3 for GAME OVER, rows 13-16 for copy).
MASK_X, MASK_Y, MASK_W, MASK_H = 5, 4, 10, 9
MAX_TILES = 96
SCREEN_W, SCREEN_H = 160, 144

# Shared colour 0, plus the authored text palettes (not taken from the image).
C0 = (4, 1, 3)          # deep near-black with a hint of indigo-red
PAL_BACKDROP = [C0, (5, 6, 10), (9, 10, 14), (16, 17, 21)]
PAL_TITLE = [C0, (14, 2, 3), (28, 8, 6), (31, 14, 8)]
PAL_GOLD = [C0, (16, 10, 2), (26, 20, 6), (31, 29, 20)]
# Fallback stone / ember if the image is missing.
PAL_STONE = [C0, (8, 7, 8), (16, 13, 12), (24, 21, 18)]
PAL_EMBER = [C0, (14, 3, 2), (26, 10, 3), (31, 24, 12)]


def to555(rgb):
    r, g, b = (int(v) for v in rgb[:3])
    if max(r, g, b) > 31:
        r, g, b = r >> 3, g >> 3, b >> 3
    return (max(0, min(31, r)), max(0, min(31, g)), max(0, min(31, b)))


def from555(c):
    return tuple(v * 255 // 31 for v in c)


def bgr555(c):
    r, g, b = c
    return (b << 10) | (g << 5) | r


def tile_bytes(idx8):
    out = []
    for y in range(8):
        lo = hi = 0
        for x, v in enumerate(idx8[y]):
            v = int(v) & 3
            if v & 1:
                lo |= 0x80 >> x
            if v & 2:
                hi |= 0x80 >> x
        out += [lo, hi]
    return out


def c_array(typ, name, data, width=16, fmt=None):
    if typ == "u16":
        fmt = fmt or (lambda v: f"0x{v:04X}")
        step = 8
    else:
        fmt = fmt or (lambda v: f"0x{v:02X}")
        step = 16
    lines = [f"static const {typ} {name}[{len(data)}] = {{"]
    for i in range(0, len(data), step):
        lines.append("    " + ", ".join(fmt(v) for v in data[i:i + step]) + ",")
    lines.append("};")
    return "\n".join(lines)


def pal_array(name, pal):
    vals = [bgr555(to555(c)) for c in pal]
    return f"const u16 {name}[4] = {{ " + ", ".join(f"0x{v:04X}" for v in vals) + " };"


def kmeans4(colors, weights, fixed0=C0):
    cols = [to555(c) for c in colors]
    unique = {}
    for c, w in zip(cols, weights):
        unique[c] = unique.get(c, 0) + w
    # Always keep colour 0 as the shared void.
    rest = [c for c in unique if c != to555(fixed0)]
    if not rest:
        pal = [to555(fixed0)] * 4
        return pal
    pts = np.array(rest, float)
    w = np.array([unique[c] for c in rest], float)
    n = min(3, len(pts))
    if n < 3:
        centers = list(pts)
        while len(centers) < 3:
            centers.append(centers[-1])
        pal = [to555(fixed0)] + [tuple(int(round(v)) for v in c) for c in centers]
        return pal
    order = np.argsort(pts @ np.array([3.0, 6.0, 1.0]))
    centers = pts[order[np.linspace(0, len(pts) - 1, 3).astype(int)]]
    for _ in range(10):
        d = ((pts[:, None] - centers[None]) ** 2).sum(2)
        lab = d.argmin(1)
        for k in range(3):
            m = lab == k
            if m.any():
                centers[k] = (pts[m] * w[m, None]).sum(0) / w[m].sum()
    rest_p = [tuple(int(max(0, min(31, round(v)))) for v in c) for c in centers]
    # Sort remaining by luminance so 1 is dark stone/ember, 3 is highlight.
    rest_p.sort(key=lambda c: c[0] * 3 + c[1] * 6 + c[2])
    return [to555(fixed0)] + rest_p


def fit_cell(cell, pals):
    """cell is 8x8x3 RGB555. Return index plane, pal index, error."""
    best = None
    for pi, pal in enumerate(pals):
        pa = np.array(pal, float)
        d = ((cell[:, :, None, :] - pa[None, None]) ** 2).sum(3)
        idx, err = d.argmin(2), float(d.min(2).sum())
        if best is None or err < best[2]:
            best = (idx.astype(int), pi, err)
        if err == 0:
            break
    return best


class Pool:
    def __init__(self):
        self.patterns = []
        self.lookup = {}

    def add(self, idx):
        idx = np.asarray(idx, int)
        for flip, arr in ((0, idx), (0x20, idx[:, ::-1]),
                          (0x40, idx[::-1]), (0x60, idx[::-1, ::-1])):
            key = arr.tobytes()
            if key in self.lookup:
                return self.lookup[key], flip
        n = len(self.patterns)
        self.patterns.append(idx.copy())
        self.lookup[idx.tobytes()] = n
        return n, 0


def is_blank(idx):
    return int(np.max(idx)) == 0


def procedural_mask():
    """80x72 RGB555 image of a hollow rune visor, used if no PNG is given."""
    w, h = MASK_W * 8, MASK_H * 8
    img = np.zeros((h, w, 3), dtype=int)
    img[:, :] = C0
    cy, cx = h * 0.48, w * 0.5
    for y in range(h):
        for x in range(w):
            nx = (x - cx) / (w * 0.46)
            ny = (y - cy) / (h * 0.52)
            r2 = nx * nx + ny * ny * 0.85
            # Crossed ley-staves behind the mask (stone rods, not bones).
            staff_a = abs((x - 8) * 0.7 - (y - 4) * 0.55) < 2.2 and 6 < x < w - 6 and 8 < y < h - 6
            staff_b = abs((w - 8 - x) * 0.7 - (y - 4) * 0.55) < 2.2 and 6 < x < w - 6 and 8 < y < h - 6
            if staff_a or staff_b:
                img[y, x] = PAL_STONE[1] if (x + y) & 1 else PAL_STONE[2]
            if r2 > 1.05:
                continue
            # Stone body.
            if r2 > 0.22:
                ring = 1 if r2 > 0.92 else (2 if ((x >> 1) + y) % 5 else 1)
                img[y, x] = PAL_STONE[ring]
                if r2 > 0.92:
                    img[y, x] = PAL_STONE[3] if (x + y * 3) % 7 == 0 else PAL_STONE[1]
            # Vertical wound.
            if abs(x - cx) <= 1 and 10 < y < h - 8:
                img[y, x] = PAL_EMBER[2 if abs(x - cx) == 0 else 1]
            # Eye slits (vertical rift-slashes).
            for side in (-1, 1):
                ex = cx + side * 14
                if abs(x - ex) <= 1.6 and 16 < y < 40:
                    img[y, x] = PAL_EMBER[3 if abs(x - ex) < 1 and 20 < y < 36 else 2]
            # Brow runes: a few square notches.
            if 8 <= y <= 12 and int(x) in (20, 21, 38, 39, 56, 57):
                img[y, x] = PAL_EMBER[2]
            # Chips on the rim.
            if r2 > 0.88 and r2 < 1.02 and (x * 13 + y * 7) % 17 == 0:
                img[y, x] = C0
    return img


def load_png(path):
    im = Image.open(path).convert("RGB")
    # Box-downsample to one game pixel per source block.
    im = im.resize((SCREEN_W, SCREEN_H), Image.BOX)
    arr = np.asarray(im).astype(int)
    # Convert to RGB555.
    out = np.zeros_like(arr)
    out[:, :, 0] = arr[:, :, 0] >> 3
    out[:, :, 1] = arr[:, :, 1] >> 3
    out[:, :, 2] = arr[:, :, 2] >> 3
    return out


def extract_mask(screen):
    y0, x0 = MASK_Y * 8, MASK_X * 8
    return screen[y0:y0 + MASK_H * 8, x0:x0 + MASK_W * 8].copy()


def fit_content_to_well(screen):
    """Scale the non-void motif into the 10x9 well so staves are not cropped."""
    lum = screen.max(axis=2)
    # Background is the dark void; keep pixels clearly above it.
    ys, xs = np.where(lum >= 6)
    if len(xs) < 16:
        return extract_mask(screen)
    pad = 6
    x0 = max(0, int(xs.min()) - pad)
    x1 = min(screen.shape[1], int(xs.max()) + 1 + pad)
    y0 = max(0, int(ys.min()) - pad)
    y1 = min(screen.shape[0], int(ys.max()) + 1 + pad)
    crop = screen[y0:y1, x0:x1]
    # Pillow needs 8-bit RGB; we are in RGB555 (0..31).
    rgb = np.clip(crop * 8, 0, 255).astype(np.uint8)
    im = Image.fromarray(rgb, "RGB").resize((MASK_W * 8, MASK_H * 8), Image.BOX)
    arr = np.asarray(im).astype(int)
    out = np.empty_like(arr)
    out[:, :, 0] = arr[:, :, 0] >> 3
    out[:, :, 1] = arr[:, :, 1] >> 3
    out[:, :, 2] = arr[:, :, 2] >> 3
    return out


def split_stone_ember(mask):
    """Heuristic: reddish/high-chroma cells go to the ember palette."""
    h, w, _ = mask.shape
    tags = np.zeros((h // 8, w // 8), dtype=int)  # 1 stone, 2 ember
    for ty in range(h // 8):
        for tx in range(w // 8):
            cell = mask[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8]
            r, g, b = cell[:, :, 0].astype(float), cell[:, :, 1].astype(float), cell[:, :, 2].astype(float)
            # Skip near-black cells.
            if cell.max() <= 4:
                tags[ty, tx] = 1
                continue
            warmth = (r - g * 0.5 - b * 0.5).mean()
            if warmth > 3.0 and r.mean() > 8:
                tags[ty, tx] = 2
            else:
                tags[ty, tx] = 1
    return tags


def build(mask, stone_pal=None, ember_pal=None):
    tags = split_stone_ember(mask)
    if stone_pal is None:
        stone_px, stone_w = [], []
        ember_px, ember_w = [], []
        for ty in range(MASK_H):
            for tx in range(MASK_W):
                cell = mask[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8]
                flat = cell.reshape(-1, 3)
                for p in flat:
                    t = tuple(int(v) for v in p)
                    if tags[ty, tx] == 2:
                        ember_px.append(t); ember_w.append(1)
                    else:
                        stone_px.append(t); stone_w.append(1)
        stone_pal = kmeans4(stone_px or [C0], stone_w or [1])
        ember_pal = kmeans4(ember_px or [C0, PAL_EMBER[2]], ember_w or [1, 1])
        # Keep colour 0 identical.
        stone_pal[0] = to555(C0)
        ember_pal[0] = to555(C0)

    pals = [PAL_BACKDROP, stone_pal, ember_pal]
    pool = Pool()
    map_ids = []
    map_attrs = []
    for ty in range(MASK_H):
        for tx in range(MASK_W):
            cell = mask[ty * 8:(ty + 1) * 8, tx * 8:(tx + 1) * 8].astype(float)
            # Prefer the tagged palette, but allow a better fit.
            preferred = tags[ty, tx]
            idx, pi, err = fit_cell(cell, pals)
            # If the preferred pal is close, keep it so cracks stay on ember.
            idx_p, _, err_p = fit_cell(cell, [pals[preferred]])
            if err_p <= err * 1.15 + 8:
                idx, pi = idx_p, preferred
            if is_blank(idx):
                map_ids.append(0)
                map_attrs.append(0)  # bank 0, pal 0, blank font tile
                continue
            tid, flip = pool.add(idx)
            map_ids.append(tid)
            # bank 1 (0x08) + palette + flip
            map_attrs.append(0x08 | (pi & 7) | flip)

    if len(pool.patterns) > MAX_TILES:
        raise SystemExit(f"too many unique tiles: {len(pool.patterns)} > {MAX_TILES}")
    return pool.patterns, map_ids, map_attrs, stone_pal, ember_pal


def shard_tiles():
    """Four 8x8 rune-chip / ember-spark object tiles (colour 0 transparent)."""
    tiles = []
    # 0: angled stone chip
    t = np.zeros((8, 8), int)
    for y, row in enumerate([
        "00000000",
        "00012000",
        "00133200",
        "01332100",
        "00131000",
        "00010000",
        "00000000",
        "00000000",
    ]):
        t[y] = [int(c) for c in row]
    tiles.append(t)
    # 1: smaller chip, flipped pose
    t = np.zeros((8, 8), int)
    for y, row in enumerate([
        "00000000",
        "00000000",
        "00021000",
        "00233100",
        "00132100",
        "00021000",
        "00000000",
        "00000000",
    ]):
        t[y] = [int(c) for c in row]
    tiles.append(t)
    # 2: ember spark
    t = np.zeros((8, 8), int)
    for y, row in enumerate([
        "00000000",
        "00030000",
        "00323000",
        "03232300",
        "00323000",
        "00030000",
        "00000000",
        "00000000",
    ]):
        t[y] = [int(c) for c in row]
    tiles.append(t)
    # 3: fading spark
    t = np.zeros((8, 8), int)
    for y, row in enumerate([
        "00000000",
        "00000000",
        "00020000",
        "00232000",
        "00020000",
        "00000000",
        "00000000",
        "00000000",
    ]):
        t[y] = [int(c) for c in row]
    tiles.append(t)
    return tiles


def border_tile():
    """Muted dithered frame tile, bank 0 index 37, backdrop palette."""
    t = np.zeros((8, 8), int)
    for y in range(8):
        for x in range(8):
            if x == 0 or y == 0 or x == 7 or y == 7:
                t[y, x] = 2 if (x + y) & 1 else 1
            elif (x + y) & 3 == 0:
                t[y, x] = 1
    return t


def preview(mask, patterns, map_ids, map_attrs, stone, ember, path):
    pals = [PAL_BACKDROP, stone, ember]
    screen = np.zeros((SCREEN_H, SCREEN_W, 3), dtype=np.uint8)
    bg = np.array(from555(C0), np.uint8)
    screen[:, :] = bg
    # Frame
    bt = border_tile()
    bpal = np.array([from555(c) for c in PAL_BACKDROP], np.uint8)
    for ty in range(18):
        for tx in range(20):
            if ty in (0, 17):
                for y in range(8):
                    for x in range(8):
                        screen[ty * 8 + y, tx * 8 + x] = bpal[bt[y, x]]
    for ty in range(MASK_H):
        for tx in range(MASK_W):
            i = ty * MASK_W + tx
            attr = map_attrs[i]
            if not (attr & 0x08):
                continue
            tid = map_ids[i]
            pat = patterns[tid]
            if attr & 0x20:
                pat = pat[:, ::-1]
            if attr & 0x40:
                pat = pat[::-1]
            pal = pals[attr & 7]
            for y in range(8):
                for x in range(8):
                    screen[(MASK_Y + ty) * 8 + y, (MASK_X + tx) * 8 + x] = from555(pal[int(pat[y, x])])
    # Scale 4x for review.
    im = Image.fromarray(screen, "RGB").resize((SCREEN_W * 4, SCREEN_H * 4), Image.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    print(f"preview {path} tiles={len(patterns)}")


def emit(patterns, map_ids, map_attrs, stone, ember):
    tile_data = []
    for pat in patterns:
        tile_data += tile_bytes(pat)
    shards = shard_tiles()
    shard_data = []
    for s in shards:
        shard_data += tile_bytes(s)
    border = tile_bytes(border_tile())

    h = f"""#ifndef QUINTRA_RENDER_GAMEOVER_ART_H
#define QUINTRA_RENDER_GAMEOVER_ART_H

#include "core/types.h"

// Generated by scripts/gen_gameover_art.py. Do not edit the counts by hand.

#define GOART_MASK_X     {MASK_X}
#define GOART_MASK_Y     {MASK_Y}
#define GOART_MASK_W     {MASK_W}
#define GOART_MASK_H     {MASK_H}
#define GOART_TILE_COUNT {len(patterns)}
#define GOART_SHARD_TILES 4
#define GOART_BORDER_TILE 37
#define GOART_PAL_BACKDROP 0
#define GOART_PAL_STONE    1
#define GOART_PAL_EMBER    2
#define GOART_PAL_TITLE    3
#define GOART_PAL_GOLD     4

extern const u16 goart_pal_backdrop[4];
extern const u16 goart_pal_stone[4];
extern const u16 goart_pal_ember[4];
extern const u16 goart_pal_title[4];
extern const u16 goart_pal_gold[4];
extern const u16 goart_pal_shard[4];

void gameover_art_load(void) BANKED;
void gameover_art_draw_rise(u8 rows) BANKED;
void gameover_art_draw_full(void) BANKED;
void gameover_art_paint_attrs(u8 text_on) BANKED;
void gameover_art_load_shards(void) BANKED;
void gameover_art_hide_shards(void) BANKED;
void gameover_art_draw_frame(void) BANKED;
void gameover_art_reveal_row(u8 mask_row) BANKED;
void gameover_art_copy_pals(u16 *out) BANKED;

#endif
"""

    c = f"""#pragma bank 27
// Generated by scripts/gen_gameover_art.py from the Nameless Visor art.
// Do not edit the arrays by hand.

#include <gb/gb.h>
#include <gb/cgb.h>

#include "render/gameover_art.h"
#include "render/palette.h"

BANKREF(gameover_art_load)

{pal_array("goart_pal_backdrop", PAL_BACKDROP)}
{pal_array("goart_pal_stone", stone)}
{pal_array("goart_pal_ember", ember)}
{pal_array("goart_pal_title", PAL_TITLE)}
{pal_array("goart_pal_gold", PAL_GOLD)}
{pal_array("goart_pal_shard", PAL_EMBER)}

{c_array("u8", "goart_tiles", tile_data)}
{c_array("u8", "goart_map", map_ids)}
{c_array("u8", "goart_mask_attr", map_attrs)}
{c_array("u8", "goart_shards", shard_data)}
{c_array("u8", "goart_border", border)}

static u8 *const bg_map = (u8 *)0x9800;

static void write_row(u8 x, u8 y, u8 n, const u8 *tiles, const u8 *attrs) {{
    /* Write both BG maps. font/console and LCDC can disagree about 9800 vs
       9C00, and a one-map write left Game Over glyphs on one plane with
       empty attributes on the other. */
    set_tiles(x, y, n, 1, (u8 *)0x9800, tiles);
    set_tiles(x, y, n, 1, (u8 *)0x9C00, tiles);
    VBK_REG = 1;
    set_tiles(x, y, n, 1, (u8 *)0x9800, attrs);
    set_tiles(x, y, n, 1, (u8 *)0x9C00, attrs);
    VBK_REG = 0;
}}

void gameover_art_load(void) BANKED {{
    u8 i;
    /* Bank 1 holds the visor patterns. font_min stays in bank 0. */
    VBK_REG = 1;
    set_bkg_data(0, GOART_TILE_COUNT, goart_tiles);
    VBK_REG = 0;
    set_bkg_data(GOART_BORDER_TILE, 1, goart_border);
    palette_bg_load(GOART_PAL_BACKDROP, goart_pal_backdrop);
    palette_bg_load(GOART_PAL_STONE, goart_pal_stone);
    palette_bg_load(GOART_PAL_EMBER, goart_pal_ember);
    palette_bg_load(GOART_PAL_TITLE, goart_pal_title);
    palette_bg_load(GOART_PAL_GOLD, goart_pal_gold);
    palette_obj_load(0, goart_pal_shard);
    for (i = 0; i < 40; i++) move_sprite(i, 0, 0);
}}

void gameover_art_copy_pals(u16 *out) BANKED {{
    u8 i;
    const u16 *src;
    src = goart_pal_backdrop;
    for (i = 0; i < 4; i++) out[i] = src[i];
    src = goart_pal_stone;
    for (i = 0; i < 4; i++) out[4 + i] = src[i];
    src = goart_pal_ember;
    for (i = 0; i < 4; i++) out[8 + i] = src[i];
    src = goart_pal_title;
    for (i = 0; i < 4; i++) out[12 + i] = src[i];
    src = goart_pal_gold;
    for (i = 0; i < 4; i++) out[16 + i] = src[i];
    src = goart_pal_shard;
    for (i = 0; i < 4; i++) out[20 + i] = src[i];
}}

void gameover_art_load_shards(void) BANKED {{
    set_sprite_data(0, GOART_SHARD_TILES, goart_shards);
}}

void gameover_art_hide_shards(void) BANKED {{
    u8 i;
    for (i = 0; i < GOART_SHARD_TILES; i++) move_sprite(i, 0, 0);
}}

void gameover_art_draw_frame(void) BANKED {{
    u8 x;
    u8 tiles[20];
    u8 attrs[20];
    /* Top and bottom bars only. A side column would be punched out by
       the 19-glyph hint at (1, 13) and by long stat lines. */
    for (x = 0; x < 20; x++) {{
        tiles[x] = GOART_BORDER_TILE;
        attrs[x] = GOART_PAL_BACKDROP;
    }}
    write_row(0, 0, 20, tiles, attrs);
    write_row(0, 17, 20, tiles, attrs);
}}

static void mask_row(u8 sy, u8 dy) {{
    u8 tiles[GOART_MASK_W];
    u8 attrs[GOART_MASK_W];
    u8 x;
    const u8 *src = goart_map + (u16)sy * GOART_MASK_W;
    const u8 *asrc = goart_mask_attr + (u16)sy * GOART_MASK_W;
    for (x = 0; x < GOART_MASK_W; x++) {{
        tiles[x] = src[x];
        attrs[x] = asrc[x];
    }}
    write_row(GOART_MASK_X, dy, GOART_MASK_W, tiles, attrs);
}}

static void blank_row(u8 dy) {{
    u8 tiles[GOART_MASK_W];
    u8 attrs[GOART_MASK_W];
    u8 x;
    for (x = 0; x < GOART_MASK_W; x++) {{
        tiles[x] = 0;
        attrs[x] = GOART_PAL_BACKDROP;
    }}
    write_row(GOART_MASK_X, dy, GOART_MASK_W, tiles, attrs);
}}

void gameover_art_draw_rise(u8 rows) BANKED {{
    u8 y;
    if (rows > GOART_MASK_H) rows = GOART_MASK_H;
    /* The top of the visor sits on the well floor and climbs, so the
       motif actually rises rather than wiping in from the bottom. */
    for (y = 0; y < GOART_MASK_H; y++) {{
        if (y < (u8)(GOART_MASK_H - rows)) blank_row((u8)(GOART_MASK_Y + y));
        else mask_row((u8)(y - (GOART_MASK_H - rows)), (u8)(GOART_MASK_Y + y));
    }}
}}

void gameover_art_draw_full(void) BANKED {{
    gameover_art_draw_rise(GOART_MASK_H);
}}

void gameover_art_reveal_row(u8 sy) BANKED {{
    if (sy >= GOART_MASK_H) return;
    mask_row(sy, (u8)(GOART_MASK_Y + sy));
}}

void gameover_art_paint_attrs(u8 text_on) BANKED {{
    u8 x, y;
    u8 attrs[20];
    u8 *map = bg_map;
    for (y = 0; y < 18; y++) {{
        u8 pal = GOART_PAL_BACKDROP;
        if (text_on) {{
            if (y == 3) pal = GOART_PAL_TITLE;
            else if (y == 2 || (y >= 13 && y <= 16)) pal = GOART_PAL_GOLD;
        }}
        for (x = 0; x < 20; x++) attrs[x] = pal;
        if (y == 0 || y == 17) {{
            for (x = 0; x < 20; x++) attrs[x] = GOART_PAL_BACKDROP;
        }} else if (!(text_on && y == 13)) {{
            /* The Normal hint is 19 glyphs starting at column 1, so
               column 19 must keep the gold text palette on that row. */
            attrs[0] = GOART_PAL_BACKDROP;
            attrs[19] = GOART_PAL_BACKDROP;
        }} else {{
            attrs[0] = GOART_PAL_BACKDROP;
        }}
        /* Only stamp visor attributes once the corresponding bank-1 tiles
           are in place. Doing this on enter left tile 0 in bank 1 showing
           as a grid of scraps during the rise. */
        if (text_on && y >= GOART_MASK_Y && y < (u8)(GOART_MASK_Y + GOART_MASK_H)) {{
            u8 sy = (u8)(y - GOART_MASK_Y);
            const u8 *asrc = goart_mask_attr + (u16)sy * GOART_MASK_W;
            for (x = 0; x < GOART_MASK_W; x++) attrs[GOART_MASK_X + x] = asrc[x];
        }}
        VBK_REG = 1;
        set_tiles(0, y, 20, 1, (u8 *)0x9800, attrs);
        set_tiles(0, y, 20, 1, (u8 *)0x9C00, attrs);
    }}
    VBK_REG = 0;
    text_on;
}}
"""
    OUT_H.write_text(h)
    OUT_C.write_text(c)
    print(f"wrote {OUT_C} ({len(patterns)} tiles, {OUT_C.stat().st_size} bytes)")
    print(f"wrote {OUT_H}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--png", type=Path, help="1024px (or any) GPT render to quantize")
    ap.add_argument("--preview", type=Path, help="write a 4x PNG sheet")
    args = ap.parse_args()
    if args.png:
        screen = load_png(args.png)
        # Force the text bands to the shared void so glyphs stay clean.
        screen[:MASK_Y * 8, :] = C0
        screen[(MASK_Y + MASK_H) * 8:, :] = C0
        # Keep a little breathing room on the left/right of the well too
        # only outside the well itself; do not wipe the visor.
        mask = fit_content_to_well(screen)
    else:
        mask = procedural_mask()
    # Snap the well void (the crop's corner colour) to the shared colour 0
    # so a navy rectangle does not sit behind the visor.
    corners = np.array([mask[0,0], mask[0,-1], mask[-1,0], mask[-1,-1]], int)
    void = np.median(corners, axis=0)
    diff = np.abs(mask.astype(int) - void).sum(axis=2)
    mask[diff <= 10] = C0
    patterns, map_ids, map_attrs, stone, ember = build(mask)
    emit(patterns, map_ids, map_attrs, stone, ember)
    if args.preview:
        preview(mask, patterns, map_ids, map_attrs, stone, ember, args.preview)
    print(f"stone={stone} ember={ember}")


if __name__ == "__main__":
    main()
