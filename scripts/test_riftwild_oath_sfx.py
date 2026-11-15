#!/usr/bin/env python3
"""Riftwild A+B / screen-clear must not reuse the secret-discovery jingles."""

import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SCREEN_ROOM = 5


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


PLAYER, RUN, ENTITIES, SCREEN, ENEMY_COUNT, SEALED = map(addr, (
    "_player", "_run_state", "_entities", "_loop_current_screen",
    "_entity_enemy_count", "_room_combat_sealed"))
SFX_PLAY = addr("_sfx_play")
TILEMAP = addr("_room_tilemap")

PL_HP_MAX, PL_HP, PL_MP_MAX, PL_MP = 1, 2, 3, 4
PL_X, PL_Y, PL_IFRAMES = 9, 11, 15
PL_ACTIVE_CHARGE, PL_WILL, PL_OATH = 19, 42, 43
RS_BOSSES, RS_WORLD_MODE = 11, 17


def sfx_ids():
    body = (ROOT / "src/audio/sfx.h").read_text().split("enum {", 1)[1]
    body = body.split("};", 1)[0]
    ids, number = {}, 0
    for raw in body.splitlines():
        line = raw.split("//", 1)[0].strip().rstrip(",")
        if not line:
            continue
        if "=" in line:
            name, value = (part.strip() for part in line.split("=", 1))
            number = int(value, 0)
        else:
            name = line
        ids[name] = number
        number += 1
    return ids


def put16(pb, at, value):
    pb.memory[at] = value & 0xFF
    pb.memory[at + 1] = (value >> 8) & 0xFF


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    pb.tick(240)
    pb.button("start")
    pb.tick(30)
    pb.button("a")
    pb.tick(90)
    assert pb.memory[SCREEN] == SCREEN_ROOM
    return pb


def hook_sfx(pb, seen):
    def on_sfx(_ctx):
        seen.append(pb.register_file.A)

    pb.hook_register(SFX_PLAY >> 16, SFX_PLAY & 0xFFFF, on_sfx, None)


def clear_entities(pb):
    for i in range(32 * 28):
        pb.memory[ENTITIES + i] = 0
    pb.memory[ENEMY_COUNT] = 0


def floor_clearing(pb):
    for y in range(4, 13):
        for x in range(5, 16):
            pb.memory[TILEMAP + y * 20 + x] = 1
    put16(pb, PLAYER + PL_X, 80)
    put16(pb, PLAYER + PL_Y, 64)


def spawn_enemy(pb, x=112, y=64, hp=4):
    e = ENTITIES
    pb.memory[e] = 2
    pb.memory[e + 1] = 0x07
    put16(pb, e + 3, x)
    put16(pb, e + 7, y)
    pb.memory[e + 10] = 0
    pb.memory[e + 11] = 0
    pb.memory[e + 14] = hp
    pb.memory[e + 16] = 40
    pb.memory[e + 25] = 0x77
    pb.memory[e + 26] = 1
    pb.memory[ENEMY_COUNT] = 1


def settle(pb, frames=16):
    clear_entities(pb)
    floor_clearing(pb)
    for _ in range(frames):
        pb.memory[PLAYER + PL_IFRAMES] = 200
        pb.memory[PLAYER + PL_HP] = pb.memory[PLAYER + PL_HP_MAX]
        pb.tick()


def arm(pb, world, mp_to_max_minus):
    pb.memory[RUN + RS_WORLD_MODE] = world
    pb.memory[RUN + RS_BOSSES] = 1
    pb.memory[PLAYER + PL_OATH] = 0
    pb.memory[PLAYER + PL_ACTIVE_CHARGE] = 0
    pb.memory[PLAYER + PL_WILL] = 0
    pb.memory[SEALED] = 0
    mx = max(2, pb.memory[PLAYER + PL_MP_MAX])
    pb.memory[PLAYER + PL_MP_MAX] = mx
    pb.memory[PLAYER + PL_MP] = mx if mp_to_max_minus < 0 else max(1, mx - mp_to_max_minus)
    pb.memory[PLAYER + PL_IFRAMES] = 200
    floor_clearing(pb)


def chord(pb, settle_frames=24):
    pb.button_press("a")
    pb.button_press("b")
    pb.tick(5)
    pb.button_release("a")
    pb.button_release("b")
    pb.tick(settle_frames)


def structural_contract():
    room = (ROOT / "src/game/room.c").read_text()
    oath = room.split("} else if (chord && player.mp < player.mp_max) {", 1)[1]
    oath = oath.split("        }", 1)[0]
    assert "oath_arts_fire" in oath
    assert "sfx_play(SFX_PUZZLE)" not in oath, oath
    assert "sfx_play(SFX_DASH)" in oath

    clear = room.split("if (alive == 0 && hostiles_prev != 0", 1)[1]
    clear = clear.split("if (run_state.rooms_cleared", 1)[0]
    assert "sfx_play_reward(SFX_REWARD_UNLOCK)" in clear
    assert "sfx_play(SFX_CLEAR)" in clear
    assert "!run_state.world_mode" in clear


