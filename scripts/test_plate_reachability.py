#!/usr/bin/env python3
"""Every walk-on puzzle plate must be reachable by a 12px walking body.

Regression for #235: KEEP's row-6 portcullis sat directly above the Aether
Lattice north plates at (4,7) and (12,7). The feet sample is (x+8, y+12),
so those plates could not be stepped on. Only Sauran's lightning could press
them, and any phrase using plate 0 or 2 soft-locked every other hero.
"""
from __future__ import annotations

import os
from collections import deque
from pathlib import Path

from quintra_topology import (
    PUZZLE_RUNE_SEQUENCE,
    dungeon_size,
    mission_graph,
    puzzle_slot_kind,
)
from test_stage_archetypes import generated_room, addr

ROOT = Path(__file__).resolve().parent.parent
ROM = Path(os.environ.get("QUINTRA_TEST_ROM", ROOT / "rom/working/quintra.gbc"))
NOI = ROM.with_suffix(".noi").read_text() if ROM.with_suffix(".noi").is_file() else ""
ROOM_W, ROOM_H = 20, 17
BGT_DOOR = 3
BGT_NOTE_0, BGT_NOTE_FLASH = 111, 121

# Mirror room_tile_walkable() closely enough for dungeon plate courts.
WALKABLE = {1, 3, 7, 23, 31}
WALKABLE.update(range(9, 21))       # HUD digits through BGT_FLOOR3
WALKABLE.update(range(33, 37))      # switch, portal, grass, path
WALKABLE.update(range(BGT_NOTE_0, BGT_NOTE_FLASH + 1))

def rune_addrs():
    names = (
        "_room_rune_count", "_room_rune_x", "_room_rune_y",
    )
    return {name: addr(name) for name in names}


KIND = addr("_room_puzzle_kind") if NOI else 0


# #235 repros: Easy Corvin seeds on stage 6 (KEEP) where both north plates
# were blocked. Other seeds cover every stage's deep-switch row plus the
# early-game rune-sequence Trial / Waystone rooms.
REPRO = (
    (5, 2064128949),
    (5, 2064128583),
)
SWEEP_SEEDS = (0xCAFE1234, 0xCAFE1235, 0x51A6D00D, 0xDEADBEEF, 0x7B081BB4)


def tile(tiles, x, y):
    return tiles[y * ROOM_W + x]


def body_ok(tiles, x, y):
    """True when the 12px feet box can occupy the 2x2 whose SE tile is (x, y)."""
    if not (1 <= x <= ROOM_W - 1 and 1 <= y <= ROOM_H - 1):
        return False
    return all(
        tile(tiles, tx, ty) in WALKABLE
        for tx, ty in ((x - 1, y - 1), (x, y - 1), (x - 1, y), (x, y))
    )


def flood_from(tiles, starts):
    seen = {pos for pos in starts if body_ok(tiles, *pos)}
    todo = deque(seen)
    while todo:
        x, y = todo.popleft()
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if (nx, ny) not in seen and body_ok(tiles, nx, ny):
                seen.add((nx, ny))
                todo.append((nx, ny))
    return seen


def door_starts(tiles):
    """Body positions whose 2x2 includes a real door, plus wide-court seams.

    Wide 31x31 courts turn the compact east/south edges into interior floor
    (not BGT_DOOR); those two seams are valid approaches. Hardcoded cardinal
    aprons are not used unless they are actually walkable.
    """
    starts = set()
    for y in range(ROOM_H):
        for x in range(ROOM_W):
            if tile(tiles, x, y) != BGT_DOOR:
                continue
            for bx, by in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1)):
                if body_ok(tiles, bx, by):
                    starts.add((bx, by))
    for pos in ((19, 9), (10, 16)):
        if body_ok(tiles, *pos):
            starts.add(pos)
    return starts


def row_slice(tiles, y, x0=0, x1=17):
    return " ".join(f"{tile(tiles, x, y):3d}" for x in range(x0, x1 + 1))


