#!/usr/bin/env python3
"""Live-ROM contract for Frost's hollow web-spider and blinking weak point."""
from pathlib import Path

from test_boss_identity import PL, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
BODY_MIN, BODY_MAX = 55, 63
EYE_TILE, WEB_TILE = 59, 61
FRAME = addr("_loop_frame_counter")


def body_tiles(pb):
    tiles = list(pb.memory[TM:TM + 20 * 17])
    return [(i % 20, i // 20, tile) for i, tile in enumerate(tiles)
            if BODY_MIN <= tile <= BODY_MAX]


def position(pb, entity):
    return (pb.memory[entity + 3], pb.memory[entity + 7])


def pulse_art(frame):
    pb, _ = enter_boss(3, keep_open=True)
    put16(pb, FRAME, frame)
    for _ in range(4):
        pb.tick()
    lcdc = pb.memory[0xFF40]
    pb.memory[0xFF40] = lcdc & 0x7F
    pb.memory[0xFF4F] = 0
    base = 0x8000 if lcdc & 0x10 else 0x9000
    eye = bytes(pb.memory[base + EYE_TILE * 16:base + (EYE_TILE + 1) * 16])
    web = bytes(pb.memory[base + WEB_TILE * 16:base + (WEB_TILE + 1) * 16])
    pb.stop(save=False)
    return eye, web


def main():
    pb, boss = enter_boss(3, keep_open=True)
    body = body_tiles(pb)
    xs = [x for x, _, _ in body]
    ys = [y for _, y, _ in body]
    assert len(body) == 94, f"Frost web-spider drifted: {len(body)} tiles"
    assert (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1) == (14, 8), (
        f"Spider lost its 112x64 footprint: x={min(xs)}..{max(xs)} "
        f"y={min(ys)}..{max(ys)}")
    tiles = list(pb.memory[TM:TM + 20 * 17])
    assert all(not BODY_MIN <= tiles[7 * 20 + x] <= BODY_MAX
               for x in range(8, 12)), "Spider lost its hollow web cavity"
    assert all(not BODY_MIN <= tiles[9 * 20 + x] <= BODY_MAX
               for x in range(9, 11)), "Spider lost its lower web opening"

    put16(pb, PL + 9, 24)
    put16(pb, PL + 11, 72)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    # Finish the input transaction before placing the hero for the warp.
    # PyBoy can expose a nested VBlank before the release frame commits.
    for _ in range(2):
        pb.tick()
    assert pb.memory[PL + 9] > before_x, "Spider projection became collision"

    # The old telegraph/warp remains the actual target movement: the huge web
    # does not pin or duplicate the vulnerable core.
    put16(pb, PL + 9, 80)
    put16(pb, PL + 11, 72)
    before = position(pb, boss)
    pb.memory[boss + 10] = 1
    for _ in range(4):
        pb.tick()
    after = position(pb, boss)
    leap = abs(after[0] - before[0]) + abs(after[1] - before[1])
    assert leap >= 20, f"Spider weak point stopped blinking: {before}->{after}"

    screenshot = ROOT / "tmp" / "spider-colossal-arena.png"
    pb.screen.image.save(screenshot)
    pb.stop(save=False)

    open_eye, open_web = pulse_art(0x0E)
    closed_eye, charged_web = pulse_art(0x2E)
    assert open_eye != closed_eye and open_web != charged_web, (
        "Spider eyes/web stopped pulsing")
    print(f"[colossal-spider] PASS {len(body)} BG tiles, 112x64 hollow "
          f"web-spider, weak-point blink {leap}px, animated charge, walkable")


if __name__ == "__main__":
    main()
