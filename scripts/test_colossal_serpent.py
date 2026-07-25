#!/usr/bin/env python3
"""Live-ROM contract for Verdant's storm coil, moving head, and wide field."""
from pathlib import Path

from test_boss_identity import PL, TM, addr, enter_boss, put16


ROOT = Path(__file__).resolve().parent.parent
BODY_MIN, BODY_MAX = 55, 63
RUNE_TILE = 61
FRAME = addr("_loop_frame_counter")
CAMERA_X = addr("_room_camera_x")


def body_tiles(pb):
    tiles = list(pb.memory[TM:TM + 20 * 17])
    return [(i % 20, i // 20, tile) for i, tile in enumerate(tiles)
            if BODY_MIN <= tile <= BODY_MAX]


def position(pb, entity):
    return (pb.memory[entity + 3] | pb.memory[entity + 4] << 8,
            pb.memory[entity + 7] | pb.memory[entity + 8] << 8)


def rune_art(frame):
    pb, _ = enter_boss(1, keep_open=True)
    put16(pb, FRAME, frame)
    for _ in range(4):
        pb.tick()
    lcdc = pb.memory[0xFF40]
    pb.memory[0xFF40] = lcdc & 0x7F
    pb.memory[0xFF4F] = 0
    base = 0x8000 if lcdc & 0x10 else 0x9000
    art = bytes(pb.memory[base + RUNE_TILE * 16:base + (RUNE_TILE + 1) * 16])
    pb.stop(save=False)
    return art


def main():
    pb, boss = enter_boss(1, keep_open=True)
    body = body_tiles(pb)
    xs = [x for x, _, _ in body]
    ys = [y for _, y, _ in body]
    assert len(body) == 84, f"Storm Serpent coil drifted: {len(body)} tiles"
    assert (max(xs) - min(xs) + 1, max(ys) - min(ys) + 1) == (14, 8), (
        f"Serpent lost its 112x64 outer span: x={min(xs)}..{max(xs)} "
        f"y={min(ys)}..{max(ys)}")
    tiles = list(pb.memory[TM:TM + 20 * 17])
    assert not BODY_MIN <= tiles[7 * 20 + 9] <= BODY_MAX
    assert not BODY_MIN <= tiles[9 * 20 + 10] <= BODY_MAX, (
        "Serpent coil lost its hollow S-shaped waist")

    # Crossing the charged coil must remain possible; only the mobile OBJ
    # head owns the fight's vulnerable/contact body.
    put16(pb, PL + 9, 24)
    put16(pb, PL + 11, 72)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    assert pb.memory[PL + 9] > before_x, "Serpent coil became collision"

    # Preserve the established diagonal rebound head rather than pinning the
    # target to decorative art.
    put16(pb, boss + 3, 64)
    put16(pb, boss + 7, 48)
    pb.memory[boss + 15] = 3
    pb.memory[boss + 16] = 3
    before = position(pb, boss)
    for _ in range(3):
        pb.tick()
    after = position(pb, boss)
    assert after[0] > before[0] and after[1] > before[1], (
        f"Serpent head stopped rebounding: {before}->{after}")

    # Verdant now shares the true 224px Colossus field. Walk its eastern half
    # rather than testing the obsolete decorative 0..3px compact-room sway.
    put16(pb, PL + 9, 200)
    scx = []
    for _ in range(80):
        pb.tick()
        scx.append(pb.memory[0xFF43])
    assert pb.memory[CAMERA_X] == 64 and 61 <= scx[-1] <= 67, (
        f"Serpent field did not reach its eastern camera: "
        f"camera={pb.memory[CAMERA_X]} SCX={scx[-1]}")

    screenshot = ROOT / "tmp" / "serpent-colossal-arena.png"
    pb.screen.image.save(screenshot)
    pb.stop(save=False)

    assert rune_art(0x0F) != rune_art(0x2F), (
        "Serpent lightning stopped travelling through the coil")
    print(f"[colossal-serpent] PASS {len(body)} BG tiles, 112x64 hollow "
          f"coil, head bounce {before}->{after}, camera 0..64, animated charge")


if __name__ == "__main__":
    main()
