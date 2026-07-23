#!/usr/bin/env python3
"""Live-ROM contract: the sanctuary visibly and audibly warns of its boss."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_BOSS_ROOM, STAGE_START, dungeon_direction, dungeon_neighbor,
    dungeon_size,
)


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
BGT_DOOR = 3
BGT_WALL = 1
BGT_BOSS_GATE_L = 72
BGT_BOSS_GATE_R = 73
BGT_BOSS_GATE_TOP = 74
BGT_BOSS_GATE_BOTTOM = 75
BGPAL_DOOR = 3
BGPAL_CRACK = 4
ROOM_W = 20
ROOM_H = 17


SEALS = {
    0: ((9, 0), (10, 0), (9, 1), (10, 1)),       # north
    1: ((18, 8), (19, 8), (18, 9), (19, 9)),     # east
    2: ((9, 15), (10, 15), (9, 16), (10, 16)),   # south
    3: ((0, 8), (1, 8), (0, 9), (1, 9)),         # west
}
DOORS = {
    0: ((9, 0), (10, 0)),
    1: ((19, 8), (19, 9)),
    2: ((9, 16), (10, 16)),
    3: ((0, 8), (0, 9)),
}


def addr(name: str) -> int:
    match = re.search(rf"DEF {re.escape(name)} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


def put16(pb: PyBoy, address: int, value: int) -> None:
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = value >> 8


def put_at_edge(pb: PyBoy, player: int, direction: int) -> None:
    x, y = {
        0: (72, 0), 1: (144, 60), 2: (72, 120), 3: (0, 60),
    }[direction]
    put16(pb, player + 9, x)
    put16(pb, player + 11, y)


def redraw_room(pb: PyBoy) -> None:
    pb.button("start"); pb.tick(30)
    pb.button("b"); pb.tick(60)


def set_cardinal_fixture(pb: PyBoy, rs: int, tilemap: int, direction: int) -> None:
    for x in range(ROOM_W):
        pb.memory[tilemap + x] = BGT_WALL
        pb.memory[tilemap + (ROOM_H - 1) * ROOM_W + x] = BGT_WALL
    for y in range(ROOM_H):
        pb.memory[tilemap + y * ROOM_W] = BGT_WALL
        pb.memory[tilemap + y * ROOM_W + ROOM_W - 1] = BGT_WALL
    for door_dir in (direction, (direction + 2) & 3):
        for x, y in DOORS[door_dir]:
            pb.memory[tilemap + y * ROOM_W + x] = BGT_DOOR
    pb.memory[rs + 6] = direction
    redraw_room(pb)


def main() -> None:
    rs, player, entities, tilemap, sealed = map(addr, (
        "_run_state", "_player", "_entities", "_room_tilemap",
        "_room_combat_sealed"))
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240); pb.button("start"); pb.tick(30); pb.button("a"); pb.tick(90)
    for i in range(32 * 28):
        pb.memory[entities + i] = 0
    pb.memory[sealed] = 0
    # Local 11 sits immediately west of the opening sanctuary at local 12.
    source, sanctuary = 11, 12
    approach = dungeon_direction(source, sanctuary)
    pb.memory[rs + 1] = STAGE_START[0] + source
    pb.memory[rs + 6] = 0xFF
    pb.memory[rs + 23] = 1
    pb.memory[rs + 27] = 1 << 3
    for x, y in DOORS[approach]:
        pb.memory[tilemap + y * ROOM_W + x] = BGT_DOOR
    put_at_edge(pb, player, approach)
    for _ in range(180):
        pb.tick()
        if pb.memory[rs + 1] == STAGE_BOSS_ROOM[0] - 1:
            break
    assert pb.memory[rs + 1] == STAGE_BOSS_ROOM[0] - 1, \
        "could not enter pre-boss sanctuary"
    heard_roar = False
    for _ in range(60):
        before_audio = tuple(pb.memory[a] for a in (0xFF10, 0xFF11, 0xFF12,
                                                    0xFF42, 0xFF43))
        pb.tick()
        audio = tuple(pb.memory[a] for a in (0xFF10, 0xFF11, 0xFF12,
                                             0xFF42, 0xFF43))
        if audio != before_audio:
            heard_roar = True

    # The opening sanctuary's real boss neighbor is east; its north return
    # remains ordinary gold.
    pb.memory[0xFF4F] = 1
    boss_attr = pb.memory[0x9800 + 8 * 32 + 19]
    return_attr = pb.memory[0x9800 + 9]
    pb.memory[0xFF4F] = 0
    boss_tiles = tuple(pb.memory[0x9800 + y * 32 + x]
                       for x, y in SEALS[1])
    return_tiles = (pb.memory[0x9800 + 9], pb.memory[0x9800 + 10])
    assert boss_tiles == (BGT_BOSS_GATE_L, BGT_BOSS_GATE_R,
                          BGT_BOSS_GATE_TOP, BGT_BOSS_GATE_BOTTOM), (
        f"east boss threshold lost 16x16 skull seal: {boss_tiles}")
    assert return_tiles == (BGT_DOOR, BGT_DOOR), (
        f"ordinary return door inherited boss art: {return_tiles}")
    assert boss_attr == BGPAL_CRACK, f"boss door is not amber: {boss_attr}"
    assert return_attr == BGPAL_DOOR, (
        f"return door lost normal palette: attr={return_attr}")

    # Every actual boss-adjacent graph edge across all nine stage footprints
    # assembles the same complete skull. A boss can have two approaches.
    expected_seal = (BGT_BOSS_GATE_L, BGT_BOSS_GATE_R,
                     BGT_BOSS_GATE_TOP, BGT_BOSS_GATE_BOTTOM)
    observed_directions = set()
    for stage in range(9):
        size, boss = dungeon_size(stage), dungeon_size(stage) - 1
        for source in range(size - 1):
            for direction in range(4):
                if dungeon_neighbor(source, size, direction) != boss:
                    continue
                observed_directions.add(direction)
                pb.memory[rs + 11] = stage
                pb.memory[rs + 1] = STAGE_START[stage] + source
                pb.memory[rs + 23] = 0xFF
                pb.memory[rs + 24] = 0x01
                pb.memory[rs + 27] = 1 << 3
                set_cardinal_fixture(pb, rs, tilemap, direction)
                pb.memory[0xFF4F] = 0
                shown = tuple(pb.memory[0x9800 + y * 32 + x]
                              for x, y in SEALS[direction])
                pb.memory[0xFF4F] = 1
                attrs = tuple(pb.memory[0x9800 + y * 32 + x]
                              for x, y in SEALS[direction])
                assert shown == expected_seal, (
                    f"stage {stage + 1} cell {source} direction {direction} "
                    f"did not assemble skull seal: {shown}")
                assert attrs == (BGPAL_CRACK,) * 4, (
                    f"stage {stage + 1} direction {direction} lost amber: {attrs}")
    assert observed_directions == {1, 2, 3}, observed_directions

    # Restore the opening sanctuary's east-facing fixture for proximity audio.
    pb.memory[rs + 11] = 0
    pb.memory[rs + 1] = STAGE_BOSS_ROOM[0] - 1
    set_cardinal_fixture(pb, rs, tilemap, 1)

    # Arrival can place the hero inside the 16-pixel approach band; in that
    # case the one-shot warning is heard immediately. Otherwise, approach the
    # forward threshold explicitly and require either probe to trigger it.
    put16(pb, player + 9, 128); put16(pb, player + 11, 60)
    before_audio = tuple(pb.memory[a] for a in (0xFF10, 0xFF11, 0xFF12,
                                                0xFF42, 0xFF43))
    pb.tick()
    roar = tuple(pb.memory[a] for a in (0xFF10, 0xFF11, 0xFF12,
                                       0xFF42, 0xFF43))
    heard_roar |= roar != before_audio
    assert heard_roar, f"boss threshold never changed either roar channel: {roar}"
    pb.screen.image.save(ROOT / "tmp" / "boss-threshold-cue.png")
    pb.stop(save=False)
    print("[boss-threshold] PASS all graph approaches use 16x16 amber skull seal + proximity roar")


if __name__ == "__main__":
    main()
