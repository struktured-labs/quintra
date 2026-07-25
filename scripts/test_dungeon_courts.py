#!/usr/bin/env python3
"""Live-ROM contract for generated 248x248 dungeon districts."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W, ROOM_H = 20, 17
WIDE_W, WIDE_H = 31, 31
EXT_W, BOTTOM_H = WIDE_W - ROOM_W, WIDE_H - ROOM_H
WORLD_PX = WIDE_W * 8
FAR_EDGE = WORLD_PX - 16
CAMERA_X_MAX = WORLD_PX - ROOM_W * 8
CAMERA_Y_MAX = WORLD_PX - ROOM_H * 8


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


(
    RS, PL, EN, TM, EXT, BOTTOM, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y,
    LARGE, SEALED, PUZZLE_LOCKED, ORIGIN_X, ORIGIN_Y,
) = map(
    addr,
    (
        "_run_state", "_player", "_entities", "_room_tilemap",
        "_room_world_extension", "_room_world_bottom", "_room_world_width",
        "_room_world_height", "_room_camera_x", "_room_camera_y",
        "_procgen_current_room_is_large", "_room_combat_sealed",
        "_room_puzzle_locked", "_room_bg_origin_x", "_room_bg_origin_y",
    ),
)


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = value >> 8


def clear_hostiles(pb):
    for slot in range(32):
        base = EN + slot * 28
        if pb.memory[base] == 2:
            pb.memory[base] = pb.memory[base + 1] = 0


def settle(pb, frames=100):
    for _ in range(frames):
        pb.memory[PL + 2] = pb.memory[PL + 1]
        pb.memory[PL + 15] = 120
        pb.tick()


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    try:
        settle(pb, 240)
        pb.button("start")
        settle(pb, 30)
        pb.button("a")
        settle(pb, 60)

        # The very first playable screen establishes the dungeon's physical
        # scale instead of hiding every scrolling field behind several compact
        # thresholds.
        assert pb.memory[RS + 1] == 0
        assert pb.memory[LARGE] == 1
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)

        # Publish opening-dungeon local room 3, then cross its east threshold
        # into local room 4—the first dense scrolling approach expanse.
        pb.memory[RS + 1] = 3
        pb.memory[RS + 11] = 0
        pb.memory[RS + 13] = 0
        pb.memory[LARGE] = 0
        pb.memory[WORLD_W] = 160
        pb.memory[WORLD_H] = 136
        pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
        pb.memory[TM + 8 * ROOM_W + 19] = 3
        pb.memory[TM + 9 * ROOM_W + 19] = 3
        clear_hostiles(pb)
        put16(pb, PL + 9, 144)
        put16(pb, PL + 11, 60)
        settle(pb)

        assert pb.memory[RS + 1] == 4
        assert pb.memory[LARGE] == 1
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)
        # The next graph edge is the true far east edge. Crossing it keeps
        # wide-world state and enters the paired lighter turn court.
        clear_hostiles(pb)
        put16(pb, PL + 9, FAR_EDGE)
        put16(pb, PL + 11, 60)
        settle(pb)

        assert pb.memory[RS + 1] == 5
        assert pb.memory[LARGE] == 1
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)
        # Local 5 owns reciprocal west and south links. The old east/south
        # viewport edges are interior; only the true 31x31 perimeter closes.
        assert pb.memory[TM + 8 * ROOM_W] == 3
        assert pb.memory[TM + 9 * ROOM_W] == 3
        walkable = (1, 19, 20, 23, 31)
        assert pb.memory[TM + 8 * ROOM_W + 19] in walkable
        assert pb.memory[TM + 16 * ROOM_W + 10] in walkable
        assert pb.memory[EXT + 8 * EXT_W + EXT_W - 1] == 2
        assert pb.memory[EXT + 9 * EXT_W + EXT_W - 1] == 2
        assert pb.memory[BOTTOM + (BOTTOM_H - 1) * WIDE_W + 9] == 3
        assert pb.memory[BOTTOM + (BOTTOM_H - 1) * WIDE_W + 10] == 3
        assert not any(
            pb.memory[EXT + i] & 0x80 for i in range(ROOM_H * EXT_W)
        )
        assert not any(
            pb.memory[BOTTOM + i] & 0x80
            for i in range(BOTTOM_H * WIDE_W)
        )
        field = []
        for y in range(WIDE_H):
            row = []
            for x in range(WIDE_W):
                if y < 17 and x < 20:
                    row.append(pb.memory[TM + y * 20 + x] & 0x7F)
                elif y < 17:
                    row.append(
                        pb.memory[EXT + y * EXT_W + x - ROOM_W] & 0x7F)
                else:
                    row.append(
                        pb.memory[BOTTOM + (y - ROOM_H) * WIDE_W + x] & 0x7F)
            field.append(row)
        passable = {1, 3, 19, 20, 23, 31}
        queue = [(1, 8)]
        seen = set(queue)
        while queue:
            x, y = queue.pop()
            for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
                if (
                    0 <= nx < WIDE_W
                    and 0 <= ny < WIDE_H
                    and (nx, ny) not in seen
                    and field[ny][nx] in passable
                ):
                    seen.add((nx, ny))
                    queue.append((nx, ny))
        assert {(0, 8), (0, 9),
                (9, WIDE_H - 1), (10, WIDE_H - 1)} <= seen
        assert sum(
            field[y][x] == 21
            for y in range(WIDE_H)
            for x in range(WIDE_W)
            if x >= 20 or y >= 17
        ) >= 24

        hostiles = [
            (
                pb.memory[EN + slot * 28 + 3]
                | pb.memory[EN + slot * 28 + 4] << 8,
                pb.memory[EN + slot * 28 + 7]
                | pb.memory[EN + slot * 28 + 8] << 8,
            )
            for slot in range(32)
            if pb.memory[EN + slot * 28] == 2
        ]
        assert any(x >= 160 and y >= 136 for x, y in hostiles), hostiles
        assert len(set(hostiles)) == len(hostiles), (
            f"wide encounter bodies stacked on one coordinate: {hostiles}")

        # Exercise both camera axes in the actual added combat terrain.
        clear_hostiles(pb)
        put16(pb, PL + 9, 216)
        put16(pb, PL + 11, 216)
        settle(pb, 64)
        assert (pb.memory[CAMERA_X], pb.memory[CAMERA_Y]) == (
            CAMERA_X_MAX, CAMERA_Y_MAX)
        assert (pb.memory[0xFF43], pb.memory[0xFF42]) == (
            ((pb.memory[ORIGIN_X] << 3) + CAMERA_X_MAX) & 0xFF,
            ((pb.memory[ORIGIN_Y] << 3) + CAMERA_Y_MAX) & 0xFF)
        shot = ROOT / "tmp" / "dungeon-turn-court.png"
        shot.parent.mkdir(exist_ok=True)
        pb.screen.image.save(shot)

        # The true south door continues into local room 6 without collapsing
        # back to a one-screen field. A turn now reads as a scrolling district,
        # not one isolated large room.
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, FAR_EDGE)
        settle(pb)
        assert pb.memory[RS + 1] == 6, (
            f"south seam stayed room={pb.memory[RS + 1]} "
            f"player={pb.memory[PL + 9] | pb.memory[PL + 10] << 8},"
            f"{pb.memory[PL + 11] | pb.memory[PL + 12] << 8} "
            f"door={pb.memory[BOTTOM + (BOTTOM_H - 1) * WIDE_W + 9]} "
            f"world={pb.memory[WORLD_W]}x{pb.memory[WORLD_H]} "
            f"sealed={pb.memory[SEALED]} puzzle={pb.memory[PUZZLE_LOCKED]} "
            f"entered={pb.memory[RS + 6]}")
        assert pb.memory[LARGE] == 1
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)

        # Re-enter local 5 from the scrolling south neighbour. The champion
        # belongs at the true lower edge and SCY=112 immediately, never hidden
        # below the LCD.
        clear_hostiles(pb)
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 0)
        settle(pb)
        assert pb.memory[RS + 1] == 5
        assert pb.memory[LARGE] == 1
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)
        player_y = pb.memory[PL + 11] | pb.memory[PL + 12] << 8
        assert player_y == 224, player_y
        assert pb.memory[CAMERA_Y] == CAMERA_Y_MAX
        assert pb.memory[0xFF42] == (
            ((pb.memory[ORIGIN_Y] << 3) + CAMERA_Y_MAX) & 0xFF)

        # Local 7 is the authored Waystone fixture and deliberately returns
        # to the compact presentation so its puzzle language remains legible.
        clear_hostiles(pb)
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, FAR_EDGE)
        settle(pb)
        assert pb.memory[RS + 1] == 6
        clear_hostiles(pb)
        put16(pb, PL + 9, 0)
        put16(pb, PL + 11, 60)
        settle(pb)
        assert pb.memory[RS + 1] == 7
        assert pb.memory[LARGE] == 0
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (160, 136)
        assert (pb.memory[CAMERA_X], pb.memory[CAMERA_Y]) == (0, 0)

        # The central back-half approach is also a field. Without this beat,
        # the middle row collapses into a run of compact rooms even though the
        # nominal graph remains large.
        pb.memory[RS + 1] = 13
        pb.memory[TM + 8 * ROOM_W + ROOM_W - 1] = 3
        pb.memory[TM + 9 * ROOM_W + ROOM_W - 1] = 3
        clear_hostiles(pb)
        put16(pb, PL + 9, 144)
        put16(pb, PL + 11, 60)
        settle(pb)
        assert pb.memory[RS + 1] == 14
        assert pb.memory[LARGE] == 1
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)
    finally:
        pb.stop(save=False)

    # Stage 3's Grove archetype is layered over the court's compact western
    # sector. Its checkpoint proves that stage decoration cannot resurrect
    # the old 160x136 border as an invisible wall inside one scrolling field.
    state = (
        ROOT / "tmp/stage-states/"
        "quintra-stage-03-entry-picsean-easy.pyboy"
    )
    assert state.exists(), f"missing generated court checkpoint: {state}"
    pb = PyBoy(str(ROM), window="null", cgb=True)
    try:
        with state.open("rb") as checkpoint:
            pb.load_state(checkpoint)
        assert pb.memory[LARGE] == 1
        passable = {1, 3, 19, 20, 23, 31}
        assert all(
            (pb.memory[TM + 16 * ROOM_W + x] & 0x7F) in passable
            for x in range(1, ROOM_W - 1)
        ), "stage archetype restored the old south viewport wall"
        assert all(
            (pb.memory[TM + y * ROOM_W + 19] & 0x7F) in passable
            for y in range(1, ROOM_H - 1)
        ), "stage archetype restored the old east viewport wall"
    finally:
        pb.stop(save=False)

    print(
        "[dungeon-courts] PASS wide foyer + scrolling 248x248 districts + "
        "distributed encounters + seamless archetypes + reciprocal arrival"
    )


if __name__ == "__main__":
    main()
