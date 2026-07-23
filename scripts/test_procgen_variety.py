#!/usr/bin/env python3
"""Live-ROM contract: seeds vary collision, rosters, elites, and encounter size.

The Rust property test covers the deterministic base generator exhaustively.
This companion samples the linked cartridge after stage architecture and
entity spawning, preventing a future C-side change from leaving procgen varied
only in floor speckles.
"""
from collections import defaultdict

from pyboy import PyBoy
from quintra_topology import STAGE_START

from test_stage_archetypes import (
    EN, PL, ROM, ROOM_H, ROOM_W, RS, TM, put16, wait_for_generated_room,
)


SEEDS = tuple((0xA511E9B3 * index + 0x51A7E001) & 0xFFFFFFFF
              for index in range(12))
FLOORISH = {1, 19, 20, 23}
ENTITY_SIZE = 28
MAX_ENTITIES = 32
ENT_ENEMY = 2
EF_ACTIVE = 0x01
EF_ELITE = 0x20


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()
    return pb


def sample_stage_entry(pb, stage, seed):
    # Sample a real ordinary combat room, not one of the authored puzzle,
    # miniboss, shop, or sanctuary roles. Phase-family stages reserve both
    # local 1 and 2, so use their still-ordinary local 4 Rift room.
    local = 4 if stage % 3 == 2 else 2
    target = STAGE_START[stage] + local
    pb.memory[RS + 1] = target - 1
    for offset, byte in enumerate(seed.to_bytes(4, "little")):
        pb.memory[RS + 2 + offset] = byte
    pb.memory[RS + 6] = 0xFF       # center entry; no stale directional lane
    pb.memory[RS + 11] = stage
    pb.memory[RS + 12] = 0         # pending_unseal
    pb.memory[RS + 13] = 0         # secret_pending
    pb.memory[RS + 17] = 1         # stand in Riftwild's dungeon gate cell
    pb.memory[RS + 18] = 6
    pb.memory[PL + 2] = pb.memory[PL + 1]
    pb.memory[PL + 15] = 60
    for slot in range(MAX_ENTITIES):
        base = EN + slot * ENTITY_SIZE
        pb.memory[base] = pb.memory[base + 1] = 0
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 60)
    pb.memory[TM + 9 * ROOM_W + 10] = 34  # BGT_PORTAL under feet center
    for _ in range(30):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, (
        f"could not enter stage={stage} seed={seed:#x}; "
        f"room={pb.memory[RS + 1]} world={pb.memory[RS + 17]}"
    )
    tiles = wait_for_generated_room(pb)
    hostiles = []
    elite_count = 0
    for slot in range(MAX_ENTITIES):
        base = EN + slot * ENTITY_SIZE
        flags = pb.memory[base + 1]
        if pb.memory[base] == ENT_ENEMY and flags & EF_ACTIVE:
            hostiles.append(pb.memory[base + 17])
            elite_count += bool(flags & EF_ELITE)
    # Collapse only non-interactive floor texture/rubble. Walls, cover,
    # hazards, pots, blocks, secrets, doors, and portals retain identity.
    geometry = tuple(1 if tile in FLOORISH else tile for tile in tiles)
    return geometry, tuple(sorted(hostiles)), elite_count


def main():
    geometries = defaultdict(set)
    roster_kinds = defaultdict(set)
    roster_signatures = defaultdict(set)
    body_counts = []
    elite_total = 0
    pb = boot()
    try:
        for stage in range(9):
            for seed in SEEDS:
                geometry, roster, elites = sample_stage_entry(pb, stage, seed)
                geometries[stage].add(geometry)
                roster_kinds[stage].update(roster)
                roster_signatures[stage].add(roster)
                body_counts.append(len(roster))
                elite_total += elites
    finally:
        pb.stop(save=False)

    for stage in range(9):
        assert len(geometries[stage]) >= 8, (
            f"stage {stage + 1} collapsed to {len(geometries[stage])}/12 "
            "meaningful entry geometries"
        )
        assert len(roster_kinds[stage]) >= 3, (
            f"stage {stage + 1} exposed only enemy ids {sorted(roster_kinds[stage])}"
        )
        assert len(roster_signatures[stage]) >= 6, (
            f"stage {stage + 1} collapsed to {len(roster_signatures[stage])}/12 "
            "encounter rosters"
        )
    assert min(body_counts) >= 2, f"ordinary room lost minimum pressure: {body_counts}"
    assert max(body_counts) > min(body_counts), "enemy population stopped varying"
    assert elite_total >= 4, f"elite roll nearly disappeared ({elite_total}/108 samples)"

    print(
        "[procgen-variety] PASS "
        f"geometry={[len(geometries[s]) for s in range(9)]}/12, "
        f"enemy-kinds={[len(roster_kinds[s]) for s in range(9)]}, "
        f"rosters={[len(roster_signatures[s]) for s in range(9)]}/12, "
        f"bodies={min(body_counts)}-{max(body_counts)}, elites={elite_total}/108"
    )


if __name__ == "__main__":
    main()
