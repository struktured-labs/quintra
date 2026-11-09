#!/usr/bin/env python3
"""Live-ROM contract for Golden Temple's moving heart, without a mural."""
from pathlib import Path

from test_boss_identity import PL, addr, enter_boss, projection_cells, put16


ROOT = Path(__file__).resolve().parent.parent
EYE_TILE, RUNE_TILE = 59, 61
FRAME = addr("_loop_frame_counter")


def position(pb, entity):
    return (pb.memory[entity + 3] | pb.memory[entity + 4] << 8,
            pb.memory[entity + 7] | pb.memory[entity + 8] << 8)


def wake_art(frame):
    pb, _ = enter_boss(6, keep_open=True)
    put16(pb, FRAME, frame)
    # PyBoy may restore on either half of the cartridge's alternate-frame
    # entity cadence. Cross the upload boundary and one complete draw beat.
    for _ in range(8):
        pb.tick()
    lcdc = pb.memory[0xFF40]
    pb.memory[0xFF40] = lcdc & 0x7F
    pb.memory[0xFF4F] = 0
    base = 0x8000 if lcdc & 0x10 else 0x9000
    eye = bytes(pb.memory[base + EYE_TILE * 16:base + (EYE_TILE + 1) * 16])
    rune = bytes(pb.memory[base + RUNE_TILE * 16:base + (RUNE_TILE + 1) * 16])
    pb.stop(save=False)
    return eye, rune


def main():
    pb, boss = enter_boss(6, keep_open=True)
    assert projection_cells(pb) == 0, "Golem still paints a detached idol mural"

    # The projected stone is scenery only; the original moving 32x32 heart
    # remains the encounter's sole collision and vulnerability contract.
    put16(pb, PL + 9, 24)
    put16(pb, PL + 11, 72)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    assert pb.memory[PL + 9] > before_x, "Golem projection became collision"

    before = position(pb, boss)
    for _ in range(16):
        pb.tick()
    after = position(pb, boss)
    assert after != before, f"Golem heart stopped pursuing: {before}->{after}"

    screenshot = ROOT / "tmp" / "golem-colossal-arena.png"
    pb.screen.image.save(screenshot)
    pb.stop(save=False)

    awake_eye, bright_rune = wake_art(0x4E)
    sleeping_eye, dim_rune = wake_art(0x6E)
    assert awake_eye == sleeping_eye and bright_rune == dim_rune, (
        "Retired golem mural blinked again")
    assert awake_eye != bright_rune and any(awake_eye) and any(bright_rune), (
        "Golem BG atlas lost its distinct eye and rune")
    print(f"[colossal-golem] PASS no mural, moving heart {before}->{after}, "
          f"static atlas, walkable")


if __name__ == "__main__":
    main()
