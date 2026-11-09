#!/usr/bin/env python3
"""An opened secret mouth stays enterable and never redraws barred."""
import re
from pathlib import Path

from pyboy import PyBoy


ROOT = Path(__file__).resolve().parent.parent
ROM = ROOT / "rom/working/quintra.gbc"
NOI = ROM.with_suffix(".noi").read_text()
BGT_DOOR = 3
BGT_DOOR_LOCKED = 126
BGT_WALL_CRACK = 24
BGT_CRYSTAL = 22
ENT_PROJECTILE = 1
ENT_ENEMY = 2
EF_ACTIVE = 0x01
EF_ALIVE = 0x02
EF_PLAYER_PROJ = 0x10
SCREEN_ROOM = 5


def addr(name):
    match = re.search(rf"DEF {name} 0x([0-9A-Fa-f]+)", NOI)
    if not match:
        raise RuntimeError(name)
    return int(match.group(1), 16)


(RS, PL, EN, TM, SEALED, PUZZLE, LARGE, WORLD_W, WORLD_H, CAMERA_X,
 CAMERA_Y, SCREEN, SECRET_X, SECRET_Y, SECRET_X2, SECRET_Y2,
 ENCOUNTER) = map(addr, (
    "_run_state", "_player", "_entities", "_room_tilemap",
    "_room_combat_sealed", "_room_puzzle_locked",
    "_procgen_current_room_is_large", "_room_world_width",
    "_room_world_height", "_room_camera_x", "_room_camera_y",
    "_loop_current_screen", "_secret_door_x", "_secret_door_y",
    "_secret_door_x2", "_secret_door_y2", "_room_encounter_kind",
))


def put16(pb, address, value):
    pb.memory[address] = value & 0xFF
    pb.memory[address + 1] = (value >> 8) & 0xFF


def tick(pb, count):
    for _ in range(count):
        pb.tick()


def boot():
    pb = PyBoy(str(ROM), window="null", cgb=True)
    tick(pb, 240)
    pb.button("start")
    tick(pb, 30)
    pb.button("a")
    tick(pb, 240)
    assert pb.memory[SCREEN] == SCREEN_ROOM
    pb.memory[LARGE] = 0
    pb.memory[WORLD_W], pb.memory[WORLD_H] = 160, 136
    pb.memory[CAMERA_X] = pb.memory[CAMERA_Y] = 0
    pb.memory[0xFF43] = pb.memory[0xFF42] = 0
    pb.memory[PUZZLE] = 0
    for slot in range(32):
        entity = EN + slot * 28
        pb.memory[entity] = pb.memory[entity + 1] = 0
    # One living hostile keeps the ordinary exits sealed.
    pb.memory[EN] = ENT_ENEMY
    pb.memory[EN + 1] = EF_ACTIVE | EF_ALIVE
    pb.memory[EN + 14] = 4
    put16(pb, EN + 3, 120)
    put16(pb, EN + 7, 80)
    pb.memory[SEALED] = 1
    pb.memory[RS + 6] = 1  # entered from the east; north is not the return
    pb.memory[PL + 15] = 120
    return pb


def vram(pb, x, y):
    address = 0x9800 + y * 32 + x
    return pb.memory[0, address]


def shoot_crack(pb):
    pb.memory[TM + 4] = BGT_WALL_CRACK
    pb.memory[TM + 5] = 2  # neighbouring wall, not a second crack
    shot = EN + 28
    pb.memory[shot] = ENT_PROJECTILE
    pb.memory[shot + 1] = EF_ACTIVE | EF_PLAYER_PROJ
    put16(pb, shot + 3, 32)  # tile column 4
    put16(pb, shot + 7, 0)   # north border
    pb.memory[shot + 10] = pb.memory[shot + 11] = 0
    pb.memory[shot + 16] = 8
    for offset in range(17, 25):
        pb.memory[shot + offset] = 0
    tick(pb, 4)
    assert pb.memory[SECRET_X] == 4 and pb.memory[SECRET_Y] == 0, (
        f"crack did not open a vault mouth: "
        f"{pb.memory[SECRET_X]},{pb.memory[SECRET_Y]}")
    assert vram(pb, 4, 0) == BGT_DOOR and vram(pb, 5, 0) == BGT_DOOR, (
        "opened mouth was not drawn as a door")


