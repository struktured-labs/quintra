#!/usr/bin/env python3
"""Live-ROM contract: seeds vary collision, rosters, alphas, and encounter size.

The Rust property test covers the deterministic base generator exhaustively.
This companion samples the linked cartridge after stage architecture and
entity spawning, preventing a future C-side change from leaving procgen varied
only in floor speckles.
"""
from collections import defaultdict

from pyboy import PyBoy
from quintra_topology import (
    STAGE_START, dungeon_predecessor, dungeon_size, mission_graph,
)
from make_stage_states import cross_graph_edge, normalize_compact_source

from test_stage_archetypes import (
    EN, PL, ROM, ROOM_H, ROOM_W, RS, TM, addr, put16,
    wait_for_generated_room,
)


SEEDS = tuple((0xA511E9B3 * index + 0x51A7E001) & 0xFFFFFFFF
              for index in range(12))
FLOORISH = {1, 19, 20, 23}
ENTITY_SIZE = 28
MAX_ENTITIES = 32
ENT_ENEMY = 2
EF_ACTIVE = 0x01
EF_ELITE = 0x20
EF_ALPHA = 0x40
DIRECTIVE = addr("_room_encounter_kind")
ROSTER_KIND = addr("_room_roster_kind")
ROSTER_PRIMARY = addr("_room_roster_primary")
ROSTER_SECONDARY = addr("_room_roster_secondary")
SOURCE_ADDRS = {
    name: addr(name) for name in (
        "_procgen_current_room_is_large", "_room_world_width",
        "_room_world_height", "_room_camera_x", "_room_camera_y",
    )
}
PUZZLE_LOCKED = addr("_room_puzzle_locked")
COMBAT_SEALED = addr("_room_combat_sealed")
ROOM_COMMIT = addr("_room_puzzle_kind")

ROOM_ROSTER_MIXED = 0
ROOM_ROSTER_BROOD = 1
ROOM_ROSTER_PAIR = 2
ROOM_ROSTER_COMMAND = 3
ROOM_FILL_SPECIALISTS = {19, 20, 21, 27, 30, 32}


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    # Dense wide-room population continues after the title has switched to
    # the room screen. Do not rewrite run state while that first banked entry
    # transaction still owns the entity table.
    for _ in range(240):
        pb.tick()
    return pb


