#!/usr/bin/env python3
"""Live-ROM contract for Bloodmoon's moving core, without a painted coil."""
from pathlib import Path

from test_boss_identity import PL, addr, enter_boss, projection_cells, put16


ROOT = Path(__file__).resolve().parent.parent
EYE_TILE, MAW_TILE = 59, 62
FRAME = addr("_loop_frame_counter")
CAMERA_X = addr("_room_camera_x")


def position(pb, entity):
    return (pb.memory[entity + 3] | pb.memory[entity + 4] << 8,
            pb.memory[entity + 7] | pb.memory[entity + 8] << 8)


def head_art(frame):
    pb, _ = enter_boss(7, keep_open=True)
    put16(pb, FRAME, frame)
    # The counter advances only after the banked VRAM upload returns.
    target = frame + 3
    for _ in range(30):
        pb.tick()
        current = pb.memory[FRAME] | pb.memory[FRAME + 1] << 8
        if current >= target:
            break
    else:
        raise AssertionError("Hydra tile upload did not return")
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
    assert projection_cells(pb) == 0, "Hydra still paints a detached coil mural"

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

    # The late boss now occupies a Penta-scale field with a real eastern
    # chamber, while vertical camera space remains locked to the HUD.
    put16(pb, PL + 9, 200)
    scroll = []
    for _ in range(80):
        pb.tick()
        scroll.append((pb.memory[0xFF43], pb.memory[0xFF42]))
    assert pb.memory[CAMERA_X] == 64 and 61 <= scroll[-1][0] <= 67, (
        f"Hydra field did not reach its eastern camera: "
        f"camera={pb.memory[CAMERA_X]} SCX={scroll[-1][0]}")
    assert {y for _, y in scroll} == {0}, f"Hydra camera tilted: {set(scroll)}"

    screenshot = ROOT / "tmp" / "hydra-colossal-arena.png"
    pb.screen.image.save(screenshot)
    pb.stop(save=False)

    side_a, centre_a = head_art(0x0E)
    side_b, centre_b = head_art(0x1E)
    assert side_a == side_b and centre_a == centre_b, (
        "Retired hydra mural swapped head tiles")
    assert side_a != centre_a and any(side_a) and any(centre_a), (
        "Hydra BG atlas lost its distinct head tiles")

    print(f"[colossal-hydra] PASS no mural, moving core {before}->{after}, "
          f"camera 0..64, static atlas, walkable")


if __name__ == "__main__":
    main()
