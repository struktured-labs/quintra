#!/usr/bin/env python3
"""A light-puzzle (Sun Lattice) room never has a basilisk in its guard pack.

The lattice's light beam and a basilisk's floor beam share the crystal BG
palette, so in the same room the puzzle light and the hazard look alike,
and a basilisk beam that ends repaints the floor under its lanes. Puzzle
rooms keep a small guard pack rolled like any other room, and two roster
kinds could put a basilisk in it: a Command room's leader is taken from the
raw stage pool, and a Mixed room rolls the raw pool.

Replay: stage 3, seed 0x1818E811. Its Trial is a Sun Lattice on a Command
roster whose leader was the Ley Basilisk: the pack was [40, 25, 25, 25].
The basilisk must now be the room's themed species, in the same slot, with
the same body count, and the lattice's beam cells must stay put while the
guards move around.
"""
from quintra_topology import dungeon_size, mission_graph
from test_stage_archetypes import EN, addr, generated_room

SEED, STAGE = 0x1818E811, 2
PUZZLE_SUN_LATTICE = 5
BASILISKS = {40: "Ley", 42: "Sun", 43: "Nox"}
MAIN_PACK = [40, 25, 25, 25]          # what main 0ed13b15 spawned here
BEAM_TILES = (60, 61, 62)             # SUN_LATTICE_TILE + 4..6, VRAM bank 1
KIND = addr("_room_puzzle_kind")
ORIGIN_X, ORIGIN_Y = addr("_room_bg_origin_x"), addr("_room_bg_origin_y")


def guards(pb):
    return [(i, pb.memory[EN + i * 28 + 17]) for i in range(32)
            if pb.memory[EN + i * 28] == 2 and pb.memory[EN + i * 28 + 1] & 1]


def beam_cells(pb):
    """BG-map cells showing a lattice beam tile (bank-1 art, crystal slot)."""
    cells = set()
    for y in range(32):
        for x in range(32):
            a = 0x9800 + y * 32 + x
            if (pb.memory[0, a] in BEAM_TILES
                    and (pb.memory[1, a] & 0x0F) == 0x0A):   # bank 1 | crystal
                cells.add((x, y))
    return cells


def main():
    trial = mission_graph(dungeon_size(STAGE), SEED, STAGE)["trial"]
    pb = generated_room(STAGE, SEED, local_room=trial, keep_running=True)
    for _ in range(10):
        pb.tick()
    assert pb.memory[KIND] == PUZZLE_SUN_LATTICE, (
        f"replay room is not a Sun Lattice: kind {pb.memory[KIND]}")
    pack = guards(pb)
    ids = [eid for _slot, eid in pack]
    found = [BASILISKS[e] for e in ids if e in BASILISKS]
    assert not found, (
        f"{found} Basilisk in a Sun Lattice guard pack: {ids}")
    assert len(ids) == len(MAIN_PACK), (
        f"guard pack changed size: {ids}, main had {MAIN_PACK}")
    assert ids == [25, 25, 25, 25], (
        f"the basilisk should have become the room's themed species: {ids}")
    for slot, _eid in pack:
        hp = pb.memory[EN + slot * 28 + 14]
        assert hp > 0, f"guard in slot {slot} has no HP"

    # The light must not be disturbed by the guards over a few seconds.
    lit = beam_cells(pb)
    assert lit, "the lattice shows no beam cells to protect"
    for _ in range(400):
        pb.memory[addr("_player") + 15] = 200     # hero stays safe
        pb.tick()
        assert not any(e in BASILISKS for _s, e in guards(pb))
    assert beam_cells(pb) == lit, (
        f"lattice beam cells changed with no player action: "
        f"lost {sorted(lit - beam_cells(pb))}, "
        f"gained {sorted(beam_cells(pb) - lit)}")
    pb.stop(save=False)
    print(f"[no-basilisk-in-sun-lattice] PASS seed 0x{SEED:08X} stage 3 Trial: "
          f"pack {ids} (main: {MAIN_PACK}), {len(lit)} beam cells unchanged "
          f"over 400 frames")


if __name__ == "__main__":
    main()
