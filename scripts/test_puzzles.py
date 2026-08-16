#!/usr/bin/env python3
"""Live-ROM contracts for the three procedural dungeon puzzle families."""

import itertools
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_START, dungeon_direction, dungeon_predecessor, dungeon_size,
    mission_graph,
)
from test_stage_archetypes import generated_room

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, EN, TM, KIND, LOCKED, COMBAT, WORLD_W, WORLD_H = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_puzzle_kind", "_room_puzzle_locked", "_room_combat_sealed",
    "_room_world_width", "_room_world_height",
))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def cross_edge(pb, source_local, target_local):
    direction = dungeon_direction(source_local, target_local)
    x, y = {
        0: (72, 0),
        1: (pb.memory[WORLD_W] - 16, 60),
        2: (72, pb.memory[WORLD_H] - 16),
        3: (0, 60),
    }[direction]
    for tx, ty in {
        0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
        2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
    }[direction]:
        pb.memory[TM + ty * 20 + tx] = 3
    put16(pb, PL + 9, x)
    put16(pb, PL + 11, y)
    for _ in range(180):
        pb.tick()


def load(stage):
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    pb.button("a")
    pb.tick(60)
    stage_index = stage - 1
    seed = 0xCAFE1234
    trial = mission_graph(
        dungeon_size(stage_index), seed, stage_index)["trial"]
    target = STAGE_START[stage_index] + trial
    # Use the real between-stage gate instead of a ROM-specific emulator
    # snapshot. ABI/layout changes can never make this puzzle test execute a
    # stale instruction stream.
    pb.memory[RS + 1] = target - 1
    for i, byte in enumerate(seed.to_bytes(4, "little")):
        pb.memory[RS + 2 + i] = byte
    pb.memory[RS + 11] = stage_index
    pb.memory[RS + 12] = pb.memory[RS + 13] = 0
    pb.memory[RS + 17] = 1
    pb.memory[RS + 18] = 6
    pb.memory[RS + 37] = 0
    for i in range(32):
        ep = EN + i * 28
        pb.memory[ep] = pb.memory[ep + 1] = 0
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 60)
    pb.memory[TM + 9 * 20 + 10] = 34
    for _ in range(30):
        pb.tick()
        if pb.memory[RS + 1] == target:
            break
    assert pb.memory[RS + 1] == target
    for _ in range(90):
        pb.tick()
    return pb


def feet_on(pb, tx, ty):
    put16(pb, PL + 9, tx * 8 - 8)
    put16(pb, PL + 11, ty * 8 - 12)
    for _ in range(3):
        pb.tick()


def step_off(pb):
    feet_on(pb, 10, 13)


def push_seal_contract():
    pb = load(1)
    assert pb.memory[KIND] == 1 and pb.memory[LOCKED] == 1
    assert not any(pb.memory[EN + i * 28] == 2 for i in range(32)), (
        "push puzzle retained mandatory hostiles")
    blocks = [(x, y) for y in range(1, 16) for x in range(1, 19)
              if pb.memory[TM + y * 20 + x] == 25]
    assert len(blocks) == 1, f"push seal needs one readable cairn, got {blocks}"
    bx, by = blocks[0]
    put16(pb, PL + 9, bx * 8 - 16)
    put16(pb, PL + 11, by * 8 - 8)
    pb.button_press("right")
    for _ in range(120):
        pb.tick()
        if pb.memory[LOCKED] == 0:
            break
    pb.button_release("right")
    assert pb.memory[LOCKED] == 0, "moving the ordinary cairn did not release seal"
    assert pb.memory[RS + 27] & 1, "Trial solve did not persist its stable bit"
    # Large dungeon courts continue beyond the legacy 20x17 viewport. Door
    # release must target the real 31x31 perimeter; stamping the old south
    # edge at y=16 leaves two conspicuous gold door tiles in mid-room.
    if pb.memory[WORLD_H] > 17 * 8:
        interior_south = (pb.memory[TM + 16 * 20 + 9],
                          pb.memory[TM + 16 * 20 + 10])
        assert 3 not in interior_south, (
            f"push solve stamped a false interior south door: {interior_south}")
    if pb.memory[WORLD_W] > 20 * 8:
        interior_east = (pb.memory[TM + 8 * 20 + 19],
                         pb.memory[TM + 9 * 20 + 19])
        assert 3 not in interior_east, (
            f"push solve stamped a false interior east door: {interior_east}")
    pb.stop(save=False)


