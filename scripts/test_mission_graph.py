#!/usr/bin/env python3
"""Live-ROM contract: every stage resolves a valid mission before its room."""

from pyboy import PyBoy

from quintra_topology import STAGE_START, dungeon_size, mission_graph
from test_stage_archetypes import EN, PL, ROM, RS, TM, addr, put16


RS_ROOM, RS_SEED, RS_STAGE = 1, 2, 11
RS_WORLD_MODE, RS_WORLD_SCREEN = 17, 18
RS_PUZZLES, RS_PHASE = 27, 28
RS_MISSION_READY = 37
MISSION_READY = 0xA5
ENTITY_SIZE, MAX_ENTITIES = 28, 32
BGT_PORTAL = 34
ROOM_COMMIT = addr("_room_puzzle_kind")
SEEDS = (0xCAFE1234, 0x51A7E001, 0xF00D739B, 0x11223344)


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    pb.button("a")
    pb.tick(240)
    return pb


def generate(pb, stage, seed):
    # Enter through the real Riftwild gate so run_state_begin_dungeon clears
    # all per-stage progress before procgen asks the graph for room semantics.
    target = STAGE_START[stage] + 4
    pb.memory[RS + RS_ROOM] = target - 1
    for i, byte in enumerate(seed.to_bytes(4, "little")):
        pb.memory[RS + RS_SEED + i] = byte
    pb.memory[RS + RS_STAGE] = stage
    pb.memory[RS + 6] = 0xFF
    pb.memory[RS + RS_WORLD_MODE] = 1
    pb.memory[RS + RS_WORLD_SCREEN] = \
        (8, 21, 34)[(stage - 1) % 3 if stage else 0]
    pb.memory[RS + RS_MISSION_READY] = 0
    # The room counter advances before a dense banked room transaction has
    # finished. A sentinel in the post-procgen puzzle-role pass prevents the
    # next synthetic sample from rewriting state mid-transition.
    pb.memory[ROOM_COMMIT] = 0xA5
    for slot in range(MAX_ENTITIES):
        base = EN + slot * ENTITY_SIZE
        pb.memory[base] = pb.memory[base + 1] = 0
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 60)
    pb.memory[PL + 15] = 120
    pb.memory[TM + 9 * 20 + 10] = BGT_PORTAL
    for _ in range(240):
        pb.tick()
        if pb.memory[RS + RS_ROOM] == target:
            break
    assert pb.memory[RS + RS_ROOM] == target
    for _ in range(480):
        pb.tick()
        if pb.memory[ROOM_COMMIT] != 0xA5:
            break
    assert pb.memory[ROOM_COMMIT] != 0xA5
    assert pb.memory[RS + RS_MISSION_READY] == MISSION_READY
    return {
        "order": pb.memory[RS + 38],
        "trial": pb.memory[RS + 39],
        "sigil": pb.memory[RS + 40],
        "warden": pb.memory[RS + 41],
        "waystone": pb.memory[RS + 42],
        "deep_warden": pb.memory[RS + 43],
        "deep_switch": pb.memory[RS + 44],
        "deep_gate": pb.memory[RS + 45],
    }


def main():
    pb = boot()
    layouts = set()
    orders = set()
    try:
        for stage in range(9):
            for seed in SEEDS:
                live = generate(pb, stage, seed)
                expected = mission_graph(dungeon_size(stage), seed, stage)
                for key in ("order", "trial", "sigil", "warden", "waystone",
                            "deep_warden", "deep_switch", "deep_gate"):
                    assert live[key] == expected[key], (
                        f"stage={stage} seed={seed:#x} {key}: "
                        f"live={live[key]} expected={expected[key]}")
                roles = [live[key] for key in ("trial", "sigil", "warden",
                    "waystone", "deep_warden", "deep_switch", "deep_gate")]
                assert len(set(roles)) == 7
                assert all(0 < cell < dungeon_size(stage) - 3
                           for cell in roles)
                sequence = [live["trial"]]
                sequence += ([live["warden"], live["sigil"]]
                    if live["order"] else [live["sigil"], live["warden"]])
                sequence += [live["waystone"], live["deep_warden"],
                             live["deep_switch"], live["deep_gate"]]
                discovery = expected["discovery"]
                positions = [discovery.index(cell) for cell in sequence]
                assert positions == sorted(positions) and len(set(positions)) == 7
                layouts.add(tuple(sequence))
                orders.add(live["order"])
                # Stage entry reset occurs before graph build, not afterward.
                assert pb.memory[RS + RS_PUZZLES] == 0
                assert pb.memory[RS + RS_PHASE] == 0
    finally:
        pb.stop(save=False)
    assert len(layouts) >= 10, f"mission layouts barely vary: {layouts}"
    assert orders == {0, 1}, f"Sigil/Warden branch never varies: {orders}"
    print("[mission-graph] PASS 36 live seed/stage graphs are distinct, "
          "reachable, ordered, and generated before room roles")


if __name__ == "__main__":
    main()
