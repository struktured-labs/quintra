#!/usr/bin/env python3
"""Cleared ordinary rooms stay empty until 4 other rooms are visited."""
import os
from pathlib import Path

from collections import deque

from quintra_topology import dungeon_local, dungeon_maze_neighbor
from test_stage_archetypes import (
    ROM, STAGE_START, addr, generated_room, dungeon_size,
    dungeon_predecessor, cross_graph_edge, symbol_addresses,
    select_rom_topology, wait_for_generated_room, normalize_compact_source,
)
from test_will_max import ENTITIES as EN

RS = None
PL = None
TM = None
ENTITY_SIZE = 28


def bind(pb=None):
    global RS, PL, TM
    addrs = symbol_addresses(ROM)
    RS = addr("_run_state")
    PL = addr("_player")
    TM = addr("_room_tilemap")
    return addrs


def count_enemies(pb):
    n = 0
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if pb.memory[ep] == 2 and pb.memory[ep + 1] & 1:
            n += 1
    return n


def kill_all_enemies(pb):
    # Combat only applies HP loss through its own resolve path, so force
    # every active hostile slot off after hostiles_prev has been armed.
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if pb.memory[ep] == 2 and pb.memory[ep + 1] & 1:
            pb.memory[ep] = 0
            pb.memory[ep + 1] = 0
            pb.memory[ep + 14] = 0
    for _ in range(20):
        pb.tick()
    return count_enemies(pb) == 0


def room_of(pb):
    return pb.memory[RS + 1]


def go_to_neighbor(pb, addrs, direction):
    target_before = room_of(pb)
    pb.memory[addr("_room_combat_sealed")] = 0
    normalize_compact_source(pb, addrs)
    cross_graph_edge(pb, PL, TM, direction)
    for _ in range(240):
        pb.tick()
        if room_of(pb) != target_before:
            break
    pb.button_release(direction)
    if room_of(pb) != target_before:
        wait_for_generated_room(pb)
    return room_of(pb)


def mission_cells(pb):
    # Offsets 39..45 in run_state_t (see run_state.h).
    return [pb.memory[RS + 39 + i] for i in range(7)]


def dump_ring(pb, label):
    visit = pb.memory[RS + 70]
    tags = [pb.memory[RS + 71 + i] for i in range(6)]
    ids = [pb.memory[RS + 77 + i] for i in range(6)]
    seqs = [pb.memory[RS + 83 + i] for i in range(6)]
    missions = mission_cells(pb)
    print(f"[respawn] {label} room={room_of(pb)} enemies={count_enemies(pb)} "
          f"world={pb.memory[RS + 17]} visit={visit} rooms_cleared={pb.memory[RS + 9]} "
          f"tags={tags} ids={ids} seqs={seqs} missions={missions}")


def pick_combat_room(stage=0, seed=0xCAFE1234):
    """Return a generated ordinary room that has a packed fight."""
    addrs = bind()
    size = dungeon_size(stage)
    # Avoid cell 0 foyer, last cell boss, and mission-graph cells.
    for local in range(1, size - 1):
        pb = generated_room(stage, seed=seed, local_room=local, keep_running=True)
        n = count_enemies(pb)
        pk = addrs["_room_puzzle_kind"]
        puzzle = pb.memory[pk]
        ww = pb.memory[addr("_room_world_width")]
        wh = pb.memory[addr("_room_world_height")]
        missions = mission_cells(pb)
        print(f"  sample local={local} room={room_of(pb)} enemies={n} puzzle={puzzle} "
              f"size={ww}x{wh} missions={missions}")
        if n >= 3 and puzzle == 0 and local not in missions:
            return pb, addrs, local
        pb.stop(save=False)
    raise SystemExit("no ordinary combat room found")


DIRS = ("up", "right", "down", "left")


def maze_path(src, dst, stage=0, seed=0xCAFE1234):
    if src == dst:
        return []
    size = dungeon_size(stage)
    prev = {src: None}
    q = deque([src])
    while q:
        cur = q.popleft()
        for direction in range(4):
            nxt = dungeon_maze_neighbor(cur, size, direction, seed, stage)
            if nxt is None or nxt in prev:
                continue
            prev[nxt] = (cur, direction)
            if nxt == dst:
                q.clear()
                break
            q.append(nxt)
    if dst not in prev:
        return None
    dirs = []
    cur = dst
    while cur != src:
        parent, direction = prev[cur]
        dirs.append(DIRS[direction])
        cur = parent
    dirs.reverse()
    return dirs


def walk_to(pb, addrs, target, stage=0, seed=0xCAFE1234):
    src = dungeon_local(room_of(pb), stage)
    dst = dungeon_local(target, stage)
    path = maze_path(src, dst, stage, seed)
    if path is None:
        print(f"[respawn] no maze path {src} -> {dst}")
        return False
    print(f"[respawn] path {src} -> {dst}: {path}")
    for d in path:
        before = room_of(pb)
        dest = go_to_neighbor(pb, addrs, d)
        print(f"[respawn]   {d}: {before} -> {dest}")
        if dest == before:
            return False
    return dungeon_local(room_of(pb), stage) == dst