def try_rune_order(order):
    pb = load(2)
    assert pb.memory[KIND] == 2 and pb.memory[LOCKED] == 1
    runes = [(x, y) for y in range(1, 16) for x in range(1, 19)
             if pb.memory[TM + y * 20 + x] == 33]
    assert len(runes) == 3, f"sequence needs three runes, got {runes}"
    feedback_seen = False
    for index in order:
        tx, ty = runes[index]
        feet_on(pb, tx, ty)
        feedback_seen |= pb.memory[TM + ty * 20 + tx] == 19
        step_off(pb)
    solved = pb.memory[LOCKED] == 0
    pb.stop(save=False)
    return solved, feedback_seen


def rune_sequence_contract():
    solved_orders = 0
    feedback = False
    for order in itertools.permutations(range(3)):
        solved, seen = try_rune_order(order)
        solved_orders += int(solved)
        feedback |= seen
    assert solved_orders == 1, f"expected one deterministic rune order, got {solved_orders}"
    assert feedback, "correct rune steps gave no lit-tile feedback"


def exit_to(pb, target, stage):
    source = pb.memory[RS + 1] - STAGE_START[stage]
    destination = target - STAGE_START[stage]
    cross_edge(pb, source, destination)
    # room_counter changes before the streamed slide and destination role
    # finish. Observe the completed room, not that intentional mid-slide
    # checkpoint exposed by PyBoy's per-VBlank scheduler.
    for _ in range(180):
        pb.tick()
        if pb.memory[KIND] == 4 and not (pb.memory[0xFF42] or pb.memory[0xFF43]):
            break


def late_depth_puzzle_contract():
    # Expanded dungeons spend their new depth on a second authored puzzle
    # beat at local room seven, rather than padding the route with only
    # ordinary extermination rooms.
    pb = load(3)
    seed = sum(pb.memory[RS + 2 + i] << (8 * i) for i in range(4))
    waystone = mission_graph(dungeon_size(2), seed, 2)["waystone"]
    source, _ = dungeon_predecessor(waystone, dungeon_size(2), seed, 2)
    target = STAGE_START[2] + waystone
    pb.memory[RS + 1] = STAGE_START[2] + source
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[COMBAT] = 0
    pb.memory[LOCKED] = 0
    cross_edge(pb, source, waystone)
    for _ in range(60):
        pb.tick()
        if (pb.memory[RS + 1] == target and pb.memory[KIND] in (1, 2)
                and pb.memory[LOCKED]):
            break
    assert pb.memory[RS + 1] == target, "could not enter late-depth puzzle room"
    assert pb.memory[KIND] in (1, 2) and pb.memory[LOCKED] == 1, \
        "generated Waystone became filler instead of a mechanical puzzle"
    assert not any(pb.memory[EN + i * 28] == 2 for i in range(32)), \
        "late-depth puzzle retained mandatory hostiles"
    fixture_count = sum(
        pb.memory[TM + y * 20 + x] in (25, 33)
        for y in range(1, 16) for x in range(1, 19))
    assert fixture_count >= (1 if pb.memory[KIND] == 1 else 3), \
        "late-depth puzzle has no readable fixture"
    if pb.memory[KIND] == 1:
        bx, by = next(
            (x, y) for y in range(1, 16) for x in range(1, 19)
            if pb.memory[TM + y * 20 + x] == 25
        )
        put16(pb, PL + 9, bx * 8 - 16)
        put16(pb, PL + 11, by * 8 - 8)
        pb.button_press("right")
        for _ in range(120):
            pb.tick()
            if not pb.memory[LOCKED]:
                break
        pb.button_release("right")
    else:
        runes = [
            (x, y) for y in range(1, 16) for x in range(1, 19)
            if pb.memory[TM + y * 20 + x] == 33
        ]
        # Every wrong contact resets visibly. Trying all six short orders with
        # a step-off between plates therefore solves through ordinary input
        # without peeking at private rune_order state.
        for order in itertools.permutations(runes):
            for tx, ty in order:
                feet_on(pb, tx, ty)
                step_off(pb)
                if not pb.memory[LOCKED]:
                    break
            if not pb.memory[LOCKED]:
                break
    assert pb.memory[LOCKED] == 0, "generated Waystone could not be solved"
    assert pb.memory[RS + 27] & (1 << 7), \
        "Waystone solve did not persist its stable route bit"
    pb.stop(save=False)


