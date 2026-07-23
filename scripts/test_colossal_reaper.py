#!/usr/bin/env python3
"""Live-ROM contract for Shadow Keep's spectral cloak and mobile weak point."""
from pathlib import Path

from test_boss_identity import PL, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
BODY_MIN, BODY_MAX = 55, 63
VOID_TILE, EYE_TILE = 55, 59
FRAME = addr("_loop_frame_counter")


def body_tiles(pb):
    tiles = list(pb.memory[TM:TM + 20 * 17])
    return [(i % 20, i // 20, tile) for i, tile in enumerate(tiles)
            if BODY_MIN <= tile <= BODY_MAX]


def position(pb, entity):
    return pb.memory[entity + 3], pb.memory[entity + 7]


def phase_art(frame):
    pb, _ = enter_boss(5, keep_open=True)
    put16(pb, FRAME, frame)
    for _ in range(4):
        pb.tick()
    lcdc = pb.memory[0xFF40]
    pb.memory[0xFF40] = lcdc & 0x7F
    pb.memory[0xFF4F] = 0
    base = 0x8000 if lcdc & 0x10 else 0x9000
    void = bytes(pb.memory[base + VOID_TILE * 16:base + (VOID_TILE + 1) * 16])
    eye = bytes(pb.memory[base + EYE_TILE * 16:base + (EYE_TILE + 1) * 16])
    pb.stop(save=False)
    return void, eye


def main():
    pb, boss = enter_boss(5, keep_open=True)
    body = body_tiles(pb)
    xs = [x for x, _, _ in body]
    ys = [y for _, y, _ in body]
    assert len(body) == 96, f"Dusk Reaper cloak drifted: {len(body)} tiles"
    assert (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1) == (14, 8), (
        f"Reaper lost its 112x64 footprint: x={min(xs)}..{max(xs)} "
        f"y={min(ys)}..{max(ys)}")
    tiles = list(pb.memory[TM:TM + 20 * 17])
    assert all(not BODY_MIN <= tiles[11 * 20 + x] <= BODY_MAX
               for x in (6, 8, 11, 13)), "Reaper lost its tattered hem"

    put16(pb, PL + 9, 24)
    put16(pb, PL + 11, 72)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    assert pb.memory[PL + 9] > before_x, "Reaper projection became collision"

    # Force the existing hunt countdown through its warned flank re-entry.
    # The mobile OBJ weak point, not the huge robe, remains the actual target.
    put16(pb, PL + 9, 80)
    put16(pb, PL + 11, 72)
    before = position(pb, boss)
    pb.memory[boss + 10] = 1
    for _ in range(4):
        pb.tick()
    after = position(pb, boss)
    leap = abs(after[0] - before[0]) + abs(after[1] - before[1])
    assert leap >= 20, f"Reaper weak point stopped re-entering: {before}->{after}"

    screenshot = ROOT / "tmp" / "reaper-colossal-arena.png"
    pb.screen.image.save(screenshot)
    pb.stop(save=False)

    solid_void, open_eye = phase_art(0x0E)
    phased_void, closed_eye = phase_art(0x2E)
    assert solid_void != phased_void and open_eye != closed_eye, (
        "Reaper cloak stopped phasing")
    print(f"[colossal-reaper] PASS {len(body)} BG tiles, 112x64 tattered "
          f"cloak, weak-point re-entry {leap}px, animated phase, walkable")


if __name__ == "__main__":
    main()
