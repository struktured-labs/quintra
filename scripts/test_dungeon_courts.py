#!/usr/bin/env python3
"""Live-ROM contract for generated 248x248 dungeon districts."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import dungeon_direction, dungeon_maze_neighbor, dungeon_size


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
HARD_SCENERY = {2, 21, 22}
FLOOR_SCENERY = {1, 3, 19, 20, 23, 31, 33, 34}


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


def opening_expedition(seed):
    """Depth-first walk covering every large pre-service cell."""
    size = dungeon_size(0)
    large_cells = size - 3
    seen = {0}
    walk = []

    def visit(source):
        for direction in range(4):
            target = dungeon_maze_neighbor(source, size, direction, seed, 0)
            if target is None or target >= large_cells or target in seen:
                continue
            seen.add(target)
            walk.append((source, target))
            visit(target)
            walk.append((target, source))

    visit(0)
    assert seen == set(range(large_cells)), (
        f"large district graph disconnected: {sorted(set(range(large_cells)) - seen)}")
    return walk, large_cells


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

        # Follow the actual generated fold through every pre-service node.
        # This is the cartridge-facing proof that the scale response is one
        # sustained 17-field expedition, including Sigil/Waystone/Warden
        # roles, rather than another sparse selection of nominally large
        # rooms. The final shop, sanctuary, and Colossus remain deliberately
        # compact after this run.
        seed = sum(pb.memory[RS + 2 + i] << (i * 8) for i in range(4))
        route, large_cells = opening_expedition(seed)
        for source, target in route:
            direction = dungeon_direction(source, target)
            clear_hostiles(pb)
            pb.memory[SEALED] = 0
            pb.memory[PUZZLE_LOCKED] = 0
            px, py = {
                0: (72, 0), 1: (FAR_EDGE, 60),
                2: (72, FAR_EDGE), 3: (0, 60),
            }[direction]
            put16(pb, PL + 9, px)
            put16(pb, PL + 11, py)
            settle(pb)
            assert pb.memory[RS + 1] == target, (
                f"generated route stopped at {source}->{target}: "
                f"room={pb.memory[RS + 1]}")
            assert pb.memory[LARGE] == 1, (
                f"local {target} collapsed the sustained expedition")
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
        # Local 5 is now a genuine dead-end court in this fold. Its reciprocal
        # west link remains usable, while the old east/south viewport edges
        # are interior and only the true 31x31 perimeter closes.
        assert pb.memory[TM + 8 * ROOM_W] == 3
        assert pb.memory[TM + 9 * ROOM_W] == 3
        walkable = (1, 19, 20, 23, 31)
        assert pb.memory[TM + 8 * ROOM_W + 19] in walkable
        assert pb.memory[TM + 16 * ROOM_W + 10] in walkable
        assert pb.memory[EXT + 8 * EXT_W + EXT_W - 1] == 2
        assert pb.memory[EXT + 9 * EXT_W + EXT_W - 1] == 2
        assert pb.memory[BOTTOM + (BOTTOM_H - 1) * WIDE_W + 9] == 2
        assert pb.memory[BOTTOM + (BOTTOM_H - 1) * WIDE_W + 10] == 2
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
        false_gaps = []
        for y in range(1, WIDE_H - 1):
            for x in range(1, WIDE_W - 1):
                if field[y][x] not in FLOOR_SCENERY:
                    continue
                if (field[y][x - 1] in HARD_SCENERY
                        and field[y][x + 1] in HARD_SCENERY):
                    false_gaps.append((x, y, "vertical slit"))
                if (field[y - 1][x] in HARD_SCENERY
                        and field[y + 1][x] in HARD_SCENERY):
                    false_gaps.append((x, y, "horizontal slit"))
        assert not false_gaps, (
            "31x31 court contains champion-inaccessible visible gaps: "
            f"{false_gaps}"
        )
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
        assert {(0, 8), (0, 9)} <= seen
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
        f"[dungeon-courts] PASS branched {large_cells}→27-field expedition + "
        "distributed encounters + seamless archetypes + reciprocal arrival"
    )


if __name__ == "__main__":
    main()
