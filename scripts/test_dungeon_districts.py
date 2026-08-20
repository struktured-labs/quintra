#!/usr/bin/env python3
"""Live-ROM contract for five named, mechanically distinct depth districts."""

import re
from pathlib import Path

from pyboy import PyBoy

from quintra_topology import dungeon_size
from test_stage_archetypes import (
    EN, PL, ROM, RS, TM, generated_room, put16,
)


ROOT = Path(__file__).resolve().parent.parent
VERTICAL_STATE = (
    ROOT / "tmp/stage-states/quintra-stage-01-entry-wolfkin-easy.pyboy"
)
NOI = ROM.with_suffix(".noi").read_text()
ROOM_W, ROOM_H = 20, 17
WIDE_W, WIDE_H = 31, 31
EXT_W = WIDE_W - ROOM_W
BOTTOM_H = WIDE_H - ROOM_H
BGT_FLOOR, BGT_DOOR = 1, 3
BGT_FLOOR2, BGT_FLOOR3 = 19, 20
BGT_PILLAR, BGT_RUBBLE, BGT_SPIKES = 21, 23, 31
PASSABLE = {BGT_FLOOR, BGT_DOOR, BGT_FLOOR2, BGT_FLOOR3,
            BGT_RUBBLE, BGT_SPIKES, 33, 34}


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


EXT, BOTTOM, COMBAT, PUZZLE, ORIGIN_X, ORIGIN_Y, LABEL_TICKS, DIRECTIVE = map(
    addr,
    (
        "_room_world_extension", "_room_world_bottom",
        "_room_combat_sealed", "_room_puzzle_locked",
        "_room_bg_origin_x", "_room_bg_origin_y",
        "_room_district_label_ticks",
        "_room_encounter_kind",
    ),
)


def field_from_memory(pb):
    field = []
    for y in range(WIDE_H):
        row = []
        for x in range(WIDE_W):
            if y < ROOM_H and x < ROOM_W:
                value = pb.memory[TM + y * ROOM_W + x]
            elif y < ROOM_H:
                value = pb.memory[EXT + y * EXT_W + x - ROOM_W]
            else:
                value = pb.memory[BOTTOM + (y - ROOM_H) * WIDE_W + x]
            row.append(value & 0x7F)
        field.append(row)
    return field


def reachable(field, start=(10, 9)):
    seen = {start}
    pending = [start]
    while pending:
        x, y = pending.pop()
        for point in ((x, y - 1), (x + 1, y),
                      (x, y + 1), (x - 1, y)):
            nx, ny = point
            if (
                0 <= nx < WIDE_W
                and 0 <= ny < WIDE_H
                and point not in seen
                and field[ny][nx] in PASSABLE
            ):
                seen.add(point)
                pending.append(point)
    return seen


def reachable_bodies(field, start=(9, 8)):
    def body_ok(x, y):
        return (
            0 <= x < WIDE_W - 1 and 0 <= y < WIDE_H - 1
            and all(
                field[ty][tx] in PASSABLE
                for tx, ty in (
                    (x, y), (x + 1, y),
                    (x, y + 1), (x + 1, y + 1),
                )
            )
        )

    assert body_ok(*start)
    seen = {start}
    pending = [start]
    while pending:
        x, y = pending.pop()
        for point in ((x, y - 1), (x + 1, y),
                      (x, y + 1), (x - 1, y)):
            if point not in seen and body_ok(*point):
                seen.add(point)
                pending.append(point)
    return seen, body_ok


def disconnected_bodies(field):
    seen, body_ok = reachable_bodies(field)
    return [
        (x, y)
        for y in range(WIDE_H - 1)
        for x in range(WIDE_W - 1)
        if body_ok(x, y) and (x, y) not in seen
    ]


def logical_bg_tile(pb, x, y):
    px = (pb.memory[ORIGIN_X] + x) & 31
    py = (pb.memory[ORIGIN_Y] + y) & 31
    return pb.memory[0x9800 + py * 32 + px]


