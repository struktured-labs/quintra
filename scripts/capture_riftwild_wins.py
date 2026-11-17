#!/usr/bin/env python3
"""Headless before/after Riftwild atlas from real VRAM (Riftwild quick wins).

Walks every one of the 36 fields over real seams (the audit route), forces a
complete BG redraw in each field by opening and closing the Compass, then
renders the 31x31 field straight from VRAM tile data, BG map, attributes and
palette RAM. That is exactly what the LCD shows, including render-only tile
variants in VRAM bank 1. It also dumps the logical tile grid and the arrival
hostile count for the metrics script.

  uv run --with pyboy==2.7.0 --with pillow python \
      scripts/capture_riftwild_wins.py OUTDIR BOSSES SEED [SEED...]

Never opens a window (PyBoy window="null").
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "docs/superpowers/specs/assets/riftwild-wonder"))
from PIL import Image, ImageDraw  # noqa: E402
from test_overworld import EN, ORIGIN_X, ORIGIN_Y, PL, RS, SCREEN, addr  # noqa: E402
from vram_render import field_from_bg  # noqa: E402
from test_riftwild_landmarks import ROUTE, wide_tiles  # noqa: E402
from capture_riftwild_atlas import boot, clear_entities, entities, keep_alive  # noqa: E402

SCREEN_ROOM, SCREEN_MAP = 5, 8


def settle(pb, n):
    for _ in range(n):
        keep_alive(pb)
        pb.tick()


def redraw(pb):
    """SELECT -> Compass -> B: room_draw_tilemap() repaints all 32 rows."""
    pb.button_press("select")
    for _ in range(120):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_MAP:
            break
    pb.button_release("select")
    settle(pb, 20)
    pb.button_press("b")
    for _ in range(180):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            break
    pb.button_release("b")
    settle(pb, 30)


def capture_field(pb):
    settle(pb, 40)
    ents = entities(pb)
    hostiles = sum(1 for e in ents if e["type"] == 2)
    wide = wide_tiles(pb)
    redraw(pb)
    img = field_from_bg(pb, pb.memory[ORIGIN_X], pb.memory[ORIGIN_Y])
    marked = img.copy()
    d = ImageDraw.Draw(marked)
    for e in ents:
        x, y = e["x"], e["y"]
        if e["type"] == 2:
            d.rectangle((x + 3, y + 3, x + 12, y + 12), outline=(255, 40, 40))
        else:
            d.rectangle((x + 1, y + 1, x + 14, y + 14), outline=(255, 230, 0))
    return img, marked, {"tiles": wide, "entities": ents, "hostiles": hostiles}


def cross_to(pb, target, x, y):
    clear_entities(pb)
    pb.memory[PL + 9] = x & 255
    pb.memory[PL + 10] = x >> 8
    pb.memory[PL + 11] = y & 255
    pb.memory[PL + 12] = y >> 8
    for _ in range(200):
        keep_alive(pb)
        pb.tick()
        if pb.memory[RS + 18] == target and pb.memory[0xFF40] & 0x02:
            break
    settle(pb, 30)
    assert pb.memory[RS + 18] == target, (target, pb.memory[RS + 18])


def run(seed, bosses):
    pb = boot(seed, bosses)
    out = {}
    try:
        start = pb.memory[RS + 18]
        assert start == 0, start
        out[0] = capture_field(pb)
        for screen, x, y in ROUTE:
            cross_to(pb, screen, x, y)
            if screen not in out:
                out[screen] = capture_field(pb)
    finally:
        pb.stop(save=False)
    return out


def atlas(fields, idx):
    gap = 4
    im = Image.new("RGB", (6 * 248 + 5 * gap, 6 * 248 + 5 * gap), (20, 20, 20))
    d = ImageDraw.Draw(im)
    for scr, f in fields.items():
        r, c = divmod(scr, 6)
        im.paste(f[idx], (c * (248 + gap), r * (248 + gap)))
        d.text((c * (248 + gap) + 3, r * (248 + gap) + 3), f"{scr:02d}",
               fill=(255, 255, 255))
    return im


def main():
    out = Path(sys.argv[1])
    bosses = int(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for s in sys.argv[3:]:
        seed = int(s, 16)
        fields = run(seed, bosses)
        name = f"riftwild-{seed:08x}-b{bosses}"
        atlas(fields, 0).save(out / f"{name}.png")
        atlas(fields, 1).save(out / f"{name}-entities.png")
        (out / f"{name}.json").write_text(json.dumps(
            {str(k): v[2] for k, v in fields.items()}))
        print("wrote", out / f"{name}.png", len(fields))


if __name__ == "__main__":
    main()
