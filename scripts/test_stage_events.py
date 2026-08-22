#!/usr/bin/env python3
"""Live-ROM contracts for four procedural biome-event hazard grammars."""

import re
from pathlib import Path

from test_stage_archetypes import generated_room

ROOT = Path(__file__).resolve().parent.parent
NOI = (ROOT / "rom/working/quintra.noi").read_text()
ROOM_W = 20
BGT_VOID, BGT_FLOOR2, BGT_CRYSTAL = 0, 19, 22
BGT_SPIKES, BGT_SWITCH, BGT_ARROW_TRAP = 31, 33, 125
SPR_FX_ARROW = 157


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


PL, EN, TM, EXT, BOTTOM, WORLD_W, WORLD_H, KIND, PHASE, REMAIN = map(addr, (
    "_player", "_entities", "_room_tilemap", "_room_world_extension",
    "_room_world_bottom", "_room_world_width", "_room_world_height",
    "_room_stage_event_kind", "_room_stage_event_phase",
    "_room_stage_event_remaining",
))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def clear_entities(pb):
    for offset in range(32 * 28):
        pb.memory[EN + offset] = 0


def world_tile(pb, x, y):
    """Read the authoritative compact/extension/bottom backing store."""
    if y < 17:
        return (pb.memory[TM + y * ROOM_W + x] if x < ROOM_W
                else pb.memory[EXT + y * 11 + x - ROOM_W])
    return pb.memory[BOTTOM + (y - 17) * 31 + x]


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


def arrow_probe(pb, _tiles):
    width = pb.memory[WORLD_W] // 8
    height = pb.memory[WORLD_H] // 8
    sites = ((0, 4), (width - 1, height - 5),
             (width - 1, 4), (0, height - 5))
    assert pb.memory[KIND] == 3 and pb.memory[REMAIN] == 4, \
        "seeded Frost event did not prepare four wall launchers"
    assert all(world_tile(pb, x, y) == BGT_ARROW_TRAP for x, y in sites), \
        f"Frost launchers were not mounted on the true room walls: {sites}"
    clear_entities(pb)
    put16(pb, PL + 9, 72)
    put16(pb, PL + 11, 25)  # first left launcher crosses the hurt box
    pb.memory[PL + 2] = 8
    pb.memory[PL + 15] = 0
    velocities = set()
    saw_warning = saw_damage = False
    for _ in range(430):
        pb.tick()
        saw_warning |= pb.memory[PHASE] == 1
        for i in range(32):
            entity = EN + i * 28
            if (pb.memory[entity] == 1
                    and pb.memory[entity + 12] == SPR_FX_ARROW):
                raw_vx = pb.memory[entity + 10]
                velocities.add(raw_vx if raw_vx < 128 else raw_vx - 256)
        saw_damage |= pb.memory[PL + 2] < 8
        if velocities == {-4, 4}:
            break
    assert saw_warning, "wall launcher fired without its amber warning beat"
    assert velocities == {-4, 4}, \
        f"wall launchers did not fire inward from both walls: {velocities}"
    assert saw_damage, "a wall arrow crossed the hero without dealing damage"


def fading_probe(pb, _tiles):
    wide = pb.memory[WORLD_W] > 160
    xs = (4, 12, 20, 27) if wide else (4, 7, 12, 15)
    sites = tuple((x, y) for y in (7, 10) for x in xs)
    assert pb.memory[KIND] == 4 and pb.memory[REMAIN] == 8, \
        "seeded Shadow event did not prepare eight fading panels"
    assert all(world_tile(pb, x, y) == BGT_FLOOR2 for x, y in sites), \
        "Shadow panels did not begin as visibly cracked floor"
    clear_entities(pb)
    # Stand on the first north-side panel. Its guaranteed safe neighbor is
    # the permanent processional one tile south.
    tx, ty = sites[0]
    put16(pb, PL + 9, tx * 8 - 8)
    put16(pb, PL + 11, ty * 8 - 12)
    pb.memory[PL + 2] = 8
    pb.memory[PL + 15] = 0
    saw_warning = saw_void = saw_damage = False
    for _ in range(620):
        pb.tick()
        phase = pb.memory[PHASE]
        saw_warning |= (phase in (1, 2)
                        and any(world_tile(pb, x, y) == BGT_SWITCH
                                for x, y in sites))
        if phase == 4:
            saw_void = all(world_tile(pb, x, y) == BGT_VOID for x, y in sites)
        saw_damage |= pb.memory[PL + 2] == 7
        if saw_void and saw_damage and phase == 0:
            break
    assert saw_warning, "fading floor disappeared without a gold warning wave"
    assert saw_void, "fading floor never completed its absent phase"
    assert saw_damage and pb.memory[PL + 2] == 7, \
        f"a panel vanishing underfoot did not deal exactly one hit: {pb.memory[PL + 2]}"
    px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
    py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
    assert world_tile(pb, (px + 8) // 8, (py + 12) // 8) != BGT_VOID, \
        "fading-floor stumble left the hero standing in the void"
    assert all(world_tile(pb, x, y) == BGT_FLOOR2 for x, y in sites), \
        "fading panels never reformed into traversable floor"


def main():
    # Local 5 is a stable event cell in both early biomes and is not a
    # mandatory puzzle/service role for the deterministic gallery seed.
    generated_room(1, local_room=5, probe=root_probe)
    generated_room(2, local_room=5, probe=furnace_probe)
    generated_room(3, local_room=5, probe=arrow_probe)
    generated_room(5, local_room=5, probe=fading_probe)
    print("[stage-events] PASS roots + furnace + wall arrows + fading floors")


if __name__ == "__main__":
    main()
