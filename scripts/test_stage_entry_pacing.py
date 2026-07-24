#!/usr/bin/env python3
"""Live-ROM contract: later stage foyers stay procedural but avoid spike rolls."""
from collections import defaultdict

from pyboy import PyBoy
from quintra_topology import STAGE_START

from test_stage_archetypes import (
    EN, PL, ROM, ROOM_H, ROOM_W, RS, TM, put16, wait_for_generated_room,
)


SEEDS = tuple((0xB5297A4D * index + 0xF07E0011) & 0xFFFFFFFF
              for index in range(12))
ENTITY_SIZE = 28
MAX_ENTITIES = 32
ENT_ENEMY = 2
EF_ACTIVE = 0x01
EF_ELITE = 0x20
BGT_PORTAL = 34


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


def sample_foyer(pb, stage, seed):
    target = STAGE_START[stage]
    pb.memory[RS + 1] = target - 1
    for offset, byte in enumerate(seed.to_bytes(4, "little")):
        pb.memory[RS + 2 + offset] = byte
    pb.memory[RS + 6] = 0xFF
    pb.memory[RS + 11] = stage
    pb.memory[RS + 12] = 0
    pb.memory[RS + 13] = 0
    pb.memory[RS + 17] = 1
    pb.memory[RS + 18] = 6
    for slot in range(MAX_ENTITIES):
        base = EN + slot * ENTITY_SIZE
        pb.memory[base] = pb.memory[base + 1] = 0
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 60)
    pb.memory[TM + 9 * ROOM_W + 10] = BGT_PORTAL
    for _ in range(30):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target, (
        f"could not enter stage {stage + 1} foyer seed={seed:#x}")
    wait_for_generated_room(pb)

    roster = []
    elite_count = 0
    total_hp = 0
    for slot in range(MAX_ENTITIES):
        base = EN + slot * ENTITY_SIZE
        flags = pb.memory[base + 1]
        if pb.memory[base] == ENT_ENEMY and flags & EF_ACTIVE:
            roster.append(pb.memory[base + 17])
            total_hp += pb.memory[base + 14]
            elite_count += bool(flags & EF_ELITE)
    return tuple(sorted(roster)), elite_count, total_hp


def main():
    pb = boot()
    signatures = defaultdict(set)
    counts = []
    max_hp = defaultdict(int)
    try:
        # The opening Crystal room retains its tutorial behavior. Every later
        # stage arrives from Riftwild or a village and owns the foyer contract.
        for stage in range(1, 9):
            for seed in SEEDS:
                roster, elites, total_hp = sample_foyer(pb, stage, seed)
                assert 2 <= len(roster) <= 4, (
                    f"stage {stage + 1} foyer count={len(roster)} roster={roster}")
                assert elites == 0, (
                    f"stage {stage + 1} foyer promoted {elites} elite(s)")
                signatures[stage].add(roster)
                counts.append(len(roster))
                max_hp[stage] = max(max_hp[stage], total_hp)
                if stage == 6 and seed == SEEDS[0]:
                    (ROM.parent.parent.parent / "tmp").mkdir(exist_ok=True)
                    pb.screen.image.save(
                        ROM.parent.parent.parent / "tmp" /
                        "golden-temple-foyer.png")
    finally:
        pb.stop(save=False)

    for stage in range(1, 9):
        assert len(signatures[stage]) >= 6, (
            f"stage {stage + 1} foyer collapsed to "
            f"{len(signatures[stage])}/12 rosters")

    print(
        "[stage-entry-pacing] PASS stages 2-9 procedural foyers "
        f"bodies={min(counts)}-{max(counts)}, elites=0, "
        f"rosters={[len(signatures[s]) for s in range(1, 9)]}/12, "
        f"max_hp={[max_hp[s] for s in range(1, 9)]}"
    )


if __name__ == "__main__":
    main()
