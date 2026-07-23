#!/usr/bin/env python3
"""Live-ROM contract for Ember Depths' furnace-beast projection and core."""
from pathlib import Path

from test_boss_identity import PL, TM, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
BODY_MIN, BODY_MAX = 55, 63
EYE_TILE, MAW_TILE = 59, 62


def body_tiles(pb):
    tiles = list(pb.memory[TM:TM + 20 * 17])
    return [(i % 20, i // 20, tile) for i, tile in enumerate(tiles)
            if BODY_MIN <= tile <= BODY_MAX]


def footprint(body):
    xs = [x for x, _, _ in body]
    ys = [y for _, y, _ in body]
    return max(xs) - min(xs) + 1, max(ys) - min(ys) + 1


def projection_art(state):
    pb, boss = enter_boss(2, keep_open=True)
    pb.memory[boss + 15] = state
    pb.memory[boss + 10] = 10
    for _ in range(3):
        pb.tick()
    lcdc = pb.memory[0xFF40]
    pb.memory[0xFF40] = lcdc & 0x7F
    pb.memory[0xFF4F] = 0
    base = 0x8000 if lcdc & 0x10 else 0x9000
    eye = bytes(pb.memory[base + EYE_TILE * 16:base + (EYE_TILE + 1) * 16])
    maw = bytes(pb.memory[base + MAW_TILE * 16:base + (MAW_TILE + 1) * 16])
    pb.stop(save=False)
    return eye, maw


def position(pb, entity):
    return (pb.memory[entity + 3] | pb.memory[entity + 4] << 8,
            pb.memory[entity + 7] | pb.memory[entity + 8] << 8)


def main():
    pb, boss = enter_boss(2, keep_open=True)
    body = body_tiles(pb)
    assert len(body) == 96, f"Cinder furnace body drifted: {len(body)} tiles"
    assert footprint(body) == (14, 8), (
        f"Cinder lost its 112x64 footprint: {footprint(body)}")

    tiles = list(pb.memory[TM:TM + 20 * 17])
    assert tiles[6 * 20 + 6] == EYE_TILE
    assert tiles[6 * 20 + 13] == EYE_TILE, "Cinder lost its paired eye sockets"
    assert tiles[7 * 20 + 8] == MAW_TILE
    assert tiles[7 * 20 + 11] == MAW_TILE, "Cinder lost its four-tile maw"

    # The projected shoulders and jaw are spectacle, not invisible collision.
    put16(pb, PL + 9, 24)
    put16(pb, PL + 11, 72)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    # Complete the controller-release transaction before debugger-style
    # placement below. A PyBoy tick can return at a nested VBlank while the
    # current movement update still owns its pre-release position.
    for _ in range(2):
        pb.tick()
    assert pb.memory[PL + 9] > before_x, "Cinder projection became collision"

    # Force the existing wind-up over its boundary and prove that the same
    # vulnerable OBJ core still performs the authored hard lunge.
    put16(pb, PL + 9, 128)
    put16(pb, PL + 11, 64)
    put16(pb, boss + 3, 64)
    put16(pb, boss + 7, 64)
    pb.memory[boss + 15] = 0
    pb.memory[boss + 10] = 1
    before = position(pb, boss)
    after = before
    for _ in range(8):
        pb.tick()
        after = position(pb, boss)
        if after != before:
            break
    assert after[0] > before[0], f"Cinder core stopped lunging: {before}->{after}"

    screenshot = ROOT / "tmp" / "cinder-colossal-arena.png"
    pb.screen.image.save(screenshot)
    pb.stop(save=False)

    open_eye, open_maw = projection_art(0)
    closed_eye, closed_maw = projection_art(2)
    assert open_eye != closed_eye and open_maw != closed_maw, (
        "Cinder furnace face did not clench during recovery")

    print(f"[colossal-cinder] PASS {len(body)} BG tiles, 112x64 furnace "
          f"body, core lunge {before}->{after}, animated recovery, walkable")


if __name__ == "__main__":
    main()
