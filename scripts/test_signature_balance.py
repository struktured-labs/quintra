#!/usr/bin/env python3
"""Live-ROM contracts for the differentiated hero B/Will balance pass."""

import re
from pathlib import Path

from test_boss_identity import EN, PL, enter_boss
from test_will_max import (
    ENTITY_SIZE, ENTITIES, PLAYER, boot, clear_arena, player_shots, put16,
)


ROOT = Path(__file__).resolve().parent.parent
NOI = ROOT.joinpath("rom/working/quintra.noi").read_text()
EF_ACTIVE_ALIVE_ONSCREEN = 0x07
EF_PLAYER_PROJ = 0x10
PROJ_FLAG_HOWL = 0x04


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


MARK_SLOT = addr("_will_corvin_mark_slot")
MARK_TICKS = addr("_will_corvin_mark_ticks")
HOWL_HITS = addr("_will_howl_giant_hits")
SWARM_TICKS = addr("_will_vespine_swarm_ticks")


def put_fix8(pb, address, pixels):
    raw = pixels << 8
    for i in range(4):
        pb.memory[address + i] = (raw >> (i * 8)) & 0xFF


def make_enemy(pb, slot, x, y, *, hp=50, enemy_id=10, giant=False):
    e = ENTITIES + slot * ENTITY_SIZE
    for i in range(ENTITY_SIZE):
        pb.memory[e + i] = 0
    pb.memory[e] = 2
    pb.memory[e + 1] = EF_ACTIVE_ALIVE_ONSCREEN
    put_fix8(pb, e + 2, x)
    put_fix8(pb, e + 6, y)
    pb.memory[e + 14] = hp
    pb.memory[e + 16] = 120
    pb.memory[e + 17] = enemy_id
    pb.memory[e + 20] = 1 if giant else 0
    pb.memory[e + 25] = 0xFF if giant else 0x77
    pb.memory[e + 26] = 1
    return e


def make_player_shot(pb, slot, x, y, damage, flag=0):
    e = ENTITIES + slot * ENTITY_SIZE
    for i in range(ENTITY_SIZE):
        pb.memory[e + i] = 0
    pb.memory[e] = 1
    pb.memory[e + 1] = 0x03 | EF_PLAYER_PROJ
    put_fix8(pb, e + 2, x)
    put_fix8(pb, e + 6, y)
    pb.memory[e + 14] = 1
    pb.memory[e + 16] = 90
    pb.memory[e + 20] = flag
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = damage
    return e


def press_b(pb, aim=None):
    if aim:
        pb.button_press(aim)
    pb.button_press("b")
    for _ in range(30):
        pb.tick()
        if pb.memory[PLAYER + 19] > 0:
            break
    pb.button_release("b")
    if aim:
        pb.button_release(aim)
    pb.tick(2)


def test_corvin_mark():
    pb = boot(2)
    clear_arena(pb)
    enemy = make_enemy(pb, 0, 112, 72)
    pb.memory[PLAYER + 4] = pb.memory[PLAYER + 3]
    pb.memory[PLAYER + 19] = 0
    press_b(pb, "right")
    assert pb.memory[MARK_SLOT] == 0, "Raven Mark did not choose the nearest foe"
    assert pb.memory[MARK_TICKS] > 160, "Raven Mark did not start its focus window"
    assert len(player_shots(pb)) <= 1, (
        "Corvin B is still an instantaneous multi-projectile fan")

    # The marked target takes exactly one extra point on the ordinary combat
    # path; a second identical hit after clearing the mark stays at base damage.
    before = pb.memory[enemy + 14]
    make_player_shot(pb, 2, 112, 72, 3)
    pb.tick(2)
    marked_loss = before - pb.memory[enemy + 14]
    pb.memory[MARK_TICKS] = 0
    before = pb.memory[enemy + 14]
    make_player_shot(pb, 2, 112, 72, 3)
    pb.tick(2)
    plain_loss = before - pb.memory[enemy + 14]
    assert marked_loss == plain_loss + 1, (
        f"Raven Mark bonus drifted: marked={marked_loss} plain={plain_loss}")
    pb.stop(save=False)


def test_vespine_swarm():
    pb = boot(4)
    clear_arena(pb)
    pb.memory[PLAYER + 4] = pb.memory[PLAYER + 3]
    pb.memory[PLAYER + 19] = 0
    press_b(pb, "right")
    assert pb.memory[SWARM_TICKS] > 80, "Vespine B did not start a timed swarm"
    shots = player_shots(pb)
    assert len(shots) <= 1, f"Vespine B still opened as a {len(shots)}-shot fan"
    assert shots, "rotating swarm did not release its first aimed sting"
    first_velocity = (pb.memory[shots[0] + 10], pb.memory[shots[0] + 11])

    second_velocity = first_velocity
    for _ in range(80):
        pb.tick()
        shots = player_shots(pb)
        if shots:
            candidate = (pb.memory[shots[-1] + 10], pb.memory[shots[-1] + 11])
            if candidate != first_velocity:
                second_velocity = candidate
                break
    assert second_velocity != first_velocity, (
        f"Vespine swarm repeated one lane: {first_velocity}")
    pb.stop(save=False)


def test_howl_colossus_cap():
    pb, boss = enter_boss(0, keep_open=True)
    boss_x, boss_y = pb.memory[boss + 3], pb.memory[boss + 7]
    pb.memory[boss + 14] = 100
    pb.memory[PL + 2] = pb.memory[PL + 1]
    pb.memory[HOWL_HITS] = 0
    made = 0
    for slot in range(32):
        shot = EN + slot * ENTITY_SIZE
        if shot == boss:
            continue
        make_player_shot(pb, slot, boss_x, boss_y, 7, PROJ_FLAG_HOWL)
        made += 1
        if made == 8:
            break
    before = pb.memory[boss + 14]
    for _ in range(20):
        pb.tick()
    loss = before - pb.memory[boss + 14]
    assert loss == 21, f"Howl landed {loss}; expected three 7-damage Colossus hits"
    assert pb.memory[HOWL_HITS] == 3, "Howl cast-wide giant budget did not clamp"
    pb.stop(save=False)


def main():
    test_corvin_mark()
    test_vespine_swarm()
    test_howl_colossus_cap()
    print("[signature-balance] PASS Raven Mark, rotating Swarm, and Howl giant cap")


if __name__ == "__main__":
    main()
