#!/usr/bin/env python3
"""Live-ROM contract for Frost's blink and a mural-free arena."""
from pathlib import Path

from test_boss_identity import PL, addr, enter_boss, projection_cells, put16


ROOT = Path(__file__).resolve().parent.parent
EYE_TILE, WEB_TILE = 59, 61
FRAME = addr("_loop_frame_counter")


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
    assert projection_cells(pb) == 0, "Frost still paints a detached web mural"

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
    assert open_eye == closed_eye and open_web == charged_web, (
        "Retired web mural blinked again")
    assert any(open_eye) and any(open_web), "Spider BG atlas was not uploaded"
    print(f"[colossal-spider] PASS no mural, weak-point blink {leap}px, "
          f"static atlas, walkable")


if __name__ == "__main__":
    main()
