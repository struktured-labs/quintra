#!/usr/bin/env python3
"""ROM contract: every required early Sentinel spawns in the player's component."""

from test_stage_archetypes import EN, PL, ROOM_H, ROOM_W, generated_room, tile


ENTITY_SIZE = 28
ENT_ENEMY = 2
EF_ACTIVE = 0x01
ENEMY_STONE_SENTINEL = 1
WALKABLE = {1, 3, 7, 19, 20, 23, 31, 33, 34, *range(9, 19)}


def body_ok(tiles, x, y):
    return (1 <= x < ROOM_W - 1 and 1 <= y < ROOM_H - 1
            and all(tile(tiles, tx, ty) in WALKABLE
                    for tx, ty in ((x, y), (x + 1, y),
                                   (x, y + 1), (x + 1, y + 1))))


def reachable(tiles, start):
    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if (nx, ny) not in seen and body_ok(tiles, nx, ny):
                seen.add((nx, ny))
                todo.append((nx, ny))
    return seen


def main():
    checked = []

    def inspect(pb, tiles):
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
        assert body_ok(tiles, sx, sy), f"Sentinel overlaps solid tile at {(sx, sy)}"
        assert (sx, sy) in reachable(tiles, start), (
            f"Sentinel at {(sx, sy)} is outside player component from {start}")
        checked.append((sx, sy))

    # Exercise distinct fixed interior layouts at the same required local
    # room. The generator may still decorate them differently, but all must
    # preserve a reachable 2x2 combat body for the mandatory Sentinel.
    for seed in range(0x51A70000, 0x51A70010):
        generated_room(0, seed, probe=inspect, local_room=3)

    assert len(checked) == 16
    print(f"[miniboss-spawn-reach] PASS 16 required Sentinel positions={checked}")


if __name__ == "__main__":
    main()
