#!/usr/bin/env python3
"""Live-ROM contracts for the three procedural dungeon puzzle families."""

import re
from pathlib import Path

from quintra_topology import (
    STAGE_START, dungeon_direction, dungeon_predecessor, dungeon_size,
    mission_graph,
)
from make_stage_states import (
    boot_to_stage, cross_graph_edge, normalize_compact_source,
    select_rom_topology, symbol_addresses,
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
    stage_index = stage - 1
    seed = 0x51A6D00D
    select_rom_topology(ROM)
    addrs = symbol_addresses(ROM)
    pb, _ram, _entry = boot_to_stage(ROM, addrs, stage_index, "normal", 0)
    trial = mission_graph(
        dungeon_size(stage_index), seed, stage_index)["trial"]
    target = STAGE_START[stage_index] + trial
    if pb.memory[RS + 1] != target:
        # Cross a reciprocal live maze edge. The old shortcut painted a
        # portal into room_tilemap while the opening room used its 31x31
        # streamed backing store, so the engine correctly never saw it.
        source, direction_id = dungeon_predecessor(
            trial, dungeon_size(stage_index), seed, stage_index)
        pb.memory[RS + 1] = STAGE_START[stage_index] + source
        pb.memory[RS + 6] = 0xFF
        pb.memory[LOCKED] = 0
        pb.memory[COMBAT] = 0
        normalize_compact_source(pb, addrs)
        for i in range(32):
            ep = EN + i * 28
            if pb.memory[ep] == 2:
                pb.memory[ep] = pb.memory[ep + 1] = 0
        direction = ("up", "right", "down", "left")[direction_id]
        cross_graph_edge(pb, PL, TM, direction)
        for _ in range(120):
            pb.tick()
            if pb.memory[RS + 1] == target:
                break
        pb.button_release(direction)
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


def body_component(tiles, start):
    """Return compact-court cells reachable by the champion's 2x2 body."""
    walkable = {1, 3, 7, 19, 20, 23, 31, 33, 34, *range(9, 19)}

    def body_ok(x, y):
        return (1 <= x <= 19 and 1 <= y <= 16
                and all(tiles[ty * 20 + tx] in walkable
                        for tx, ty in ((x - 1, y - 1), (x, y - 1),
                                       (x - 1, y), (x, y))))

    seen, pending = {start}, [start]
    while pending:
        x, y = pending.pop()
        for cell in ((x, y - 1), (x + 1, y),
                     (x, y + 1), (x - 1, y)):
            if cell not in seen and body_ok(*cell):
                seen.add(cell)
                pending.append(cell)
    return seen


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


def solve_runes(pb, runes):
    """Discover a deterministic phrase through only its visible lit feedback."""
    prefix = []

    def lit(rune):
        x, y = rune
        return pb.memory[TM + y * 20 + x] == 19

    while pb.memory[LOCKED] and len(prefix) < len(runes):
        found = None
        for candidate in runes:
            if candidate in prefix:
                continue
            # A wrong candidate clears every rune. Replay only the known
            # prefix, exactly as a player following the tones would.
            if prefix and not all(lit(rune) for rune in prefix):
                for rune in prefix:
                    feet_on(pb, *rune)
                    step_off(pb)
            hp_before = pb.memory[PL + 2]
            feet_on(pb, *candidate)
            if not pb.memory[LOCKED] or all(lit(rune) for rune in (*prefix, candidate)):
                assert pb.memory[PL + 2] == hp_before, (
                    "correct rune damaged the champion"
                )
                found = candidate
                prefix.append(candidate)
                step_off(pb)
                break
            assert pb.memory[PL + 2] == hp_before - 1, (
                "wrong rune did not charge exactly one half-heart"
            )
            # This routine intentionally discovers the hidden order through
            # mistakes. Refill only its test vessel so later candidates can
            # verify the same live damage contract without dying mid-proof.
            pb.memory[PL + 2] = hp_before
            step_off(pb)
        assert found is not None, f"visible feedback exposed no next tone after {prefix}"
    assert not pb.memory[LOCKED], f"discovered phrase did not release seal: {prefix}"
    return prefix


def rune_sequence_contract():
    pb = load(2)
    assert pb.memory[KIND] == 2 and pb.memory[LOCKED] == 1
    runes = [(x, y) for y in range(1, 16) for x in range(1, 19)
             if pb.memory[TM + y * 20 + x] == 33]
    assert len(runes) == 4, f"stage two needs four runes, got {runes}"
    assert max(x for x, _ in runes) - min(x for x, _ in runes) >= 12
    assert max(y for _, y in runes) - min(y for _, y in runes) >= 8
    order = solve_runes(pb, runes)
    assert len(order) == 4 and len(set(order)) == 4
    pb.stop(save=False)


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
    assert fixture_count >= (1 if pb.memory[KIND] == 1 else 5), \
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
        assert len(runes) == 5, f"stage three Waystone needs five runes: {runes}"
        solve_runes(pb, runes)
    assert pb.memory[LOCKED] == 0, "generated Waystone could not be solved"
    assert pb.memory[RS + 27] & (1 << 7), \
        "Waystone solve did not persist its stable route bit"
    pb.stop(save=False)


def wide_waystone_circuit_contract():
    # The fixed full-campaign world once produced a horizontal Stage 7 court
    # whose first rune was reachable but whose lower note was an isolated
    # floor island. Mandatory phrases must retain their unknown order without
    # asking the player to cross solid procedural scenery.
    stage = 6
    seed = 2064128163
    waystone = mission_graph(dungeon_size(stage), seed, stage)["waystone"]

    def probe(pb, tiles):
        assert pb.memory[KIND] == 2 and pb.memory[LOCKED] == 1
        runes = [(x, y) for y in range(1, 16) for x in range(1, 19)
                 if pb.memory[TM + y * 20 + x] == 33]
        assert len(runes) == 5, f"Stage 7 Waystone lost notes: {runes}"
        reachable = body_component(tiles, runes[0])
        assert set(runes) <= reachable, (
            f"wide-court Waystone marooned required notes: "
            f"{set(runes) - reachable}")

    generated_room(stage, seed, local_room=waystone, probe=probe)


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
        xs = (4, 8, 12, 16)
        masks = (0x03, 0x07, 0x0E, 0x0C)

        def state():
            return sum((pb.memory[TM + 8 * 20 + x] == 19) << i
                       for i, x in enumerate(xs))

        initial = state()
        assert initial != 0x0F, "deep Aether Lattice spawned already solved"
        # Solve from the cartridge's visible state, not from its seed. This
        # mirrors a player reasoning about the transformation rule and proves
        # the generated fixture is genuinely solvable in three/four presses.
        pending = [(initial, ())]
        seen = {initial}
        solution = None
        while pending:
            current, path = pending.pop(0)
            if current == 0x0F:
                solution = path
                break
            for i, mask in enumerate(masks):
                nxt = current ^ mask
                if nxt not in seen:
                    seen.add(nxt)
                    pending.append((nxt, path + (i,)))
        assert solution is not None and len(solution) >= 3, \
            f"deep Aether Lattice was trivial or unsolvable: {initial:04b}"
        for press in solution:
            before = state()
            feet_on(pb, xs[press], 8)
            step_off(pb)
            assert state() == (before ^ masks[press]), \
                f"plate {press} did not transform its neighbor lattice"
        assert pb.memory[RS + 28] & bit, \
            "solved deep Aether Lattice did not persist its remote phase bit"
        assert state() == 0x0F, "solved Aether Lattice did not finish fully lit"

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
    wide_waystone_circuit_contract()
    opening_shop_is_not_a_puzzle()
    deep_phase_contract()
    print("[puzzles] PASS generated Trial/Waystone + connected ordered runes "
          "+ service exclusion + four-panel remote Aether Lattice/gate circuit "
          "+ persistent gate crossing")


if __name__ == "__main__":
    main()