def redraw(pb, sealed):
    """Pack resume repaints the live tilemap, including seal overlays."""
    pb.button("start")
    opened = False
    for _ in range(40):
        pb.tick()
        if pb.memory[SCREEN] != SCREEN_ROOM:
            opened = True
            break
    assert opened, "START did not open the pack"
    pb.memory[SEALED] = sealed
    pb.button_press("b")
    for _ in range(30):
        pb.tick()
        if pb.memory[SCREEN] == SCREEN_ROOM:
            break
    else:
        raise AssertionError("pack did not return to the room")
    pb.button_release("b")
    tick(pb, 4)
    assert pb.memory[SCREEN] == SCREEN_ROOM, (
        f"pack did not return to the room, screen={pb.memory[SCREEN]}")


def main():
    pb = boot()
    try:
        shoot_crack(pb)
        redraw(pb, sealed=1)
        assert vram(pb, 4, 0) == BGT_DOOR and vram(pb, 5, 0) == BGT_DOOR, (
            f"sealed redraw barred the open mouth: "
            f"{vram(pb, 4, 0)},{vram(pb, 5, 0)}")
        # A seal-time redraw must not be allowed to leave a portcullis after
        # the last hostile falls. Force that stale paint, then clear.
        pb.memory[0, 0x9800 + 4] = BGT_DOOR_LOCKED
        pb.memory[0, 0x9800 + 5] = BGT_DOOR_LOCKED
        pb.memory[ENCOUNTER] = 0
        pb.memory[SEALED] = 1
        pb.memory[EN] = ENT_ENEMY
        pb.memory[EN + 1] = EF_ACTIVE | EF_ALIVE
        pb.memory[EN + 14] = 4
        put16(pb, PL + 9, 80)
        put16(pb, PL + 11, 64)
        tick(pb, 3)
        assert pb.memory[SEALED] == 1, "fixture lost its combat seal"
        pb.memory[EN] = pb.memory[EN + 1] = 0
        tick(pb, 8)
        assert pb.memory[SEALED] == 0, "removing the last hostile did not unseal"
        assert vram(pb, 4, 0) == BGT_DOOR and vram(pb, 5, 0) == BGT_DOOR, (
            f"clear left the mouth barred: "
            f"{vram(pb, 4, 0)},{vram(pb, 5, 0)}")
        redraw(pb, sealed=0)
        assert vram(pb, 4, 0) == BGT_DOOR and vram(pb, 5, 0) == BGT_DOOR, (
            "post-clear redraw closed the mouth")

        # Re-seal and prove the still-open mouth can be walked while hostiles live.
        pb.memory[ENCOUNTER] = 0
        pb.memory[SEALED] = 1
        pb.memory[EN] = ENT_ENEMY
        pb.memory[EN + 1] = EF_ACTIVE | EF_ALIVE
        pb.memory[EN + 14] = 4
        put16(pb, PL + 9, 80)
        put16(pb, PL + 11, 64)
        tick(pb, 3)
        assert pb.memory[SEALED] == 1 and pb.memory[EN] == ENT_ENEMY
        room = pb.memory[RS + 1]
        put16(pb, PL + 9, 24)
        put16(pb, PL + 11, 0)
        entered = False
        for _ in range(30):
            pb.tick()
            if pb.memory[RS + 13] == 2:
                entered = True
                break
        assert entered, (
            f"sealed open mouth refused entry: room={pb.memory[RS + 1]} "
            f"secret={pb.memory[RS + 13]} y={pb.memory[PL + 11]}")
        assert pb.memory[RS + 1] == room, "vault stole a graph cell"
        assert any(pb.memory[TM + i] == BGT_CRYSTAL for i in range(20 * 17)), (
            "secret vault did not build its crystal ring")
    finally:
        pb.stop(save=False)
    print("[secret-door-seal] PASS open mouth stays enterable and open")


if __name__ == "__main__":
    main()