def sample_stage_entry(pb, stage, seed):
    # Sample a real ordinary combat court, not one of the generated Trial,
    # Sigil, Warden, Waystone, switch/gate, shop, or sanctuary roles. Mission
    # placement is seed-first now, so a fixed local room can legitimately be
    # a three-body Warden beat rather than a baseline density sample.
    roles = set(mission_graph(dungeon_size(stage), seed, stage)["sequence"])
    candidates = [
        cell for cell in (4, 6, 10, 12, 13, 14, 16)
        if cell < dungeon_size(stage) - 3
        and cell not in roles and cell != 15
    ]
    # Spread the twelve seed probes over several ordinary districts instead
    # of always taking the numerically first legal cell. That measures the
    # generated dungeon's collision vocabulary, not twelve recolorings of
    # one recurring landmark position.
    local = candidates[((seed >> 24) ^ seed) % len(candidates)]
    source, direction = dungeon_predecessor(
        local, dungeon_size(stage), seed, stage)
    target = STAGE_START[stage] + local
    pb.memory[RS + 1] = STAGE_START[stage] + source
    for offset, byte in enumerate(seed.to_bytes(4, "little")):
        pb.memory[RS + 2 + offset] = byte
    pb.memory[RS + 6] = 0xFF       # center entry; no stale directional lane
    pb.memory[RS + 11] = stage
    pb.memory[RS + 12] = 0         # pending_unseal
    pb.memory[RS + 13] = 0         # secret_pending
    pb.memory[RS + 36] = 0         # rebuild dungeon law for injected seed
    pb.memory[RS + 37] = 0         # rebuild seed-first mission roles
    # Each injection models a fresh first visit. The same emulator samples
    # all stages, so clear prior synthetic visit/hunt history explicitly.
    for offset in range(52, 57):
        pb.memory[RS + offset] = 0
    pb.memory[RS + 17] = 0
    pb.memory[PL + 2] = pb.memory[PL + 1]
    pb.memory[PL + 15] = 60
    for slot in range(MAX_ENTITIES):
        base = EN + slot * ENTITY_SIZE
        pb.memory[base] = pb.memory[base + 1] = 0
    pb.memory[PUZZLE_LOCKED] = 0
    pb.memory[COMBAT_SEALED] = 0
    # room_counter changes at the start of the banked doorway transaction,
    # well before a dense 16-body court has finished spawning. The compact
    # tilemap can remain stable throughout that in-place rebuild, so use the
    # post-procgen puzzle-role pass as the authoritative commit edge.
    pb.memory[ROOM_COMMIT] = 0xA5
    normalize_compact_source(pb, SOURCE_ADDRS)
    direction_name = ("up", "right", "down", "left")[direction]
    cross_graph_edge(pb, PL, TM, direction_name)
    for _ in range(120):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    pb.button_release(direction_name)
    assert pb.memory[RS + 1] == target, (
        f"could not enter stage={stage} seed={seed:#x}; "
        f"room={pb.memory[RS + 1]} world={pb.memory[RS + 17]}"
    )
    for _ in range(480):
        pb.tick()
        if pb.memory[ROOM_COMMIT] != 0xA5:
            break
    assert pb.memory[ROOM_COMMIT] != 0xA5, (
        f"room generation did not commit for stage={stage} seed={seed:#x}"
    )
    tiles = wait_for_generated_room(pb)
    hostiles = []
    elite_count = 0
    for slot in range(MAX_ENTITIES):
        base = EN + slot * ENTITY_SIZE
        flags = pb.memory[base + 1]
        if pb.memory[base] == ENT_ENEMY and flags & EF_ACTIVE:
            hostiles.append(pb.memory[base + 17])
            elite_count += bool(flags & (EF_ELITE | EF_ALPHA))
    # Collapse only non-interactive floor texture/rubble. Walls, cover,
    # hazards, pots, blocks, secrets, doors, and portals retain identity.
    geometry = tuple(1 if tile in FLOORISH else tile for tile in tiles)
    return (
        geometry,
        tuple(sorted(hostiles)),
        elite_count,
        pb.memory[DIRECTIVE],
        pb.memory[ROSTER_KIND],
        pb.memory[ROSTER_PRIMARY],
        pb.memory[ROSTER_SECONDARY],
    )


