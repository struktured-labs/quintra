#!/usr/bin/env python3
"""Live-ROM contract for generated optional Farfold Cache expeditions."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_START, dungeon_cache_cell, dungeon_maze_neighbor, dungeon_size,
)


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
ENTITY_SIZE = 28
MAX_ENTITIES = 32
ENT_ENEMY = 2
ENT_PICKUP = 3
PICKUP_FARFOLD_RELIC = 19
RUN_FARFOLD_CACHE_BIT = 0x02
SCREEN_ROOM = 5
SCREEN_MAP = 8
BGT_MAP_BIG_CACHE = 123
GX = (1, 4, 7, 10, 13, 16,
      16, 13, 10, 7, 4, 1,
      1, 4, 7, 10, 13, 16,
      16, 13, 10, 7, 4, 1,
      1, 4, 7, 10, 13, 16)
GY = (2, 2, 2, 2, 2, 2,
      5, 5, 5, 5, 5, 5,
      8, 8, 8, 8, 8, 8,
      11, 11, 11, 11, 11, 11,
      14, 14, 14, 14, 14, 14)


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, EN, TM, BOTTOM, WORLD_W, WORLD_H, LARGE, SEALED, PUZZLE_LOCKED, SCREEN = map(
    addr,
    (
        "_run_state", "_player", "_entities", "_room_tilemap",
        "_room_world_bottom", "_room_world_width", "_room_world_height",
        "_procgen_current_room_is_large", "_room_combat_sealed",
        "_room_puzzle_locked", "_loop_current_screen",
    ),
)


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def get16(pb, address):
    return pb.memory[address] | pb.memory[address + 1] << 8


def settle(pb, frames=90):
    for _ in range(frames):
        pb.memory[PL + 2] = pb.memory[PL + 1]
        pb.memory[PL + 15] = 120
        pb.tick()


def clear_hostiles(pb):
    for slot in range(MAX_ENTITIES):
        base = EN + slot * ENTITY_SIZE
        if pb.memory[base] == ENT_ENEMY:
            pb.memory[base] = pb.memory[base + 1] = 0


def farfold_entities(pb):
    return [
        EN + slot * ENTITY_SIZE
        for slot in range(MAX_ENTITIES)
        if pb.memory[EN + slot * ENTITY_SIZE] == ENT_PICKUP
        and pb.memory[EN + slot * ENTITY_SIZE + 1] & 1
        and pb.memory[EN + slot * ENTITY_SIZE + 17] == PICKUP_FARFOLD_RELIC
    ]


def map_node(pb, cell):
    return pb.memory[0x9800 + GY[cell] * 32 + GX[cell]]


def open_compass(pb):
    pb.button_press("select")
    try:
        for _ in range(180):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_MAP:
                settle(pb, 30)
                return
    finally:
        pb.button_release("select")
    raise AssertionError("SELECT did not enter Farfold Compass")


def close_compass(pb):
    pb.button_press("b")
    try:
        for _ in range(180):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_ROOM:
                settle(pb, 30)
                return
    finally:
        pb.button_release("b")
    raise AssertionError("B did not return from Farfold Compass")


def cross(pb, direction):
    clear_hostiles(pb)
    pb.memory[SEALED] = 0
    pb.memory[PUZZLE_LOCKED] = 0
    x, y = {
        0: (72, 0),
        1: (232, 60),
        2: (72, 232),
        3: (0, 60),
    }[direction]
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    settle(pb, 120)


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    try:
        settle(pb, 240)
        pb.button("start")
        settle(pb, 30)
        pb.button("a")
        settle(pb, 90)
        assert pb.memory[SCREEN] == SCREEN_ROOM

        seed = sum(pb.memory[RS + 2 + i] << (i * 8) for i in range(4))
        size = dungeon_size(0)
        cache = dungeon_cache_cell(size, seed, 0)

        # SELECT advertises the optional destination before the player walks
        # there, while keeping it semantically separate from required GOAL.
        open_compass(pb)
        assert map_node(pb, cache) == BGT_MAP_BIG_CACHE, (
            f"cache cell {cache} lacks its optional LOOT node")
        close_compass(pb)

        # Enter the generated cache cell through the cartridge's real
        # Riftwild-to-dungeon transaction so all room banks and runtime
        # orchestration execute exactly as they do in play.
        target = STAGE_START[0] + cache
        pb.memory[RS + 1] = target - 1
        pb.memory[RS + 11] = 0
        pb.memory[RS + 12] = 0
        pb.memory[RS + 13] = 0
        pb.memory[RS + 17] = 1
        pb.memory[RS + 18] = 6
        clear_hostiles(pb)
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 60)
        pb.memory[TM + 9 * 20 + 10] = 34
        for _ in range(30):
            pb.tick()
            if pb.memory[RS + 1] == target:
                break
        settle(pb, 120)
        assert pb.memory[RS + 1] == target
        assert pb.memory[LARGE] == 1
        assert (pb.memory[WORLD_W], pb.memory[WORLD_H]) == (248, 248)

        relics = farfold_entities(pb)
        assert len(relics) == 1, f"cache spawned {len(relics)} relics"
        relic = relics[0]
        # The altar's visible switch occupies the authored center. The shared
        # pickup safety pass snaps the orb one floor cell east, still inside
        # the shrine but never on top of an interactive terrain tile.
        assert (get16(pb, relic + 3), get16(pb, relic + 7)) == (224, 208)
        item_index = pb.memory[relic + 18]
        assert item_index in (10, 11, 12, 15, 16, 17, 19), item_index
        # The southeast altar is real collision-world architecture, beyond
        # both former viewport seams—not a host-only marker.
        assert pb.memory[BOTTOM + (26 - 17) * 31 + 27] == 33

        clear_hostiles(pb)
        settle(pb, 360)
        assert farfold_entities(pb) == [relic], (
            "optional relic expired before the player could explore to it")

        inventory_before = bytes(pb.memory[PL + 24 + i] for i in range(16))
        put16(pb, PL + 9, 212)
        put16(pb, PL + 11, 200)
        settle(pb, 12)
        assert pb.memory[RS + 28] & RUN_FARFOLD_CACHE_BIT
        assert not farfold_entities(pb), "claimed cache relic remained active"
        inventory_after = bytes(pb.memory[PL + 24 + i] for i in range(16))
        assert inventory_after != inventory_before, (
            "cache relic did not enter the run inventory")

        # Leave along the cache arm's unique edge. Its Compass icon clears,
        # and returning to the reliquary cannot farm a second permanent item.
        neighbors = [
            (direction, dungeon_maze_neighbor(cache, size, direction, seed, 0))
            for direction in range(4)
        ]
        neighbors = [(direction, cell) for direction, cell in neighbors
                     if cell is not None]
        assert len(neighbors) == 1, neighbors
        direction, neighbor = neighbors[0]
        cross(pb, direction)
        assert pb.memory[RS + 1] == STAGE_START[0] + neighbor
        open_compass(pb)
        assert map_node(pb, cache) != BGT_MAP_BIG_CACHE, (
            "claimed cache remained marked as unclaimed LOOT")
        close_compass(pb)
        cross(pb, direction ^ 2)
        assert pb.memory[RS + 1] == target
        assert not farfold_entities(pb), "cache relic respawned after backtrack"

        pb.screen.image.save(ROOT / "tmp" / "farfold-cache-claimed.png")
    finally:
        pb.stop(save=False)

    print(
        f"[farfold-cache] PASS seed={seed:08x} cell={cache} "
        f"item={item_index} persistent + one-shot + Compass LOOT"
    )


if __name__ == "__main__":
    main()