def plate_positions(pb):
    addrs = rune_addrs()
    count = pb.memory[addrs["_room_rune_count"]]
    xs, ys = addrs["_room_rune_x"], addrs["_room_rune_y"]
    return [(pb.memory[xs + i], pb.memory[ys + i]) for i in range(count)]


def assert_plates_reachable(label, pb, tiles, expected=None):
    kind = pb.memory[KIND]
    plates = plate_positions(pb)
    assert plates, f"{label}: no rune plates published (kind={kind})"
    if expected is not None:
        assert plates == list(expected), (
            f"{label}: plate positions {plates} != {list(expected)}")
    starts = door_starts(tiles)
    assert starts, f"{label}: no walkable door or wide-court seam to start from"
    from_doors = flood_from(tiles, starts)
    missing = [plate for plate in plates if plate not in from_doors]
    from_first = flood_from(tiles, [plates[0]])
    stranded = [plate for plate in plates[1:] if plate not in from_first]
    if missing or stranded:
        why = []
        if missing:
            why.append(f"unreachable from doors: {missing}")
        if stranded:
            why.append(f"not connected to plate {plates[0]}: {stranded}")
        raise AssertionError(
            f"{label}: {' / '.join(why)} "
            f"(kind={kind}, plates={plates})\n"
            f"  row 5: {row_slice(tiles, 5)}\n"
            f"  row 6: {row_slice(tiles, 6)}\n"
            f"  row 7: {row_slice(tiles, 7)}\n"
            f"  row 8: {row_slice(tiles, 8)}\n"
            f"  row 9: {row_slice(tiles, 9)}"
        )


def cases():
    seen = set()
    for stage, seed in REPRO:
        graph = mission_graph(dungeon_size(stage), seed, stage)
        seen.add((stage, seed, graph["deep_switch"], "aether"))
        yield stage, seed, graph["deep_switch"], "aether"
    for stage in range(9):
        for seed in SWEEP_SEEDS:
            graph = mission_graph(dungeon_size(stage), seed, stage)
            key = (stage, seed, graph["deep_switch"], "aether")
            if key not in seen:
                seen.add(key)
                yield key
            for slot, role in ((0, "trial"), (1, "waystone")):
                if puzzle_slot_kind(seed, stage, slot) != PUZZLE_RUNE_SEQUENCE:
                    continue
                cell = graph["trial" if slot == 0 else "waystone"]
                key = (stage, seed, cell, role)
                if key not in seen:
                    seen.add(key)
                    yield key


def main():
    assert ROM.is_file() and NOI, f"missing ROM or symbols for {ROM}"
    # Fast source contract: the row-6 aprons must stay next to the existing
    # cardinal roads so a later author cannot drop only the KEEP workaround.
    puzzle = (ROOT / "src/game/puzzle.c").read_text()
    assert "floor_rect(3, 6, 3, 1);" in puzzle, \
        "north plate 0 row-6 apron missing from prepare_phase_switch"
    assert "floor_rect(11, 6, 3, 1);" in puzzle, \
        "north plate 2 row-6 apron missing from prepare_phase_switch"

    aether_plates = ((4, 7), (8, 9), (12, 7), (16, 9))
    failed = []
    checked = 0
    for stage, seed, cell, role in cases():
        label = f"stage {stage + 1} seed {seed:08x} {role} cell {cell}"
        print(f"[plate-reach] {label}", flush=True)
        def probe(pb, tiles, _label=label, _role=role):
            expected = aether_plates if _role == "aether" else None
            assert_plates_reachable(_label, pb, tiles, expected)
        try:
            generated_room(stage, seed=seed, local_room=cell, probe=probe)
        except Exception as exc:
            failed.append(f"{label}: {exc}")
            print(f"[plate-reach] FAIL {label}: {exc}", flush=True)
        else:
            checked += 1
    if failed:
        raise SystemExit(
            f"{len(failed)} unreachable plate layout(s) of {checked + len(failed)}:\n"
            + "\n".join(failed)
        )
    print(f"[plate-reach] ok: {checked} rooms, every required plate reachable")


if __name__ == "__main__":
    main()
