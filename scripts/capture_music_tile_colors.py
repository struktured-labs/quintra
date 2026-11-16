#!/usr/bin/env python3
"""Capture before/after screenshots of a rune-sequence room.

Usage:
  python3 scripts/capture_music_tile_colors.py OUT_DIR
  python3 scripts/capture_music_tile_colors.py OUT_DIR --before ROM
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

if len(sys.argv) > 3 and sys.argv[2] == "--before":
    os.environ.setdefault("QUINTRA_ROM", str(Path(sys.argv[3]).resolve()))

import test_puzzles as puzzles  # noqa: E402


def scale(img):
    return img.convert("RGB").resize((480, 432), 0)


def snap(pb, out, name):
    out.mkdir(parents=True, exist_ok=True)
    scale(pb.screen.image).save(out / f"{name}.png")


def capture_four_note(prefix, out):
    pb = puzzles.load(2)
    # Let arrival labels and palettes settle.
    for _ in range(60):
        pb.tick()
    snap(pb, out, f"{prefix}stage2-trial-idle")
    runes = puzzles.find_rune_plates(pb) if hasattr(puzzles, "find_rune_plates") else [
        (x, y) for y in range(1, 16) for x in range(1, 19)
        if pb.memory[puzzles.TM + y * 20 + x] == 33
    ]
    frames = [scale(pb.screen.image.copy())]
    if runes:
        puzzles.feet_on(pb, *runes[0])
        for _ in range(16):
            frames.append(scale(pb.screen.image.copy()))
            pb.tick()
        snap(pb, out, f"{prefix}stage2-trial-voiced")
    frames[0].save(out / f"{prefix}stage2-trial-voice.gif",
                   save_all=True, append_images=frames[1:],
                   duration=80, loop=0)
    pb.stop(save=False)


def capture_three_note(prefix, out):
    if not hasattr(puzzles, "load_rune_room"):
        return
    pb, _ = puzzles.load_rune_room(0, "waystone")
    for _ in range(60):
        pb.tick()
    snap(pb, out, f"{prefix}stage1-waystone-idle")
    pb.stop(save=False)


def main():
    out = Path(sys.argv[1])
    prefix = "before_" if (len(sys.argv) > 3 and sys.argv[2] == "--before") else "after_"
    if prefix == "before_":
        rom = Path(sys.argv[3]).resolve()
        puzzles.ROM = rom
        # NOI must sit beside the ROM for symbol lookup.
    capture_four_note(prefix, out)
    if prefix == "after_":
        capture_three_note(prefix, out)


if __name__ == "__main__":
    main()
