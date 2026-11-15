#!/usr/bin/env python3
"""Headless Riftwild atlas: walk all 36 fields for a seed, stitch 248x248 each.

Run from the repo root after `make`:
  python3 docs/superpowers/specs/assets/riftwild-wonder/capture_riftwild_atlas.py \
      0 BOSSES SEED [SEED...]
BOSSES is bosses_beaten (1 = first Riftwild, 4 = region 2). Suffix a seed with
"h" for the Worldglass Hollow counterpart. The first argument is unused (kept
for compatibility with the earlier screenshot-stitching variant).
Never opens a window (PyBoy window="null"). Writes tmp/riftwild-atlas/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageDraw  # noqa: E402
from pyboy import PyBoy  # noqa: E402
from test_overworld import (  # noqa: E402
    CAMERA_X, CAMERA_Y, EN, LARGE, PL, ROM, RS, TM,
    WORLD_H, WORLD_W, exit_at, put16)
from quintra_topology import STAGE_BOSS_ROOM  # noqa: E402
from vram_render import field_from_wram  # noqa: E402
from test_riftwild_landmarks import ROUTE, wide_tiles  # noqa: E402

OUT = Path("tmp/riftwild-atlas")


def keep_alive(pb):
    pb.memory[PL + 2] = pb.memory[PL + 1]
    pb.memory[PL + 15] = 120


def clear_entities(pb):
    for slot in range(32):
        b = EN + slot * 28
        if pb.memory[b] == 2:
            pb.memory[b] = pb.memory[b + 1] = 0


def boot(seed, bosses=1):
    pb = PyBoy(str(ROM), window="null", cgb=True, sound_emulated=False)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()
    for i in range(4):
        pb.memory[RS + 2 + i] = (seed >> (8 * i)) & 255
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[bosses - 1]
    pb.memory[RS + 11] = bosses
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    pb.memory[TM + 16 * 20 + 9] = 3
    pb.memory[TM + 16 * 20 + 10] = 3
    exit_at(pb, 72, 120)
    return pb


def entities(pb):
    out = []
    for slot in range(32):
        b = EN + slot * 28
        t = pb.memory[b]
        if t in (2, 3):
            out.append({"type": t,
                        "x": pb.memory[b + 3] | pb.memory[b + 4] << 8,
                        "y": pb.memory[b + 7] | pb.memory[b + 8] << 8,
                        "kind": pb.memory[b + 17],
                        "tile": pb.memory[b + 12]})
    return out


KIND = {3: "I", 11: "S", 16: "R", 21: "W", 22: "G", 24: "?", 25: "H",
        19: "F", 0: "h", 1: "c", 2: "c", 6: "m"}


def capture_field(pb, hud_top):
    for _ in range(40):
        keep_alive(pb)
        pb.tick()
    wide = wide_tiles(pb)
    ents = entities(pb)
    field = field_from_wram(pb, wide)
    d = ImageDraw.Draw(field)
    for e in ents:
        x, y = e["x"], e["y"]
        if e["type"] == 2:
            d.rectangle((x + 3, y + 3, x + 12, y + 12), outline=(255, 40, 40))
        else:
            k = KIND.get(e["kind"], "p")
            d.rectangle((x + 1, y + 1, x + 14, y + 14), outline=(255, 230, 0))
            d.text((x + 5, y + 3), k, fill=(255, 255, 0))
    return field, {"tiles": wide, "entities": ents}


def cross_to(pb, target, x, y):
    clear_entities(pb)
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    for _ in range(200):
        keep_alive(pb)
        pb.tick()
        if pb.memory[RS + 18] == target and pb.memory[0xFF40] & 0x02:
            break
    for _ in range(30):
        keep_alive(pb)
        pb.tick()
    assert pb.memory[RS + 18] == target, (target, pb.memory[RS + 18])


def run(seed, bosses, hud_top, hollow=False):
    pb = boot(seed, bosses)
    fields, tiles = {}, {}
    try:
        start = pb.memory[RS + 18]
        if hollow:
            # Debug fixture for the Worldglass counterpart: every later field
            # generation reads riftwild_shadow bit 0 (run_state offset 57).
            pb.memory[RS + 57] |= 1
        else:
            fields[start], tiles[start] = capture_field(pb, hud_top)
        # Route in test_riftwild_landmarks starts from cell 0.
        if start != 0:
            raise SystemExit(f"unexpected start {start}")
        for screen, x, y in ROUTE:
            cross_to(pb, screen, x, y)
            if screen not in fields:
                fields[screen], tiles[screen] = capture_field(pb, hud_top)
    finally:
        pb.stop(save=False)
    return fields, tiles


def main():
    hud_top = int(sys.argv[1])
    bosses = int(sys.argv[2])
    OUT.mkdir(parents=True, exist_ok=True)
    import json
    for s in sys.argv[3:]:
        hollow = s.endswith("h")
        seed = int(s.rstrip("h"), 0)
        fields, tiles = run(seed, bosses, hud_top, hollow)
        gap = 4
        atlas = Image.new("RGB", (6 * 248 + 5 * gap, 6 * 248 + 5 * gap),
                          (20, 20, 20))
        d = ImageDraw.Draw(atlas)
        for scr, img in fields.items():
            r, c = divmod(scr, 6)
            atlas.paste(img, (c * (248 + gap), r * (248 + gap)))
            d.text((c * (248 + gap) + 3, r * (248 + gap) + 3),
                   f"{scr:02d}", fill=(255, 255, 255))
        name = (f"riftwild-seed-{seed:08x}-b{bosses}"
                + ("-hollow" if hollow else ""))
        atlas.save(OUT / f"{name}.png")
        (OUT / f"{name}.json").write_text(json.dumps(
            {str(k): v for k, v in tiles.items()}))
        print("wrote", OUT / f"{name}.png", len(fields))


if __name__ == "__main__":
    main()
