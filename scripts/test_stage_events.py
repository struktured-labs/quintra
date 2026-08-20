#!/usr/bin/env python3
"""Live-ROM contracts for Verdant root knots and Ember furnace cycles."""

import re
from pathlib import Path

from test_stage_archetypes import generated_room

ROOT = Path(__file__).resolve().parent.parent
NOI = (ROOT / "rom/working/quintra.noi").read_text()
ROOM_W = 20
BGT_FLOOR2, BGT_CRYSTAL, BGT_SPIKES, BGT_SWITCH = 19, 22, 31, 33


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


PL, EN, TM, KIND, PHASE, REMAIN = map(addr, (
    "_player", "_entities", "_room_tilemap", "_room_stage_event_kind",
    "_room_stage_event_phase", "_room_stage_event_remaining",
))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def clear_entities(pb):
    for offset in range(32 * 28):
        pb.memory[EN + offset] = 0


def root_probe(pb, tiles):
    assert pb.memory[KIND] == 1 and pb.memory[REMAIN] == 3, \
        "seeded Verdant event did not prepare three root knots"
    candidates = ((5, 5), (14, 5), (10, 12), (5, 11), (14, 11), (10, 4))
    roots = [(x, y) for x, y in candidates
             if tiles[y * ROOM_W + x] == BGT_CRYSTAL]
    assert len(roots) == 3, f"root event did not author three cuttable knots: {roots}"
    clear_entities(pb)
    for expected, (tx, ty) in zip((2, 1, 0), roots):
        pb.memory[PL + 22] = 0  # fire cooldown
        put16(pb, PL + 9, tx * 8 - 17)
        put16(pb, PL + 11, ty * 8 - 6)
        pb.memory[PL + 13] = 1  # FACE_E; neutral A avoids movement variance
        pb.button_press("a")
        for _ in range(4):
            pb.tick()
        pb.button_release("a")
        assert pb.memory[TM + ty * ROOM_W + tx] != BGT_CRYSTAL, \
            f"Fang strike did not cut root at {(tx, ty)}"
        assert pb.memory[REMAIN] == expected, \
            f"root count drifted after {(tx, ty)}: {pb.memory[REMAIN]}"
    surges = [EN + i * 28 for i in range(32)
              if pb.memory[EN + i * 28] == 3
              and pb.memory[EN + i * 28 + 17] == 14]
    assert surges, "cutting the full root network paid no weapon surge"


def furnace_probe(pb, tiles):
    sites = ((5, 5), (7, 5), (9, 5), (11, 5), (13, 5),
             (15, 5), (6, 11), (9, 11), (12, 11), (15, 11))
    assert pb.memory[KIND] == 2 and pb.memory[PHASE] == 0, \
        "seeded Ember event did not begin in its cool phase"
    assert all(tiles[y * ROOM_W + x] == BGT_FLOOR2 for x, y in sites), \
        "Ember furnace lanes were not visibly marked while cool"
    clear_entities(pb)
    put16(pb, PL + 9, 16)
    put16(pb, PL + 11, 104)
    pb.memory[PL + 15] = 255  # observe the entire cycle without combat noise
    saw_warning = saw_hot = False
    for _ in range(520):
        pb.tick()
        phase = pb.memory[PHASE]
        if phase in (1, 2):
            saw_warning |= any(
                pb.memory[TM + y * ROOM_W + x] == BGT_SWITCH for x, y in sites)
        if phase == 4:
            saw_hot = all(
                pb.memory[TM + y * ROOM_W + x] == BGT_SPIKES for x, y in sites)
        if saw_hot and phase == 0:
            break
    # The cooling transition publishes phase 0 immediately before its banked
    # reward constructor validates the complete 16x16 footprint. A host VBlank
    # can observe that boundary mid-call, so let the cartridge finish the
    # transaction before inspecting the entity table.
    for _ in range(8):
        pb.tick()
    assert saw_warning, "furnace jumped to damage without a gold warning wave"
    assert saw_hot, "furnace cycle never completed its hot hazard lanes"
    assert pb.memory[PHASE] == 0, "furnace lanes never cooled back into a route"
    assert all(pb.memory[TM + y * ROOM_W + x] == BGT_FLOOR2 for x, y in sites), \
        "cooling wave did not restore the marked floor"
    assert any(pb.memory[EN + i * 28] == 3
               and pb.memory[EN + i * 28 + 17] == 14 for i in range(32)), \
        "surviving the first furnace cycle paid no weapon surge"


def main():
    # Local 5 is a stable event cell in both early biomes and is not a
    # mandatory puzzle/service role for the deterministic gallery seed.
    generated_room(1, local_room=5, probe=root_probe)
    generated_room(2, local_room=5, probe=furnace_probe)
    print("[stage-events] PASS Verdant roots + Ember warn/ignite/cool reward cycle")


if __name__ == "__main__":
    main()
