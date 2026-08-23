#!/usr/bin/env python3
"""ROM contract: every required dungeon specialist is player-reachable."""

from test_stage_archetypes import (
    EN, PL, ROOM_H, ROOM_W, addr, generated_room,
)
from quintra_topology import dungeon_size, mission_graph


ENTITY_SIZE = 28
ENT_ENEMY = 2
EF_ACTIVE = 0x01
ENEMY_STONE_SENTINEL = 1
ENEMY_STAGE_REAPER = 34
WALKABLE = {1, 3, 7, 19, 20, 23, 31, 33, 34, *range(9, 19)}
WORLD_EXT, WORLD_BOTTOM, WORLD_W, WORLD_H = map(addr, (
    "_room_world_extension", "_room_world_bottom",
    "_room_world_width", "_room_world_height",
))


def body_ok(tiles, width, height, x, y):
    return (1 <= x < width - 1 and 1 <= y < height - 1
            and all(tiles[ty * width + tx] in WALKABLE
                    for tx, ty in ((x, y), (x + 1, y),
                                   (x, y + 1), (x + 1, y + 1))))


def reachable(tiles, width, height, start):
    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if ((nx, ny) not in seen
                    and body_ok(tiles, width, height, nx, ny)):
                seen.add((nx, ny))
                todo.append((nx, ny))
    return seen


def world_tiles(pb, compact):
    width = pb.memory[WORLD_W] // 8
    height = pb.memory[WORLD_H] // 8
    result = []
    for y in range(height):
        for x in range(width):
            if y < ROOM_H and x < ROOM_W:
                result.append(compact[y * ROOM_W + x])
            elif y < ROOM_H:
                result.append(pb.memory[WORLD_EXT + y * 11 + x - ROOM_W])
            else:
                result.append(pb.memory[WORLD_BOTTOM + (y - ROOM_H) * 31 + x])
    return result, width, height


def main():
    checked = []
    expected = {"id": ENEMY_STONE_SENTINEL, "hp": 50, "name": "Sentinel"}

    def inspect(pb, tiles):
        tiles, width, height = world_tiles(pb, tiles)
        specialists = []
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            if (pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE
                    and pb.memory[ep + 17] == expected["id"]
                    and pb.memory[ep + 14] >= expected["hp"]):
                specialists.append(ep)
        assert len(specialists) == 1, (
            f"expected one required {expected['name']}, got {len(specialists)}")
        specialist = specialists[0]
        sx = (pb.memory[specialist + 3] + 4) // 8
        sy = (pb.memory[specialist + 7] + 4) // 8
        px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
        py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
        start = ((px + 2) // 8, (py + 8) // 8)
        assert body_ok(tiles, width, height, sx, sy), \
            f"{expected['name']} overlaps solid tile at {(sx, sy)}"
        assert (sx, sy) in reachable(tiles, width, height, start), (
            f"{expected['name']} at {(sx, sy)} is outside player component from {start}")
        checked.append((sx, sy))

    # The two Warden cells retain the stage-scaled Sentinel, while the fixed
    # deep court at local 15 now belongs to the one-per-dungeon Dread Reaper.
    for seed in range(0x51A70000, 0x51A70010):
        graph = mission_graph(dungeon_size(0), seed, 0)
        for local_room, enemy_id, hp, name in (
                (graph["warden"], ENEMY_STONE_SENTINEL, 50, "Sentinel"),
                (graph["deep_warden"], ENEMY_STONE_SENTINEL, 50, "Sentinel"),
                (15, ENEMY_STAGE_REAPER, 30, "Dread Reaper")):
            expected.update(id=enemy_id, hp=hp, name=name)
            generated_room(0, seed, probe=inspect, local_room=local_room)

    assert len(checked) == 48
    print(f"[miniboss-spawn-reach] PASS 32 Sentinels + 16 Reapers positions={checked}")


if __name__ == "__main__":
    main()
