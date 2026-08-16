#!/usr/bin/env python3
"""Live-ROM contract: all nine Colossus victories unlock distinct verbs."""

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


PLAYER, RUN, ENTITIES, SCREEN, ENEMY_COUNT = map(addr, (
    "_player", "_run_state", "_entities", "_loop_current_screen",
    "_entity_enemy_count"))

SCREEN_ROOM = 5
PL_HP_MAX, PL_HP, PL_MP_MAX, PL_MP = 1, 2, 3, 4
PL_X, PL_Y, PL_IFRAMES = 9, 11, 15
PL_ACTIVE_CHARGE, PL_WILL, PL_OATH = 19, 42, 43
RS_BOSSES = 11


def put16(pb, at, value):
    pb.memory[at] = value & 0xFF
    pb.memory[at + 1] = (value >> 8) & 0xFF


def get16(pb, at):
    return pb.memory[at] | (pb.memory[at + 1] << 8)


def press(pb, button, held=4, released=5):
    pb.button_press(button)
    pb.tick(held)
    pb.button_release(button)
    pb.tick(released)


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    press(pb, "start")
    pb.tick(30)
    press(pb, "a")
    pb.tick(90)
    assert pb.memory[SCREEN] == SCREEN_ROOM
    return pb


def clear_entities(pb):
    for i in range(32 * 28):
        pb.memory[ENTITIES + i] = 0
    pb.memory[ENEMY_COUNT] = 0


def entity(pb, slot, kind, x, y, hp=20, vx=0, vy=0, player_shot=False):
    e = ENTITIES + slot * 28
    pb.memory[e] = kind
    pb.memory[e + 1] = 0x07 | (0x10 if player_shot else 0)
    put16(pb, e + 3, x)
    put16(pb, e + 7, y)
    pb.memory[e + 10] = vx & 0xFF
    pb.memory[e + 11] = vy & 0xFF
    pb.memory[e + 14] = hp
    pb.memory[e + 16] = 40
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = 1
    if kind == 2:
        pb.memory[ENEMY_COUNT] = (pb.memory[ENEMY_COUNT] + 1) & 0xFF
    return e


def chord(pb, settle=8):
    pb.button_press("a")
    pb.button_press("b")
    pb.tick(5)
    pb.button_release("a")
    pb.button_release("b")
    pb.tick(settle)


def prepare(pb, art):
    clear_entities(pb)
    pb.memory[RUN + RS_BOSSES] = 9
    pb.memory[PLAYER + PL_OATH] = art
    pb.memory[PLAYER + PL_ACTIVE_CHARGE] = 0
    pb.memory[PLAYER + PL_WILL] = 0
    pb.memory[PLAYER + PL_MP] = max(1, pb.memory[PLAYER + PL_MP_MAX] - 1)
    pb.memory[PLAYER + PL_IFRAMES] = 80
    # Stable central floor for displacement verbs. The first viewport's
    # compact map begins at a separately exported address.
    tilemap = addr("_room_tilemap")
    for y in range(4, 13):
        for x in range(5, 16):
            pb.memory[tilemap + y * 20 + x] = 1
    put16(pb, PLAYER + PL_X, 80)
    put16(pb, PLAYER + PL_Y, 64)
    # Keep the room's clear-reward transition from refunding one MP while an
    # art's exact resource cost is under test. This distant durable body is
    # outside every local assertion; effect-specific fixtures use slot zero.
    entity(pb, 31, 2, 224, 224, hp=200)
    return pb.memory[PLAYER + PL_MP]


def signed(byte):
    return byte - 256 if byte & 0x80 else byte


def active_player_shots(pb):
    return sum(
        1 for i in range(32)
        if pb.memory[ENTITIES + i * 28] == 1
        and pb.memory[ENTITIES + i * 28 + 1] & 0x11 == 0x11
    )


def assert_cost(pb, before, art):
    assert pb.memory[PLAYER + PL_MP] == before - 1, f"art {art} did not cost 1 MP"
    assert pb.memory[PLAYER + PL_ACTIVE_CHARGE] > 0, f"art {art} has no cooldown"


