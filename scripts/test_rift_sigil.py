#!/usr/bin/env python3
"""ROM contract: staged dungeon fixtures gate only the boss threshold."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_BOSS_ROOM, STAGE_START, dungeon_cell_xy, dungeon_direction,
    dungeon_predecessor, dungeon_size, mission_graph,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, EN, TM, SEALED, SIGIL_STATUS, SCREEN, HITSTOP, FRAME_COUNTER, LARGE, WORLD_W, WORLD_H, CAMERA_X, CAMERA_Y = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_combat_sealed", "_room_sigil_status", "_loop_current_screen",
    "_g_hitstop", "_loop_frame_counter", "_procgen_current_room_is_large",
    "_room_world_width", "_room_world_height",
    "_room_camera_x", "_room_camera_y"))
RS_SIGILS = 23
RS_BOSSES = 11
RS_PUZZLES = 27
BGT_VOID = 0
BGT_SWITCH = 33
BGT_MAP_BIG_UNKNOWN = 106
BGT_MAP_BIG_GOAL = 114
DEFAULT_SEED = 0xCAFE1234
RUN_REQUIRED_PUZZLES = (1 << 0) | (1 << 3) | (1 << 6) | (1 << 7)
RUN_REQUIRED_PHASE = (1 << 2) | (1 << 7)


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def put32(pb, address, value):
    for i in range(4):
        pb.memory[address + i] = (value >> (i * 8)) & 0xFF


def main():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()

    def clear_entities():
        for i in range(32 * 28):
            pb.memory[EN + i] = 0

    def compact_source():
        pb.memory[LARGE] = 0
        pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
        pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
        pb.memory[0xFF43] = pb.memory[0xFF42] = 0

    def role_door(stage, seed=DEFAULT_SEED, role="sigil"):
        graph = mission_graph(dungeon_size(stage), seed, stage)
        target = graph[role]
        source, direction = dungeon_predecessor(
            target, dungeon_size(stage), seed, stage)
        pb.memory[RS + 1] = STAGE_START[stage] + source
        pb.memory[RS + RS_BOSSES] = stage
        put32(pb, RS + 2, seed)
        pb.memory[RS + 37] = 0
        compact_source()
        for tx, ty in {
            0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
            2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
        }[direction]:
            pb.memory[TM + ty * 20 + tx] = 3
        x, y = {
            0: (72, 0), 1: (144, 60),
            2: (72, 120), 3: (0, 60),
        }[direction]
        put16(pb, PL + 9, x)
        put16(pb, PL + 11, y)
        return target

    def boss_door(stage):
        compact_source()
        size = dungeon_size(stage)
        direction = dungeon_direction(size - 2, size - 1)
        for tx, ty in {
            0: ((9, 0), (10, 0)), 1: ((19, 8), (19, 9)),
            2: ((9, 16), (10, 16)), 3: ((0, 8), (0, 9)),
        }[direction]:
            pb.memory[TM + ty * 20 + tx] = 3
        x, y = {
            0: (72, 0), 1: (144, 60),
            2: (72, 120), 3: (0, 60),
        }[direction]
        put16(pb, PL + 9, x)
        put16(pb, PL + 11, y)

    # The opening sanctuary refuses its forward door while the stage bit is absent.
    clear_entities()
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[0] - 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[RS + RS_SIGILS] = pb.memory[RS + RS_SIGILS + 1] = 0
    pb.memory[RS + RS_PUZZLES] = RUN_REQUIRED_PUZZLES
    pb.memory[RS + 28] = RUN_REQUIRED_PHASE
    pb.memory[SEALED] = 0
    boss_door(0)
    for _ in range(8):
        pb.tick()
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[0] - 1, \
        "missing Sigil did not hold boss threshold"

    # Use a fresh runtime for recovery so the gate test cannot carry private
    # timers into the pickup test (the player-visible contract is persistence,
    # not debugger mutation of an already-entered room).
    pb.stop(save=False)
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()

    # The generated role always regenerates this stage's objective until collected.
    pb.memory[RS + 6] = 0xFF
    pb.memory[RS + RS_PUZZLES] |= 1 << 0
    pb.memory[SEALED] = 0
    sigil_cell = role_door(0)
    for _ in range(240):
        pb.tick()
        if pb.memory[SIGIL_STATUS] != 2:
            break
    assert pb.memory[RS + 1] == sigil_cell and pb.memory[SIGIL_STATUS] == 5, (
        f"room transaction incomplete: room={pb.memory[RS + 1]} "
        f"status={pb.memory[SIGIL_STATUS]}")
    sigils = []
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 3 and pb.memory[ep + 17] == 11:
            sigils.append(ep)
    assert len(sigils) == 1, (
        "generated objective room did not contain exactly one Rift Sigil: "
        f"status={pb.memory[SIGIL_STATUS]} rs={list(pb.memory[RS:RS + 26])} "
        f"entities={[list(pb.memory[EN + i * 28:EN + i * 28 + 20]) for i in range(10)]}")
    # The generator has already published the Sigil by this point, but an
    # in-place Zelda-style slide may still be consuming VBlanks inside the
    # transition call. Let it finish before exercising normal room updates.
    for _ in range(60):
        pb.tick()
    ep = sigils[0]
    for i in range(32):
        other = EN + i * 28
        if other != ep:
            pb.memory[other] = pb.memory[other + 1] = 0

    # Inspect the objective before collecting it. Move the displayed cursor
    # away from its cell so YOU does not intentionally cover its GOAL icon.
    pb.memory[RS + 1] = 0
    pb.button("select")
    for _ in range(120):
        pb.tick()
    assert pb.memory[SCREEN] == 8
    pb.memory[0xFF4F] = 0
    bg = 0x9800

    def node_tile(cell):
        col, row = dungeon_cell_xy(cell)
        return pb.memory[bg + (2 + row * 3) * 32 + 1 + col * 3]

    assert node_tile(sigil_cell) == BGT_MAP_BIG_GOAL, \
        "unclaimed Sigil lacks its violet 2x2 GOAL node"
    pb.button("b")
    for _ in range(30):
        pb.tick()
    assert pb.memory[SCREEN] == 5
    pb.memory[RS + 1] = sigil_cell

    pb.memory[PL + 2] = pb.memory[PL + 1]
    pb.memory[PL + 15] = 0
    # Put the full pickup box *inside* the 6x6 Sigil, rather than merely
    # kissing its corner. This stays stable if the hero feet box is refined.
    put16(pb, PL + 9, (pb.memory[ep + 3] - 2) & 0xFF)
    put16(pb, PL + 11, (pb.memory[ep + 7] - 9) & 0xFF)
    # A banked fixture reservation runs during the same in-place room
    # transition as its slide/fade. Give that presentation transaction a
    # complete short settle window before asserting the ordinary walk-over.
    for _ in range(30):
        pb.tick()
    assert pb.memory[RS + RS_SIGILS] & 1, (
        "Sigil pickup did not persist stage bit "
        f"rs={list(pb.memory[RS:RS + 28])} "
        f"player={list(pb.memory[PL + 9:PL + 16])} "
        f"entity={list(pb.memory[ep:ep + 22])} hitbox=0x{pb.memory[ep + 25]:02X} "
        f"screen={pb.memory[SCREEN]} hitstop={pb.memory[HITSTOP]} "
        f"frame={pb.memory[FRAME_COUNTER] | pb.memory[FRAME_COUNTER + 1] << 8}")

    # SELECT is a graphical tile map. Move the displayed cursor one room past
    # the recovered fixture so its icon can be asserted in the room that owns
    # it, rather than at the old confusing floating center marker.
    pb.memory[RS + 1] = 0
    pb.button("select")
    for _ in range(120):
        pb.tick()
    assert pb.memory[SCREEN] == 8
    pb.memory[0xFF4F] = 0

    # The screen-filling Pocket Grid gives every room a readable 2x2 node.
    # Recovery clears the generated completed GOAL and reveals the Warden as the next
    # amber Warden trial. The tutorial has no nonlinear rift at later
    # dungeons' midpoint, and the unseen boss stays anonymous.
    graph0 = mission_graph(dungeon_size(0), DEFAULT_SEED, 0)
    assert node_tile(sigil_cell) != BGT_MAP_BIG_GOAL, \
        "found Sigil left a stale violet GOAL node"
    assert node_tile(graph0["warden"]) == BGT_MAP_BIG_GOAL, \
        "claimed Sigil did not reveal the Warden GOAL node"
    assert pb.memory[bg + 4 * 32 + 9] == BGT_VOID, \
        "tutorial Compass incorrectly revealed a nonlinear Rift link"
    assert node_tile(19) == BGT_MAP_BIG_UNKNOWN, \
        "unseen boss cell leaked its identity through the dim footprint"
    pb.screen.image.save(ROOT / "tmp" / "dungeon-tile-map.png")
    pb.button("b")
    for _ in range(30):
        pb.tick()
    assert pb.memory[SCREEN] == 5

    # The Sigil reveals the Warden but does not replace its trial. The exact
    # same sanctuary threshold remains closed until every generated role is
    # earned in sequence.
    clear_entities()
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[0] - 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[SEALED] = 0
    boss_door(0)
    for _ in range(8):
        pb.tick()
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[0] - 1, \
        "claimed Sigil bypassed the missing Warden Boon"
    pb.memory[RS + RS_PUZZLES] |= 1 << 3
    pb.tick(8)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[0] - 1, \
        "roomier opening route ignored the missing Waystone"
    pb.memory[RS + RS_PUZZLES] |= 1 << 7
    pb.tick(8)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[0] - 1, \
        "roomier opening route ignored the missing deep Warden"
    pb.memory[RS + 28] |= 1 << 7
    pb.tick(8)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[0] - 1, \
        "full-size opening route ignored the missing Deep Seal"
    pb.memory[RS + 28] |= 1 << 2
    pb.tick(8)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[0] - 1, \
        "full mission ignored the uncrossed Deep Gate"
    pb.memory[RS + RS_PUZZLES] |= 1 << 6
    pb.tick(45)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[0], \
        "complete opening route did not unlock boss threshold"

    # The invariant repeats for every dungeon, not just the opening one.
    # Start that contract from a fresh room runtime. The opening boss is now a
    # real 224px arena; debugger-mutating its room counter would intentionally
    # preserve that live wide-world boundary until a normal room transaction
    # resets it, so x=144 would no longer be the east exit. Persistence is the
    # behavior under test here, not leaked arena-private camera state.
    pb.stop(save=False)
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()

    # Simulate a boss-1 clear and enter stage two's generated Sigil role.
    clear_entities()
    pb.memory[RS + RS_BOSSES] = 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[RS + RS_SIGILS] &= 0xFD
    pb.memory[SEALED] = 0
    stage_two_sigil = role_door(1)
    for _ in range(240):
        pb.tick()
        if pb.memory[SIGIL_STATUS] == 5:
            break
    assert pb.memory[RS + 1] == STAGE_START[1] + stage_two_sigil \
        and pb.memory[SIGIL_STATUS] == 5, (
        "stage-two generated role did not receive its Rift Sigil")
    assert sum(
        pb.memory[EN + i * 28] == 3 and pb.memory[EN + i * 28 + 17] == 11
        for i in range(32)
    ) == 1, "stage-two Rift Sigil was not spawned exactly once"

    # Its sanctuary is independently sealed until the new bit is obtained.
    clear_entities()
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[1] - 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[SEALED] = 0
    boss_door(1)
    for _ in range(8):
        pb.tick()
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[1] - 1, \
        "stage-two sanctuary ignored missing Sigil"
    pb.memory[RS + RS_SIGILS] |= 2
    pb.memory[RS + RS_PUZZLES] = RUN_REQUIRED_PUZZLES
    pb.memory[RS + 28] |= RUN_REQUIRED_PHASE
    for _ in range(45):
        pb.tick()
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[1], \
        "stage-two Sigil did not unlock its boss"

    # Every generated stage has a required Waystone role.
    clear_entities()
    pb.memory[RS + RS_BOSSES] = 2
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[2] - 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[RS + RS_SIGILS] |= 1 << 2
    pb.memory[RS + RS_PUZZLES] = RUN_REQUIRED_PUZZLES & ~(1 << 7)
    pb.memory[RS + 28] = RUN_REQUIRED_PHASE
    pb.memory[SEALED] = 0
    boss_door(2)
    pb.tick(8)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[2] - 1, \
        "roomier sanctuary ignored missing Waystone"
    pb.memory[RS + RS_PUZZLES] |= 1 << 7
    pb.tick(45)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[2], \
        "completed Waystone did not unlock the isolated route gate"

    # The generated deep Warden is independently required.
    clear_entities()
    pb.memory[RS + RS_BOSSES] = 5
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[5] - 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[RS + RS_SIGILS] |= 1 << 5
    pb.memory[RS + RS_PUZZLES] = RUN_REQUIRED_PUZZLES
    pb.memory[RS + 28] = 1 << 2
    pb.memory[SEALED] = 0
    boss_door(5)
    pb.tick(8)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[5] - 1, \
        "fourteen-room sanctuary ignored missing deep Warden"
    pb.memory[RS + 28] |= 1 << 7
    pb.tick(45)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[5], \
        "deep Warden clear did not unlock fourteen-room boss"

    # Stage three caught a historical controller stall in its Sigil room.
    # Exercise the real generated graph edge so every objective survives
    # procgen population.
    clear_entities()
    pb.memory[RS + RS_BOSSES] = 2
    pb.memory[RS + RS_SIGILS] &= 0xFB
    pb.memory[RS + 6] = 0xFF
    pb.memory[SEALED] = 0
    stage_three_sigil = role_door(2)
    for _ in range(240):
        pb.tick()
        if pb.memory[SIGIL_STATUS] == 5:
            break
    assert pb.memory[RS + 1] == STAGE_START[2] + stage_three_sigil \
        and pb.memory[SIGIL_STATUS] == 5, (
        "stage-three generated role did not receive its Rift Sigil")
    assert sum(
        pb.memory[EN + i * 28] == 3 and pb.memory[EN + i * 28 + 17] == 11
        for i in range(32)
    ) == 1, "stage-three Rift Sigil was not spawned exactly once"

    # A real high-population seed once filled the 32-slot table before room.c
    # tried to add this fixture, silently omitting the required stage-three
    # Sigil. Pin that exact transaction: the objective must exist alongside
    # all authored combat/loot pressure, not merely in an empty debug room.
    # Start the recorded transaction from a clean cartridge. Rewinding the
    # room counter in the prior live scene would retain its tile transition
    # internals and would not exercise procgen for room 14 at all.
    pb.stop(save=False)
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")
    for _ in range(60):
        pb.tick()

    clear_entities()
    put32(pb, RS + 2, 2064128116)
    pb.memory[RS + RS_BOSSES] = 2
    pb.memory[RS + RS_SIGILS] = 3
    pb.memory[RS + RS_SIGILS + 1] = 0
    pb.memory[RS + 6] = 0xFF
    pb.memory[SEALED] = 0
    dense_sigil = role_door(2, seed=2064128116)
    for _ in range(240):
        pb.tick()
        if pb.memory[SIGIL_STATUS] == 5:
            break
    assert pb.memory[RS + 1] == STAGE_START[2] + dense_sigil \
        and pb.memory[SIGIL_STATUS] == 5, (
        "dense stage-three room did not reserve its Rift Sigil "
        f"(room={pb.memory[RS + 1]} status={pb.memory[SIGIL_STATUS]} "
        f"sealed={pb.memory[SEALED]} hitstop={pb.memory[HITSTOP]})")
    assert sum(
        pb.memory[EN + i * 28] == 3 and pb.memory[EN + i * 28 + 17] == 11
        for i in range(32)
    ) == 1, "dense stage-three room lost its reserved Rift Sigil"

    pb.stop(save=False)
    print("[rift-sigil] PASS generated Sigil + Trial/Wardens/Waystone/Deep-Gate route gates")


if __name__ == "__main__":
    main()
