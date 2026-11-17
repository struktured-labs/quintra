#!/usr/bin/env python3
"""Headless Riftwild tile audit: fragments, clutter and 4x field captures.

Walks all 36 fields over real seams (PyBoy window="null"), forces a full BG
redraw per field, then reads the BG map + attributes from VRAM and the logical
31x31 tile grid from WRAM.

  uv run --with pyboy==2.7.0 --with pillow python \
      scripts/riftwild_tile_audit.py OUTDIR [--hollow] [--png] SEED [SEED...]

Writes OUTDIR/audit-<seed>[-hollow].json (per-field metrics + fragments) and,
with --png, OUTDIR/<seed>[-hollow]/field_NN.png at 4x.
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "docs/superpowers/specs/assets/riftwild-wonder"))
from test_overworld import ORIGIN_X, ORIGIN_Y, RS  # noqa: E402
from vram_render import field_from_bg, vram  # noqa: E402
from test_riftwild_landmarks import ROUTE, WALKABLE, wide_tiles  # noqa: E402
from capture_riftwild_atlas import boot  # noqa: E402
from capture_riftwild_wins import capture_field  # noqa: E402
from test_riftwild_landmarks import cross_to  # noqa: E402

RIFTWILD_SHADOW = 57
# Bank-1 2x2 metatile quarters (riftwild_art.h): TL, TR, BL, BR.
QUADS = {10: (0, 0), 11: (1, 0), 12: (0, 1), 13: (1, 1),
         14: (0, 0), 15: (1, 0), 16: (0, 1), 17: (1, 1)}
FAMILY = {10: 10, 11: 10, 12: 10, 13: 10, 14: 14, 15: 14, 16: 14, 17: 14}
# Logical obstacle ids that read as "props" (not broad terrain bodies).
WATERISH = {97, 108, 101, 102}


def bg_cells(pb):
    lcdc = pb.memory[0xFF40]
    base = 0x9C00 if lcdc & 0x08 else 0x9800
    idx = vram(pb, 0, base, base + 1024)
    att = vram(pb, 1, base, base + 1024)
    return idx, att


def ink_table(pb):
    """Non-colour-0 pixel count per (bank, tile id) for the BG tile region."""
    lcdc = pb.memory[0xFF40]
    signed = not (lcdc & 0x10)
    out = {}
    for bank in (0, 1):
        data = vram(pb, bank, 0x8000, 0x9800)
        for t in range(256):
            off = (0x1000 + (t - 256 if t >= 128 else t) * 16) if signed else t * 16
            out[(bank, t)] = sum(bin(data[off + i] | data[off + i + 1]).count("1")
                                 for i in range(0, 16, 2))
    return out


def field_cells(pb):
    idx, att = bg_cells(pb)
    ox, oy = pb.memory[ORIGIN_X], pb.memory[ORIGIN_Y]
    out = []
    for y in range(31):
        row = []
        for x in range(31):
            k = ((oy + y) & 31) * 32 + ((ox + x) & 31)
            row.append((idx[k], att[k]))
        out.append(row)
    return out


def components(mask):
    h, w = len(mask), len(mask[0])
    seen = [[False] * w for _ in range(h)]
    sizes = []
    for y in range(h):
        for x in range(w):
            if not mask[y][x] or seen[y][x]:
                continue
            stack, n = [(x, y)], 0
            seen[y][x] = True
            while stack:
                cx, cy = stack.pop()
                n += 1
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
                    if 0 <= nx < w and 0 <= ny < h and mask[ny][nx] and not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((nx, ny))
            sizes.append(n)
    return sizes


GROUND = {35, 105, 106, 107, 96}


def analyse(wide, cells, ink):
    frags = []
    for y in range(31):
        for x in range(31):
            t, a = cells[y][x]
            if not (a & 0x08) or t not in QUADS:
                continue
            qx, qy = QUADS[t]
            fam = FAMILY[t]
            ok = True
            for ex in (0, 1):
                for ey in (0, 1):
                    px, py = x - qx + ex, y - qy + ey
                    if not (0 <= px < 31 and 0 <= py < 31):
                        ok = False
                        continue
                    pt, pa = cells[py][px]
                    if not (pa & 0x08) or pt != fam + ey * 2 + ex:
                        ok = False
            if not ok:
                frags.append({"x": x, "y": y, "art": t, "logical": wide[y][x]})
    inner = [(x, y) for y in range(1, 30) for x in range(1, 30)]
    walk = sum(1 for x, y in inner if wide[y][x] in WALKABLE)
    mask = [[(1 <= x <= 29 and 1 <= y <= 29 and wide[y][x] not in WALKABLE
              and wide[y][x] not in WATERISH) for x in range(31)] for y in range(31)]
    sizes = components(mask)
    ground = [(x, y) for x, y in inner if wide[y][x] in GROUND]
    marked = sum(1 for x, y in ground
                 if ink[((cells[y][x][1] >> 3) & 1, cells[y][x][0])] > 3)
    noise = sum(ink[((cells[y][x][1] >> 3) & 1, cells[y][x][0])]
                for x, y in ground)
    return {
        "open_pct": round(100 * walk / len(inner), 1),
        "props": len(sizes),
        "prop_singles": sum(1 for s in sizes if s <= 2),
        # Ground cells carrying a visible mark (>3 inked pixels), and the
        # mean share of inked (non-ground-colour) pixels per ground cell.
        "detail_pct": round(100 * marked / max(len(ground), 1), 1),
        "ground_ink_pct": round(100 * noise / max(64 * len(ground), 1), 1),
        "fragments": frags,
        "tiles": Counter(t for r in wide for t in r).most_common(12),
    }


def run(seed, hollow, png_dir):
    pb = boot(seed, 1)
    res = {}
    try:
        if hollow:
            pb.memory[RS + RIFTWILD_SHADOW] |= 1
        def grab(screen):
            img, _, meta = capture_field(pb)
            cells = field_cells(pb)
            res[screen] = analyse(meta["tiles"], cells, ink_table(pb))
            res[screen]["wide"] = meta["tiles"]
            if png_dir:
                img.resize((img.width * 4, img.height * 4)).save(
                    png_dir / f"field_{screen:02d}.png")
        if not hollow:
            grab(0)
        for screen, x, y in ROUTE:
            cross_to(pb, screen, x, y)
            if screen not in res:
                grab(screen)
    finally:
        pb.stop(save=False)
    return res


def main():
    args = sys.argv[1:]
    out = Path(args.pop(0))
    hollow = "--hollow" in args
    png = "--png" in args
    seeds = [a for a in args if not a.startswith("--")]
    out.mkdir(parents=True, exist_ok=True)
    for s in seeds:
        seed = int(s, 16)
        tag = f"{seed:08x}" + ("-hollow" if hollow else "")
        pd = None
        if png:
            pd = out / tag
            pd.mkdir(exist_ok=True)
        res = run(seed, hollow, pd)
        (out / f"audit-{tag}.json").write_text(json.dumps(res))
        n = len(res)
        fr = sum(len(v["fragments"]) for v in res.values())
        op = sum(v["open_pct"] for v in res.values()) / n
        pr = sum(v["props"] for v in res.values()) / n
        sg = sum(v["prop_singles"] for v in res.values()) / n
        dt = sum(v["detail_pct"] for v in res.values()) / n
        ink = sum(v["ground_ink_pct"] for v in res.values()) / n
        mn = min(v["open_pct"] for v in res.values())
        print(f"{tag}: fields={n} fragments={fr} open_mean={op:.1f}% "
              f"open_min={mn:.1f}% props={pr:.1f} singles={sg:.1f} "
              f"marked={dt:.1f}% ground_ink={ink:.1f}%")


if __name__ == "__main__":
    main()
