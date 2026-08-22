#!/usr/bin/env python3
"""Procgen invariant: every collectible occupies player-reachable terrain."""
from pathlib import Path

from quintra_topology import dungeon_cache_cell, dungeon_size, mission_graph
from test_stage_archetypes import EN, PL, RS, TM, addr, generated_room

ROOT = Path(__file__).resolve().parent.parent
EXT = addr("_room_world_extension")
BOTTOM = addr("_room_world_bottom")
WORLD_W = addr("_room_world_width")
WORLD_H = addr("_room_world_height")

ROOM_W, ROOM_H = 20, 17
WIDE_W = 31
ENTITY_SIZE = 28
ENT_PICKUP = 3
COLLECTIBLE = {*range(7), 11, 14, 16, 19, 20}
WALKABLE = {1, 3, 7, *range(9, 19), 19, 20, 23, 31, 33, 34,
            35, 36, 96, *range(55, 64)}
SAFE_REWARD = WALKABLE - {31, 33, 34}
SEED = 0x5A17C0DE


def i16(pb, where):
    value = pb.memory[where] | pb.memory[where + 1] << 8
    return value - 0x10000 if value & 0x8000 else value


def world_tiles(pb):
    width = pb.memory[WORLD_W] // 8
    height = pb.memory[WORLD_H] // 8
    tiles = []
    for y in range(height):
        row = []
        for x in range(width):
            if y < ROOM_H and x < ROOM_W:
                value = pb.memory[TM + y * ROOM_W + x]
            elif y < ROOM_H:
                value = pb.memory[EXT + y * (WIDE_W - ROOM_W) + x - ROOM_W]
            else:
                value = pb.memory[BOTTOM + (y - ROOM_H) * WIDE_W + x]
            row.append(value & 0x7F)
        tiles.append(row)
    return tiles


def reachable_body_cells(pb, tiles):
    width, height = len(tiles[0]), len(tiles)

    def body_open(x, y):
        return (0 <= x < width - 1 and 0 <= y < height - 1
                and all(tiles[ty][tx] in WALKABLE
                        for tx, ty in ((x, y), (x + 1, y),
                                       (x, y + 1), (x + 1, y + 1))))

    start = ((i16(pb, PL + 9) + 2) >> 3, (i16(pb, PL + 11) + 8) >> 3)
    assert body_open(*start), f"player began outside traversable body space: {start}"
    seen, pending = {start}, [start]
    while pending:
        x, y = pending.pop()
        for cell in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if cell not in seen and body_open(*cell):
                seen.add(cell)
                pending.append(cell)
    return seen


def inspect_room(label, found_kinds, stage):
    def probe(pb, _compact):
        sigils = pb.memory[RS + 23] | pb.memory[RS + 24] << 8
        # The synthetic portal entry leaves the test champion in the center;
        # a correctly reachable Sigil can therefore be claimed before room
        # settling finishes. Count that real collision transaction as coverage.
        if "sigil" in label and sigils & (1 << stage):
            found_kinds.add(11)
        tiles = world_tiles(pb)
        reachable = reachable_body_cells(pb, tiles)
        for slot in range(32):
            base = EN + slot * ENTITY_SIZE
            if (pb.memory[base] != ENT_PICKUP
                    or not pb.memory[base + 1] & 1):
                continue
            kind = pb.memory[base + 17]
            if kind not in COLLECTIBLE:
                continue
            found_kinds.add(kind)
            x, y = i16(pb, base + 3), i16(pb, base + 7)
            width, height = len(tiles[0]), len(tiles)
            samples = ((x + 1, y + 1), (x + 14, y + 1),
                       (x + 1, y + 14), (x + 14, y + 14))
            assert all(0 <= px // 8 < width and 0 <= py // 8 < height
                       for px, py in samples), (
                f"{label}: pickup kind {kind} lies outside the world at {(x, y)}")
            terrain = [tiles[py // 8][px // 8] for px, py in samples]
            assert all(tile in SAFE_REWARD for tile in terrain), (
                f"{label}: pickup kind {kind} embedded in {terrain} at {(x, y)}")
            hitbox = pb.memory[base + 25]
            item_w, item_h = hitbox >> 4, hitbox & 0x0F
            approaches = [cell for cell in reachable
                          if cell[0] * 8 < x + item_w
                          and x < cell[0] * 8 + 12
                          and cell[1] * 8 < y + item_h
                          and y < cell[1] * 8 + 8]
            assert approaches, (
                f"{label}: pickup kind {kind} is on a disconnected island "
                f"at {(x, y)}")
    return probe


def main():
    # The shared constructor is the runtime defense for enemy drops, puzzle
    # rewards, boss loot, shop stock, Sigils, weapons, and boons alike.
    source = (ROOT / "src/game/pickup.c").read_text()
    constructor = source[source.index("u8 pickup_spawn("):
                         source.index("u8 pickup_spawn_item(")]
    assert "pickup_make_position_safe(&x, &y)" in constructor
    assert "snap_major_pickup_to_reachable(kind, &x, &y)" in constructor
    reach = (ROOT / "src/game/spawn_reach.c").read_text()
    assert "snap_reward_to_reachable" in reach
    assert "PICKUP_RIFT_SIGIL" in reach and "PICKUP_FARFOLD_RELIC" in reach
    assert "room_tile_at_px" in source and "room_world_width" in source

    found_kinds = set()
    for stage in range(9):
        size = dungeon_size(stage)
        graph = mission_graph(size, SEED, stage)
        cache = dungeon_cache_cell(size, SEED, stage)
        roles = (("sigil", graph["sigil"]),
                 ("cache", cache),
                 ("shop", size - 3))
        for role, local in roles:
            label = f"stage {stage + 1} {role} cell {local}"
            generated_room(stage, SEED, local_room=local,
                           probe=inspect_room(label, found_kinds, stage))

    assert {4, 11, 19} <= found_kinds, (
        f"coverage missed shop/Sigil/Farfold fixtures: {sorted(found_kinds)}")
    print("[pickup-reachability] PASS 27 generated role rooms: shop stock, "
          "Rift Sigils, and Farfold relics are safe + connected; ordinary "
          "major loot uses the guarded constructor")


if __name__ == "__main__":
    main()
