#!/usr/bin/env python3
"""ROM contract: Wolfkin A is a true melee form, never a shot stream."""
import re
from pathlib import Path

from pyboy import PyBoy

ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    for _ in range(240):
        pb.tick()
    pb.button("start")
    for _ in range(30):
        pb.tick()
    pb.button("a")  # Wolfkin is the default highlighted champion
    for _ in range(60):
        pb.tick()
    return pb


def clear_entities(pb, entities):
    for i in range(32 * 28):
        pb.memory[entities + i] = 0


def clear_room_floor(pb, tilemap):
    # The held-combo contract measures input/cadence, not whether a randomly
    # generated wall immediately consumes the stationary contact arc.
    for i in range(20 * 17):
        pb.memory[tilemap + i] = 1  # BGT_FLOOR


def player_projectiles(pb, entities):
    return [entities + i * 28 for i in range(32)
            if pb.memory[entities + i * 28] == 1
            and (pb.memory[entities + i * 28 + 1] & 0x10)]


def main():
    player, entities, tilemap = map(
        addr, ("_player", "_entities", "_room_tilemap"))
    pb = boot()
    assert pb.memory[player] == 0, "did not enter as Wolfkin"
    # The reach contract is about a blade lane, not a seed-dependent wall
    # collision. Give the opening probes the same open arena used below for
    # cadence so a room boundary cannot despawn an otherwise valid sword.
    clear_room_floor(pb, tilemap)

    # A with a D-pad direction is the narrow contact stab.
    clear_entities(pb, entities)
    pb.memory[player + 22] = 0  # fire cooldown
    stab_origin_x = pb.memory[player + 9] | (pb.memory[player + 10] << 8)
    pb.button_press("right")
    pb.button("a")
    for _ in range(3):
        pb.tick()
    pb.button_release("right")
    stab = player_projectiles(pb, entities)
    assert len(stab) == 1, f"directed A spawned {len(stab)} attacks"
    assert pb.memory[stab[0] + 12] == 122, "stab lost physical arc art"
    assert pb.memory[stab[0] + 16] <= 18, "stab travels like a projectile"
    assert pb.memory[stab[0] + 25] == 0x88, "directed sword no longer covers its blade art"
    assert pb.memory[stab[0] + 26] == 3, \
        "normal Wolfkin opener regressed above its three-damage floor"
    # The sword begins at Wolfkin's visible weapon edge instead of inside the
    # old fist silhouette or beyond an unhittable close-range gap. Entity x's
    # integer half is offset +3 from the struct base.
    stab_x = pb.memory[stab[0] + 3] | (pb.memory[stab[0] + 4] << 8)
    # This sample is three ticks after the press; the short physical thrust
    # has advanced at most nine pixels beyond its 10px spawn edge. The old
    # 24px-gap form would already be beyond +30 here.
    assert stab_origin_x + 14 <= stab_x <= stab_origin_x + 20, \
        "directed sword no longer begins at the weapon edge"
    # It must also carry through the intended compact lane.  This catches a
    # seemingly harmless TTL/origin regression that would leave Wolfkin with
    # a visible blade but only point-blank practical reach.
    furthest_stab_x = stab_x
    for _ in range(18):
        pb.tick()
        for shot in player_projectiles(pb, entities):
            shot_x = pb.memory[shot + 3] | (pb.memory[shot + 4] << 8)
            furthest_stab_x = max(furthest_stab_x, shot_x)
    assert furthest_stab_x >= stab_origin_x + 60, \
        ("directed sword no longer owns its committed forward lane: "
         f"origin={stab_origin_x} furthest={furthest_stab_x}")

    # Neutral A is the wider sweep, still a single physical hitbox.
    clear_entities(pb, entities)
    pb.memory[player + 22] = 0
    pb.button("a")
    for _ in range(3):
        pb.tick()
    sweep = player_projectiles(pb, entities)
    assert len(sweep) == 1, f"neutral A spawned {len(sweep)} overlapping arcs"
    assert pb.memory[sweep[0] + 25] == 0xBB, "neutral A did not widen into a sweep"

    # Holding A commits to a slow physical combo, not the ranged champions'
    # shot stream and not the old hold-to-auto-dash. MAX now belongs to the
    # shared full-Will system covered by test_will_max.py.
    combo_pb = boot()
    assert combo_pb.memory[player] == 0, "fresh combo test did not enter as Wolfkin"
    clear_entities(combo_pb, entities)
    clear_room_floor(combo_pb, tilemap)
    combo_pb.memory[player + 22] = 0
    combo_pb.memory[player + 42] = 0
    combo_pb.button_press("left")
    combo_pb.button_press("a")
    held_combo = []
    for _ in range(72):
        combo_pb.tick()
        held_combo.extend((combo_pb.memory[e + 12], combo_pb.memory[e + 16])
                          for e in player_projectiles(combo_pb, entities))
    combo_pb.button_release("a")
    combo_pb.button_release("left")
    assert any(tile == 122 for tile, _ in held_combo), \
        f"held Wolfkin A did not continue with a slow physical combo: {held_combo}"
    assert all(tile == 122 and ttl <= 18 for tile, ttl in held_combo), \
        "held Wolfkin combo became a traveling shot stream"
    combo_pb.stop(save=False)

    # One long-lived arc may cleave a second body, but it must never apply its
    # full damage to the same overlapping target again on the next sweep.
    hit_pb = boot()
    clear_entities(hit_pb, entities)
    clear_room_floor(hit_pb, tilemap)
    hit_pb.memory[player + 22] = 0
    hit_pb.memory[player + 42] = 0
    hit_pb.memory[player + 13] = 1  # FACE_E
    hit_pb.button_press("a")
    for _ in range(3):
        hit_pb.tick()
    hit_pb.button_release("a")
    hit_shot = player_projectiles(hit_pb, entities)[0]
    hit_pb.memory[hit_shot + 10] = hit_pb.memory[hit_shot + 11] = 0
    shot_x = hit_pb.memory[hit_shot + 3] | (hit_pb.memory[hit_shot + 4] << 8)
    shot_y = hit_pb.memory[hit_shot + 7] | (hit_pb.memory[hit_shot + 8] << 8)
    foe = next(entities + i * 28 for i in range(32)
               if entities + i * 28 != hit_shot)
    hit_pb.memory[foe] = 2
    hit_pb.memory[foe + 1] = 0x07
    hit_pb.memory[foe + 3] = shot_x & 0xFF
    hit_pb.memory[foe + 4] = shot_x >> 8
    hit_pb.memory[foe + 7] = shot_y & 0xFF
    hit_pb.memory[foe + 8] = shot_y >> 8
    hit_pb.memory[foe + 14] = 8
    hit_pb.memory[foe + 17] = 2  # Hornet: not weak to Wolfkin fire
    hit_pb.memory[foe + 25] = 0x88
    hit_pb.memory[foe + 26] = 1
    hit_pb.tick()
    assert hit_pb.memory[foe + 14] == 5, \
        f"Fang's first ordinary contact was not three damage: {hit_pb.memory[foe + 14]}"
    hit_pb.tick()
    assert hit_pb.memory[foe + 14] == 5, \
        "one Fang arc damaged the same overlapping body twice"
    hit_pb.stop(save=False)

    # A weapon orb replaces A's actual mechanics, not just its name. Wolfkin
    # holding Sauran's Tail Spike must regain that item's normal lunge instead
    # of silently retaining Fang Stab's short arc and missing nearby bodies.
    swap_pb = boot()
    clear_entities(swap_pb, entities)
    swap_pb.memory[player + 21] = 1  # Tail Spike item index
    swap_pb.memory[player + 22] = 0
    swap_pb.button_press("right")
    swap_pb.button("a")
    for _ in range(3):
        swap_pb.tick()
    swap_pb.button_release("right")
    swapped = player_projectiles(swap_pb, entities)
    assert len(swapped) == 1, f"Tail Spike swap spawned {len(swapped)} attacks"
    assert swap_pb.memory[swapped[0] + 16] > 8, \
        "Wolfkin weapon swap retained Fang Stab's short lifetime"
    assert swap_pb.memory[swapped[0] + 25] == 0x77, \
        "Wolfkin weapon swap retained Fang Stab's oversized blade hitbox"
    swap_pb.stop(save=False)
    pb.stop(save=False)
    print("[wolfkin-forms] PASS 3-damage Fang, one-hit/body cleave, forms and weapon swap")


if __name__ == "__main__":
    main()
