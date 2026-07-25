#!/usr/bin/env python3
"""Live-ROM regression: every stage boss owns one scrolling Colossus field."""
from pathlib import Path

from test_boss_identity import (
    CAMERA_X, CAMERA_Y, PL, TM, WORLD_H, WORLD_W, enter_boss, put16,
)


ROOT = Path(__file__).resolve().parent.parent
ROOM_W = 20
WORLD_WIDTH = 224
WORLD_HEIGHT = 136
MAX_CAMERA_X = WORLD_WIDTH - 160


def settle_camera(pb, x):
    put16(pb, PL + 9, x)
    for _ in range(80):
        pb.tick()
    return pb.memory[CAMERA_X], pb.memory[0xFF43]


def main():
    out = ROOT / "tmp" / "scrolling-colossi"
    out.mkdir(parents=True, exist_ok=True)

    for stage in range(9):
        pb, boss = enter_boss(stage, keep_open=True)
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (
            WORLD_WIDTH, WORLD_HEIGHT
        ), (
            f"stage {stage} arena remained compact: "
            f"{pb.memory[WORLD_W]}x{pb.memory[WORLD_H]}"
        )
        assert pb.memory[CAMERA_Y] == 0, (
            f"stage {stage} horizontal arena acquired vertical scroll"
        )
        assert all(
            pb.memory[TM + y * ROOM_W + (ROOM_W - 1)] == 1
            for y in range(1, 16)
        ), f"stage {stage} retained a solid viewport seam"

        west_camera, west_scx = settle_camera(pb, 8)
        assert west_camera == 0 and west_scx <= 3, (
            f"stage {stage} could not traverse west: "
            f"camera={west_camera}, SCX={west_scx}"
        )
        pb.screen.image.save(out / f"stage-{stage}-west.png")

        east_camera, east_scx = settle_camera(pb, 200)
        assert east_camera == MAX_CAMERA_X and east_scx >= MAX_CAMERA_X - 3, (
            f"stage {stage} could not traverse east: "
            f"camera={east_camera}, SCX={east_scx}"
        )
        assert pb.memory[boss + 1] & 1, (
            f"stage {stage} boss vanished during camera traverse"
        )
        pb.screen.image.save(out / f"stage-{stage}-east.png")
        pb.stop(save=False)

    print(
        "[scrolling-colossi] PASS 9/9 arenas are 224x136; "
        "west/east camera traverse 0..64; no compact seam"
    )


if __name__ == "__main__":
    main()
