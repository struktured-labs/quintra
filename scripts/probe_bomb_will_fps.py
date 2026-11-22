#!/usr/bin/env python3
"""Max-tier bomb in a 16-crawler room: 180-frame loop_frame count."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if (ROOT / "scripts").is_dir():
    sys.path.insert(0, str(ROOT / "scripts"))
    REPO = ROOT
else:
    sys.path.insert(0, str(ROOT))
    REPO = ROOT.parent

# Reuse the official performance helpers.
sys.path.insert(0, str(REPO / "scripts"))
from test_performance import (  # noqa: E402
    boot_room, make_fixed_crawlers, loop_frames, PL, EN,
)
from test_will_max import PLAYER as P, put16  # noqa: E402
from test_will_b_weapons import set_will, fire_b  # noqa: E402

ITEM_BOMBS = 48


def main():
    pb = boot_room()
    make_fixed_crawlers(pb)
    pb.memory[P + 24] = ITEM_BOMBS
    pb.memory[P + 18] = ITEM_BOMBS
    pb.memory[P + 19] = 0
    pb.memory[P + 13] = 1
    put16(pb, P + 9, 80)
    put16(pb, P + 11, 72)
    pb.memory[P + 1] = 20
    pb.memory[P + 2] = 20
    pb.memory[P + 3] = 16
    pb.memory[P + 4] = 16
    pb.memory[P + 15] = 200
    set_will(pb, 1, 90, 0)
    pb.tick(2)
    fire_b(pb)
    before = loop_frames(pb)
    pb.tick(180)
    loops = (loop_frames(pb) - before) & 0xFFFF
    active = sum(1 for i in range(32) if pb.memory[EN + i * 28] and (pb.memory[EN + i * 28 + 1] & 1))
    print(f"[bomb will fps] max-blast + 16 crawlers: {loops}/180 loop frames, live={active}", flush=True)
    # Same dense-room floor as test_performance.py; do not ship a drop below it.
    assert loops >= 135, f"max-tier bomb in dense room dropped frames: {loops}/180"
    pb.stop(save=False)


if __name__ == "__main__":
    main()
