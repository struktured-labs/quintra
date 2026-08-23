#!/usr/bin/env python3
"""Live-ROM contract for procedural Road Echo followers and Compass ASK."""

import io
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
STATES = ROOT / "tmp/stage-states"
NOI = ROM.with_suffix(".noi").read_text()

ENTITY_SIZE = 28
ENT_PROJECTILE = 1
ENT_PICKUP = 3
EF_ACTIVE = 0x01
EF_PLAYER_PROJ = 0x10
PICKUP_COMPANION = 23
SPR_COMPANION_A = 224
SPR_COMPANION_B = 228
SCREEN_ROOM = 5
SCREEN_MAP = 8

# Stable player ABI offsets.
PL_HP_MAX = 1
PL_HP = 2
PL_MP_MAX = 3
PL_MP = 4
PL_X = 9
PL_Y = 11
PL_IFRAMES = 15

# The new run-state byte is appended after the 51-byte pre-companion ABI.
RS_RUN_TIMER = 7
RS_COMPANION_COOLDOWN = 51


def sym(name):
    match = re.search(rf"DEF _{re.escape(name)} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PLAYER = sym("player")
RUN_STATE = sym("run_state")
ENTITIES = sym("entities")
SCREEN = sym("loop_current_screen")


def emulator():
    return PyBoy(
        str(ROM), window="null", cgb=True,
        ram_file=io.BytesIO(bytes(32 * 1024)),
    )


def tick(pb, count):
    for _ in range(count):
        pb.tick()


def tap(pb, button):
    pb.button_press(button)
    tick(pb, 6)
    pb.button_release(button)
    tick(pb, 9)


def load(pb, filename):
    with (STATES / filename).open("rb") as handle:
        pb.load_state(handle)
    tick(pb, 4)


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def get16(pb, address):
    return pb.memory[address] | pb.memory[address + 1] << 8


def entities(pb, entity_type):
    return [ENTITIES + slot * ENTITY_SIZE for slot in range(32)
            if pb.memory[ENTITIES + slot * ENTITY_SIZE] == entity_type
            and pb.memory[ENTITIES + slot * ENTITY_SIZE + 1] & EF_ACTIVE]


def companions(pb):
    return [entity for entity in entities(pb, ENT_PICKUP)
            if pb.memory[entity + 17] == PICKUP_COMPANION]


def obj_tile(pb, tile):
    pb.memory[0xFF4F] = 0
    return bytes(pb.memory[0x8000 + tile * 16 + i] for i in range(64))


def test_presence_and_art(pb):
    kinds = []
    for stage in range(1, 10):
        load(pb, f"quintra-stage-{stage:02d}-entry-wolfkin.pyboy")
        followers = companions(pb)
        assert len(followers) == 1, (
            f"stage {stage} has {len(followers)} Road Echoes")
        follower = followers[0]
        kind = pb.memory[follower + 18]
        kinds.append(kind)
        assert kind in range(3), f"invalid Road Echo role {kind}"
        assert pb.memory[follower + 12] in (SPR_COMPANION_A, SPR_COMPANION_B)
        assert pb.memory[follower + 25] == 0, "Road Echo has a blocking hitbox"
    assert len(set(kinds[:3])) == 3, (
        f"seeded roles did not rotate across early expeditions: {kinds[:3]}")
    assert any(obj_tile(pb, SPR_COMPANION_A)), "Road Echo stride A is blank"
    assert any(obj_tile(pb, SPR_COMPANION_B)), "Road Echo stride B is blank"
    assert obj_tile(pb, SPR_COMPANION_A) != obj_tile(pb, SPR_COMPANION_B), (
        "Road Echo stride frames are identical")


def test_follow_and_fire(pb):
    # Stage one opens on its authored Trial; stage two is the first entry
    # state with the normal fourteen-body field used by this combat check.
    load(pb, "quintra-stage-02-entry-wolfkin.pyboy")
    follower = companions(pb)[0]

    # Stage-entry courts keep this central east-west road clear. Place the
    # follower eighty pixels behind the champion: below the warp threshold,
    # above the follow gap, and far enough to measure real pursuit.
    put16(pb, PLAYER + PL_X, 112)
    put16(pb, PLAYER + PL_Y, 56)
    put16(pb, follower + 3, 32)
    put16(pb, follower + 7, 64)
    before = get16(pb, follower + 3)
    tick(pb, 18)
    after = get16(pb, follower + 3)
    assert after > before, f"Road Echo did not follow east: {before}->{after}"
    assert pb.memory[follower + 12] in (SPR_COMPANION_A, SPR_COMPANION_B)
    (ROOT / "tmp").mkdir(exist_ok=True)
    pb.screen.image.save(ROOT / "tmp" / "road-echo-room.png")

    hostiles = entities(pb, 2)
    assert hostiles, "stage entry has no target for follower fire test"
    target = hostiles[0]
    tx = get16(pb, target + 3)
    ty = get16(pb, target + 7)
    put16(pb, follower + 3, max(16, tx - 32))
    put16(pb, follower + 7, ty)
    pb.memory[follower + 16] = 0
    tick(pb, 3)
    allied = [shot for shot in entities(pb, ENT_PROJECTILE)
              if pb.memory[shot + 1] & EF_PLAYER_PROJ
              and pb.memory[shot + 26] == 1]
    assert allied, "Road Echo did not fire its restrained one-damage bolt"


def test_ask(pb):
    load(pb, "quintra-stage-01-entry-wolfkin.pyboy")
    follower = companions(pb)[0]
    kind = pb.memory[follower + 18]
    pb.memory[RUN_STATE + RS_COMPANION_COOLDOWN] = 0

    if kind == 0:
        pb.memory[PLAYER + PL_HP] = max(1, pb.memory[PLAYER + PL_HP_MAX] - 4)
        before = pb.memory[PLAYER + PL_HP]
    elif kind == 1:
        pb.memory[PLAYER + PL_MP] = max(0, pb.memory[PLAYER + PL_MP_MAX] - 4)
        before = pb.memory[PLAYER + PL_MP]
    else:
        pb.memory[PLAYER + PL_IFRAMES] = 0
        before = 0

    tap(pb, "select")
    assert pb.memory[SCREEN] == SCREEN_MAP, "SELECT did not open Compass"
    tick(pb, 20)
    pb.screen.image.save(ROOT / "tmp" / "road-echo-ask.png")
    tap(pb, "a")
    assert pb.memory[SCREEN] == SCREEN_ROOM, "A ASK did not resume the room"
    assert pb.memory[RUN_STATE + RS_COMPANION_COOLDOWN] == 20
    if kind == 0:
        assert pb.memory[PLAYER + PL_HP] == min(
            pb.memory[PLAYER + PL_HP_MAX], before + 2)
    elif kind == 1:
        assert pb.memory[PLAYER + PL_MP] == min(
            pb.memory[PLAYER + PL_MP_MAX], before + 2)
    else:
        assert pb.memory[PLAYER + PL_IFRAMES] > 0

    # A second ASK during cooldown refuses the effect and remains on Compass.
    tick(pb, 20)
    tap(pb, "select")
    assert pb.memory[SCREEN] == SCREEN_MAP
    tap(pb, "a")
    assert pb.memory[SCREEN] == SCREEN_MAP, "cooldown ASK incorrectly succeeded"
    tap(pb, "b")
    assert pb.memory[SCREEN] == SCREEN_ROOM
    tick(pb, 20)

    # The persisted cooldown counts active-play seconds, not menu frames.
    follower = companions(pb)[0]
    old_timer = get16(pb, RUN_STATE + RS_RUN_TIMER)
    put16(pb, RUN_STATE + RS_RUN_TIMER, (old_timer + 1) & 0xFFFF)
    tick(pb, 2)
    assert pb.memory[RUN_STATE + RS_COMPANION_COOLDOWN] == 19, (
        "Road Echo ASK cooldown did not consume one active-play second")


def main():
    pb = emulator()
    try:
        test_presence_and_art(pb)
        test_follow_and_fire(pb)
        test_ask(pb)
    finally:
        pb.stop(save=False)
    print(
        "[companion] PASS 9-stage presence, two-beat follow, restrained fire, "
        "three-role Compass ASK, cooldown refusal + active-time recovery"
    )


if __name__ == "__main__":
    main()
