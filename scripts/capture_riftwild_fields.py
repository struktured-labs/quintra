#!/usr/bin/env python3
"""Full-field Riftwild captures: 36 fields stitched from 4 camera corners.

usage: python scripts/capture_riftwild_fields.py OUTDIR  (headless PyBoy)
Writes OUTDIR/fields/field_NN.png (248x248), OUTDIR/map.png (6x6 atlas)
and OUTDIR/pieces.json (set-piece id/anchor per field)."""
import sys, json, os
sys.path.insert(0, "scripts")
from pathlib import Path
from PIL import Image
import test_riftwild_landmarks as L
from test_overworld import PL, RS, EN, CAMERA_X, CAMERA_Y, put16, addr

out = Path(sys.argv[1]); (out / "fields").mkdir(parents=True, exist_ok=True)
try:
    sym = {k: addr(v) for k, v in (("id", "_riftwild_setpiece_id"),
           ("x", "_riftwild_setpiece_x"), ("y", "_riftwild_setpiece_y"))}
except Exception:
    sym = None

def calm(pb):
    for slot in range(32):
        b = EN + slot * 28
        pb.memory[b] = pb.memory[b + 1] = 0
    pb.memory[PL + 2] = pb.memory[PL + 1]
    pb.memory[PL + 15] = 120

def spot(wide, xs, ys):
    for y in ys:
        for x in xs:
            if all(wide[ty][tx] in L.WALKABLE for ty in (y, y + 1) for tx in (x, x + 1)):
                return x * 8 + 4, y * 8 + 4
    return None

def field_image(pb):
    wide = L.wide_tiles(pb)
    canvas = Image.new("RGB", (248, 248), (0, 0, 0))
    lo, hi = tuple(range(2, 10)), tuple(range(28, 21, -1))
    corners = ((lo, lo), (hi, lo), (lo, hi), (hi, hi))
    for xs, ys in corners:
        p = spot(wide, xs, ys)
        if not p:
            continue
        put16(pb, PL + 9, p[0]); put16(pb, PL + 11, p[1])
        for _ in range(70):
            calm(pb); pb.tick()
        cx, cy = pb.memory[CAMERA_X], pb.memory[CAMERA_Y]
        canvas.paste(pb.screen.image.convert("RGB").crop((0, 0, 160, 136)), (cx, cy))
    return canvas

pb = L.boot_world()
meta = {}
try:
    for _ in range(150):
        calm(pb); pb.tick()
    def snap(screen):
        if screen in meta:
            return
        img = field_image(pb)
        img.save(out / "fields" / f"field_{screen:02d}.png")
        meta[screen] = ({k: pb.memory[a] for k, a in sym.items()} if sym else {})
    snap(0)
    for screen, x, y in L.ROUTE:
        calm(pb)
        L.cross_to(pb, screen, x, y)
        for _ in range(150):
            calm(pb); pb.tick()
        snap(screen)
finally:
    pb.stop(save=False)
atlas = Image.new("RGB", (6 * 250, 6 * 250), (16, 16, 16))
for s in range(36):
    f = out / "fields" / f"field_{s:02d}.png"
    if f.exists():
        atlas.paste(Image.open(f), ((s % 6) * 250 + 1, (s // 6) * 250 + 1))
atlas.save(out / "map.png")
json.dump(meta, open(out / "pieces.json", "w"))
print("captured", len(meta))
