#!/usr/bin/env python3
"""Live-ROM contract: an incomplete empty sanctuary always has a retreat."""
from __future__ import annotations

import re
from pathlib import Path

from quintra_pyboy_env import (
    ACTION_DOWN, ACTION_LEFT, ACTION_RIGHT, ACTION_UP, QuintraPyBoyEnv,
)
from quintra_topology import (
    STAGE_BOSS_ROOM, STAGE_START, dungeon_maze_neighbor, dungeon_size,
)


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom" / "working" / "quintra.gbc"
STATES = ROOT / "tmp" / "stage-states"
BGT_DOOR = 3
BGT_DOOR_LOCKED = 126
DOORS = {
    0: ((9, 0), (10, 0)),
    1: ((19, 8), (19, 9)),
    2: ((9, 16), (10, 16)),
    3: ((0, 8), (0, 9)),
}


def symbol(name: str) -> int:
    text = ROM.with_suffix(".noi").read_text()
    match = re.search(rf"DEF {re.escape(name)} 0x([0-9A-Fa-f]+)", text)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


def put16(memory, address: int, value: int) -> None:
    memory[address] = value & 0xFF
    memory[address + 1] = (value >> 8) & 0xFF


def reveal_cell(memory, run_state: int, cell: int) -> None:
    offsets = (20, 29, 31, 33)
    memory[run_state + offsets[cell >> 3]] |= 1 << (cell & 7)


def redraw_room(pb) -> None:
    pb.button("start"); pb.tick(30)
    pb.button("b"); pb.tick(60)


def shown_door(pb, direction: int) -> tuple[int, int]:
    pb.memory[0xFF4F] = 0
    return tuple(pb.memory[0x9800 + y * 32 + x]
                 for x, y in DOORS[direction])


