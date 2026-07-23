#!/usr/bin/env python3
"""Live-ROM contract for Golden Temple's monumental idol and OBJ heart."""
from pathlib import Path

from test_boss_identity import PL, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
BODY_MIN, BODY_MAX = 55, 63
EYE_TILE, RUNE_TILE = 59, 61
FRAME = addr("_loop_frame_counter")


def body_tiles(pb):
    tiles = list(pb.memory[TM:TM + 20 * 17])
    return [(i % 20, i // 20, tile) for i, tile in enumerate(tiles)
            if BODY_MIN <= tile <= BODY_MAX]


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
    body = body_tiles(pb)
    xs = [x for x, _, _ in body]
    ys = [y for _, y, _ in body]
    assert len(body) == 106, f"Golden Golem idol drifted: {len(body)} tiles"
    assert (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1) == (14, 9), (
        f"Golem lost its 112x72 footprint: x={min(xs)}..{max(xs)} "
        f"y={min(ys)}..{max(ys)}")
    tiles = list(pb.memory[TM:TM + 20 * 17])
    assert tiles[5 * 20 + 6] == EYE_TILE
    assert tiles[5 * 20 + 13] == EYE_TILE, "Golem lost its paired idol eyes"
    assert tiles[6 * 20 + 7] == RUNE_TILE
    assert tiles[6 * 20 + 12] == RUNE_TILE, "Golem lost its paired sun seals"
    assert all(not BODY_MIN <= tiles[11 * 20 + x] <= BODY_MAX
               for x in (9, 10)), "Golem lost its split stone feet"

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
    assert awake_eye != sleeping_eye and bright_rune != dim_rune, (
        "Golem stopped alternating stone sleep and sun-rune wake")
    print(f"[colossal-golem] PASS {len(body)} BG tiles, 112x72 temple idol, "
          f"moving heart {before}->{after}, animated sun seals, walkable")


if __name__ == "__main__":
    main()