def main():
    seed = 0xCAFE1234
    labels = (
        (85, 84, 79, 86),          # GATE
        (81, 89, 80, 86, 76),      # LOWER
        (82, 86, 86, 90),          # DEEP
        (77, 91, 91, 86, 76),      # INNER
        (92, 86, 84, 76, 79),      # HEART
    )
    directive_labels = {
        1: (79, 76, 84, 90),      # TRAP
        2: (80, 84, 83, 86),      # WAVE
        3: (86, 81, 77, 79, 86),  # ELITE
        4: (92, 89, 81, 82),      # HOLD
    }
    fields = []

    def inspect(district):
        def probe(pb, _tiles):
            field = field_from_memory(pb)
            fields.append(tuple(tuple(row) for row in field))
            seen = reachable(field)
            disconnected = disconnected_bodies(field)
            assert not disconnected, (
                f"district {district} left disconnected floor: "
                f"{disconnected[:12]}")
            assert (23, 6) in seen, (
                f"district {district} sealed the eastern encounter apron")
            assert (29, 6) in seen, (
                f"district {district} pocketed the far side of the east ruin")
            assert (15, 25) in seen, (
                f"district {district} pocketed the lower ruin cloister: "
                f"{[field[y][12:19] for y in range(15, 30)]}")
            assert (26, 25) in seen, (
                f"district {district} sealed the deep encounter apron")
            expected_label = directive_labels.get(
                pb.memory[DIRECTIVE], labels[district])
            label = tuple(
                logical_bg_tile(pb, 8 + i, 1)
                for i in range(len(expected_label))
            )
            assert label == expected_label, (
                f"district {district} label mismatch: {label}")
            assert pb.memory[LABEL_TICKS] > 0, (
                f"district {district} callout timer was not armed")
            # Keep the callout clock under test, not stage-nine combat. A late
            # hostile can otherwise kill the fixture and stop room_tick before
            # the two-second presentation beat expires.
            for slot in range(32):
                base = EN + slot * 28
                pb.memory[base] = pb.memory[base + 1] = 0
            pb.memory[PL + 15] = 255
            pb.tick(130)
            faded = tuple(
                logical_bg_tile(pb, 8 + i, 1)
                for i in range(len(expected_label))
            )
            assert pb.memory[LABEL_TICKS] == 0, (
                f"district {district} callout did not expire")
            assert faded != expected_label, (
                f"district {district} label remained permanent terrain")

            # Pin one unmistakable full-field structure per depth band. These
            # samples live beyond the old 160px viewport, so a compact western
            # archetype cannot satisfy this test accidentally.
            if district == 0:
                assert all(field[y][27] == BGT_PILLAR
                           for y in (*range(2, 5), *range(10, 16)))
            elif district == 1:
                lower_wall = [field[12][x] for x in range(20, 30)]
                assert sum(value == BGT_PILLAR for value in lower_wall) >= 8, (
                    f"LOWER retaining wall changed: {lower_wall}")
                assert all(
                    value == BGT_PILLAR or x in (22, 23)
                    for x, value in zip(range(20, 30), lower_wall)
                ), f"LOWER gate moved outside its authored pair: {lower_wall}"
            elif district == 2:
                deep_wall = [field[15][x] for x in range(20, 30)]
                assert sum(value == BGT_PILLAR for value in deep_wall) == 8, (
                    f"DEEP ring lost its two-tile gate: {deep_wall}")
                deep_gap = tuple(
                    x for x, value in zip(range(20, 30), deep_wall)
                    if value != BGT_PILLAR
                )
                assert deep_gap in ((21, 22), (24, 25)), deep_gap
            elif district == 3:
                inner_columns = [
                    sum(field[y][x] == BGT_PILLAR
                        for y in (*range(2, 8), *range(10, 20),
                                  *range(22, 29)))
                    for x in (20, 21)
                ]
                assert max(inner_columns) >= 19, (
                    f"INNER processional wall missing: {inner_columns}")
            else:
                heart_wall = [field[18][x] for x in range(19, 28)]
                assert sum(value == BGT_PILLAR for value in heart_wall) == 7, (
                    f"HEART inner keep lost its gate: {heart_wall}")
                heart_gap = tuple(
                    x for x, value in zip(range(19, 28), heart_wall)
                    if value != BGT_PILLAR
                )
                assert heart_gap in ((20, 21), (23, 24)), heart_gap

            if district == 4:
                # Show the actual far-side nested Heart, not merely its label.
                for slot in range(32):
                    base = EN + slot * 28
                    pb.memory[base] = pb.memory[base + 1] = 0
                put16(pb, PL + 9, 216)
                put16(pb, PL + 11, 216)
                pb.memory[PL + 15] = 120
                pb.tick(64)
                shot = ROOT / "tmp/dungeon-heart-district.png"
                shot.parent.mkdir(exist_ok=True)
                pb.screen.image.save(shot)
        return probe

    # Stage nine owns all five complete six-cell rows. Sampling the first
    # large node in each row proves a single dungeon changes geography as the
    # player descends, independently of stage palette or run seed.
    for district in range(5):
        generated_room(
            8, seed, local_room=district * 6, probe=inspect(district)
        )

    # Pin the two exact fixed-campaign compositions that originally exposed
    # landmark/perimeter overlap. They are deliberately separate from the
    # stage-nine five-band sample above: stage archetype and district layers
    # must compose safely, not merely remain reachable in isolation.
    def campaign_reach(label, point):
        def probe(pb, _tiles):
            field = field_from_memory(pb)
            seen = reachable(field)
            assert point in seen, f"{label} remained an isolated pocket"
            disconnected = disconnected_bodies(field)
            assert not disconnected, (
                f"{label} retained disconnected floor: {disconnected[:12]}")
        return probe

    generated_room(
        4, 2064128163, local_room=2,
        # Row five now belongs to the mutable WAX/WANE architecture, so its
        # old sample can correctly be solid in one Law state. Pin the stable
        # floor below it; the full-body connectivity assertion still proves
        # that both halves of the ruin rejoin through the generated gap.
        probe=campaign_reach("stage-five Gate east ruin", (26, 7)),
    )
    generated_room(
        5, 2064128163, local_room=19,
        probe=campaign_reach("stage-six Inner lower cloister", (15, 25)),
    )

    # Compose every stage-specific terrain archetype with every depth row it
    # actually owns. This catches pockets created only by the overlap of two
    # individually safe procedural layers before a full campaign can find one.
    def matrix_probe(stage, local):
        def probe(pb, _tiles):
            disconnected = disconnected_bodies(field_from_memory(pb))
            assert not disconnected, (
                f"stage {stage + 1} local {local} disconnected body cells: "
                f"{disconnected[:12]}")
        return probe

    for stage in range(9):
        locals_to_check = [1]
        # The last three nodes are compact merchant/sanctuary/Colossus
        # cadence, so their stale wide backing storage is outside this test.
        locals_to_check.extend(range(6, dungeon_size(stage) - 3, 6))
        for local in locals_to_check:
            generated_room(
                stage, 2064128163, local_room=local,
                probe=matrix_probe(stage, local),
            )

    assert len(set(fields)) == 5, "five depth bands collapsed to one field"
    for left in range(5):
        for right in range(left + 1, 5):
            changed = sum(
                fields[left][y][x] != fields[right][y][x]
                for y in range(WIDE_H) for x in range(WIDE_W)
            )
            assert changed >= 80, (
                f"districts {left}/{right} differ at only {changed} tiles")

    # Exercise an actual vertical maze seam. Row changes are the only physical
    # north/south dungeon edges, so the destination generator must leave the
    # dedicated A4→D5 boundary bell resident on CH1.
    pb = PyBoy(str(ROM), window="null", cgb=True)
    try:
        with VERTICAL_STATE.open("rb") as handle:
            pb.load_state(handle)
        for _ in range(12):
            pb.tick()
        # Every generated fold guarantees the objective branch 1→10. It is
        # both a real maze edge and the first named Gate→Lower boundary.
        source, target = 1, 10
        assert pb.memory[RS + 1] == source

        for slot in range(32):
            base = EN + slot * 28
            pb.memory[base] = pb.memory[base + 1] = 0
        pb.memory[COMBAT] = 0
        pb.memory[PUZZLE] = 0
        put16(pb, PL + 9, 72)
        put16(pb, PL + 11, 232)
        for _ in range(180):
            pb.tick()
            if pb.memory[RS + 1] == target:
                break
        assert pb.memory[RS + 1] == target, "vertical district seam stalled"
        # Cell state advances before the destination finishes drawing, and
        # wider district silhouettes legitimately vary that redraw latency.
        # Observe the complete low-A4 -> D5 figure instead of sampling one
        # brittle frame after the transition. NR13 is write-only and NR14 has
        # read masks on real hardware/PyBoy, so the two fresh envelopes are
        # the stable CH1 contract (and cannot come from the CH2 stage melody).
        heard_low = pb.memory[0xFF12] == 0x94
        heard_answer = False
        for _ in range(120):
            pb.tick()
            envelope = pb.memory[0xFF12]
            if envelope == 0x94:
                heard_low = True
            elif heard_low and envelope == 0xB4:
                heard_answer = True
                break
        assert heard_low and heard_answer, (
            "district boundary bell did not complete its two attacks: "
            f"low={heard_low} answer={heard_answer} "
            f"NR12={pb.memory[0xFF12]:#04x}")
    finally:
        pb.stop(save=False)

    print("[dungeon-districts] PASS GATE→LOWER→DEEP→INNER→HEART "
          "full-field silhouettes + fading callouts + connected aprons "
          "+ boundary bell")


if __name__ == "__main__":
    main()