def main() -> None:
    env = QuintraPyBoyEnv(ROM, window="null")
    puzzle_locked = symbol("_room_puzzle_locked")
    try:
        for stage in range(9):
            state = STATES / (
                f"quintra-stage-{stage + 1:02d}-sanctuary-wolfkin.pyboy")
            obs = env.load_state(state)
            assert not obs["hostiles"], f"stage {stage + 1} sanctuary is not empty"
            assert env.pb is not None
            pb = env.pb
            rs = env.addrs["_run_state"]
            player = env.addrs["_player"]
            seed = sum(pb.memory[rs + 2 + i] << (8 * i) for i in range(4))
            local = dungeon_size(stage) - 2
            retreats = [
                (direction, neighbor)
                for direction in range(4)
                if (neighbor := dungeon_maze_neighbor(
                    local, dungeon_size(stage), direction, seed, stage))
                is not None and neighbor < local
            ]
            assert retreats, f"stage {stage + 1} sanctuary has no graph retreat"
            direction, neighbor = retreats[0]

            # Reproduce the dangerous combination: the boss objectives are
            # incomplete, no cardinal arrival survives, and an obsolete lock
            # byte says this empty room is a puzzle. The lower graph edge must
            # still work; it can never skip an objective or enter the boss.
            if stage < 8:
                pb.memory[rs + 23] &= ~(1 << stage) & 0xFF
            else:
                pb.memory[rs + 24] &= ~1 & 0xFF
            pb.memory[rs + 6] = 0xFF
            # These curriculum states jump directly to the sanctuary rather
            # than walking its predecessor. Model the real-run evidence that
            # makes the edge a safe retreat before deleting arrival metadata.
            reveal_cell(pb.memory, rs, neighbor)
            pb.memory[puzzle_locked] = 1
            x, y, action = {
                0: (72, 0, ACTION_UP),
                1: (144, 60, ACTION_RIGHT),
                2: (72, 120, ACTION_DOWN),
                3: (0, 60, ACTION_LEFT),
            }[direction]
            put16(pb.memory, player + 9, x)
            put16(pb.memory, player + 11, y)
            target = STAGE_START[stage] + neighbor
            for _ in range(40):
                obs, _, terminal, _ = env.step(action, 4)
                if obs["room"] == target or terminal:
                    break
            assert obs["room"] == target and not terminal, (
                f"stage {stage + 1} empty sanctuary trapped the run: "
                f"room={obs['room']} expected retreat={target}")

        # Stage 3 contains the shape the old numeric fallback missed: a fold
        # can enter a later sealed cell from a numerically higher predecessor.
        # Simulate lost arrival metadata while retaining the authoritative
        # visited-map bit. That proven retreat must remain usable.
        stage = 2
        state = STATES / "quintra-stage-03-entry-wolfkin.pyboy"
        env.load_state(state)
        assert env.pb is not None
        pb = env.pb
        rs = env.addrs["_run_state"]
        player = env.addrs["_player"]
        tilemap = env.addrs["_room_tilemap"]
        seed = sum(pb.memory[rs + 2 + i] << (8 * i) for i in range(4))
        current = pb.memory[rs + 43]  # generated deep Warden cell
        direction, neighbor = next(
            (direction, neighbor)
            for direction in range(4)
            if (neighbor := dungeon_maze_neighbor(
                current, dungeon_size(stage), direction, seed, stage))
            is not None and neighbor > current
        )
        pb.memory[rs + 1] = STAGE_START[stage] + current
        pb.memory[rs + 6] = 0xFF
        pb.memory[rs + 13] = 0
        pb.memory[rs + 17] = 0
        for offset in (20, 29, 31, 33):
            pb.memory[rs + offset] = 0
        reveal_cell(pb.memory, rs, current)
        reveal_cell(pb.memory, rs, neighbor)
        pb.memory[puzzle_locked] = 1
        pb.memory[symbol("_room_combat_sealed")] = 0
        pb.memory[symbol("_procgen_current_room_is_large")] = 0
        pb.memory[env.addrs["_room_world_width"]] = 160
        pb.memory[env.addrs["_room_world_height"]] = 136
        pb.memory[env.addrs["_room_camera_x"]] = 0
        pb.memory[env.addrs["_room_camera_y"]] = 0
        pb.memory[0xFF42] = pb.memory[0xFF43] = 0
        for i in range(32 * 28):
            pb.memory[env.addrs["_entities"] + i] = 0
        graph_directions = []
        for graph_direction in range(4):
            graph_neighbor = dungeon_maze_neighbor(
                current, dungeon_size(stage), graph_direction, seed, stage)
            if graph_neighbor is None:
                continue
            graph_directions.append(graph_direction)
            for tx, ty in DOORS[graph_direction]:
                pb.memory[tilemap + ty * 20 + tx] = BGT_DOOR
        blocked_direction = next(
            graph_direction for graph_direction in graph_directions
            if graph_direction != direction)

        # The visible threshold communicates the exact collision rule: the
        # proven visited retreat stays amber/open, while the unseen forward
        # edge receives a real portcullis. Releasing the seal swaps that art
        # back to an ordinary door rather than leaving a stale barred tile.
        redraw_room(pb)
        assert shown_door(pb, direction) == (BGT_DOOR, BGT_DOOR), (
            "Stage 3 safe retreat was drawn as locked")
        assert shown_door(pb, blocked_direction) == (
            BGT_DOOR_LOCKED, BGT_DOOR_LOCKED), (
            "Stage 3 forward seal was not visibly barred")
        pb.memory[puzzle_locked] = 0
        redraw_room(pb)
        assert shown_door(pb, blocked_direction) == (BGT_DOOR, BGT_DOOR), (
            "released Stage 3 door kept stale locked art")
        pb.memory[puzzle_locked] = 1
        redraw_room(pb)
        x, y, action = {
            0: (72, 0, ACTION_UP),
            1: (144, 60, ACTION_RIGHT),
            2: (72, 120, ACTION_DOWN),
            3: (0, 60, ACTION_LEFT),
        }[direction]
        put16(pb.memory, player + 9, x)
        put16(pb.memory, player + 11, y)
        target = STAGE_START[stage] + neighbor
        for _ in range(40):
            obs, _, terminal, _ = env.step(action, 4)
            if obs["room"] == target or terminal:
                break
        assert obs["room"] == target and not terminal, (
            "Stage 3 higher-number seen retreat remained sealed: "
            f"room={obs['room']} expected={target}")
    finally:
        env.close()
    print("[sanctuary-escape] PASS 9 thresholds + Stage 3 folded seen retreat "
          "+ visible seal")


if __name__ == "__main__":
    main()
