#!/usr/bin/env python3
"""ROM contract: every required Sentinel spawns in the player's component."""

from test_stage_archetypes import (
    EN, PL, ROOM_H, ROOM_W, addr, generated_room,
)
from quintra_topology import dungeon_size, mission_graph


ENTITY_SIZE = 28
ENT_ENEMY = 2
EF_ACTIVE = 0x01
ENEMY_STONE_SENTINEL = 1
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

    def inspect(pb, tiles):
        tiles, width, height = world_tiles(pb, tiles)
        sentinels = []
        for i in range(32):
            ep = EN + i * ENTITY_SIZE
            if (pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE
                    and pb.memory[ep + 17] == ENEMY_STONE_SENTINEL
                    and pb.memory[ep + 14] >= 50):
                sentinels.append(ep)
        assert len(sentinels) == 1, f"expected one required Sentinel, got {len(sentinels)}"
        sentinel = sentinels[0]
        sx = (pb.memory[sentinel + 3] + 4) // 8
        sy = (pb.memory[sentinel + 7] + 4) // 8
        px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
        py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
        start = ((px + 2) // 8, (py + 8) // 8)
        assert body_ok(tiles, width, height, sx, sy), \
            f"Sentinel overlaps solid tile at {(sx, sy)}"
        assert (sx, sy) in reachable(tiles, width, height, start), (
            f"Sentinel at {(sx, sy)} is outside player component from {start}")
        checked.append((sx, sy))

    # The two Warden cells are seed-authored mission roles now; local 15
    # remains the recurring midpoint Sentinel. Exercise all three required
    # fights for each graph instead of pinning the former fixed 3/9 layout.
    for seed in range(0x51A70000, 0x51A70010):
        graph = mission_graph(dungeon_size(0), seed, 0)
        for local_room in (graph["warden"], graph["deep_warden"], 15):
            generated_room(0, seed, probe=inspect, local_room=local_room)

    assert len(checked) == 48
    print(f"[miniboss-spawn-reach] PASS 48 required Sentinel positions={checked}")


if __name__ == "__main__":
    main()