def opening_shop_is_not_a_puzzle():
    pb = load(1)
    # The merchant remains the generated footprint's size-3 service cell.
    target_local = dungeon_size(0) - 3
    target = STAGE_START[0] + target_local
    seed = sum(pb.memory[RS + 2 + i] << (8 * i) for i in range(4))
    source, _ = dungeon_predecessor(target_local, dungeon_size(0), seed, 0)
    pb.memory[RS + 1] = STAGE_START[0] + source
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[COMBAT] = 0
    pb.memory[LOCKED] = 0
    cross_edge(pb, source, target_local)
    for _ in range(60):
        pb.tick()
        if pb.memory[RS + 1] == target and pb.memory[KIND] == 0:
            break
    assert pb.memory[RS + 1] == target
    assert pb.memory[KIND] == 0 and pb.memory[LOCKED] == 0, \
        "opening shop collided with the late-depth puzzle role"
    pb.stop(save=False)


def deep_phase_contract():
    bit = 1 << 2

    def switch_probe(pb, _tiles):
        assert pb.memory[KIND] == 3 and pb.memory[LOCKED] == 0
        assert not (pb.memory[RS + 28] & bit)
        feet_on(pb, 10, 8)
        step_off(pb)
        assert pb.memory[RS + 28] & bit, \
            "local-room-12 deep switch did not persist its phase bit"

    def closed_gate_probe(pb, _tiles):
        assert pb.memory[KIND] == 4 and pb.memory[LOCKED] == 0
        assert all(pb.memory[TM + 11 * 20 + x] == 21 for x in range(4, 16))
        assert all(pb.memory[TM + 11 * 20 + x] != 21
                   for x in (2, 3, 16, 17)), \
            "closed deep wall lost its body-width anti-softlock detours"

    def open_gate_probe(pb, _tiles):
        assert pb.memory[KIND] == 4 and pb.memory[LOCKED] == 0
        assert all(pb.memory[TM + 11 * 20 + x] == 19 for x in range(4, 16))
        assert pb.memory[RS + 27] & (1 << 6), \
            "revisiting the opened mission gate did not persist its crossing"

    seed = 0xDEED1200
    graph = mission_graph(dungeon_size(0), seed, 0)
    generated_room(0, seed, local_room=graph["deep_switch"], probe=switch_probe)
    generated_room(0, seed, local_room=graph["deep_gate"], dungeon_phase=0,
                   probe=closed_gate_probe)
    generated_room(0, seed, local_room=graph["deep_gate"], dungeon_phase=bit,
                   probe=open_gate_probe)


def main():
    push_seal_contract()
    rune_sequence_contract()
    late_depth_puzzle_contract()
    opening_shop_is_not_a_puzzle()
    deep_phase_contract()
    print("[puzzles] PASS generated Trial/Waystone + ordered runes + service exclusion "
          "+ remote deep switch/gate circuit + persistent gate crossing")


if __name__ == "__main__":
    main()