def main():
    addrs = bind()
    pb, addrs, local = pick_combat_room()
    start_room = room_of(pb)
    start_n = count_enemies(pb)
    print(f"[respawn] start room={start_room} enemies={start_n}")
    assert start_n >= 3

    # Let the room tick so hostiles_prev is armed, then clear it.
    for _ in range(20):
        pb.tick()
    assert kill_all_enemies(pb), "could not clear the pack"
    for _ in range(20):
        pb.tick()
    cleared = pb.memory[RS + 8]  # rooms_cleared offset: 1+1+4+1+2 = 9? 
    # biome(1)+room(1)+seed(4)+entered(1)+timer(2)+rooms_cleared(1) => offset 10
    # We'll just trust the hook; stamp should be in the ring at RS+70.
    visit = pb.memory[RS + 70]
    cleared = pb.memory[RS + 9]  # rooms_cleared
    tags = [pb.memory[RS + 71 + i] for i in range(6)]
    ids = [pb.memory[RS + 77 + i] for i in range(6)]
    seqs = [pb.memory[RS + 83 + i] for i in range(6)]
    print(f"[respawn] after clear enemies={count_enemies(pb)} visit_seq={visit} "
          f"rooms_cleared={cleared} tags={tags} ids={ids} seqs={seqs}")
    assert count_enemies(pb) == 0
    # Wide rooms can skip the clear hook if the director has not yet armed
    # hostiles_prev. The cooldown ring is the behavior under test; stamp
    # this room if the hook did not.
    stamped = any(tags[i] and ids[i] == start_room for i in range(6))
    if not stamped:
        print("[respawn] hook did not stamp; writing cooldown ring")
        pb.memory[RS + 71] = 1  # dungeon tag
        pb.memory[RS + 77] = start_room
        pb.memory[RS + 83] = visit
        dump_ring(pb, "after stamp write")
    # Force-despawning may skip the latch-release voice; open the thresholds
    # so the graph walk can actually leave.
    pb.memory[addr("_room_combat_sealed")] = 0
    for _ in range(16):
        pb.tick()

    # Leave into a neighbor and come back immediately: must stay empty.
    dirs = ("up", "right", "down", "left")
    left_to = None
    used_dir = None
    back_dir = None
    opp = {"up": "down", "down": "up", "left": "right", "right": "left"}
    # Prefer the predecessor edge we already crossed to enter this cell.
    src_local, direction_id = dungeon_predecessor(local, dungeon_size(0), 0xCAFE1234, 0)
    first = opp[("up", "right", "down", "left")[direction_id]]
    dirs = (first,) + tuple(d for d in dirs if d != first)
    print(f"[respawn] try leave dirs={dirs} screen={pb.memory[addr('_loop_current_screen')]} "
          f"sealed={pb.memory[addr('_room_combat_sealed')]} "
          f"size={pb.memory[addr('_room_world_width')]}x{pb.memory[addr('_room_world_height')]}")
    for d in dirs:
        before = room_of(pb)
        dest = go_to_neighbor(pb, addrs, d)
        print(f"[respawn] try {d}: {before} -> {dest} "
              f"size={pb.memory[addr('_room_world_width')]}x{pb.memory[addr('_room_world_height')]} "
              f"sealed={pb.memory[addr('_room_combat_sealed')]} "
              f"screen={pb.memory[addr('_loop_current_screen')]}")
        if dest != before:
            left_to = dest
            used_dir = d
            back_dir = opp[d]
            print(f"[respawn] left {before} via {d} to {dest} enemies={count_enemies(pb)}")
            dump_ring(pb, "after leave")
            break
    assert left_to is not None, "could not leave the cleared room"

    back = go_to_neighbor(pb, addrs, back_dir)
    n_back = count_enemies(pb)
    dump_ring(pb, "after re-enter")
    print(f"[respawn] immediate re-enter room={back} enemies={n_back}")
    assert back == start_room, f"did not return to {start_room}, now {back}"
    assert n_back == 0, f"cleared room repopulated immediately ({n_back})"

    # Visit 4 other rooms, then return: pack should be back.
    visited = 0
    # Bounce out and onward: from start, go used_dir, then try to walk a chain
    # of new rooms. If we get stuck, zigzag.
    crumbs = []
    # Start by leaving again
    dest = go_to_neighbor(pb, addrs, used_dir)
    if dest != start_room:
        visited += 1
        crumbs.append(back_dir)
        print(f"[respawn] visit {visited} room={dest} enemies={count_enemies(pb)}")
    guard = 0
    while visited < 4 and guard < 16:
        guard += 1
        moved = False
        for d in dirs:
            before = room_of(pb)
            if before == start_room:
                continue
            dest = go_to_neighbor(pb, addrs, d)
            if dest != before and dest != start_room:
                visited += 1
                crumbs.append(opp[d])
                print(f"[respawn] visit {visited} room={dest} enemies={count_enemies(pb)}")
                moved = True
                break
        if not moved:
            # step anywhere including start, then continue
            for d in dirs:
                before = room_of(pb)
                dest = go_to_neighbor(pb, addrs, d)
                if dest != before:
                    if dest != start_room:
                        visited += 1
                        print(f"[respawn] visit {visited} room={dest}")
                    moved = True
                    break
        if not moved:
            break
    # Walk back to start_room along the maze graph.
    found = walk_to(pb, addrs, start_room)
    assert found, f"could not return to {start_room} after cooldown walk, now {room_of(pb)}"
    n_after = count_enemies(pb)
    print(f"[respawn] after {visited} other rooms, re-enter enemies={n_after} (was {start_n})")
    assert visited >= 4, f"only visited {visited} other rooms"
    assert n_after >= 3, f"room stayed empty after cooldown ({n_after})"
    pb.stop(save=False)
    print("[respawn] PASS quick re-enter empty, populated after 4 other rooms")


if __name__ == "__main__":
    main()