def main():
    structural_contract()
    ids = sfx_ids()
    puzzle, clear, roar, dash = (
        ids["SFX_PUZZLE"], ids["SFX_CLEAR"], ids["SFX_ROAR"], ids["SFX_DASH"])

    pb = boot()
    try:
        seen = []
        hook_sfx(pb, seen)

        def take(label):
            seen.clear()
            return seen

        # Mid-MP A+B in Riftwild must fire the oath, never the secret fanfare.
        settle(pb)
        arm(pb, world=1, mp_to_max_minus=1)
        before = pb.memory[PLAYER + PL_MP]
        take("rift-oath")
        chord(pb)
        assert pb.memory[PLAYER + PL_ACTIVE_CHARGE] > 0, "Riftwild oath did not fire"
        assert pb.memory[PLAYER + PL_MP] == before - 1
        assert puzzle not in seen, ("Riftwild oath played SFX_PUZZLE", seen)
        assert clear not in seen, ("Riftwild oath played SFX_CLEAR", seen)
        assert roar not in seen, ("Riftwild oath played SFX_ROAR", seen)
        assert dash in seen, ("Riftwild oath missed SFX_DASH", seen)

        # Wiping the last Riftwild hostile still must not play the secret arpeggio.
        settle(pb)
        arm(pb, world=1, mp_to_max_minus=1)
        spawn_enemy(pb, hp=1)
        for _ in range(8):
            pb.memory[PLAYER + PL_IFRAMES] = 200
            pb.tick()
        take("rift-oath-wipe")
        chord(pb)
        assert puzzle not in seen, ("Riftwild oath-wipe played SFX_PUZZLE", seen)
        assert clear not in seen, ("Riftwild screen clear played SFX_CLEAR", seen)

        # Full-MP chord remains Spirit Convergence.
        settle(pb)
        arm(pb, world=1, mp_to_max_minus=-1)
        take("rift-conv")
        chord(pb)
        assert pb.memory[PLAYER + PL_MP] == 0
        assert roar in seen, ("Spirit Convergence missed SFX_ROAR", seen)
        assert puzzle not in seen, ("Convergence played SFX_PUZZLE", seen)

        # A plain Riftwild last-enemy clear is silent on the secret bus.
        settle(pb)
        arm(pb, world=1, mp_to_max_minus=1)
        spawn_enemy(pb)
        for _ in range(8):
            pb.memory[PLAYER + PL_IFRAMES] = 200
            pb.tick()
        take("rift-clear")
        pb.memory[ENTITIES] = 0
        pb.memory[ENTITIES + 1] = 0
        for _ in range(20):
            pb.memory[PLAYER + PL_IFRAMES] = 200
            pb.tick()
        assert clear not in seen, ("Riftwild last enemy played SFX_CLEAR", seen)
        assert puzzle not in seen, ("Riftwild last enemy played SFX_PUZZLE", seen)

        # Optional unsealed dungeon rooms still get the lighter clear arpeggio.
        settle(pb)
        arm(pb, world=0, mp_to_max_minus=1)
        spawn_enemy(pb)
        for _ in range(8):
            pb.memory[PLAYER + PL_IFRAMES] = 200
            pb.tick()
        take("dungeon-clear")
        pb.memory[ENTITIES] = 0
        pb.memory[ENTITIES + 1] = 0
        for _ in range(20):
            pb.memory[PLAYER + PL_IFRAMES] = 200
            pb.tick()
        assert clear in seen, ("unsealed dungeon clear lost SFX_CLEAR", seen)

        # Sealed dungeon rooms keep the latch-release path, not the secret arpeggio.
        settle(pb)
        arm(pb, world=0, mp_to_max_minus=1)
        pb.memory[SEALED] = 1
        spawn_enemy(pb)
        for _ in range(8):
            pb.memory[PLAYER + PL_IFRAMES] = 200
            pb.tick()
        take("dungeon-sealed")
        pb.memory[ENTITIES] = 0
        pb.memory[ENTITIES + 1] = 0
        for _ in range(20):
            pb.memory[PLAYER + PL_IFRAMES] = 200
            pb.tick()
        assert clear not in seen, ("sealed dungeon clear played SFX_CLEAR", seen)
        assert puzzle not in seen
    finally:
        pb.stop(save=False)

    print("[riftwild-oath-sfx] PASS oath uses SFX_DASH; Riftwild clears stay off "
          "SFX_PUZZLE/SFX_CLEAR; sealed dungeon unlock and optional dungeon "
          "clear voices stay put")


if __name__ == "__main__":
    main()
