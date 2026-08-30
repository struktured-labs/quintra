#!/usr/bin/env python3
"""Live-ROM contract for secret-found Road Echo followers and Compass ASK."""

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
SCREEN_DIALOG = 10

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
RS_SECRET_PENDING = 13
RS_DUNGEON_PHASE = 28
COMPANION_COOLDOWN_MASK = 0x3F
COMPANION_PENDING_BIT = 0x40
COMPANION_DISCOVERED_BIT = 0x80
BGT_FLOOR = 1
BGT_WALL = 2


def sym(name):
    match = re.search(rf"DEF _{re.escape(name)} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(f"missing symbol {name}")
    return int(match.group(1), 16)


PLAYER = sym("player")
RUN_STATE = sym("run_state")
ENTITIES = sym("entities")
SCREEN = sym("loop_current_screen")
TILEMAP = sym("room_tilemap")
SEALED = sym("room_combat_sealed")
PUZZLE_LOCKED = sym("room_puzzle_locked")
HIDDEN_KIND = sym("room_hidden_secret_kind")
HIDDEN_X = sym("room_hidden_secret_x")
HIDDEN_Y = sym("room_hidden_secret_y")
HIDDEN_X2 = sym("room_hidden_secret_x2")
HIDDEN_Y2 = sym("room_hidden_secret_y2")
HIDDEN_BIT = sym("room_hidden_secret_bit")


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


def clear_board(pb):
    for offset in range(32 * ENTITY_SIZE):
        pb.memory[ENTITIES + offset] = 0
    for offset in range(20 * 17):
        pb.memory[TILEMAP + offset] = BGT_FLOOR
    pb.memory[SEALED] = 0
    pb.memory[PUZZLE_LOCKED] = 0


def test_hidden_until_discovered(pb):
    # Checkpoint creation uses ordinary stage entry, so no expedition starts
    # with a free follower. Every stage remains eligible to discover the same
    # run-seeded Echo through one of its optional disguised caches.
    for stage in range(1, 10):
        load(pb, f"quintra-stage-{stage:02d}-entry-wolfkin.pyboy")
        assert not companions(pb), f"stage {stage} gave away a Road Echo"
        assert not (pb.memory[RUN_STATE + RS_COMPANION_COOLDOWN]
                    & COMPANION_DISCOVERED_BIT)

    # ASK is not merely dimmed before discovery: the Compass has no follower
    # action and A cannot invoke a seed-derived aid without a physical Echo.
    tap(pb, "select")
    assert pb.memory[SCREEN] == SCREEN_MAP
    tap(pb, "a")
    assert pb.memory[SCREEN] == SCREEN_MAP, "undiscovered ASK granted an aid"
    tap(pb, "b")
    assert pb.memory[SCREEN] == SCREEN_ROOM


def discover_through_secret(pb):
    # Exercise the real invisible-wall threshold used by procgen secrets. The
    # cache regeneration must mark discovery, stage the spirit in its crystal
    # ring, and clear the one-room reveal bit without a test-only spawn.
    clear_board(pb)
    pb.memory[HIDDEN_KIND] = 2
    pb.memory[HIDDEN_BIT] = 0x08
    pb.memory[RUN_STATE + RS_DUNGEON_PHASE] &= 0x87
    pb.memory[HIDDEN_X], pb.memory[HIDDEN_Y] = 10, 0
    pb.memory[HIDDEN_X2], pb.memory[HIDDEN_Y2] = 11, 0
    pb.memory[TILEMAP + 10] = pb.memory[TILEMAP + 11] = BGT_WALL
    put16(pb, PLAYER + PL_X, 80)
    put16(pb, PLAYER + PL_Y, 0)
    pb.button_press("up")
    try:
        for _ in range(180):
            pb.tick()
            if pb.memory[RUN_STATE + RS_SECRET_PENDING] == 2:
                break
    finally:
        pb.button_release("up")
    assert pb.memory[RUN_STATE + RS_SECRET_PENDING] == 2, (
        "invisible cache did not become the Road Echo discovery room")
    # secret_pending is published near the start of the banked cache build;
    # let its remaining VBlank-sliced terrain/loot transaction finish before
    # inspecting or normalizing the resident entity table.
    tick(pb, 120)
    assert pb.memory[SCREEN] == SCREEN_DIALOG, (
        "new Road Echo did not receive its discovery introduction")
    tap(pb, "a")
    assert pb.memory[SCREEN] == SCREEN_ROOM, (
        "Road Echo introduction did not resume its secret room")
    state = pb.memory[RUN_STATE + RS_COMPANION_COOLDOWN]
    assert state & COMPANION_DISCOVERED_BIT, "secret did not persist discovery"
    assert not (state & COMPANION_PENDING_BIT), "reveal bit survived cache spawn"
    followers = companions(pb)
    assert len(followers) == 1, f"secret revealed {len(followers)} Road Echoes"
    follower = followers[0]
    kind = pb.memory[follower + 18]
    assert kind in range(3), f"invalid Road Echo role {kind}"
    assert pb.memory[follower + 12] in (SPR_COMPANION_A, SPR_COMPANION_B)
    assert pb.memory[follower + 25] == 0, "Road Echo has a blocking hitbox"
    assert any(obj_tile(pb, SPR_COMPANION_A)), "Road Echo stride A is blank"
    assert any(obj_tile(pb, SPR_COMPANION_B)), "Road Echo stride B is blank"
    assert obj_tile(pb, SPR_COMPANION_A) != obj_tile(pb, SPR_COMPANION_B), (
        "Road Echo stride frames are identical")
    return follower


def test_follow_and_fire(pb, follower):
    # Normalize the secret vault to open floor, then provide one ordinary
    # on-screen hostile so following and restrained fire remain independent
    # from this seed's generated encounter roster.
    kind = pb.memory[follower + 18]
    clear_board(pb)
    pb.memory[follower] = ENT_PICKUP
    pb.memory[follower + 1] = 0x07
    pb.memory[follower + 12] = SPR_COMPANION_A
    pb.memory[follower + 13] = 4 if kind == 0 else 6 if kind == 1 else 5
    pb.memory[follower + 17] = PICKUP_COMPANION
    pb.memory[follower + 18] = kind
    pb.memory[follower + 25] = 0
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

    target = next(ENTITIES + slot * ENTITY_SIZE for slot in range(32)
                  if ENTITIES + slot * ENTITY_SIZE != follower
                  and pb.memory[ENTITIES + slot * ENTITY_SIZE] == 0)
    pb.memory[target] = 2
    pb.memory[target + 1] = 0x07
    put16(pb, target + 3, 144)
    put16(pb, target + 7, 64)
    pb.memory[target + 12] = 20
    pb.memory[target + 14] = 8
    pb.memory[target + 17] = 0
    pb.memory[target + 25] = 0x77
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


def test_ask(pb, follower):
    kind = pb.memory[follower + 18]
    pb.memory[RUN_STATE + RS_COMPANION_COOLDOWN] = COMPANION_DISCOVERED_BIT

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
    state = pb.memory[RUN_STATE + RS_COMPANION_COOLDOWN]
    assert state & COMPANION_DISCOVERED_BIT
    assert state & COMPANION_COOLDOWN_MASK == 20
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
    before_cooldown = (pb.memory[RUN_STATE + RS_COMPANION_COOLDOWN]
                       & COMPANION_COOLDOWN_MASK)
    old_timer = get16(pb, RUN_STATE + RS_RUN_TIMER)
    put16(pb, RUN_STATE + RS_RUN_TIMER, (old_timer + 1) & 0xFFFF)
    tick(pb, 4)
    state = pb.memory[RUN_STATE + RS_COMPANION_COOLDOWN]
    assert state & COMPANION_DISCOVERED_BIT, "ASK tick erased discovery"
    assert (state & COMPANION_COOLDOWN_MASK) == max(0, before_cooldown - 1), (
        "Road Echo ASK cooldown did not consume one active-play second: "
        f"{before_cooldown}->{state & COMPANION_COOLDOWN_MASK}")


def main():
    pb = emulator()
    try:
        test_hidden_until_discovered(pb)
        follower = discover_through_secret(pb)
        test_follow_and_fire(pb, follower)
        test_ask(pb, follower)
    finally:
        pb.stop(save=False)
    print(
        "[companion] PASS 9-stage absence, secret-cache discovery, persistent "
        "identity, two-beat follow, restrained fire, ASK + active cooldown"
    )


if __name__ == "__main__":
    main()