def main():
    geometries = defaultdict(set)
    roster_kinds = defaultdict(set)
    roster_signatures = defaultdict(set)
    body_counts = []
    body_counts_by_stage = defaultdict(list)
    body_counts_by_kind = defaultdict(list)
    kinds_by_stage = defaultdict(list)
    kinds_seen = set()
    roster_grammars = defaultdict(list)
    grammars_by_stage = defaultdict(set)
    elite_total = 0
    pb = boot()
    try:
        for stage in range(9):
            for seed in SEEDS:
                (geometry, roster, elites, kind, grammar,
                 primary, secondary) = sample_stage_entry(pb, stage, seed)
                geometries[stage].add(geometry)
                roster_kinds[stage].update(roster)
                roster_signatures[stage].add(roster)
                body_counts.append(len(roster))
                body_counts_by_stage[stage].append(len(roster))
                body_counts_by_kind[kind].append(len(roster))
                kinds_by_stage[stage].append(kind)
                kinds_seen.add(kind)
                grammars_by_stage[stage].add(grammar)
                roster_grammars[grammar].append(
                    (stage, roster, primary, secondary))
                elite_total += elites
                if len(roster) >= 3:
                    assert elites == 1, (
                        f"stage {stage + 1} seed={seed:#x} grammar={grammar} "
                        f"directive={kind} roster={roster} has {elites} alphas")
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
        assert len(grammars_by_stage[stage]) >= 3, (
            f"stage {stage + 1} exposed only room roster grammars "
            f"{sorted(grammars_by_stage[stage])}"
        )
    assert set(roster_grammars) == {
        ROOM_ROSTER_MIXED,
        ROOM_ROSTER_BROOD,
        ROOM_ROSTER_PAIR,
        ROOM_ROSTER_COMMAND,
    }, f"room roster grammar collapsed: {sorted(roster_grammars)}"

    # Themed rooms are a structural contract, not a lucky weighted sample.
    # Broods own one species; pairs alternate two compatible species; command
    # rooms contain exactly one stage-native leader plus one minion species.
    # Mixed rooms intentionally retain the old unrestricted weighted pool.
    for stage, roster, primary, secondary in roster_grammars[ROOM_ROSTER_BROOD]:
        assert primary not in ROOM_FILL_SPECIALISTS, (
            f"stage {stage + 1} repeated specialist {primary} as a brood")
        if not roster:  # trap hush; its later spawn inherits this grammar
            continue
        assert set(roster) == {primary}, (
            f"stage {stage + 1} brood dissolved into {roster}; primary={primary}"
        )
    for grammar in (ROOM_ROSTER_PAIR, ROOM_ROSTER_COMMAND):
        for stage, roster, primary, secondary in roster_grammars[grammar]:
            assert primary not in ROOM_FILL_SPECIALISTS, (
                f"stage {stage + 1} repeated specialist {primary} in grammar {grammar}")
            assert primary != secondary
            if not roster:  # trap hush; covered live by director wave tests
                continue
            assert set(roster) <= {primary, secondary}, (
                f"stage {stage + 1} grammar {grammar} became hodgepodge "
                f"{roster}; family=({primary},{secondary})"
            )
            if len(roster) >= 2:
                assert primary in roster and secondary in roster, (
                    f"stage {stage + 1} grammar {grammar} lost one family "
                    f"member: {roster}; family=({primary},{secondary})"
                )
    assert kinds_seen == {0, 1, 2, 3, 4}, \
        f"director variety disappeared from seed sample: {sorted(kinds_seen)}"
    # Initial population now encodes encounter grammar. Trap rooms retain a
    # compact visible guard group (ordinary first-entry rooms are never empty),
    # wave rooms reserve bodies for phase two, and holds cap the starting pack
    # before timed reinforcements. The live director test owns transitions.
    for stage in range(9):
        expected_floor = 3 if stage == 0 else 4 if stage < 3 else 5
        baseline = [
            count for count, kind in zip(
                body_counts_by_stage[stage], kinds_by_stage[stage])
            if kind in (0, 3)
        ]
        assert baseline and min(baseline) >= expected_floor, (
            f"stage {stage + 1} baseline fell below {expected_floor}: {baseline}"
        )
    assert body_counts_by_kind[1] and min(body_counts_by_kind[1]) >= 3, \
        f"trap rooms lost their visible opening guard: {body_counts_by_kind[1]}"
    assert body_counts_by_kind[2] and min(body_counts_by_kind[2]) >= 2, \
        "wave openings became empty"
    assert body_counts_by_kind[4] and max(body_counts_by_kind[4]) <= 4, \
        "hold openings exceeded their reinforcement cap"
    assert max(body_counts) > min(body_counts), "enemy population stopped varying"
    assert elite_total >= 4, f"pack alpha contract disappeared ({elite_total}/108 samples)"

    print(
        "[procgen-variety] PASS "
        f"geometry={[len(geometries[s]) for s in range(9)]}/12, "
        f"enemy-kinds={[len(roster_kinds[s]) for s in range(9)]}, "
        f"rosters={[len(roster_signatures[s]) for s in range(9)]}/12, "
        f"grammars={sorted(roster_grammars)}, "
        f"bodies={min(body_counts)}-{max(body_counts)}, "
        f"directives={sorted(kinds_seen)}, alphas={elite_total}/108"
    )


if __name__ == "__main__":
    main()
