#!/usr/bin/env python3
"""Generate src/render/rewrite_art.{c,h}: M2 Cairn Ford art.

All art is GPT Image (gpt-image-2.6-sunburst) output quantized to GBC
formats. Quantized grids are committed in scripts/rewrite_art_grids.json;
raw renders stay out of the repo.

  python3 scripts/gen_rewrite_art.py                 # JSON -> C
  python3 scripts/gen_rewrite_art.py --png OUT [s]   # preview sheet
  python3 scripts/gen_rewrite_art.py --from-gpt RAW  # re-quantize RAW/*.png

BG tiles (VRAM bank 0, written over Riftwild-only ids while the pocket is
live; index 0 lightest .. 3 darkest): cairn 2x2 (98, 109, 110, 39),
ford (107), chasm (108), sill bed (105).
OBJ (VRAM bank 1, 176..195; basilisks never spawn there, 0 transparent,
1 body, 2 outline, 3 highlight): 176 Switch A raised, 180 Switch A lowered,
184 Switch B rock, 188 Switch B water, 192 reset plate (copied from M1).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_rime_art as m1  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
GRIDS = ROOT / "scripts" / "rewrite_art_grids.json"
BG = (("cairn", 16, "cairn16"), ("ford", 8, "ford8"), ("chasm", 8, "chasm8"),
      ("sill", 8, "sill8"))
BG_IDS = {"cairn": (98, 109, 110, 39), "ford": (107,), "chasm": (108,), "sill": (105,)}
OBJ = (("a_up", 176, "glyph_a_up"), ("a_down", 180, "glyph_a_down"),
       ("b_rock", 184, "glyph_b_rock"), ("b_wave", 188, "glyph_b_wave"))


def quant_bg(a, n):
    import numpy as np
    lum = (a[..., 0] * 3.0 + a[..., 1] * 6 + a[..., 2]) / 10
    h, w = lum.shape
    blk = np.zeros((n, n))
    for y in range(n):
        for x in range(n):
            blk[y, x] = np.median(lum[y * h // n:(y + 1) * h // n, x * w // n:(x + 1) * w // n])
    # Four shades by quartile edges of this tile (lightest = 0).
    qs = np.percentile(blk, [25, 50, 75])
    lo, hi = blk.min(), blk.max()
    edges = [lo + (hi - lo) * f for f in (0.25, 0.5, 0.75)]
    edges = [(e + q) / 2 for e, q in zip(edges, qs)]
    out = 3 - np.digitize(blk, edges)
    return ["".join(str(int(v)) for v in r) for r in out]


def quant_obj(a, n):
    """Sprite quantizer: flood the canvas colour from the border, then a
    majority downsample; inner whites become the highlight (not holes)."""
    import numpy as np
    from collections import deque
    h, w = a.shape[:2]
    small = a[::4, ::4]
    sh, sw = small.shape[:2]
    corners = np.array([small[0, 0], small[0, -1], small[-1, 0], small[-1, -1]])
    bgc = np.median(corners, 0)
    near = np.abs(small - bgc).sum(-1) < 60
    seen = np.zeros((sh, sw), bool)
    q = deque([(0, 0), (0, sw - 1), (sh - 1, 0), (sh - 1, sw - 1)])
    while q:
        y, x = q.popleft()
        if y < 0 or x < 0 or y >= sh or x >= sw or seen[y, x] or not near[y, x]:
            continue
        seen[y, x] = True
        q.extend(((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)))
    lum = (small[..., 0] * 3 + small[..., 1] * 6 + small[..., 2]) / 10
    ys, xs = np.where(~seen)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    side = max(y1 - y0, x1 - x0)
    cy, cx = (y0 + y1) // 2, (x0 + x1) // 2
    y0, x0 = max(0, cy - side // 2), max(0, cx - side // 2)
    fg_l = lum[~seen]
    t_dark = 70
    t_hi = np.percentile(fg_l[fg_l > t_dark], 72) if (fg_l > t_dark).any() else 200
    out = np.zeros((n, n), int)
    for y in range(n):
        for x in range(n):
            ya, yb = y0 + y * side // n, y0 + (y + 1) * side // n
            xa, xb = x0 + x * side // n, x0 + (x + 1) * side // n
            bgm = seen[ya:yb, xa:xb]
            if bgm.size == 0 or bgm.mean() > 0.5:
                continue
            l = lum[ya:yb, xa:xb][~bgm]
            dark = (l < t_dark).mean()
            if dark >= 0.4:
                out[y, x] = 2
            elif np.median(l) >= t_hi:
                out[y, x] = 3
            else:
                out[y, x] = 1
    return ["".join(str(int(v)) for v in r) for r in out]


def from_gpt(raw):
    import numpy as np
    from PIL import Image
    g = {"note": "BG: 0 lightest..3 darkest. OBJ: 0 transparent, 1 body, 2 outline, "
                 "3 highlight. Quantized from gpt-image-2.6-sunburst renders by "
                 "scripts/gen_rewrite_art.py --from-gpt."}
    for name, n, src in BG:
        a = np.array(Image.open(Path(raw) / f"{src}.png").convert("RGB")).astype(float)
        g[name] = quant_bg(a, n)
    for name, _, src in OBJ:
        a = np.array(Image.open(Path(raw) / f"{src}.png").convert("RGB")).astype(float)
        g[name] = quant_obj(a, 16)
    g["plate"] = json.loads(m1.GRIDS.read_text())["plate"]
    GRIDS.write_text(json.dumps(g, indent=1))


def emit(g):
    bg = []
    for name, n, _ in BG:
        bg += m1.tile_bytes(g[name]) if n == 8 else sum(
            (m1.tile_bytes(t) for t in m1.cut(g[name], 2, 2)), [])
    obj = []
    for name in ("a_up", "a_down", "b_rock", "b_wave", "plate"):
        for t in m1.cut(g[name], 2, 2):
            obj += m1.tile_bytes(t)
    ids = [i for name, _, _ in BG for i in BG_IDS[name]]
    c = f"""#pragma bank 26
