#!/usr/bin/env python3
"""Every Prism Toggle orb must land on a strikable crystal tile.

Law Lock caches its altar list on (run seed, bosses beaten) only. If that
generate runs before mission roles are filled, a later waystone can still
carry a stale altar. On seed 0x7B081BB4, stage 5 waystone (room 107,
local 20), the west-door altar apron flattened the west-edge orb to floor
(issue #233). This sweep checks the reported case, injects that stale
cache, and samples Prism rooms across stages.
"""
import sys

from test_stage_archetypes import generated_room, addr, ROM, RS
from quintra_topology import (
    PUZZLE_PRISM_TOGGLE, dungeon_size, mission_graph, puzzle_slot_kind,
)

CRYSTAL = 22
PRISM_X0, PRISM_Y0, PRISM_W, PRISM_H = 4, 3, 12, 11
PRISM_CLASS_ORB = 3
ROOM_W = 20

REPRO_SEED = 0x7B081BB4
REPRO_STAGE = 4  # stage 5, 0-based
# Roles and altars captured from the Player state that exhibited #233
# (8a1765f8, run 20261124-0145, room 107): missions were already
# [16, 13, 12, 20, 1, 3, 4], but the cached law-lock still had this list.
STALE_ROLES = [4, 9, 10, 6, 19, 14, 12]
STALE_ALTARS = [16, 20]


def prism_orbs(pb, tiles):
    cls = addr("_prism_class")
    found = []
    for y in range(PRISM_H):
        for x in range(PRISM_W):
            if pb.memory[cls + y * PRISM_W + x] != PRISM_CLASS_ORB:
                continue
            tx, ty = PRISM_X0 + x, PRISM_Y0 + y
            tile = tiles[ty * ROOM_W + tx]
            found.append((tx, ty, tile))
    return found


def check_room(stage, seed, role, cell, difficulty="easy", pre_cross=None, tag=""):
    problems = []

    def probe(pb, tiles):
        kind = pb.memory[addr("_room_puzzle_kind")]
        if kind != PUZZLE_PRISM_TOGGLE:
            problems.append(
                f"{tag}{role} stage {stage+1} seed {seed:#08x} cell {cell}: "
                f"kind {kind}, want prism")
            return
        orbs = prism_orbs(pb, tiles)
        if not orbs:
            problems.append(
                f"{tag}{role} stage {stage+1} seed {seed:#08x} cell {cell}: "
                "no orbs in prism_class")
            return
        for tx, ty, tile in orbs:
            if tile != CRYSTAL:
                problems.append(
                    f"{tag}{role} stage {stage+1} seed {seed:#08x} cell {cell}: "
                    f"orb at ({tx},{ty}) tile {tile:#04x}, want BGT_CRYSTAL"
                )

    generated_room(stage, seed=seed, local_room=cell, difficulty=difficulty,
                   probe=probe, pre_cross=pre_cross)
    return problems


def inject_stale_law_lock(pb, addrs):
    del addrs
    role = addr("_ll_role")
    for i, v in enumerate(STALE_ROLES):
        pb.memory[role + i] = v
    pb.memory[addr("_ll_altar_n")] = len(STALE_ALTARS)
    for i, v in enumerate(STALE_ALTARS):
        pb.memory[addr("_ll_altar") + i] = v
    # Pin the old cache key to this room's seed and boss tag so a
    # seed+tag-only check would keep the stale altar list. generated_room
    # writes run_seed after boot, which would otherwise miss and regenerate.
    for i, b in enumerate(REPRO_SEED.to_bytes(4, "little")):
        pb.memory[addr("_law_lock_seed") + i] = b
    bosses = pb.memory[RS + 11]  # run_state.bosses_beaten
    pb.memory[addr("_law_lock_tag")] = (bosses + 1) & 0xFF


def find_prism_cells(seed, stage):
    found = []
    for slot, role in ((0, "trial"), (1, "waystone")):
        if puzzle_slot_kind(seed, stage, slot) == PUZZLE_PRISM_TOGGLE:
            cell = mission_graph(dungeon_size(stage), seed, stage)[role]
            found.append((role, cell))
    return found


def main():
    fails = []
    print(f"ROM {ROM}")
    graph = mission_graph(dungeon_size(REPRO_STAGE), REPRO_SEED, REPRO_STAGE)
    cell = graph["waystone"]
    print(f"repro seed {REPRO_SEED:#08x} stage 5 waystone cell {cell}")
    fails.extend(check_room(REPRO_STAGE, REPRO_SEED, "waystone", cell, "easy"))
    print("repro with stale law-lock cache (Player state roles/altars)")
    fails.extend(check_room(
        REPRO_STAGE, REPRO_SEED, "waystone", cell, "easy",
        pre_cross=inject_stale_law_lock, tag="stale-cache "))
    for stage in range(9):
        seen = 0
        n = 0
        while seen < 3 and n < 800:
            seed = (0x7A11C0DE + n * 2654435761 + stage * 17) & 0xFFFFFFFF
            n += 1
            cells = find_prism_cells(seed, stage)
            if not cells:
                continue
            for role, cell in cells:
                print(f"sweep stage {stage+1} seed {seed:#08x} {role} cell {cell}")
                fails.extend(check_room(stage, seed, role, cell, "easy"))
                seen += 1
                if seen >= 3:
                    break
        if seen == 0:
            print(f"sweep stage {stage+1}: no prism rooms in {n} seeds")
    if fails:
        print(f"{len(fails)} failure(s)")
        for line in fails:
            print("FAIL", line)
        return 1
    print("[prism-orb-tiles] PASS reported room 107, stale-cache injection, and swept prism orbs stay crystal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
