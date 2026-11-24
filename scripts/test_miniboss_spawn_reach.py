#!/usr/bin/env python3
"""ROM contract: every required dungeon specialist is player-reachable."""

from test_stage_archetypes import (
    EN, PL, RS, ROOM_H, ROOM_W, addr, generated_room,
)
from quintra_topology import dungeon_size, mission_graph


ENTITY_SIZE = 28
ENT_ENEMY = 2
EF_ACTIVE = 0x01
ENEMY_STONE_SENTINEL = 1
ENEMY_DREAD_BELL = 20
ENEMY_STAGE_REAPER = 34
ENEMY_AUX_BELLWARDEN = 0xB1
WALKABLE = {1, 3, 7, 19, 20, 23, 31, 33, 34, *range(9, 19)}
WORLD_EXT, WORLD_BOTTOM, WORLD_W, WORLD_H = map(addr, (
    "_room_world_extension", "_room_world_bottom",
    "_room_world_width", "_room_world_height",
))


def body_ok(tiles, width, height, x, y):
    return (1 <= x < width - 1 and 1 <= y < height - 1
            and all(tiles[ty * width + tx] in WALKABLE
                    for tx, ty in ((x, y), (x + 1, y),
                                   (x, y + 1), (x + 1, y + 1))))


def reachable(tiles, width, height, start):
    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for nx, ny in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if ((nx, ny) not in seen
                    and body_ok(tiles, width, height, nx, ny)):
                seen.add((nx, ny))
                todo.append((nx, ny))
    return seen


def world_tiles(pb, compact):
    width = pb.memory[WORLD_W] // 8
    height = pb.memory[WORLD_H] // 8
    result = []
    for y in range(height):
        for x in range(width):
            if y < ROOM_H and x < ROOM_W:
                result.append(compact[y * ROOM_W + x])
            elif y < ROOM_H:
                result.append(pb.memory[WORLD_EXT + y * 11 + x - ROOM_W])
            else:
                result.append(pb.memory[WORLD_BOTTOM + (y - ROOM_H) * 31 + x])
    return result, width, height


def active_enemies(pb):
    found = []
    for i in range(32):
        ep = EN + i * ENTITY_SIZE
        if pb.memory[ep] == ENT_ENEMY and pb.memory[ep + 1] & EF_ACTIVE:
            found.append({
                "ep": ep,
                "id": pb.memory[ep + 17],
                "hp": pb.memory[ep + 14],
                "ai2": pb.memory[ep + 19],
                "x": pb.memory[ep + 3],
                "y": pb.memory[ep + 7],
            })
    return found


def specialists_matching(pb, expected):
    found = []
    for enemy in active_enemies(pb):
        if enemy["id"] != expected["id"]:
            continue
        if expected.get("ai2") is not None and enemy["ai2"] != expected["ai2"]:
            continue
        if enemy["hp"] < expected["hp"]:
            continue
        found.append(enemy["ep"])
    return found


