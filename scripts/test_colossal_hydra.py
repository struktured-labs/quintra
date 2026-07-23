#!/usr/bin/env python3
"""Live-ROM contract for Bloodmoon's three-headed BG coil and OBJ core."""
from pathlib import Path

from test_boss_identity import PL, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
BODY_MIN, BODY_MAX = 55, 63
EYE_TILE, MAW_TILE = 59, 62
FRAME = addr("_loop_frame_counter")


def body_tiles(pb):
    tiles = list(pb.memory[TM:TM + 20 * 17])
    return [(i % 20, i // 20, tile) for i, tile in enumerate(tiles)
            if BODY_MIN <= tile <= BODY_MAX]


def position(pb, entity):
    return (pb.memory[entity + 3] | pb.memory[entity + 4] << 8,
            pb.memory[entity + 7] | pb.memory[entity + 8] << 8)


def head_art(frame):
    pb, _ = enter_boss(7, keep_open=True)
    put16(pb, FRAME, frame)
    # room_draw observes the counter before loop.c advances it; cross the
    # next 16-frame upload boundary, then allow VRAM writes to settle.
    for _ in range(4):
        pb.tick()
    lcdc = pb.memory[0xFF40]
    pb.memory[0xFF40] &= 0x7F
    pb.memory[0xFF4F] = 0
    base = 0x8000 if lcdc & 0x10 else 0x9000
    side = bytes(pb.memory[base + EYE_TILE * 16:base + (EYE_TILE + 1) * 16])
    centre = bytes(pb.memory[base + MAW_TILE * 16:base + (MAW_TILE + 1) * 16])
    pb.stop(save=False)
    return side, centre


def main():
    pb, boss = enter_boss(7, keep_open=True)
    body = body_tiles(pb)
    xs = [x for x, _, _ in body]
    ys = [y for _, y, _ in body]
    assert len(body) == 100, f"Hydra coil drifted: {len(body)} tiles"
    assert (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1) == (14, 8), (
        f"Hydra lost its 112x64 footprint: x={min(xs)}..{max(xs)} "
        f"y={min(ys)}..{max(ys)}")
    tiles = list(pb.memory[TM:TM + 20 * 17])
    assert tiles[4 * 20 + 6] == EYE_TILE
    assert tiles[4 * 20 + 9] == MAW_TILE
    assert tiles[4 * 20 + 13] == EYE_TILE, "Hydra lost its three head anchors"

    # Projection remains walkable; only the original 32x32 mobile core can
    # receive attacks or deal contact damage.
    put16(pb, PL + 9, 24)
    put16(pb, PL + 11, 72)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    assert pb.memory[PL + 9] > before_x, "Hydra projection became collision"

    # The weak point retains the stage's slower broad bounce instead of being
    # pinned to decorative art.
    before = position(pb, boss)
    pb.memory[boss + 16] = 4
    after = before
    for _ in range(8):
        pb.tick()
        after = position(pb, boss)
        if after != before:
            break
    assert after != before, f"Hydra core stopped weaving: {before}->{after}"

    # The late boss should feel like a moving Penta-scale arena without
    # scrolling far enough to change any room-space collision decision.
    scroll = []
    for _ in range(160):
        pb.tick()
        scroll.append((pb.memory[0xFF43], pb.memory[0xFF42]))
    assert min(x for x, _ in scroll) == 0 and max(x for x, _ in scroll) == 3, (
        f"Hydra camera weave drifted: {set(scroll)}")
    assert {y for _, y in scroll} == {0}, f"Hydra camera tilted: {set(scroll)}"

    screenshot = ROOT / "tmp" / "hydra-colossal-arena.png"
    pb.screen.image.save(screenshot)
    pb.stop(save=False)

    side_open, centre_closed = head_art(0x0E)
    side_closed, centre_open = head_art(0x1E)
    assert side_open != side_closed, "Hydra heads did not animate"
    assert side_open == centre_open and centre_closed == side_closed, (
        "Hydra side/centre heads did not exchange breath posture")

    print(f"[colossal-hydra] PASS {len(body)} BG tiles, 112x64 three-head "
          f"coil, moving core {before}->{after}, 0..3px arena weave, "
          f"alternating heads, walkable")


if __name__ == "__main__":
    main()
