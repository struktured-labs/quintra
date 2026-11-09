#!/usr/bin/env python3
"""The first companion greeting waits until the vault can be seen."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
SCREEN_ROOM = 5
SCREEN_DIALOG = 10
BGT_WALL_CRACK = 24
BGT_CRYSTAL = 22
ENT_PROJECTILE = 1
ENT_PICKUP = 3
PICKUP_COMPANION = 23
EF_ACTIVE = 0x01
EF_PLAYER_PROJ = 0x10


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


RS, PL, EN, TM, SEALED, SCREEN, LARGE, WORLD_W, WORLD_H = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_combat_sealed", "_loop_current_screen",
    "_procgen_current_room_is_large",
    "_room_world_width", "_room_world_height",
))


def tick(pb, count):
    for _ in range(count):
        pb.tick()


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    tick(pb, 240)
    pb.button("start")
    tick(pb, 30)
    pb.button("a")
    for _ in range(240):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            for slot in range(32):
                entity = EN + slot * 28
                if pb.memory[entity] == 2:
                    pb.memory[entity] = pb.memory[entity + 1] = 0
            pb.memory[PL + 2] = 12
            pb.memory[PL + 15] = 200
    assert pb.memory[SCREEN] == SCREEN_ROOM
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[SEALED] = 0
    pb.memory[RS + 6] = 1
    return pb


def companion_at_vault(pb):
    for slot in range(32):
        entity = EN + slot * 28
        if (pb.memory[entity] == ENT_PICKUP
                and pb.memory[entity + 17] == PICKUP_COMPANION
                and pb.memory[entity + 1] & EF_ACTIVE):
            x = pb.memory[entity + 3]
            y = pb.memory[entity + 7]
            return 64 <= x <= 96 and 56 <= y <= 88
    return False


def main():
    pb = boot()
    try:
        pb.memory[TM + 4] = BGT_WALL_CRACK
        shot = EN
        pb.memory[shot] = ENT_PROJECTILE
        pb.memory[shot + 1] = EF_ACTIVE | EF_PLAYER_PROJ
        put16(pb, shot + 3, 32)
        put16(pb, shot + 7, 0)
        pb.memory[shot + 16] = 8
        for offset in range(17, 25):
            pb.memory[shot + offset] = 0
        tick(pb, 4)
        put16(pb, PL + 9, 24)
        put16(pb, PL + 11, 0)
        pb.memory[PL + 15] = 200
        saw_companion = False
        stable_y = None
        stable = 0
        post_arrival = 0
        for _ in range(360):
            pb.tick()
            if pb.memory[SCREEN] == SCREEN_DIALOG:
                break
            if pb.memory[SCREEN] == SCREEN_ROOM and pb.memory[RS + 13] == 2:
                y = pb.memory[PL + 11]
                if y == stable_y:
                    stable += 1
                else:
                    stable_y = y
                    stable = 0
                if stable >= 3:
                    post_arrival += 1
                    if companion_at_vault(pb):
                        saw_companion = True
        assert pb.memory[SCREEN] == SCREEN_DIALOG, (
            f"greeting never opened, screen={pb.memory[SCREEN]} "
            f"secret={pb.memory[RS+13]} post={post_arrival}")
        assert post_arrival >= 20, (
            f"greeting skipped the reveal beat ({post_arrival} frames)")
        assert saw_companion, "companion was not visible in the vault"
        assert any(pb.memory[TM + i] == BGT_CRYSTAL for i in range(20 * 17))
    finally:
        pb.stop(save=False)
    print("[companion-greeting] PASS vault and spirit show before the greeting")


if __name__ == "__main__":
    main()