def main():
    source = (ROOT / "src/game/oath_arts.c").read_text()
    for name in ("SHARD WAKE", "ROOT CALL", "CINDERSTEP", "STILL WAVE",
                 "MIASMA", "GLOAM SHIFT", "SUN TURN", "RED HARVEST",
                 "RIFT EXCHANGE"):
        assert name in source, f"missing authored art {name}"

    # 0 Shard Wake: eight-lane crystal volley.
    pb = boot()
    before = prepare(pb, 0)
    chord(pb)
    assert active_player_shots(pb) >= 6
    assert_cost(pb, before, 0)
    pb.stop(save=False)

    # 1 Root Call: four close roots plus a body pull.
    pb = boot()
    before = prepare(pb, 1)
    foe = entity(pb, 0, 2, 112, 64)
    pb.memory[foe + 17] = 10  # rotating Sentry: stationary after the pull
    old_dist = abs(get16(pb, foe + 3) - 80)
    chord(pb)
    assert abs(get16(pb, foe + 3) - get16(pb, PLAYER + PL_X)) < old_dist
    assert active_player_shots(pb) >= 2
    assert_cost(pb, before, 1)
    pb.stop(save=False)

    # 2 Cinderstep: collision-checked displacement plus flame lanes.
    pb = boot()
    before = prepare(pb, 2)
    old_y = get16(pb, PLAYER + PL_Y)
    chord(pb)
    assert get16(pb, PLAYER + PL_Y) != old_y
    assert active_player_shots(pb) >= 1
    assert_cost(pb, before, 2)
    pb.stop(save=False)

    # 3 Still Wave: hostile bullet remains but is slowed.
    pb = boot()
    before = prepare(pb, 3)
    shot = entity(pb, 0, 1, 120, 80, vx=4, vy=0)
    chord(pb)
    assert abs(signed(pb.memory[shot + 10])) <= 2
    assert_cost(pb, before, 3)
    pb.stop(save=False)

    # 4 Miasma: setup corrosion cannot execute the target.
    pb = boot()
    before = prepare(pb, 4)
    foe = entity(pb, 0, 2, 128, 96, hp=80)
    chord(pb)
    assert 1 < pb.memory[foe + 14] < 80
    assert_cost(pb, before, 4)
    pb.stop(save=False)

    # 5 Gloam Shift: a legal landing can skip intermediate geometry.
    pb = boot()
    before = prepare(pb, 5)
    old_y = get16(pb, PLAYER + PL_Y)
    chord(pb)
    assert get16(pb, PLAYER + PL_Y) != old_y
    assert_cost(pb, before, 5)
    pb.stop(save=False)

    # 6 Sun Turn: (vx,vy) rotates clockwise to (-vy,vx).
    pb = boot()
    before = prepare(pb, 6)
    shot = entity(pb, 0, 1, 120, 80, vx=3, vy=1)
    chord(pb, settle=40)
    assert signed(pb.memory[shot + 10]) == -1
    assert signed(pb.memory[shot + 11]) == 3
    assert_cost(pb, before, 6)
    pb.stop(save=False)

    # 7 Red Harvest: wounds without bypassing combat death and heals 1/2 heart.
    pb = boot()
    before = prepare(pb, 7)
    pb.memory[PLAYER + PL_HP] = pb.memory[PLAYER + PL_HP_MAX] - 2
    old_hp = pb.memory[PLAYER + PL_HP]
    foe = entity(pb, 0, 2, 128, 96, hp=10)
    chord(pb)
    assert pb.memory[foe + 14] == 9
    assert pb.memory[PLAYER + PL_HP] == old_hp + 1
    assert_cost(pb, before, 7)
    pb.stop(save=False)

    # 8 Rift Exchange: nearest small body and champion trade world positions.
    pb = boot()
    before = prepare(pb, 8)
    foe = entity(pb, 0, 2, 104, 64, hp=10)
    chord(pb)
    assert get16(pb, PLAYER + PL_X) == 104
    assert get16(pb, foe + 3) == 80
    assert_cost(pb, before, 8)
    pb.stop(save=False)

    print("[oath-arts] PASS nine stage victories unlock nine active verbs")


if __name__ == "__main__":
    main()
