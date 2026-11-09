#!/usr/bin/env python3
"""Live-ROM contract for Toxic Mire's pulse, without a painted body."""
from pathlib import Path

from test_boss_identity import PL, addr, enter_boss, projection_cells, put16


ROOT = Path(__file__).resolve().parent.parent
CAMERA_X = addr("_room_camera_x")


def assert_phase(pb, boss, phase):
    for _ in range(64):
        if (pb.memory[boss + 15] & 1) == phase:
            assert projection_cells(pb) == 0, (
                f"Mire phase {phase} painted a detached body")
            return
        pb.tick()
    raise AssertionError(
        f"Mire never reached phase {phase}: state={pb.memory[boss + 15]}")


def main():
    pb, boss = enter_boss(4, keep_open=True)

    # The pulse still toggles the live state bit. It no longer paints a
    # background silhouette for that state.
    pb.memory[boss + 15] = 0
    pb.memory[boss + 10] = 12
    assert_phase(pb, boss, 0)

    pb.memory[boss + 10] = 1
    assert_phase(pb, boss, 1)

    # Projection tiles remain walkable. The only physical/vulnerable boss body
    # is still the 32x32 OBJ heart, so the spectacle cannot create invisible
    # collision across the expanded shape.
    put16(pb, PL + 9, 32)
    put16(pb, PL + 11, 32)
    pb.memory[PL + 15] = 255
    before_x = pb.memory[PL + 9]
    pb.button_press("right")
    for _ in range(12):
        pb.tick()
    pb.button_release("right")
    # Consume the queued release before the next direct checkpoint warp.
    # PyBoy 2.7 restores the pre-event CPU sample on this boundary, which can
    # otherwise overwrite a WRAM position written in the same host interval.
    pb.tick()
    assert pb.memory[PL + 9] > before_x, "Mire projection became invisible collision"

    # The huge body now changes footprint inside a true scrolling field.
    # Traverse to the eastern chamber while keeping the WINDOW HUD fixed.
    put16(pb, PL + 9, 200)
    scroll = []
    for _ in range(80):
        pb.tick()
        scroll.append((pb.memory[0xFF43], pb.memory[0xFF42]))
    assert pb.memory[CAMERA_X] == 64 and 61 <= scroll[-1][0] <= 67, (
        f"Mire field did not reach its eastern camera: "
        f"camera={pb.memory[CAMERA_X]} SCX={scroll[-1][0]}")
    assert {y for _, y in scroll} == {0}, f"Mire camera tilted: {set(scroll)}"

    screenshot = ROOT / "tmp" / "mire-colossal-expanded.png"
    pb.screen.image.save(screenshot)

    pb.memory[boss + 15] = 1
    pb.memory[boss + 10] = 1
    assert_phase(pb, boss, 0)
    pb.stop(save=False)

    print("[colossal-mire] PASS pulse clenched -> expanded -> clenched; "
          "no mural; camera 0..64; arena walkable")


if __name__ == "__main__":
    main()
