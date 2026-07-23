#!/usr/bin/env python3
"""Live-ROM contracts for the three procedural dungeon puzzle families."""

import itertools
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import STAGE_START, dungeon_direction

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
STATES = ROOT / "tmp/stage-states"


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, EN, TM, KIND, LOCKED, COMBAT = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_puzzle_kind", "_room_puzzle_locked", "_room_combat_sealed",
))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def cross_edge(pb, source_local, target_local):
    direction = dungeon_direction(source_local, target_local)
    x, y = {
        0: (72, 0), 1: (144, 60), 2: (72, 120), 3: (0, 60),
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
    state = STATES / f"quintra-stage-{stage:02d}-entry-wolfkin.pyboy"
    with state.open("rb") as handle:
        pb.load_state(handle)
    for _ in range(4):
        pb.tick()
    target = STAGE_START[stage - 1] + 1
    if pb.memory[RS + 1] != target:
        # Deep-test entry states now begin at true local room 0. Puzzle
        # families live in local room 1, so cross one ordinary unlocked
        # threshold through cartridge code before exercising the fixture.
        for i in range(32):
            ep = EN + i * 28
            if pb.memory[ep] == 2:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        pb.memory[COMBAT] = 0
        source = pb.memory[RS + 1] - STAGE_START[stage - 1]
        cross_edge(pb, source, 1)
        # KIND is assigned one instruction window before the family-specific
        # lock/geometry is prepared. Settle the complete destination role
        # instead of accepting that observable half-transaction.
        for _ in range(60):
            pb.tick()
        assert pb.memory[RS + 1] == target
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
    assert pb.memory[RS + 27] != 0, "push solve did not persist in dungeon bitset"
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


def phase_gate_contract():
    # Ignoring the switch produces a raised, locked wall in the next room.
    closed = load(3)
    assert closed.memory[KIND] == 3 and closed.memory[RS + 28] == 0
    exit_to(closed, STAGE_START[2] + 2, 2)
    assert closed.memory[RS + 1] == STAGE_START[2] + 2 and closed.memory[KIND] == 4
    assert closed.memory[LOCKED] == 1
    assert all(closed.memory[TM + 11 * 20 + x] == 21 for x in range(2, 18))
    closed.stop(save=False)

    # Touching the prior-room switch persists the alternate state and lowers
    # that same wall when the destination is generated.
    opened = load(3)
    feet_on(opened, 10, 8)
    step_off(opened)
    assert opened.memory[RS + 28] == 1, "phase switch did not persist"
    exit_to(opened, STAGE_START[2] + 2, 2)
    assert opened.memory[RS + 1] == STAGE_START[2] + 2 and opened.memory[KIND] == 4
    assert opened.memory[LOCKED] == 0
    assert all(opened.memory[TM + 11 * 20 + x] == 19 for x in range(2, 18))
    opened.stop(save=False)


def late_depth_puzzle_contract():
    # Expanded dungeons spend their new depth on a second authored puzzle
    # beat at local room seven, rather than padding the route with only
    # ordinary extermination rooms.
    pb = load(3)
    target = STAGE_START[2] + 7
    pb.memory[RS + 1] = target - 1
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[COMBAT] = 0
    pb.memory[LOCKED] = 0
    cross_edge(pb, 6, 7)
    for _ in range(60):
        pb.tick()
        if (pb.memory[RS + 1] == target and pb.memory[KIND] in (1, 2)
                and pb.memory[LOCKED]):
            break
    assert pb.memory[RS + 1] == target, "could not enter late-depth puzzle room"
    assert pb.memory[KIND] in (1, 2) and pb.memory[LOCKED] == 1, \
        "local room seven became filler instead of a mechanical puzzle"
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
    assert pb.memory[LOCKED] == 0, "local-room-7 Waystone could not be solved"
    assert pb.memory[RS + 27] & (1 << 7), \
        "Waystone solve did not persist the local-room-7 route bit"
    pb.stop(save=False)


def opening_shop_is_not_a_puzzle():
    pb = load(1)
    target = STAGE_START[0] + 7
    pb.memory[RS + 1] = target - 1
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 2:
            pb.memory[ep] = pb.memory[ep + 1] = 0
    pb.memory[COMBAT] = 0
    pb.memory[LOCKED] = 0
    cross_edge(pb, 6, 7)
    for _ in range(60):
        pb.tick()
        if pb.memory[RS + 1] == target and pb.memory[KIND] == 0:
            break
    assert pb.memory[RS + 1] == target
    assert pb.memory[KIND] == 0 and pb.memory[LOCKED] == 0, \
        "opening shop collided with the late-depth puzzle role"
    pb.stop(save=False)


def main():
    push_seal_contract()
    rune_sequence_contract()
    phase_gate_contract()
    late_depth_puzzle_contract()
    opening_shop_is_not_a_puzzle()
    print("[puzzles] PASS push seal + ordered rune feedback + persistent phase wall "
          "+ required late Waystone + unsealed opening shop")


if __name__ == "__main__":
    main()
