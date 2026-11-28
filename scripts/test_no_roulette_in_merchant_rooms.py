#!/usr/bin/env python3
"""The cycling power-up (Roulette Capsule) never appears in a merchant room (#262).

A Roulette showed up in the middle of a dungeon shop, among the wares. It
was the once-per-dungeon power shrine: the shrine takes a seeded dead-end
cell, the public shop cell (size - 3) is a dead end in many early
dungeons, and the shrine's Roulette sits at the room centre, on the shelf
row. The hidden Veil stall's host cell could be chosen the same way.

Contracts:

  * Graph: over many seeds and all nine stages, the shrine cell is never
    the shop cell. (The same sweep counts how often the old rule put it
    there, so the bug stays reproducible on paper.)
  * Live ROM, a seed where the old rule seated the shrine in the shop:
    the shop room has its wares and no Roulette, and nothing can spawn one
    there, not even the debug spawn commands.
  * Live ROM, same seed: the shrine was moved, not lost. Its new cell
    holds exactly one shrine Roulette.
  * Live ROM, a seed where the shrine cell is the Veil host cell: the
    host room (no wares) keeps the shrine, and the stall inside it never
    shows a Roulette.
"""
import random

from quintra_topology import (
    dungeon_cache_cell, dungeon_entry_cell, dungeon_maze_neighbor,
    dungeon_size, mission_graph, veil_host_cell,
)
from test_secret_merchants import (
    EN, ENTITY_SIZE, VEIL_KIND, THICKET, mirror_host, reveal_walk,
)
from test_stage_archetypes import addr, generated_room

ENT_PICKUP = 3
PICKUP_SHOP, PICKUP_POWERUP, PICKUP_ROULETTE = 4, 27, 28
TEST_CMD = addr("_powerup_test_cmd")
WORLD_LIVE = addr("_powerup_world_live")


def shop_cell(stage):
    return dungeon_size(stage) - 3


def shrine_cell(seed, stage, shop_reserved=True):
    """Mirror dungeon_shrine_cell() in src/game/powerup_extra.c."""
    size = dungeon_size(stage)
    roles = mission_graph(size, seed, stage)["sequence"][:5]
    reserved = {dungeon_entry_cell(size, seed, stage),
                dungeon_cache_cell(size, seed, stage), *roles}
    if shop_reserved:
        reserved.add(shop_cell(stage))
    start = (((seed >> 8) & 0xFF) + stage * 17) & 0xFF
    for tries in range(size):
        cell = (start + tries) % size
        if cell in reserved:
            continue
        degree = sum(dungeon_maze_neighbor(cell, size, d, seed, stage)
                     is not None for d in range(4))
        if degree == 1:
            return cell
    return None


def pickups(pb, kind):
    return [EN + i * ENTITY_SIZE for i in range(32)
            if pb.memory[EN + i * ENTITY_SIZE] == ENT_PICKUP
            and pb.memory[EN + i * ENTITY_SIZE + 1] & 1
            and pb.memory[EN + i * ENTITY_SIZE + 17] == kind]


def assert_no_roulette(pb, where):
    assert not pickups(pb, PICKUP_ROULETTE), (
        f"{where}: a cycling power-up is in the merchant room")
    assert pickups(pb, PICKUP_SHOP), f"{where}: no wares, not a merchant room"
    # Nothing may put one here afterwards either. Commands 1 and 2 are the
    # cartridge's own drop and shrine Roulette spawns.
    for cmd in (1, 2):
        pb.memory[WORLD_LIVE] = 1
        pb.memory[TEST_CMD] = cmd
        for _ in range(8):
            pb.tick()
        assert not pickups(pb, PICKUP_ROULETTE), (
            f"{where}: spawn command {cmd} placed a cycling power-up "
            f"among the wares")


def graph_contract(rng, seeds=400):
    old_shop = old_veil = dungeons = 0
    shop_seed = veil_seed = None
    for _ in range(seeds):
        seed = rng.getrandbits(32)
        for stage in range(9):
            dungeons += 1
            veil = veil_host_cell(seed, stage)
            old = shrine_cell(seed, stage, shop_reserved=False)
            new = shrine_cell(seed, stage)
            assert new != shop_cell(stage), (
                f"seed 0x{seed:08X} stage {stage + 1}: shrine cell {new} is "
                f"the shop cell")
            if old is not None and old == shop_cell(stage):
                old_shop += 1
                if shop_seed is None and stage == 0 and new is not None:
                    shop_seed = seed
            if new is not None and new == veil:
                old_veil += 1
                if (veil_seed is None and VEIL_KIND[stage] == THICKET
                        and mirror_host(seed, stage) == veil):
                    veil_seed = (seed, stage)
    assert shop_seed is not None, "no shop-collision seed found to replay"
    return dungeons, old_shop, old_veil, shop_seed, veil_seed


def shop_contract(seed):
    stage = 0
    old = shrine_cell(seed, stage, shop_reserved=False)
    assert old == shop_cell(stage)
    pb = generated_room(stage, seed, local_room=shop_cell(stage),
                        keep_running=True)
    assert_no_roulette(pb, f"seed 0x{seed:08X} stage 1 shop")
    pb.stop(save=False)

    moved = shrine_cell(seed, stage)
    pb = generated_room(stage, seed, local_room=moved, keep_running=True)
    for _ in range(4):
        pb.tick()
    found = pickups(pb, PICKUP_ROULETTE)
    assert len(found) == 1, (
        f"seed 0x{seed:08X}: the shrine should have moved to cell {moved}, "
        f"found {len(found)} Roulettes there")
    assert not pickups(pb, PICKUP_SHOP)
    pb.stop(save=False)
    return moved


def veil_contract(seed, stage):
    host = veil_host_cell(seed, stage)
    pb = generated_room(stage, seed, local_room=host, keep_running=True)
    for _ in range(4):
        pb.tick()
    assert shrine_cell(seed, stage) == host
    assert len(pickups(pb, PICKUP_ROULETTE)) == 1, (
        f"seed 0x{seed:08X} stage {stage + 1}: the Veil host room lost "
        f"its shrine")
    assert not pickups(pb, PICKUP_SHOP)
    reveal_walk(pb)   # asserts the three-shelf stall is present
    assert_no_roulette(pb, f"seed 0x{seed:08X} stage {stage + 1} Veil stall")
    pb.stop(save=False)


def main():
    rng = random.Random(262)
    dungeons, old_shop, old_veil, shop_seed, veil_seed = graph_contract(rng)
    moved = shop_contract(shop_seed)
    if veil_seed is not None:
        veil_contract(*veil_seed)
    print(f"[no-roulette-in-merchant-rooms] PASS {dungeons} dungeons: shrine "
          f"never on the shop cell (old rule: {old_shop}; shares the Veil "
          f"host cell in {old_veil}); seed 0x{shop_seed:08X} shop is clean and its shrine "
          f"moved to cell {moved}; Veil stall "
          + ("clean, host room keeps the shrine" if veil_seed
             else "replay skipped (no THICKET seed)"))


if __name__ == "__main__":
    main()