def main():
    checked = []
    expected = {"id": ENEMY_STONE_SENTINEL, "hp": 50, "name": "Sentinel",
                "ai2": None}

    def inspect(pb, tiles):
        tiles, width, height = world_tiles(pb, tiles)
        specialists = specialists_matching(pb, expected)
        assert len(specialists) == 1, (
            f"expected one required {expected['name']}, got {len(specialists)} "
            f"enemies={[ (e['id'], e['hp'], e['ai2']) for e in active_enemies(pb) ]}")
        specialist = specialists[0]
        sx = (pb.memory[specialist + 3] + 4) // 8
        sy = (pb.memory[specialist + 7] + 4) // 8
        px = pb.memory[PL + 9] | (pb.memory[PL + 10] << 8)
        py = pb.memory[PL + 11] | (pb.memory[PL + 12] << 8)
        start = ((px + 2) // 8, (py + 8) // 8)
        assert body_ok(tiles, width, height, sx, sy), \
            f"{expected['name']} overlaps solid tile at {(sx, sy)}"
        assert (sx, sy) in reachable(tiles, width, height, start), (
            f"{expected['name']} at {(sx, sy)} is outside player component from {start}")
        checked.append((sx, sy))

    # The two Warden cells retain the stage-scaled Sentinel. Local 15 is the
    # guaranteed fallback for the one-per-dungeon Reaper hunt when no earlier
    # progressed backtrack sprung it first.
    for seed in range(0x51A70000, 0x51A70010):
        graph = mission_graph(dungeon_size(0), seed, 0)
        for local_room, enemy_id, hp, name in (
                (graph["warden"], ENEMY_STONE_SENTINEL, 50, "Sentinel"),
                (graph["deep_warden"], ENEMY_STONE_SENTINEL, 50, "Sentinel"),
                (15, ENEMY_STAGE_REAPER, 80, "Dread Reaper")):
            expected.update(id=enemy_id, hp=hp, name=name, ai2=None)
            generated_room(0, seed, probe=inspect, local_room=local_room)

    # The natural trigger is a progressed revisit, not the numeric fallback.
    # Mark wide room four as previously entered and claim the stage Sigil;
    # this seed's three-in-four hunt roll is deterministic.
    def progressed_backtrack(pb, _addrs):
        pb.memory[RS + 23] |= 0x01       # stage-one Sigil: phase >= 2
        pb.memory[RS + 53] |= 1 << 4     # actual visit bit for local room 4

    def inspect_hunt(pb, tiles):
        inspect(pb, tiles)
        assert pb.memory[addr("_room_encounter_kind")] == 6
        assert pb.memory[addr("_music_track_id")] == 9
        assert pb.memory[RS + 52] & 0x80
        # The dungeon-law overlay may replace two of the eight authored teeth,
        # but the jaws must still read as an unmistakably trapped arena.
        assert tiles.count(31) >= 6, (
            f"Reaper hunt lost its trapped spike jaws ({tiles.count(31)})")

    expected.update(id=ENEMY_STAGE_REAPER, hp=80, name="Dread Reaper", ai2=None)
    generated_room(0, 0x51A70000, probe=inspect_hunt, local_room=4,
                   pre_cross=progressed_backtrack)

    assert len(checked) == 49
    print(f"[miniboss-spawn-reach] PASS 32 Sentinels + 16 fallback Reapers "
          f"+ trapped backtrack hunt positions={checked}")

    # Issue #229: stage 5 (index 4) seed 0x7B081BB4 deep-Warden cell 1 used
    # to populate only a Mire Spore, never the required Sentinel, and the
    # sanctuary door stayed locked. Replay that seed, then sweep Warden and
    # deep-Warden cells across every stage.
    def expect_for_stage(stage):
        if stage >= 6:
            return {"id": ENEMY_DREAD_BELL, "hp": 20, "name": "Bellwarden",
                    "ai2": ENEMY_AUX_BELLWARDEN}
        # Stage-scaled miniboss Sentinels stay well above the ordinary
        # table HP. Stage 0's contract already uses 50; later stages are
        # higher, never lower.
        return {"id": ENEMY_STONE_SENTINEL, "hp": 50, "name": "Sentinel",
                "ai2": None}

    # Exact #229 repro (Easy Corvin run used this seed; generation is
    # seed-stable and the Normal harness is enough to catch a missing body).
    repro_seed = 0x7B081BB4
    repro_stage = 4
    repro_graph = mission_graph(dungeon_size(repro_stage), repro_seed, repro_stage)
    assert repro_graph["deep_warden"] == 1, repro_graph
    expected.update(**expect_for_stage(repro_stage))
    RUN_DEEP_WARDEN_BIT = 0x80

    def inspect_clear_net(pb, tiles):
        inspect(pb, tiles)
        assert not (pb.memory[RS + 28] & RUN_DEEP_WARDEN_BIT), (
            "deep-Warden bit already set before the clear-room net")
        # Deactivate every hostile without going through combat.c's
        # Sentinel/Bellwarden kill hook. The room must still record the
        # deep-Warden bit so a missing tagged kill cannot soft-lock the
        # sanctuary door.
        for enemy in active_enemies(pb):
            pb.memory[enemy["ep"] + 1] &= ~EF_ACTIVE
        for _ in range(180):
            pb.tick()
            if pb.memory[RS + 28] & RUN_DEEP_WARDEN_BIT:
                return
        raise AssertionError(
            "deep-Warden room cleared without a Warden kill, but "
            f"RUN_DEEP_WARDEN_BIT stayed clear "
            f"(phase=0x{pb.memory[RS + 28]:02X})")

    generated_room(repro_stage, repro_seed, probe=inspect_clear_net,
                   local_room=repro_graph["deep_warden"])
    print(f"[miniboss-spawn-reach] #229 repro seed={repro_seed:#x} "
          f"stage={repro_stage} cell={repro_graph['deep_warden']} "
          f"+ clear-room net PASS")

    # The live bug was an Easy Corvin run. Stage 4 Easy still keeps
    # Sentinel HP well above 50 (base 50 + 25 + 4*14, then halved).
    generated_room(repro_stage, repro_seed, probe=inspect,
                   local_room=repro_graph["deep_warden"],
                   difficulty="easy")
    print(f"[miniboss-spawn-reach] #229 Easy repro PASS")

    sweep_n = 0
    for stage in range(9):
        expected.update(**expect_for_stage(stage))
        for seed in range(0x51A70000, 0x51A70000 + 8):
            graph = mission_graph(dungeon_size(stage), seed, stage)
            for role in ("warden", "deep_warden"):
                generated_room(stage, seed, probe=inspect,
                               local_room=graph[role])
                sweep_n += 1
    print(f"[miniboss-spawn-reach] PASS {sweep_n} Warden/deep-Warden cells "
          f"across 9 stages (8 seeds each)")


if __name__ == "__main__":
    main()
