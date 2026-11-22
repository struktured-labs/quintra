#!/usr/bin/env python3
"""Headless before/after-style Will-tier bomb blast previews (4x PNG + GIF)."""
import os
import sys
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent
if (ROOT / "scripts").is_dir():
    sys.path.insert(0, str(ROOT / "scripts"))
    OUT = Path(os.environ.get("BOMB_PREVIEW_DIR", "/workspace/quintra-bweapons"))
else:
    sys.path.insert(0, str(ROOT))
    OUT = Path(os.environ.get("BOMB_PREVIEW_DIR", "/workspace/quintra-bweapons"))
    ROOT = ROOT.parent

from test_will_max import (  # noqa: E402
    PLAYER as P, TILEMAP as T, boot, clear_arena, put16, addr,
)
from test_will_b_weapons import set_will, fire_b  # noqa: E402

ITEM_BOMBS = 48
BGT_FLOOR = 1
WILL = {
    0: ("tier0-empty", 0, 0, 0),
    1: ("tier1-one-third", 0, 45, 0),
    2: ("tier2-banked-cap4", 1, 0, 7),
    3: ("tier3-full-cap1", 1, 90, 0),
}


def scale4(img):
    return img.resize((img.width * 4, img.height * 4), Image.NEAREST)


def scene():
    pb = boot(0)
    clear_arena(pb)
    pb.memory[addr("_entity_enemy_count")] = 0
    pb.memory[P + 24] = ITEM_BOMBS
    pb.memory[P + 18] = ITEM_BOMBS
    pb.memory[P + 19] = 0
    pb.memory[P + 13] = 1
    put16(pb, P + 9, 80)
    pb.memory[P + 15] = 200
    put16(pb, P + 11, 72)
    pb.memory[P + 1] = 20
    pb.memory[P + 2] = 20
    pb.memory[P + 3] = 16
    pb.memory[P + 4] = 16
    pb.memory[P + 15] = 200
    # Open floor, a few crystals to show radius.
    for ty in range(17):
        for tx in range(20):
            if pb.memory[T + ty * 20 + tx] != 1:
                pb.memory[T + ty * 20 + tx] = 1
    # Rings around a dropped bomb at tile (10,9): r=1, r=2, r=3.
    for tx, ty in ((10, 8), (11, 9), (10, 10), (9, 9), (12, 9), (10, 7), (8, 9), (10, 11), (13, 9), (10, 6), (7, 9), (10, 12)):
        pb.memory[T + ty * 20 + tx] = 22
    pb.tick(2)
    return pb


def capture_tier(tier, name, level, charge, waygear):
    pb = scene()
    set_will(pb, level, charge, waygear)
    pb.memory[P + 19] = 0
    fire_b(pb)
    frames = []
    # Fuse is 48 frames; capture the burst window plus a little hang.
    for i in range(80):
        pb.tick(1)
        if 40 <= i <= 72 and (i % 2 == 0):
            frames.append(scale4(pb.screen.image.copy()))
    # Best still: the captured frame with the most unique colors (peak FX).
    def uniq(im):
        return len(set(im.getdata()))
    still = max(frames, key=uniq) if frames else None
    OUT.mkdir(parents=True, exist_ok=True)
    still_path = OUT / f"bomb-{name}-4x.png"
    gif_path = OUT / f"bomb-{name}.gif"
    still.save(still_path)
    if frames:
        frames[0].save(
            gif_path, save_all=True, append_images=frames[1:],
            duration=80, loop=0, optimize=False,
        )
    pb.stop()
    print("wrote", still_path, gif_path, "nframes", len(frames), flush=True)


def main():
    for tier, rec in WILL.items():
        capture_tier(tier, *rec)


if __name__ == "__main__":
    main()
