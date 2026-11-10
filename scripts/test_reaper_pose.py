#!/usr/bin/env python3
"""Reaper rests, raises, and extends a crescent without changing the windows."""
from pathlib import Path

from test_boss_identity import enter_boss, put16

ART = Path("/opt/cursor/artifacts")


def body(pb):
    tiles = []
    for i in range(4, 40):
        base = 0xFE00 + i * 4
        y, x, tile, _prop = (pb.memory[base + k] for k in range(4))
        if y and x and 40 <= tile <= 55:
            tiles.append(tile)
    return tiles


def vram(pb):
    pb.memory[0xFF40] &= 0x7F
    pb.memory[0xFF4F] = 0
    raw = bytes(pb.memory[0x8000 + 40 * 16:0x8000 + 56 * 16])
    pb.memory[0xFF40] |= 0x80
    return raw


def on_screen(pb):
    image = pb.screen.image.convert("RGB")
    count = 0
    for y in range(0, image.height, 2):
        for x in range(0, image.width, 2):
            if image.getpixel((x, y)) in ((104, 88, 160), (80, 24, 120)):
                count += 1
    return count > 10


def park(pb, boss):
    put16(pb, boss + 3, 88 << 8)
    put16(pb, boss + 7, 48 << 8)
    # OAM leads the picture by a frame, and one of those frames is white.
    # Wait until the cloak is actually in the framebuffer.
    for _ in range(10):
        pb.tick(1, render=True, sound=False)
        if on_screen(pb):
            return
    raise AssertionError("reaper body did not stay on screen")


def show(pb, boss, clock):
    pb.memory[boss + 14] = 1
    pb.memory[boss + 2] = 3
    pb.memory[boss + 5] = 0
    pb.memory[boss + 6] = clock
    for _ in range(3):
        pb.tick(1, render=True, sound=False)
    park(pb, boss)
    shot = pb.screen.image.convert("RGB").copy()
    return shot, vram(pb)


def main():
    pb, boss = enter_boss(5, keep_open=True)
    ART.mkdir(parents=True, exist_ok=True)
    park(pb, boss)
    pb.screen.image.convert("RGB").save(ART / "reaper-after-rest.png")
    rested = vram(pb)

    shot, raised = show(pb, boss, 100)
    assert raised != rested, "the raise window did not change the picture"
    shot.save(ART / "reaper-after-raise.png")

    shot, linked = show(pb, boss, 160)
    assert linked != rested and linked != raised, "the link window did not change the picture"
    shot.save(ART / "reaper-after-link.png")
    pb.stop(save=False)
    print("reaper poses ok")


if __name__ == "__main__":
    main()
