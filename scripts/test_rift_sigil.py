#!/usr/bin/env python3
"""ROM contract: staged dungeon fixtures gate only the boss threshold."""
import re
from pathlib import Path

from pyboy import PyBoy
from quintra_topology import (
    STAGE_BOSS_ROOM, STAGE_START, dungeon_direction, dungeon_size,
)

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, EN, TM, SEALED, SIGIL_STATUS, SCREEN, HITSTOP, FRAME_COUNTER = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_combat_sealed", "_room_sigil_status", "_loop_current_screen", "_g_hitstop", "_loop_frame_counter"))
RS_SIGILS = 23
RS_BOSSES = 11
RS_PUZZLES = 27


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

    def right_door():
        # Local 1 -> 2 and the first three sanctuary -> boss edges all run
        # east in the reciprocal 5x4 graph.
        pb.memory[TM + 8 * 20 + 19] = pb.memory[TM + 9 * 20 + 19] = 3
        put16(pb, PL + 9, 144)
        put16(pb, PL + 11, 60)

    def boss_door(stage):
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
    pb.memory[RS + RS_PUZZLES] = 1 << 3  # isolate the missing-Sigil contract
    pb.memory[SEALED] = 0
    right_door()
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

    # Room 2 always regenerates the current stage's objective until collected.
    pb.memory[RS + 1] = 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[SEALED] = 0
    right_door()
    for _ in range(240):
        pb.tick()
        if pb.memory[SIGIL_STATUS] != 2:
            break
    assert pb.memory[RS + 1] == 2 and pb.memory[SIGIL_STATUS] == 5, (
        f"room transaction incomplete: room={pb.memory[RS + 1]} "
        f"status={pb.memory[SIGIL_STATUS]}")
    sigils = []
    for i in range(32):
        ep = EN + i * 28
        if pb.memory[ep] == 3 and pb.memory[ep + 17] == 11:
            sigils.append(ep)
    assert len(sigils) == 1, (
        "room 2 did not contain exactly one Rift Sigil: "
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
    pb.memory[RS + 1] = 4
    pb.button("select")
    for _ in range(120):
        pb.tick()
    assert pb.memory[SCREEN] == 8
    pb.memory[0xFF4F] = 0
    bg = 0x9800
    # The 5x4 Compass gives each dungeon room one glyph. Opening-stage fixture
    # room 2 is node two at (9, 3); its nearby diagonal remains empty because
    # the tutorial dungeon intentionally has no nonlinear rift.
    assert pb.memory[bg + 3 * 32 + 9] == 52, \
        "found Sigil lacks its dedicated glyph in the fixture room"
    assert pb.memory[bg + 3 * 32 + 13] == 51, \
        "claimed Sigil did not reveal the amber Warden objective"
    assert pb.memory[bg + 4 * 32 + 10] == 0, \
        "Sigil still uses the misleading floating map marker"
    assert pb.memory[bg + 9 * 32 + 13] == 95, \
        "unseen boss slot lost its dim identity-free placeholder"
    pb.screen.image.save(ROOT / "tmp" / "dungeon-tile-map.png")
    pb.button("b")
    for _ in range(30):
        pb.tick()
    assert pb.memory[SCREEN] == 5

    # The Sigil reveals the Warden but does not replace its trial. The exact
    # same sanctuary threshold remains closed until local room 3's boon bit,
    # the room-7 Waystone, and the deep Warden are earned in sequence.
    clear_entities()
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[0] - 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[SEALED] = 0
    right_door()
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
    pb.tick(45)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[0], \
        "complete opening route did not unlock boss threshold"

    # The invariant repeats for every dungeon, not just the opening one.
    # Simulate a boss-1 clear, take local room 1 south into local room 2, and make
    # sure that stage two receives a distinct objective and gate bit.
    clear_entities()
    pb.memory[RS + 1] = STAGE_START[1] + 1
    pb.memory[RS + RS_BOSSES] = 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[RS + RS_SIGILS] &= 0xFD
    pb.memory[SEALED] = 0
    right_door()
    for _ in range(240):
        pb.tick()
        if pb.memory[SIGIL_STATUS] == 5:
            break
    assert pb.memory[RS + 1] == STAGE_START[1] + 2 \
        and pb.memory[SIGIL_STATUS] == 5, (
        "stage-two room 2 did not receive its Rift Sigil")
    assert sum(
        pb.memory[EN + i * 28] == 3 and pb.memory[EN + i * 28 + 17] == 11
        for i in range(32)
    ) == 1, "stage-two Rift Sigil was not spawned exactly once"

    # Its sanctuary is independently sealed until the new bit is obtained.
    clear_entities()
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[1] - 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[SEALED] = 0
    right_door()
    for _ in range(8):
        pb.tick()
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[1] - 1, \
        "stage-two sanctuary ignored missing Sigil"
    pb.memory[RS + RS_SIGILS] |= 2
    pb.memory[RS + RS_PUZZLES] = (1 << 3) | (1 << 7)
    pb.memory[RS + 28] |= 1 << 7
    for _ in range(45):
        pb.tick()
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[1], \
        "stage-two Sigil did not unlock its boss"

    # Roomier stages make their existing local-room-7 puzzle a required
    # Waystone. This lengthens the meaningful route instead of adding filler.
    clear_entities()
    pb.memory[RS + RS_BOSSES] = 2
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[2] - 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[RS + RS_SIGILS] |= 1 << 2
    pb.memory[RS + RS_PUZZLES] = 1 << 3
    pb.memory[RS + 28] = 1 << 7
    pb.memory[SEALED] = 0
    boss_door(2)
    pb.tick(8)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[2] - 1, \
        "roomier sanctuary ignored missing Waystone"
    pb.memory[RS + RS_PUZZLES] |= 1 << 7
    pb.tick(45)
    assert pb.memory[RS + 1] == STAGE_BOSS_ROOM[2], \
        "completed Waystone did not unlock the isolated route gate"

    # The existing room-9 Warden is independently required.
    clear_entities()
    pb.memory[RS + RS_BOSSES] = 5
    pb.memory[RS + 1] = STAGE_BOSS_ROOM[5] - 1
    pb.memory[RS + 6] = 0xFF
    pb.memory[RS + RS_SIGILS] |= 1 << 5
    pb.memory[RS + RS_PUZZLES] = (1 << 3) | (1 << 7)
    pb.memory[RS + 28] = 0
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
    # Exercise the real local-room-1 -> local-room-2 transaction so every early objective,
    # not only the first two, is guaranteed to survive procgen population.
    clear_entities()
    pb.memory[RS + 1] = STAGE_START[2] + 1
    pb.memory[RS + RS_BOSSES] = 2
    pb.memory[RS + RS_SIGILS] &= 0xFB
    pb.memory[RS + 6] = 0xFF
    pb.memory[SEALED] = 0
    right_door()
    for _ in range(240):
        pb.tick()
        if pb.memory[SIGIL_STATUS] == 5:
            break
    assert pb.memory[RS + 1] == STAGE_START[2] + 2 \
        and pb.memory[SIGIL_STATUS] == 5, (
        "stage-three room 2 did not receive its Rift Sigil")
    assert sum(
        pb.memory[EN + i * 28] == 3 and pb.memory[EN + i * 28 + 17] == 11
        for i in range(32)
    ) == 1, "stage-three Rift Sigil was not spawned exactly once"

    # The same room carries the nonlinear rift to local room 8. Its bright
    # tile alone is not enough: the feet-box needs a full 2x2 walkable path
    # from the actual entry point, or a player can see a mandatory route that
    # cannot be entered. Flood the real WRAM tilemap at hero-footprint scale.
    walkable = {1, 3, 7, *range(9, 19), 19, 20, 23, 31, 33, 34}
    portals = [(x, y) for y in range(17) for x in range(20)
               if pb.memory[TM + y * 20 + x] == 34]
    assert len(portals) == 1, f"stage-three rift missing or duplicated: {portals}"
    tx, ty = portals[0]

    def body_open(x, y):
        return (0 <= x < 19 and 0 <= y < 16 and
                all((pb.memory[TM + yy * 20 + xx] & 0x7F) in walkable
                    for xx, yy in ((x, y), (x + 1, y), (x, y + 1), (x + 1, y + 1))))

    start = ((pb.memory[PL + 9] + 2) // 8, (pb.memory[PL + 11] + 8) // 8)
    goal = (tx - 1, ty - 1)
    seen, queue = {start}, [start]
    while queue:
        x, y = queue.pop(0)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (nx, ny) not in seen and body_open(nx, ny):
                seen.add((nx, ny))
                queue.append((nx, ny))
    assert goal in seen, (
        f"rift at {(tx, ty)} has no hero-footprint route from {start}")

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
    pb.memory[RS + 1] = STAGE_START[2] + 1
    pb.memory[RS + RS_BOSSES] = 2
    pb.memory[RS + RS_SIGILS] = 3
    pb.memory[RS + RS_SIGILS + 1] = 0
    pb.memory[RS + 6] = 0xFF
    pb.memory[SEALED] = 0
    right_door()
    for _ in range(240):
        pb.tick()
        if pb.memory[SIGIL_STATUS] == 5:
            break
    assert pb.memory[RS + 1] == STAGE_START[2] + 2 \
        and pb.memory[SIGIL_STATUS] == 5, (
        "dense stage-three room did not reserve its Rift Sigil "
        f"(room={pb.memory[RS + 1]} status={pb.memory[SIGIL_STATUS]} "
        f"sealed={pb.memory[SEALED]} hitstop={pb.memory[HITSTOP]})")
    assert sum(
        pb.memory[EN + i * 28] == 3 and pb.memory[EN + i * 28 + 17] == 11
        for i in range(32)
    ) == 1, "dense stage-three room lost its reserved Rift Sigil"

    pb.stop(save=False)
    print("[rift-sigil] PASS Sigil + Warden + late Waystone/deep-Warden route gates")


if __name__ == "__main__":
    main()
