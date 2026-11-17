#!/usr/bin/env python3
"""Generate the lore intro scenes (spec 2026-11-16 §1, attract addendum 2026-11-17).

Each scene is DATA: quantized panels from assets/intro/, text lines drawn with
the vignette font, and a few cell "blocks" the player writes at set times.
This script recovers <= 7 CGB palettes per scene (palette 7 = text), dedups
tiles with H/V flips into one pool of <= 512 tiles (VRAM banks 0 and 1, BG
8800 addressing), and emits one banked C file per scene plus a header.

  python3 scripts/gen_intro.py           # rewrite src/render/intro_*.{c,h}
  python3 scripts/gen_intro.py --check   # fail if checked-in files are stale
  python3 scripts/gen_intro.py --png DIR # write one PNG per block state

The player is src/game/intro.c. Timeline numbers live there; this file only
owns pictures, text, and palette sets.
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gen_vignettes import FONT, to555, from555, tile_bytes, carr  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets" / "intro"
OUT_DIR = ROOT / "src" / "render"

BLACK = (1, 0, 3)
WHITE = (31, 31, 31)
GREY = (20, 20, 24)
LIGHT_GREY = (24, 24, 27)
LINE = (12, 11, 16)
MAX_POOL = 512
BANK_LIMIT = 15800      # bytes of data per 16 KiB bank (headroom for code)
FIRST_BANK = 23
ROWS_PER_PART = 4
TGT_BG, TGT_WIN = 0, 1


def load(name):
    return np.asarray(Image.open(ASSETS / name).convert("RGB")).astype(int)


def cells_of(a):
    h, w = a.shape[:2]
    return [[a[y * 8:y * 8 + 8, x * 8:x * 8 + 8] for x in range(w // 8)]
            for y in range(h // 8)]


def c555(cell):
    return np.array([[to555(tuple(p)) for p in row] for row in cell])


# ---------------------------------------------------------------- palettes

def _kmeans4(colors, weights):
    """Reduce a weighted colour set (RGB555 tuples) to <= 4 colours."""
    cols = np.array(colors, float)
    w = np.array(weights, float)
    if len(cols) <= 4:
        return [tuple(int(v) for v in c) for c in cols]
    order = np.argsort(cols @ np.array([3.0, 6.0, 1.0]))
    centers = cols[order[np.linspace(0, len(cols) - 1, 4).astype(int)]]
    for _ in range(12):
        d = ((cols[:, None] - centers[None]) ** 2).sum(2)
        lab = d.argmin(1)
        for k in range(4):
            m = lab == k
            if m.any():
                centers[k] = (cols[m] * w[m, None]).sum(0) / w[m].sum()
    return sorted({tuple(int(round(v)) for v in c) for c in centers})


def reduce_palettes(cells, limit=7):
    """cells: list of 8x8x3 RGB555 arrays. Return <= limit palettes (4 cols)."""
    sets = {}
    for c in cells:
        key = frozenset(map(tuple, c.reshape(-1, 3)))
        sets[key] = sets.get(key, 0) + 1
    pals = []          # list of dict colour -> weight
    for s in sorted(sets, key=lambda s: (-len(s), sorted(s))):
        best = None
        for i, p in enumerate(pals):
            u = set(p) | s
            if len(u) <= 4 and (best is None or len(u) < len(set(pals[best]) | s)):
                best = i
        if best is None:
            pals.append({c: sets[s] for c in s})
        else:
            for c in s:
                pals[best][c] = pals[best].get(c, 0) + sets[s]
    # Lossy merge until within the limit: join the pair whose 4-colour
    # reduction moves the fewest weighted colour units.
    while len(pals) > limit:
        best = None
        for i in range(len(pals)):
            for j in range(i + 1, len(pals)):
                merged = dict(pals[i])
                for c, wt in pals[j].items():
                    merged[c] = merged.get(c, 0) + wt
                red = _kmeans4(list(merged), list(merged.values()))
                rr = np.array(red, float)
                err = 0.0
                for c, wt in merged.items():
                    err += wt * ((rr - np.array(c, float)) ** 2).sum(1).min()
                if best is None or err < best[0]:
                    best = (err, i, j, merged, red)
        _, i, j, merged, red = best
        rr = np.array(red, float)
        new = {}
        for c, wt in merged.items():
            k = int(((rr - np.array(c, float)) ** 2).sum(1).argmin())
            new[red[k]] = new.get(red[k], 0) + wt
        pals = [p for k, p in enumerate(pals) if k not in (i, j)] + [new]
    out = []
    for p in pals:
        cols = sorted(p, key=lambda c: (c[0] * 3 + c[1] * 6 + c[2], c))
        while len(cols) < 4:
            cols.append(cols[-1])
        out.append(cols)
    return out


def fit(cell555, pals):
    """Best palette and index plane for one 8x8 RGB555 cell."""
    best = None
    for pi, p in enumerate(pals):
        pa = np.array(p)
        d = ((cell555[:, :, None, :] - pa[None, None]) ** 2).sum(3)
        idx, err = d.argmin(2), int(d.min(2).sum())
        if best is None or err < best[1]:
            best = (idx, err, pi)
        if err == 0:
            break
    return best[0], best[2]


# ---------------------------------------------------------------- tiles

class Pool:
    def __init__(self):
        self.patterns = []
        self.lookup = {}

    def add(self, idx):
        idx = np.asarray(idx, int)
        for flip, arr in ((0, idx), (0x20, idx[:, ::-1]), (0x40, idx[::-1]),
                          (0x60, idx[::-1, ::-1])):
            key = arr.tobytes()
            if key in self.lookup:
                return self.lookup[key], flip
        n = len(self.patterns)
        self.patterns.append(idx.copy())
        self.lookup[idx.tobytes()] = n
        return n, 0


def glyph(ch):
    idx = np.zeros((8, 8), int)
    if ch != " ":
        for y, bits in enumerate(FONT[ch]):
            for x in range(8):
                if bits & (0x80 >> x):
                    idx[y, x] = 3
    return idx


class Scene:
    def __init__(self, name):
        self.name = name
        self.pool = Pool()
        self.pool.add(np.zeros((8, 8), int))      # tile 0 = blank (colour 0)
        self.blocks = []                          # (name, tgt, x, y, w, h, cells)
        self.pal_sets = []
        self.load_block = None

    def cell(self, idx, pal):
        n, flip = self.pool.add(idx)
        return (n, pal | flip | (0x08 if n >= 256 else 0))

    def blank(self, pal=7):
        return self.cell(np.zeros((8, 8), int), pal)

    def block(self, name, tgt, x, y, grid):
        h, w = len(grid), len(grid[0])
        self.blocks.append((name, tgt, x, y, w, h, grid))
        return len(self.blocks) - 1

    def text_row(self, s, pal=7, col=None, width=20):
        assert len(s) <= width, s
        missing = sorted({ch for ch in s if ch != " " and ch not in FONT})
        assert not missing, f"no glyph for {missing} in {s!r}"
        c0 = (width - len(s)) // 2 if col is None else col
        row = [self.blank() for _ in range(width)]
        for i, ch in enumerate(s):
            row[c0 + i] = self.cell(glyph(ch), pal)
        return row

    def band(self, name, l1, l2=""):
        """Window text band: rows 0..3 at WY=112, lines on rows 1 and 2."""
        grid = [[self.blank() for _ in range(20)], self.text_row(l1),
                self.text_row(l2), [self.blank() for _ in range(20)]]
        return self.block(name, TGT_WIN, 0, 0, grid)

    def panel_grid(self, cells555, pals):
        return [[self.cell(*fit(c, pals)) for c in row] for row in cells555]


def font_pal():
    return [BLACK, BLACK, GREY, WHITE]


def pal_set(pals, extra=None):
    s = [list(p) for p in pals]
    while len(s) < 7:
        s.append([BLACK] * 4)
    if extra is not None:
        s[6] = extra
    s.append(font_pal())
    return s


def blank_grid(sc, w, h):
    return [[sc.blank() for _ in range(w)] for _ in range(h)]


# ---------------------------------------------------------------- scenes

TEAR_RADII = [0, 3, 6, 10, 30]
LAND_ROW = 11      # cell rows >= this are land (dimmed toward violet in shot 2)


def scene_valley():
    sc = Scene("valley")
    val, torn = load("valley.png"), load("torn.png")
    vc = [[c555(c) for c in row] for row in cells_of(val)]
    tc = [[c555(c) for c in row] for row in cells_of(torn)][:8]
    pals = reduce_palettes([c for row in vc for c in row]
                           + [c for row in tc for c in row], 7)
    vg = sc.panel_grid(vc, pals)
    tg = sc.panel_grid(tc, pals)
    # 32x32 map: pad columns and rows so a +-2 px shake never shows junk.
    full = []
    for y in range(32):
        src = vg[y] if y < 30 else vg[0]
        full.append(src + [src[19]] * 6 + [src[0]] * 6)
    sc.load_block = sc.block("map", TGT_BG, 0, 0, full)
    for k, r in enumerate(TEAR_RADII):
        g = []
        for ty in range(8):
            row = []
            for tx in range(20):
                inside = (tx - 10) ** 2 + ((ty - 4) * 1.6) ** 2 <= r * r
                row.append(tg[ty][tx] if inside else vg[ty][tx])
            g.append(row)
        sc.block(f"tear{k}", TGT_BG, 0, 0, g)
    # Palettes used mostly by land cells dim two steps toward violet.
    use = [[0, 0] for _ in pals]
    for ty, row in enumerate(vg):
        for n, a in row:
            use[a & 7][1 if ty >= LAND_ROW else 0] += 1
    land = [i for i, (sky, gr) in enumerate(use) if gr > sky]
    sc.pal_sets.append(pal_set(pals))
    for k in (1, 2):
        dp = []
        for i, p in enumerate(pals):
            if i not in land:
                dp.append(p)
                continue
            q = []
            for c in p:
                rgb = np.array(from555(c), float)
                rgb = rgb * (1 - 0.28 * k) + np.array([40, 0, 72]) * 0.28 * k
                q.append(to555(tuple(np.clip(rgb, 0, 255))))
            dp.append(q)
        sc.pal_sets.append(pal_set(dp))
    sc.band("once", "ONCE EVERY ROAD", "KNEW ITS OWN NAME")
    sc.band("tore", "THEN THE SKY TORE")
    sc.band("devour", "THE RIFT DEVOURED", "ROADS AND NAMES")
    return sc


BUST_RECTS = [(4 + (i % 3) * 52, 2 + (i // 3) * 36, 48, 32) for i in range(9)]


def scene_busts():
    sc = Scene("busts")
    pic = load("busts.png")
    cc = [[c555(c) for c in row] for row in cells_of(pic)]
    pals = reduce_palettes([c for row in cc for c in row], 7)
    g = sc.panel_grid(cc, pals)
    h, w = len(g), len(g[0])
    owner = {}
    for cy in range(h):
        for cx in range(w):
            best = (0, None)
            for i, (x, y, bw, bh) in enumerate(BUST_RECTS):
                ox = max(0, min(cx * 8 + 8, x + bw) - max(cx * 8, x))
                oy = max(0, min(cy * 8 + 8, y + bh) - max(cy * 8, y))
                if ox * oy > best[0]:
                    best = (ox * oy, i)
            if best[1] is not None and best[0] >= 1:
                owner[(cx, cy)] = best[1]

    def state(k):
        out = blank_grid(sc, 20, 18)
        for cy in range(h):
            for cx in range(w):
                o = owner.get((cx, cy))
                if o is None or o < k:
                    out[cy][cx] = g[cy][cx]
        return out

    sc.load_block = sc.block("map", TGT_BG, 0, 0, state(0))
    for i in range(9):
        cells = [c for c, o in owner.items() if o == i]
        x0 = min(c[0] for c in cells); x1 = max(c[0] for c in cells)
        y0 = min(c[1] for c in cells); y1 = max(c[1] for c in cells)
        st = state(i + 1)
        sc.block(f"bust{i}", TGT_BG, x0, y0,
                 [st[y][x0:x1 + 1] for y in range(y0, y1 + 1)])
    sc.pal_sets.append(pal_set(pals))
    sc.band("colossi", "NINE COLOSSI ROSE", "IN THE WORLD BELOW")
    return sc


def scene_shrine():
    sc = Scene("shrine")
    pic = load("shrine.png")
    cc = [[c555(c) for c in row] for row in cells_of(pic)]
    pals = reduce_palettes([c for row in cc for c in row], 7)
    g = sc.panel_grid(cc, pals)
    full = blank_grid(sc, 20, 18)
    for y, row in enumerate(g):
        full[y] = row
    sc.load_block = sc.block("map", TGT_BG, 0, 0, full)
    sc.pal_sets.append(pal_set(pals))
    sc.band("spirits", "FIVE SPIRITS WOKE", "TO BEAR THE SPARKS")
    return sc


HEROES = [("WOLFKIN", "FANG OF FLAME"), ("SAURAN", "SCALE OF STONE"),
          ("CORVIN", "WING OF SHADOW"), ("PICSEAN", "FIN OF TIDE"),
          ("VESPINE", "STING OF BLOOM")]


def scene_chosen():
    sc = Scene("chosen")
    full = blank_grid(sc, 20, 18)
    full[1] = sc.text_row("FIVE ARE CHOSEN")
    sc.load_block = sc.block("map", TGT_BG, 0, 0, full)
    for i, (name, ep) in enumerate(HEROES):
        left = i % 2 == 0
        tx = 4 if left else 2
        if not left:
            tx = 16 - max(len(name), len(ep))
        sc.block(f"hero{i}", TGT_BG, 0, 3 + i * 3,
                 [sc.text_row(name, 7, tx), sc.text_row(ep, 6, tx)])
    sc.pal_sets.append(pal_set([], [BLACK, BLACK, GREY, LIGHT_GREY]))
    return sc


def scene_cliff():
    sc = Scene("cliff")
    pic = load("cliff.png")
    cc = [[c555(c) for c in row] for row in cells_of(pic)]
    pals = reduce_palettes([c for row in cc for c in row], 7)
    g = sc.panel_grid(cc, pals)
    sc.load_block = sc.block("map", TGT_BG, 0, 0, g)
    sc.pal_sets.append(pal_set(pals))
    sc.band("wild", "INTO THE WILD BELOW")
    sc.band("bind", "BIND THE RIFT", "ERE ALL NAMES FADE")
    return sc


def scene_title():
    sc = Scene("title")
    full = blank_grid(sc, 20, 18)
    full[3] = sc.text_row("QUINTRA")
    # Ground line at y=63 from x=12..148 (cell row 7, pixel row 7).
    for cx in range(20):
        idx = np.zeros((8, 8), int)
        for px in range(8):
            x = cx * 8 + px
            if 12 <= x <= 148:
                idx[7, px] = 1
        if idx.any():
            full[7][cx] = sc.cell(idx, 6)
    sc.load_block = sc.block("map", TGT_BG, 0, 0, full)
    blank = [sc.blank() for _ in range(20)]
    sc.block("vessel", TGT_BG, 0, 10, [sc.text_row("CHOOSE YOUR VESSEL"), blank,
                                       sc.text_row("REKINDLE THE DAWN")])
    sc.block("press", TGT_BG, 0, 10, [blank, blank, sc.text_row("PRESS  START")])
    sc.block("clear", TGT_BG, 0, 10, [blank, blank, blank])
    sc.pal_sets.append(pal_set([], [BLACK, LINE, LINE, LINE]))
    return sc


SCENES = [scene_valley, scene_busts, scene_shrine, scene_chosen,
          scene_cliff, scene_title]


# ---------------------------------------------------------------- emit

def scene_bytes(sc):
    n = len(sc.pool.patterns) * 16
    for b in sc.blocks:
        n += b[4] * b[5] * 2 + 6
    return n + len(sc.pal_sets) * 64 + 600


def assign_banks(scenes):
    bank, used, out = FIRST_BANK, 0, []
    for sc in scenes:
        size = scene_bytes(sc)
        if used and used + size > BANK_LIMIT:
            bank, used = bank + 1, 0
        used += size
        out.append(bank)
    return out


def emit_c(sc, bank, sid):
    n = sc.name
    tiles = []
    for t in sc.pool.patterns:
        tiles += tile_bytes(t)
    out = [
        f"#pragma bank {bank}",
        f"// Generated by scripts/gen_intro.py (scene {sid}: {n}). Do not edit by hand.",
        "#include <gb/gb.h>",
        "#include <gb/cgb.h>",
        "#include <string.h>",
        '#include "render/intro_data.h"',
        "",
        f"BANKREF(intro_io_{n})",
        "",
        carr(f"{n}_tiles", tiles),
    ]
    meta = []
    for bi, (bname, tgt, x, y, w, h, grid) in enumerate(sc.blocks):
        out.append(carr(f"{n}_b{bi}_t", [c[0] & 0xFF for row in grid for c in row], w))
        out.append(carr(f"{n}_b{bi}_a", [c[1] for row in grid for c in row], w))
        meta.append((tgt, x, y, w, h, bi))
    out.append(carr(f"{n}_meta", [v for m in meta for v in m[:5]], 5))
    out.append(f"static const u8 * const {n}_bt[{len(meta)}] = {{ "
               + ", ".join(f"{n}_b{m[5]}_t" for m in meta) + " };")
    out.append(f"static const u8 * const {n}_ba[{len(meta)}] = {{ "
               + ", ".join(f"{n}_b{m[5]}_a" for m in meta) + " };")
    pals = []
    for s in sc.pal_sets:
        for p in s:
            for c in p:
                pals.append(c[0] | (c[1] << 5) | (c[2] << 10))
    out.append(f"static const u16 {n}_pals[{len(pals)}] = {{")
    for i in range(0, len(pals), 8):
        out.append("    " + ", ".join(f"0x{v:04X}" for v in pals[i:i + 8]) + ",")
    out.append("};")
    ntiles = len(sc.pool.patterns)
    chunks = (ntiles + 31) // 32
    lb = sc.load_block
    lparts = (sc.blocks[lb][5] + ROWS_PER_PART - 1) // ROWS_PER_PART
    out += [
        "",
        f"static u8 {n}_block(u8 id, u8 part) {{",
        f"    const u8 *m = {n}_meta + (u16)id * 5;",
        "    u8 w = m[3], h = m[4];",
        f"    u8 r0 = (u8)(part * {ROWS_PER_PART}), r1 = (u8)(r0 + {ROWS_PER_PART});",
        "    const u8 *t, *a;",
        "    if (r1 > h) r1 = h;",
        f"    t = {n}_bt[id] + (u16)r0 * w;",
        f"    a = {n}_ba[id] + (u16)r0 * w;",
        "    if (m[0]) {",
        "        set_win_tiles(m[1], (u8)(m[2] + r0), w, (u8)(r1 - r0), t);",
        "        VBK_REG = 1;",
        "        set_win_tiles(m[1], (u8)(m[2] + r0), w, (u8)(r1 - r0), a);",
        "    } else {",
        "        set_bkg_tiles(m[1], (u8)(m[2] + r0), w, (u8)(r1 - r0), t);",
        "        VBK_REG = 1;",
        "        set_bkg_tiles(m[1], (u8)(m[2] + r0), w, (u8)(r1 - r0), a);",
        "    }",
        "    VBK_REG = 0;",
        "    return r1 < h ? 1 : 0;",
        "}",
        "",
        f"u8 intro_io_{n}(u8 op, u8 a, u8 b) BANKED {{",
        "    switch (op) {",
        "    case IOP_LOAD:",
        f"        if (a < {chunks}u) {{",
        "            u16 first = (u16)a << 5;",
        f"            u8 cnt = ({ntiles}u - first) > 32 ? 32 : (u8)({ntiles}u - first);",
        "            VBK_REG = (u8)(first >> 8);",
        f"            set_bkg_data((u8)first, cnt, {n}_tiles + (first << 4));",
        "            VBK_REG = 0;",
        "            return 1;",
        "        }",
        f"        if ((u8)(a - {chunks}u) < {lparts}u) {{",
        f"            {n}_block({lb}, (u8)(a - {chunks}u));",
        "            return 1;",
        "        }",
        f"        memcpy(intro_pal, {n}_pals, 64);",
        "        return 0;",
        "    case IOP_BLOCK:",
        f"        return {n}_block(a, b);",
        "    case IOP_PAL:",
        f"        memcpy(intro_pal, {n}_pals + (u16)a * 32, 64);",
        "        return 0;",
        "    }",
        "    return 0;",
        "}",
        "",
    ]
    return "\n".join(out)


def emit_h(scenes, banks):
    out = [
        "// Generated by scripts/gen_intro.py. Do not edit by hand.",
        "#ifndef QUINTRA_RENDER_INTRO_DATA_H",
        "#define QUINTRA_RENDER_INTRO_DATA_H",
        "",
        '#include "core/types.h"',
        "",
        "#define IOP_LOAD  0   // a = step; returns 1 while more steps remain",
        "#define IOP_BLOCK 1   // a = block, b = 4-row part; returns 1 if more parts",
        "#define IOP_PAL   2   // a = palette set -> intro_pal",
        "",
        "extern u16 intro_pal[32];",
        "",
    ]
    for sid, sc in enumerate(scenes):
        out.append(f"#define ISC_{sc.name.upper()} {sid}")
    out.append("")
    for sc in scenes:
        for bi, b in enumerate(sc.blocks):
            out.append(f"#define IB_{sc.name.upper()}_{b[0].upper()} {bi}")
        out.append(f"#define IPAL_{sc.name.upper()}_SETS {len(sc.pal_sets)}")
        out.append(f"// {sc.name}: {len(sc.pool.patterns)} tiles, bank {banks[scenes.index(sc)]}")
    out.append("")
    for sc in scenes:
        out.append(f"u8 intro_io_{sc.name}(u8 op, u8 a, u8 b) BANKED;")
    out.append("")
    disp = "#define INTRO_IO(s, op, a, b) ( \\\n"
    for sid, sc in enumerate(scenes[:-1]):
        disp += f"    (s) == {sid} ? intro_io_{sc.name}(op, a, b) : \\\n"
    disp += f"    intro_io_{scenes[-1].name}(op, a, b))"
    out.append(disp)
    out += ["", "#endif", ""]
    return "\n".join(out)


def preview_png(sc, directory):
    directory.mkdir(parents=True, exist_ok=True)
    pals = sc.pal_sets[0]
    for bi, (bname, tgt, x, y, w, h, grid) in enumerate(sc.blocks):
        img = np.zeros((h * 8, w * 8, 3), np.uint8)
        for cy, row in enumerate(grid):
            for cx, (n, a) in enumerate(row):
                idx = sc.pool.patterns[n]
                if a & 0x20:
                    idx = idx[:, ::-1]
                if a & 0x40:
                    idx = idx[::-1]
                pal = pals[a & 7]
                img[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8] = np.array(
                    [from555(pal[v]) for v in idx.flat]).reshape(8, 8, 3)
        Image.fromarray(img).save(directory / f"{sc.name}-{bi}-{bname}.png")


def main(argv):
    scenes = [f() for f in SCENES]
    for sc in scenes:
        if len(sc.pool.patterns) > MAX_POOL:
            raise SystemExit(f"{sc.name}: {len(sc.pool.patterns)} tiles > {MAX_POOL}")
        for b in sc.blocks:
            assert b[4] <= 32 and b[5] <= 32, b[0]
    banks = assign_banks(scenes)
    files = {OUT_DIR / "intro_data.h": emit_h(scenes, banks)}
    for sid, sc in enumerate(scenes):
        files[OUT_DIR / f"intro_{sc.name}.c"] = emit_c(sc, banks[sid], sid)
        print(f"[intro] {sc.name}: {len(sc.pool.patterns)} tiles, "
              f"{len(sc.blocks)} blocks, ~{scene_bytes(sc)} B, bank {banks[sid]}",
              file=sys.stderr)
    if "--png" in argv:
        d = Path(argv[argv.index("--png") + 1])
        for sc in scenes:
            preview_png(sc, d)
        return 0
    if "--check" in argv:
        stale = [str(p) for p, s in files.items()
                 if not p.exists() or p.read_text() != s]
        if stale:
            print("[intro] STALE: " + ", ".join(stale), file=sys.stderr)
            return 1
        print("[intro] OK generated files are current", file=sys.stderr)
        return 0
    for p, s in files.items():
        p.write_text(s)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