// Generated by scripts/gen_rewrite_art.py from GPT Image art. Do not edit.
#include <gb/gb.h>
#include "core/types.h"
#include "render/rewrite_art.h"

{m1.c_array("rw_bg_tiles", bg)}

static const u8 rw_bg_ids[{len(ids)}] = {{ {", ".join(map(str, ids))} }};

{m1.c_array("rw_obj_tiles", obj)}

void rw_bg_art_load(void) BANKED {{
    u8 i;
    VBK_REG = 0;
    for (i = 0; i < {len(ids)}; ++i)
        set_bkg_data(rw_bg_ids[i], 1, rw_bg_tiles + (u16)i * 16);
}}

void rw_art_load(void) BANKED {{
    VBK_REG = 1;
    set_sprite_data(RW_TILE_A_UP, {len(obj) // 16}, rw_obj_tiles);
    VBK_REG = 0;
}}
"""
    h = """#ifndef QUINTRA_RENDER_REWRITE_ART_H
#define QUINTRA_RENDER_REWRITE_ART_H
// Generated by scripts/gen_rewrite_art.py. Bank-1 OBJ tiles (2x2 each).
#include <gb/gb.h>
#define RW_TILE_A_UP   176
#define RW_TILE_A_DOWN 180
#define RW_TILE_B_ROCK 184
#define RW_TILE_B_WAVE 188
#define RW_TILE_PLATE  192
void rw_bg_art_load(void) BANKED;
void rw_art_load(void) BANKED;
#endif
"""
    (ROOT / "src/render/rewrite_art.c").write_text(c)
    (ROOT / "src/render/rewrite_art.h").write_text(h)


BG_PREV = {"cairn": [(214, 206, 189), (156, 140, 132), (99, 82, 90), (33, 24, 33)],
           "ford": [(198, 239, 247), (99, 181, 214), (41, 107, 156), (16, 41, 66)],
           "chasm": [(255, 222, 115), (214, 115, 41), (99, 41, 33), (16, 8, 8)],
           "sill": [(222, 214, 198), (165, 156, 140), (107, 99, 90), (41, 33, 33)]}
OBJ_PREV = {"a_up": m1.PREVIEW_PALS["jagger_idle"], "a_down": m1.PREVIEW_PALS["jagger_idle"],
            "b_rock": m1.PREVIEW_PALS["pipes"], "b_wave": m1.PREVIEW_PALS["pipes"],
            "plate": m1.PREVIEW_PALS["plate"]}


def preview(g, out, scale=4):
    from PIL import Image
    im = Image.new("RGB", (9 * 20 + 4, 44), (120, 140, 110))
    for i, (name, n, _) in enumerate(BG):
        rep = 16 // n
        for y in range(16):
            for x in range(16):
                im.putpixel((4 + i * 20 + x, 4 + y), BG_PREV[name][int(g[name][y % n][x % n])])
    for i, name in enumerate(("a_up", "a_down", "b_rock", "b_wave", "plate")):
        for y, row in enumerate(g[name]):
            for x, ch in enumerate(row):
                if ch != "0":
                    im.putpixel((4 + i * 20 + x, 24 + y), OBJ_PREV[name][int(ch)])
    im.resize((im.width * scale, im.height * scale), Image.NEAREST).save(out)


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--from-gpt":
        from_gpt(sys.argv[2])
    g = json.loads(GRIDS.read_text())
    if len(sys.argv) > 2 and sys.argv[1] == "--png":
        preview(g, sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 4)
        return
    emit(g)


if __name__ == "__main__":
    main()
